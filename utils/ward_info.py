# utils/ward_info.py
"""
Thông tin chi tiết của từng phường/xã khi bấm vào ranh giới trên bản đồ:
- compute_ward_stats: gom các ô lưới NDVI vào đúng đơn vị hành chính chứa nó (point-in-polygon) rồi tính thống kê.
- build_ward_popup:   dựng khung thông tin (HTML) hiển thị trong popup của bản đồ.
"""
import html as _html
import numpy as np
import pandas as pd
import streamlit as st
from utils.map_utils import NDVI_STOPS, NDVI_VMIN, NDVI_VMAX

REQUIRED_COLS = ("ma_xa", "ten_xa")      # file ranh giới có đủ 2 cột này thì mới dùng popup chi tiết
VEG_THRESHOLD = 0.3                      # cùng ngưỡng "độ phủ thực vật" ở khung Chỉ số vùng
LOW_CELLS = 5                            # ít hơn số ô này thì nhắc "chỉ mang tính tham khảo"


def has_ward_columns(gdf) -> bool:
    return gdf is not None and all(c in gdf.columns for c in REQUIRED_COLS)


# ----------------------------------------------------------------------------------------------
#  1. Thống kê NDVI theo từng đơn vị hành chính
# ----------------------------------------------------------------------------------------------
def _contains_xy(geom, x, y):
    try:
        from shapely import contains_xy
        return contains_xy(geom, x, y)
    except (ImportError, AttributeError):
        from shapely.vectorized import contains
        return contains(geom, x, y)


@st.cache_data(show_spinner=False, max_entries=4)
def compute_ward_stats(df: pd.DataFrame, _wards, key_col: str = "ma_xa"):
    """
    Mỗi ô lưới (longitude, latitude) được gán cho phường/xã chứa nó, sau đó tính theo từng đơn vị:
    số ô, NDVI trung bình, ô thấp nhất, ô cao nhất, % ô có NDVI >= 0.3, hạng NDVI (1 = xanh nhất).
    -> (bảng thống kê index = mã đơn vị dạng chuỗi, NDVI trung bình của toàn bộ dữ liệu)
    """
    d = df.dropna(subset=["longitude", "latitude", "ndvi_mean"])
    if d.empty:
        return pd.DataFrame(), float("nan")
    x = d["longitude"].to_numpy(float)
    y = d["latitude"].to_numpy(float)
    v = d["ndvi_mean"].to_numpy(float)

    keys = _wards[key_col].astype(str).to_numpy()
    owner = np.full(len(x), -1, dtype=int)
    for i, geom in enumerate(list(_wards.geometry)):
        if geom is None or getattr(geom, "is_empty", False):
            continue
        minx, miny, maxx, maxy = geom.bounds                       # lọc nhanh theo khung bao rồi mới kiểm tra chính xác
        cand = np.where((owner < 0) & (x >= minx) & (x <= maxx) & (y >= miny) & (y <= maxy))[0]
        if cand.size == 0:
            continue
        inside = np.asarray(_contains_xy(geom, x[cand], y[cand]), dtype=bool)
        owner[cand[inside]] = i

    m = owner >= 0
    if not m.any():
        return pd.DataFrame(), float(v.mean())
    frame = pd.DataFrame({"key": keys[owner[m]], "v": v[m]})
    frame["veg"] = frame["v"] >= VEG_THRESHOLD
    g = frame.groupby("key")
    stats = pd.DataFrame({
        "n_cells": g["v"].size(),
        "ndvi_mean": g["v"].mean(),
        "ndvi_min": g["v"].min(),
        "ndvi_max": g["v"].max(),
        "veg_pct": g["veg"].mean() * 100.0,
    })
    stats["rank"] = stats["ndvi_mean"].rank(ascending=False, method="min").astype(int)
    return stats, float(v.mean())


# ----------------------------------------------------------------------------------------------
#  2. Nội dung popup
# ----------------------------------------------------------------------------------------------
def _txt(row, col, default=""):
    try:
        val = row[col]
    except (KeyError, IndexError):
        return default
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    return str(val).strip()


def _num(row, col):
    try:
        val = float(row[col])
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    return None if np.isnan(val) else val


def _esc(s) -> str:
    # popup được nhúng trong chuỗi JavaScript dạng `...` nên loại bỏ ký tự có thể làm hỏng chuỗi đó
    return _html.escape(str(s)).replace("`", "'").replace("${", "$ {")


def ward_label(row) -> str:
    """'Phường An Đông' (không lặp tiền tố nếu tên đã có sẵn)."""
    name, kind = _txt(row, "ten_xa"), _txt(row, "loai")
    if not kind or name.lower().startswith(kind.lower()):
        return name
    return f"{kind} {name}"


def _count_merged(text: str) -> int:
    """Đếm số đơn vị cũ trong cột sap_nhap (chỉ tính dấu phẩy ngoài ngoặc đơn)."""
    if not text.strip():
        return 0
    depth, n = 0, 1
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            n += 1
    return n


_SPAN = NDVI_VMAX - NDVI_VMIN
_GRAD = ", ".join(f"{c} {(v - NDVI_VMIN) / _SPAN * 100:.0f}%" for v, c in NDVI_STOPS)

POPUP_CSS = """
<style>
.leaflet-popup-content-wrapper{border-radius:14px;padding:0;overflow:hidden;box-shadow:0 10px 28px rgba(20,83,45,.30)}
.leaflet-popup-content{margin:0 !important;width:auto !important}
.leaflet-popup-close-button{color:#fff !important;font-size:20px !important;padding:6px 8px 0 0 !important}
.wp{font-family:'Be Vietnam Pro','Segoe UI',Arial,sans-serif;color:#14301F;font-size:12.5px;line-height:1.4;width:318px}
.wp-h{background:linear-gradient(110deg,#14532D,#15803D 55%,#4D9A1E);color:#fff;padding:11px 36px 10px 14px}
.wp-h b{display:block;font-size:15.5px;font-weight:800;line-height:1.25}
.wp-h span{font-size:11px;opacity:.92}
.wp-b{padding:6px 14px 12px;max-height:440px;overflow-y:auto}
.wp-sec{font-weight:800;color:#15803D;font-size:10.5px;letter-spacing:.4px;margin:10px 0 5px;text-transform:uppercase}
.wp-ndvi{display:flex;align-items:center;gap:12px}
.wp-big{font-size:32px;font-weight:800;line-height:1}
.wp-chip{display:inline-block;padding:2px 10px;border-radius:99px;font-size:11px;font-weight:700}
.wp-sub{font-size:11px;color:#5B7A66;margin-top:4px}
.wp-bar{position:relative;height:10px;border-radius:5px;margin:10px 0 2px}
.wp-mark{position:absolute;top:-3px;width:4px;height:16px;border-radius:2px;background:#111827;border:1px solid #fff;transform:translateX(-50%)}
.wp-scale{display:flex;justify-content:space-between;font-size:10px;color:#5B7A66}
.wp-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:8px 0 2px}
.wp-cell{background:#F0FDF4;border:1px solid #D7E8DB;border-radius:8px;padding:5px 8px}
.wp-cell small{display:block;color:#5B7A66;font-size:10.5px}
.wp-cell b{font-size:13px}
.wp-row{display:flex;justify-content:space-between;gap:12px;padding:4px 0;border-bottom:1px dashed #E3EFE6}
.wp-row span{color:#5B7A66;white-space:nowrap}
.wp-row b{text-align:right;font-weight:600}
.wp-merge{max-height:62px;overflow:auto;font-size:11.5px;color:#3F5B49;background:#F8FCF9;border:1px solid #E3EFE6;border-radius:8px;padding:5px 8px;margin-top:3px}
.wp-note{font-size:11.5px;background:#FEF3C7;color:#92400E;border-radius:8px;padding:6px 9px;margin-top:6px}
.wp-foot{font-size:10.5px;color:#5B7A66;margin-top:9px;line-height:1.45}
</style>
"""


def _row(label, value):
    return f"<div class='wp-row'><span>{label}</span><b>{value}</b></div>"


def _ndvi_class(mean):
    if mean >= 0.5:
        return "Tốt", "#DCFCE7", "#14532D", "#15803D"
    if mean >= 0.2:
        return "Trung bình", "#FEF3C7", "#92400E", "#B45309"
    return "Cần chú ý", "#FEE2E2", "#991B1B", "#DC2626"


def _ndvi_block(stats_row, city_mean, n_ranked, period_label, data_loaded):
    if not data_loaded:
        return ("<div class='wp-note'>Chưa có dữ liệu NDVI. Hãy chọn tháng/năm ở thanh bên rồi bấm "
                "<b>Chạy dự báo AI</b> để xem chỉ số thực vật của đơn vị này.</div>")
    if stats_row is None:
        return ("<div class='wp-note'>Không có ô lưới NDVI nào nằm trong ranh giới đơn vị này "
                "(có thể do mây che phủ hoặc đơn vị quá nhỏ).</div>")

    mean = float(stats_row["ndvi_mean"])
    n = int(stats_row["n_cells"])
    label, bg, fg, big = _ndvi_class(mean)
    pos = min(100.0, max(0.0, (mean - NDVI_VMIN) / _SPAN * 100))

    diff = mean - city_mean if city_mean is not None and not np.isnan(city_mean) else None
    if diff is None:
        cmp_txt = ""
    elif abs(diff) < 0.005:
        cmp_txt = "Xấp xỉ mức trung bình toàn TP"
    else:
        cmp_txt = f"{'Cao' if diff > 0 else 'Thấp'} hơn trung bình toàn TP {abs(diff):.3f}"

    out = [
        f"<div class='wp-sec'>Chỉ số thực vật NDVI{(' · tháng ' + _esc(period_label)) if period_label else ''}</div>",
        f"<div class='wp-ndvi'><div class='wp-big' style='color:{big}'>{mean:.3f}</div><div>"
        f"<span class='wp-chip' style='background:{bg};color:{fg}'>{label}</span>"
        f"<div class='wp-sub'>{cmp_txt}</div></div></div>",
        f"<div class='wp-bar' style='background:linear-gradient(to right,{_GRAD})'>"
        f"<div class='wp-mark' style='left:{pos:.1f}%'></div></div>",
        f"<div class='wp-scale'><span>{NDVI_VMIN:g}</span><span>{NDVI_VMIN + _SPAN / 2:g}</span><span>{NDVI_VMAX:g}</span></div>",
        "<div class='wp-grid'>"
        f"<div class='wp-cell'><small>Ô thấp nhất</small><b>{float(stats_row['ndvi_min']):.3f}</b></div>"
        f"<div class='wp-cell'><small>Ô cao nhất</small><b>{float(stats_row['ndvi_max']):.3f}</b></div>"
        f"<div class='wp-cell'><small>Độ phủ thực vật</small><b>{float(stats_row['veg_pct']):.0f}%</b></div>"
        f"<div class='wp-cell'><small>Số ô lưới</small><b>{n:,}</b></div></div>",
        _row("Xếp hạng NDVI", f"{int(stats_row['rank'])}/{n_ranked} đơn vị"),
    ]
    if n < LOW_CELLS:
        out.append(f"<div class='wp-note'>Đơn vị này chỉ có {n} ô lưới nên giá trị chỉ mang tính tham khảo.</div>")
    return "".join(out)


def build_ward_popup(row, stats=None, city_mean=None, data_loaded=False, period_label="", source_label="") -> str:
    """HTML của popup cho 1 phường/xã. row = 1 dòng của file ranh giới; stats = kết quả compute_ward_stats."""
    stats_row = None
    if stats is not None and not stats.empty:
        key = _txt(row, "ma_xa")
        if key in stats.index:
            stats_row = stats.loc[key]
    n_ranked = 0 if stats is None else len(stats)

    kind, code, prov = _txt(row, "loai"), _txt(row, "ma_xa"), _txt(row, "ten_tinh")
    sub = " · ".join(p for p in (kind, f"Mã đơn vị {code}" if code else "", prov) if p)

    area, pop, dens = _num(row, "dtich_km2"), _num(row, "dan_so"), _num(row, "matdo_km2")
    info = []
    if area is not None:
        info.append(_row("Diện tích", f"{area:,.2f} km²"))
    if pop is not None:
        info.append(_row("Dân số", f"{pop:,.0f} người"))
    if dens is not None:
        info.append(_row("Mật độ dân số", f"{dens:,.0f} người/km²"))
    if stats_row is not None and area is not None:
        info.append(_row("Diện tích có thực vật (ước tính)", f"≈ {area * float(stats_row['veg_pct']) / 100:,.2f} km²"))
    hq = _txt(row, "tru_so")
    if hq:
        info.append(_row("Trụ sở UBND", _esc(hq)))
    merged = _txt(row, "sap_nhap")
    n_merged = _count_merged(merged)
    if n_merged:
        info.append(_row("Sáp nhập từ", f"{n_merged} đơn vị cũ"))

    parts = [
        f"<div class='wp'><div class='wp-h'><b>{_esc(ward_label(row))}</b><span>{_esc(sub)}</span></div><div class='wp-b'>",
        _ndvi_block(stats_row, city_mean, n_ranked, period_label, data_loaded),
        "<div class='wp-sec'>Thông tin hành chính</div>",
        "".join(info) or "<div class='wp-sub'>Chưa có thông tin.</div>",
    ]
    if merged:
        parts.append(f"<div class='wp-merge'><b>Sáp nhập từ:</b> {_esc(merged)}</div>")
    foot = "NDVI của đơn vị = trung bình các ô lưới nằm trong ranh giới."
    # if source_label:
    #     foot = f"Nguồn NDVI: {_esc(source_label)}. " + foot
    # parts.append(f"<div class='wp-foot'>{foot}</div></div></div>")
    return "".join(parts)
