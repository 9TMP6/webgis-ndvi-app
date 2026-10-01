# utils/ai_demo.py
"""
AI DEMO - dự báo NDVI trực tiếp từ CSDL, KHÔNG cần file .onnx / scaler.json.

Ý tưởng (đơn giản nhưng giữ đúng cấu trúc không gian):
    NDVI_dự_báo = NDVI_tháng_trước + phần_chênh_nhỏ
  - Phần chênh được học bằng hồi quy Ridge (numpy thuần) từ chính lịch sử trong CSDL.
  - Vì luôn cộng vào NDVI tháng trước nên ô đô thị (thấp) vẫn thấp, rừng (cao) vẫn cao
    -> không thể "xanh hóa đồng loạt" như lỗi trước.
  - Tự backtest trên 3 tháng cuối có dữ liệu. Nếu model KHÔNG thắng baseline
    "giữ nguyên tháng trước" thì tự động dùng baseline (an toàn hơn).

Hàm công khai (cùng chữ ký/cột với run_onnx_inference_for_grid cũ):
    run_demo_inference_for_grid(year, month) -> DataFrame
    render_ai_report(year, month)            -> hiện báo cáo kiểm chứng lên giao diện
"""
import numpy as np
import pandas as pd

try:
    import streamlit as st
except Exception:  # cho phép test ngoài Streamlit
    st = None


def _cache_data(**kw):
    if st is not None:
        return st.cache_data(**kw)
    return lambda f: f


# ---------------- Cấu hình ----------------
WINDOW = 12               # số tháng lịch sử đưa vào
MIN_WINDOW_VALID = 6      # ô phải có >= 6/12 tháng có dữ liệu thật
MIN_MONTH_TARGETS = 1000  # tháng đích có < 1000 ô hợp lệ thì bỏ qua khi train
MAX_ROWS_PER_MONTH = 8000 # lấy mẫu mỗi tháng để train nhanh, đỡ tốn RAM
HOLDOUT_MONTHS = 3        # số tháng cuối dùng để backtest
RIDGE_LAMBDA = 10.0
MAX_DELTA = 0.30          # chặn mức thay đổi tối đa mỗi tháng
MAX_STEPS = 12            # tối đa dự báo nối tiếp 12 tháng
NDVI_LO, NDVI_HI = -0.2, 1.0


# ---------------- Tiện ích thời gian ----------------
def _month_of(t: int) -> int:
    return (t - 1) % 12 + 1          # t = year*12 + month


# ---------------- Đọc dữ liệu ----------------
@_cache_data(ttl=3600, show_spinner=False)
def load_history() -> pd.DataFrame:
    from sqlalchemy import text
    from utils.data_loader import get_db_engine

    return pd.read_sql(
        text("""
            SELECT grid_id, longitude, latitude,
                   year * 12 + month AS t, ndvi_mean
            FROM public.ndvi_records
            WHERE ndvi_mean IS NOT NULL
        """),
        get_db_engine(),
    )


def _build_matrix(df: pd.DataFrame):
    """-> ids, coords, M [N, T] (NaN = thiếu/mây), t_min. Lịch liên tục từng tháng."""
    coords = df.groupby("grid_id")[["longitude", "latitude"]].mean()
    piv = df.groupby(["grid_id", "t"])["ndvi_mean"].mean().unstack("t")
    t_min, t_max = int(piv.columns.min()), int(piv.columns.max())
    piv = piv.reindex(columns=range(t_min, t_max + 1))
    coords = coords.loc[piv.index]
    return piv.index.to_numpy(), coords, piv.to_numpy(dtype=np.float32), t_min


# ---------------- Đặc trưng + mô hình ----------------
def _fill(W: np.ndarray) -> np.ndarray:
    """Điền khuyết TRONG cửa sổ (không nhìn sang tương lai)."""
    return pd.DataFrame(W).ffill(axis=1).bfill(axis=1).to_numpy(dtype=np.float64)


def _features(W: np.ndarray, target_month: int) -> np.ndarray:
    """W: [N,12] đã điền. Đặc trưng: chênh so với tháng cuối (11), mức NDVI, sin/cos mùa vụ."""
    last = W[:, -1]
    d = W[:, :-1] - last[:, None]
    ang = 2.0 * np.pi * target_month / 12.0
    n = len(W)
    return np.column_stack([d, last, np.full(n, np.sin(ang)), np.full(n, np.cos(ang))])


def _fit_ridge(X: np.ndarray, y: np.ndarray):
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd[sd < 1e-6] = 1.0
    Z = np.column_stack([(X - mu) / sd, np.ones(len(X))])
    A = Z.T @ Z + RIDGE_LAMBDA * np.eye(Z.shape[1])
    A[-1, -1] -= RIDGE_LAMBDA            # không phạt hệ số chặn
    w = np.linalg.solve(A, Z.T @ y)
    return mu, sd, w


def _predict_delta(model, X: np.ndarray) -> np.ndarray:
    mu, sd, w = model
    return np.clip(((X - mu) / sd) @ w[:-1] + w[-1], -MAX_DELTA, MAX_DELTA)


def _collect_samples(M: np.ndarray, t_min: int, t_end_excl: int):
    """Tạo mẫu train: với mỗi tháng đích t < t_end_excl -> (t, X, delta). Chỉ dùng dữ liệu TRƯỚC t."""
    rng = np.random.default_rng(0)
    samples = []
    for col in range(WINDOW, M.shape[1]):
        t = t_min + col
        if t >= t_end_excl:
            break
        W, y = M[:, col - WINDOW:col], M[:, col]
        ok = (~np.isnan(y)) & ((~np.isnan(W)).sum(axis=1) >= MIN_WINDOW_VALID)
        if ok.sum() < MIN_MONTH_TARGETS:
            continue
        idx = np.where(ok)[0]
        if len(idx) > MAX_ROWS_PER_MONTH:
            idx = rng.choice(idx, MAX_ROWS_PER_MONTH, replace=False)
        Wf = _fill(W[idx])
        samples.append((t, _features(Wf, _month_of(t)), y[idx].astype(np.float64) - Wf[:, -1]))
    return samples


def _train(samples):
    """-> (model|None, report). Backtest trên tháng cuối; không thắng persistence thì model=None."""
    if len(samples) < 3:
        raise RuntimeError(
            f"Chỉ có {len(samples)} tháng đủ dữ liệu để huấn luyện (cần >= 3). "
            "Kiểm tra bảng ndvi_records có đủ lịch sử liên tiếp không."
        )
    report = {"n_train_months": len(samples), "holdout": None, "used_model": True}
    final_fit = lambda: _fit_ridge(np.vstack([s[1] for s in samples]),
                                   np.concatenate([s[2] for s in samples]))

    if len(samples) >= 6:
        tr, ho = samples[:-HOLDOUT_MONTHS], samples[-HOLDOUT_MONTHS:]
        m_bt = _fit_ridge(np.vstack([s[1] for s in tr]), np.concatenate([s[2] for s in tr]))
        Xh, dh = np.vstack([s[1] for s in ho]), np.concatenate([s[2] for s in ho])
        mae_model = float(np.abs(_predict_delta(m_bt, Xh) - dh).mean())
        mae_persist = float(np.abs(dh).mean())
        report["holdout"] = {
            "months": [f"{(t - 1) // 12}-{_month_of(t):02d}" for t, _, _ in ho],
            "mae_model": mae_model,
            "mae_persistence": mae_persist,
        }
        if mae_model >= mae_persist:
            report["used_model"] = False
            return None, report
    return final_fit(), report


# ---------------- Dự báo ----------------
def forecast_from_history(df_hist: pd.DataFrame, year: int, month: int):
    ids, coords, M, t_min = _build_matrix(df_hist)
    t_max = t_min + M.shape[1] - 1
    target = year * 12 + month

    end = min(target - 1, t_max)          # tháng cuối của cửa sổ lịch sử
    steps = target - end                  # số bước dự báo (1 = bình thường)
    if steps > MAX_STEPS:
        raise RuntimeError(f"Tháng đích cách dữ liệu cuối {steps} tháng (> {MAX_STEPS}).")
    if end - WINDOW + 1 < t_min:
        raise RuntimeError("Không đủ 12 tháng lịch sử trước tháng đích.")

    samples = _collect_samples(M, t_min, t_end_excl=target)       # chỉ dùng quá khứ của tháng đích
    non_causal = False
    if len(samples) < 6 and target <= t_max:
        # Tháng đích nằm TRONG lịch sử (tháng bị mây) mà lịch sử trước nó quá ngắn:
        # cho phép học từ các tháng sau, nhưng loại hẳn chính tháng đích.
        samples = [s for s in _collect_samples(M, t_min, t_end_excl=t_max + 1) if s[0] != target]
        non_causal = True
    model, report = _train(samples)
    report["non_causal"] = non_causal

    c_end = end - t_min
    W = M[:, c_end - WINDOW + 1:c_end + 1]
    ok = (~np.isnan(W)).sum(axis=1) >= MIN_WINDOW_VALID
    idx = np.where(ok)[0]
    if len(idx) == 0:
        raise RuntimeError("Không ô nào đủ dữ liệu lịch sử trong 12 tháng gần nhất.")
    W = _fill(W[idx])
    last_obs = W[:, -1].copy()

    pred = last_obs
    for s in range(1, steps + 1):
        delta = 0.0 if model is None else _predict_delta(model, _features(W, _month_of(end + s)))
        pred = np.clip(W[:, -1] + delta, NDVI_LO, NDVI_HI)
        W = np.concatenate([W[:, 1:], pred[:, None]], axis=1)

    corr = float(np.corrcoef(last_obs, pred)[0, 1]) if pred.std() > 0 and last_obs.std() > 0 else 1.0
    report.update({
        "n_grids": int(len(idx)), "steps": int(steps),
        "last_mean": float(last_obs.mean()), "last_std": float(last_obs.std()),
        "pred_mean": float(pred.mean()), "pred_std": float(pred.std()), "corr_vs_last": corr,
    })

    band = report["holdout"]["mae_model"] if report["holdout"] else 0.05
    band = float(max(band, 0.02))
    out = coords.iloc[idx].reset_index()
    out["date"] = f"{year}-{month:02d}-01"
    out["year"] = year
    out["month"] = month
    out["ndvi_mean"] = pred.astype(float)
    out["ndvi_min"] = np.maximum(pred - band, NDVI_LO)
    out["ndvi_max"] = np.minimum(pred + band, NDVI_HI)
    out = out.dropna(subset=["longitude", "latitude", "ndvi_mean"])
    return out[["grid_id", "date", "year", "month", "longitude", "latitude",
                "ndvi_mean", "ndvi_min", "ndvi_max"]], report


@_cache_data(ttl=3600, show_spinner=False)
def _forecast_cached(year: int, month: int):
    return forecast_from_history(load_history(), int(year), int(month))


def run_demo_inference_for_grid(year: int, month: int, sample_step: int = 1) -> pd.DataFrame:
    """Thay thế trực tiếp run_onnx_inference_for_grid. Lỗi -> raise để app hiển thị rõ."""
    df, report = _forecast_cached(year, month)
    print("[AI DEMO]", report)
    return df


def render_ai_report(year: int, month: int):
    """Hiện báo cáo kiểm chứng dưới thông báo thành công (gọi trong app.py)."""
    if st is None:
        return
    try:
        _, r = _forecast_cached(year, month)
    except Exception:
        return
    ho = r.get("holdout")
    lines = [f"**AI Demo:** {r['n_grids']:,} ô, dự báo nối tiếp {r['steps']} bước, "
             f"huấn luyện trên {r['n_train_months']} tháng lịch sử."]
    if ho:
        lines.append(
            f"Backtest ({', '.join(ho['months'])}): sai số MAE model **{ho['mae_model']:.4f}** "
            f"so với giữ-nguyên-tháng-trước **{ho['mae_persistence']:.4f}**."
        )
    else:
        lines.append("Chưa đủ tháng để backtest.")
    if not r["used_model"]:
        lines.append("⚠️ Model không thắng baseline nên đang dùng baseline (giữ cấu trúc tháng trước).")
    lines.append(f"NDVI đầu vào: TB {r['last_mean']:.3f}, độ lệch {r['last_std']:.3f} → "
                 f"dự báo: TB {r['pred_mean']:.3f}, độ lệch {r['pred_std']:.3f}, tương quan {r['corr_vs_last']:.2f}.")
    st.info("\n\n".join(lines))
