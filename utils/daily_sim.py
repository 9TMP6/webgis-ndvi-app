# utils/daily_sim.py
"""
MÔ PHỎNG NDVI THEO NGÀY (demo).

Vì sao là "mô phỏng": các mô hình LSTM/GRU/CNNLSTM được huấn luyện trên chuỗi NDVI THEO THÁNG
(cửa sổ 12 tháng), còn ảnh Sentinel-2 chỉ về 5 ngày/lần và hay bị mây che ở TP.HCM nên không có
chuỗi NDVI theo ngày đủ dày để huấn luyện/kiểm chứng. Do đó, chức năng này KHÔNG phải mô hình dự báo
theo ngày, mà là cách dựng giá trị NDVI từng ngày từ các tháng đã có:

  1) Lấy bản đồ NDVI tháng M-1, M, M+1 (quan trắc trong CSDL nếu đủ ô, thiếu thì dùng AI như app đang làm).
  2) Coi mỗi giá trị tháng là NDVI "ngày giữa tháng" (ngày 15). Ngày d nằm giữa hai mốc liền kề
     nên được nội suy mượt (smoothstep) theo số ngày cách mốc.
  3) Cộng một dao động nhỏ, cố định theo (ngày, vị trí) để cùng một ngày luôn ra cùng một kết quả:
       - một độ lệch chung cả thành phố (±DAY_SHIFT_AMP), giống "hôm nay hơi khô/ẩm hơn",
       - một trường dao động trơn theo không gian (SPATIAL_AMP) + nhiễu ô rất nhỏ (CELL_AMP).

Kết quả trả về cùng cột với dự báo tháng (grid_id, date, longitude, latitude, ndvi_mean/min/max)
nên bản đồ, chỉ số, bảng xếp hạng, xuất PNG/TIF/báo cáo dùng lại nguyên không cần sửa.
KHÔNG ghi vào CSDL (tránh lẫn dữ liệu mô phỏng với dữ liệu thật, và tiết kiệm dung lượng Supabase).
"""
import calendar
import zlib

import numpy as np
import pandas as pd
import streamlit as st

from utils.data_loader import ModelError, load_ndvi_data

ANCHOR_DAY = 15            # giá trị tháng được gán cho ngày 15
MIN_VALID_CELLS = 20000    # giống ngưỡng của app: quan trắc ít hơn thì coi là thiếu (mây) và dùng AI
DAY_SHIFT_AMP = 0.010      # độ lệch chung cả thành phố theo ngày
SPATIAL_AMP = 0.012        # biên độ dao động trơn theo không gian
CELL_AMP = 0.004           # nhiễu nhỏ từng ô
BAND = 0.05                # khoảng min/max quanh giá trị trung bình (giống ai_demo)
NDVI_LO, NDVI_HI = -0.2, 1.0


# ---------------- Lấy bản đồ NDVI của một tháng ----------------
def _monthly_grid(year: int, month: int, model_name: str, force_ai: bool) -> pd.DataFrame:
    """Trả về DataFrame [grid_id, longitude, latitude, ndvi_mean] của cả tháng.
    Ưu tiên quan trắc trong CSDL (nếu đủ ô và không bật 'luôn dùng AI'), còn lại chạy AI."""
    if not force_ai:
        obs = load_ndvi_data(int(year), int(month))
        if obs is not None and not obs.empty and len(obs) >= MIN_VALID_CELLS:
            return obs[["grid_id", "longitude", "latitude", "ndvi_mean"]].copy()
    from utils import ai_demo
    df, _ = ai_demo._forecast_cached(int(year), int(month), model_name)
    return df[["grid_id", "longitude", "latitude", "ndvi_mean"]].copy()


def _shift_month(year: int, month: int, k: int):
    t = year * 12 + (month - 1) + k
    return t // 12, t % 12 + 1


# ---------------- Dao động cố định theo ngày ----------------
def _day_seed(year: int, month: int, day: int, model_name: str) -> int:
    return zlib.crc32(f"{year}-{month:02d}-{day:02d}|{model_name}".encode("utf-8"))


def _smooth_field(lon: np.ndarray, lat: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Trường dao động trơn theo không gian, trong khoảng xấp xỉ [-1, 1]."""
    out = np.zeros(len(lon), dtype=np.float64)
    for _ in range(3):
        k = rng.uniform(15.0, 45.0)                 # số sóng trên mỗi độ (bước sóng ~2.5-7 km)
        ang = rng.uniform(0, 2 * np.pi)
        phase = rng.uniform(0, 2 * np.pi)
        out += np.sin(2 * np.pi * k * (lon * np.cos(ang) + lat * np.sin(ang)) + phase)
    return out / 3.0


# ---------------- Hàm công khai ----------------
@st.cache_data(ttl=900, show_spinner=False, max_entries=8)
def simulate_daily_ndvi(year: int, month: int, day: int,
                        model_name: str = "LSTM", force_ai: bool = False) -> pd.DataFrame:
    """Mô phỏng bản đồ NDVI của ngày (year, month, day). Lỗi lấy dữ liệu tháng chính -> ModelError."""
    year, month = int(year), int(month)
    day = int(min(max(day, 1), calendar.monthrange(year, month)[1]))

    try:
        cur = _monthly_grid(year, month, model_name, force_ai)
    except Exception as e:
        raise ModelError(f"Không lấy được dữ liệu NDVI tháng {month}/{year} để mô phỏng: {e}") from e

    if day == ANCHOR_DAY:
        return _finish(cur, year, month, day, model_name)

    # Trước ngày 15: nội suy giữa mốc 15 tháng trước và mốc 15 tháng này.
    # Từ ngày 15 trở đi: nội suy giữa mốc 15 tháng này và mốc 15 tháng sau.
    k = -1 if day < ANCHOR_DAY else 1
    oy, om = _shift_month(year, month, k)
    try:
        other = _monthly_grid(oy, om, model_name, force_ai)
    except Exception:
        other = cur          # tháng kề chưa có (ví dụ quá xa tương lai) -> giữ phẳng, chỉ còn dao động nhỏ

    if k == -1:
        span = calendar.monthrange(oy, om)[1]            # số ngày giữa hai mốc = độ dài tháng trước
        t = (span - ANCHOR_DAY + day) / span
        a, b = other, cur
    else:
        span = calendar.monthrange(year, month)[1]       # số ngày giữa hai mốc = độ dài tháng này
        t = (day - ANCHOR_DAY) / span
        a, b = cur, other

    merged = a.merge(b[["grid_id", "ndvi_mean"]], on="grid_id", how="inner", suffixes=("_a", "_b"))
    s = t * t * (3 - 2 * t)                              # smoothstep: mượt ở hai đầu mốc
    merged["ndvi_mean"] = merged["ndvi_mean_a"] * (1 - s) + merged["ndvi_mean_b"] * s
    return _finish(merged[["grid_id", "longitude", "latitude", "ndvi_mean"]], year, month, day, model_name)


def _finish(base: pd.DataFrame, year: int, month: int, day: int, model_name: str) -> pd.DataFrame:
    out = base.dropna(subset=["longitude", "latitude", "ndvi_mean"]).reset_index(drop=True).copy()
    rng = np.random.default_rng(_day_seed(year, month, day, model_name))
    lon, lat = out["longitude"].to_numpy(float), out["latitude"].to_numpy(float)

    shift = rng.uniform(-DAY_SHIFT_AMP, DAY_SHIFT_AMP)                 # độ lệch chung của ngày
    spatial = SPATIAL_AMP * _smooth_field(lon, lat, rng)               # dao động trơn theo vị trí
    cell = rng.normal(0.0, CELL_AMP, size=len(out))                    # nhiễu nhỏ từng ô

    v = np.clip(out["ndvi_mean"].to_numpy(float) + shift + spatial + cell, NDVI_LO, NDVI_HI)
    out["ndvi_mean"] = v
    out["ndvi_min"] = np.maximum(v - BAND, NDVI_LO)
    out["ndvi_max"] = np.minimum(v + BAND, NDVI_HI)
    out["date"] = f"{int(year)}-{int(month):02d}-{int(day):02d}"
    return out[["grid_id", "date", "longitude", "latitude", "ndvi_mean", "ndvi_min", "ndvi_max"]]
