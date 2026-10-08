# utils/ai_demo.py
"""
AI DEMO - dự báo NDVI trực tiếp từ CSDL, KHÔNG cần file .onnx / scaler.json.

CHIẾN LƯỢC "LẤY MẪU RẢI RÁC -> DỰ BÁO -> LAN RA XUNG QUANH":
  BƯỚC 1  Chọn SAMPLE_FRACTION (mặc định 25%) số ô, RẢI ĐỀU trên bản đồ (_scatter_sample).
          Các ô còn lại bị loại khỏi dữ liệu ngay từ đầu, AI không nhìn thấy chúng.
  BƯỚC 2  AI (Ridge / baseline giữ-tháng-trước) học và dự báo CHỈ trên các ô mẫu này.
  BƯỚC 3  Giá trị dự báo của các ô mẫu được "lan" ra mọi ô còn lại bằng nội suy
          nghịch đảo khoảng cách (IDW, _spread_to_all) -> ra đủ toàn bộ lưới.
          Sau đó map_utils.generate_ndvi_raster tiếp tục làm mịn khi vẽ ảnh.

Mô hình: NDVI_dự_báo = NDVI_tháng_trước + phần_chênh_nhỏ (học bằng Ridge, numpy thuần),
nên ô đô thị (thấp) vẫn thấp, rừng (cao) vẫn cao. Tự backtest, không thắng baseline thì dùng baseline.

ONNX là TÙY CHỌN: mặc định TẮT (USE_ONNX = False). Muốn bật: đặt USE_ONNX = True và để đủ
2 file vào HCM-34-Json/ (ONNX_PATH, SCALER_PATH). Thiếu scaler thì chỉ cảnh báo và tự bỏ qua ONNX.

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


def _cache_resource(**kw):
    if st is not None:
        return st.cache_resource(**kw)
    return lambda f: f


# ---------------- Cấu hình ----------------
WINDOW = 12               # số tháng lịch sử đưa vào
MIN_WINDOW_VALID = 6      # ô phải có >= 6/12 tháng có dữ liệu thật
MIN_MONTH_TARGETS = 1000  # tháng đích có < 1000 ô hợp lệ thì bỏ qua khi train
MAX_ROWS_PER_MONTH = 8000 # lấy mẫu mỗi tháng để train nhanh, đỡ tốn RAM
SAMPLE_FRACTION = 0.25    # CHỈ ~25% số ô (rải đều) được đưa vào AI. 1.0 = dùng hết
SPREAD_TO_FULL_GRID = True  # True: lan giá trị dự báo ra TOÀN BỘ ô lưới (metrics/CSV/bản đồ đều đủ ô)
IDW_K = 6                 # số ô mẫu gần nhất dùng để nội suy cho mỗi ô còn lại
HOLDOUT_MONTHS = 3        # số tháng cuối dùng để backtest
RIDGE_LAMBDA = 10.0
MAX_DELTA = 0.30          # chặn mức thay đổi tối đa mỗi tháng
MAX_STEPS = 12            # tối đa dự báo nối tiếp 12 tháng
NDVI_LO, NDVI_HI = -0.2, 1.0
ONNX_PATH = "HCM-34-Json/lstm_ndvi_hcm_model.onnx"
SCALER_PATH = "HCM-34-Json/scaler.json"   # {"min": ..., "max": ...} lấy từ MinMaxScaler lúc train
USE_ONNX = False                          # MẶC ĐỊNH TẮT: demo chỉ dùng Ridge/baseline
GOOD_MONTH_FRAC = 0.5     # tháng được coi là 'tốt' nếu >= 50% số ô có giá trị thật (không bị mây)


# ---------------- ONNX (tùy chọn) ----------------
@_cache_resource(show_spinner=False)
def _load_onnx():
    """-> (session, input_name, (min, max)) hoặc None nếu không dùng / không có / lỗi.
    KHÔNG BAO GIỜ raise: ONNX hỏng thì demo vẫn chạy bằng Ridge."""
    import json
    import os

    if not USE_ONNX or not os.path.exists(ONNX_PATH):
        return None
    try:
        if not os.path.exists(SCALER_PATH):
            print(f"[ONNX] Có '{ONNX_PATH}' nhưng thiếu '{SCALER_PATH}' -> bỏ qua ONNX.")
            return None
        import onnxruntime as ort

        with open(SCALER_PATH, "r", encoding="utf-8") as f:
            sc = json.load(f)
        mn, mx = float(sc["min"]), float(sc["max"])
        if mx <= mn:
            print("[ONNX] scaler.json không hợp lệ (max <= min) -> bỏ qua ONNX.")
            return None
        sess = ort.InferenceSession(ONNX_PATH, providers=["CPUExecutionProvider"])
        print("[ONNX] input:", sess.get_inputs()[0].shape, "| output:", sess.get_outputs()[0].shape)
        return sess, sess.get_inputs()[0].name, (mn, mx)
    except Exception as e:
        print(f"[ONNX] Không nạp được model -> bỏ qua ONNX: {e}")
        return None


def _onnx_predict(bundle, W: np.ndarray) -> np.ndarray:
    """W: [N,12] NDVI thật -> [N] NDVI dự báo (thang thật). Tự scale đầu vào, inverse đầu ra."""
    sess, name, (mn, mx) = bundle
    x = ((W - mn) / (mx - mn)).astype(np.float32)
    outs = []
    for i in range(0, len(x), 50000):
        chunk = x[i:i + 50000].reshape(-1, WINDOW, 1)
        outs.append(np.asarray(sess.run(None, {name: chunk})[0]).reshape(-1))
    y = np.concatenate(outs).astype(np.float64) * (mx - mn) + mn
    return np.clip(y, NDVI_LO, NDVI_HI)


# ---------------- Tiện ích thời gian ----------------
def _month_of(t: int) -> int:
    return (t - 1) % 12 + 1          # t = year*12 + month


# ---------------- Đọc dữ liệu ----------------
@_cache_data(ttl=3600, show_spinner=False)
def load_history() -> pd.DataFrame:
    """Đọc lịch sử theo TỪNG NĂM (mỗi truy vấn nhỏ, tránh bị Supabase hủy vì statement timeout)."""
    from sqlalchemy import text
    from utils.data_loader import get_db_engine

    engine = get_db_engine()
    parts = []
    for y in range(2015, 2029):
        part = pd.read_sql(
            text("""
                SELECT grid_id, longitude, latitude, year * 12 + month AS t, ndvi_mean
                FROM public.ndvi_records
                WHERE year = :y AND ndvi_mean IS NOT NULL
            """),
            engine, params={"y": y},
        )
        if not part.empty:
            parts.append(part)
    if not parts:
        raise RuntimeError("Bảng ndvi_records không có dữ liệu.")
    return pd.concat(parts, ignore_index=True)


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


# ---------------- BƯỚC 1: lấy mẫu rải rác ----------------
def _scatter_sample(coords: pd.DataFrame, frac: float, seed: int = 0) -> np.ndarray:
    """Chọn ô RẢI ĐỀU: chia bản đồ thành lưới thô, mỗi ô thô bốc ngẫu nhiên 1 ô lưới.
    Trả về mảng chỉ số vị trí (0..n-1) của các ô được chọn (xấp xỉ frac*n ô)."""
    n = len(coords)
    if frac >= 1.0 or n <= 500:
        return np.arange(n)
    lon = coords["longitude"].to_numpy()
    lat = coords["latitude"].to_numpy()
    target = max(int(n * frac), 200)
    order = np.random.default_rng(seed).permutation(n)

    # Ranh giới TP.HCM không vuông -> nhiều ô thô trống -> phải tăng 'side' dần tới khi đủ số ô.
    side = max(int(np.sqrt(target)), 10)
    best = None
    for _ in range(8):
        ix = np.minimum(((lon - lon.min()) / (np.ptp(lon) + 1e-12) * side).astype(int), side - 1)
        iy = np.minimum(((lat - lat.min()) / (np.ptp(lat) + 1e-12) * side).astype(int), side - 1)
        key = ix * side + iy
        _, first = np.unique(key[order], return_index=True)
        sel = order[first]
        if best is None or abs(len(sel) - target) < abs(len(best) - target):
            best = sel
        if 0.9 * target <= len(sel) <= 1.15 * target:
            break
        side = max(int(side * np.sqrt(target / max(len(sel), 1))), 5)
    return np.sort(best)


# ---------------- BƯỚC 3: lan ra xung quanh ----------------
def _spread_to_all(coords_all: pd.DataFrame, src_ids, src_vals: np.ndarray) -> np.ndarray:
    """Lan giá trị dự báo của các ô mẫu ra TẤT CẢ ô trong coords_all bằng IDW (k ô mẫu gần nhất).
    Ô mẫu giữ nguyên giá trị AI; ô khác = trung bình có trọng số 1/d^2 của các ô mẫu quanh nó."""
    from scipy.spatial import cKDTree

    lat0 = np.radians(float(coords_all["latitude"].mean()))
    k_lon = np.cos(lat0)   # quy đổi kinh độ về cùng thang mét với vĩ độ

    def xy(d):
        return np.column_stack([d["longitude"].to_numpy() * k_lon, d["latitude"].to_numpy()])

    src = coords_all.loc[src_ids]
    k = int(min(IDW_K, len(src)))
    tree = cKDTree(xy(src))
    dist, nn = tree.query(xy(coords_all), k=k)
    if k == 1:
        dist, nn = dist[:, None], nn[:, None]
    w = 1.0 / np.maximum(dist, 1e-9) ** 2
    vals = (w * src_vals[nn]).sum(axis=1) / w.sum(axis=1)
    vals[coords_all.index.get_indexer(src_ids)] = src_vals   # ô mẫu: giữ đúng giá trị AI
    return np.clip(vals, NDVI_LO, NDVI_HI)


# ---------------- BƯỚC 2: huấn luyện + dự báo trên ô mẫu ----------------
def _collect_samples(M: np.ndarray, t_min: int, t_end_excl: int, good: np.ndarray):
    """Tạo mẫu train: với mỗi tháng đích t < t_end_excl -> (t, X, delta, W). Chỉ dùng dữ liệu TRƯỚC t."""
    rng = np.random.default_rng(0)
    samples = []
    for col in range(WINDOW, M.shape[1]):
        t = t_min + col
        if t >= t_end_excl:
            break
        if not good[col]:
            continue                    # tháng đích bị mây nhiều -> không dùng làm nhãn
        W, y = M[:, col - WINDOW:col], M[:, col]
        ok = (~np.isnan(y)) & ((~np.isnan(W)).sum(axis=1) >= MIN_WINDOW_VALID)
        if ok.sum() < max(100, min(MIN_MONTH_TARGETS, int(0.15 * M.shape[0]))):
            continue
        idx = np.where(ok)[0]
        if len(idx) > MAX_ROWS_PER_MONTH:
            idx = rng.choice(idx, MAX_ROWS_PER_MONTH, replace=False)
        Wf = _fill(W[idx])
        samples.append((t, _features(Wf, _month_of(t)), y[idx].astype(np.float64) - Wf[:, -1], Wf))
    return samples


def _train(samples, onnx_bundle=None):
    """-> (model, report). model = {"kind": "onnx" | "ridge" | "persistence", ...}.
    Backtest trên các tháng cuối rồi chọn phương án có MAE thấp nhất."""
    if len(samples) < 3:
        raise RuntimeError(
            f"Chỉ có {len(samples)} tháng đủ dữ liệu để huấn luyện (cần >= 3). "
            "Kiểm tra bảng ndvi_records có đủ lịch sử liên tiếp không."
        )
    report = {"n_train_months": len(samples), "holdout": None}

    def fit_all():
        return _fit_ridge(np.vstack([s[1] for s in samples]), np.concatenate([s[2] for s in samples]))

    if len(samples) < 6:                       # quá ít tháng để backtest
        model = ({"kind": "onnx", "bundle": onnx_bundle} if onnx_bundle is not None
                 else {"kind": "ridge", "ridge": fit_all()})
        report.update(backend=model["kind"], used_model=True)
        return model, report

    tr, ho = samples[:-HOLDOUT_MONTHS], samples[-HOLDOUT_MONTHS:]
    Xh = np.vstack([s[1] for s in ho])
    dh = np.concatenate([s[2] for s in ho])
    Wh = np.vstack([s[3] for s in ho])

    maes = {}                                   # thứ tự = ưu tiên khi hòa: onnx > ridge > persistence
    if onnx_bundle is not None:
        try:
            p = _onnx_predict(onnx_bundle, Wh)
            maes["onnx"] = float(np.abs((p - Wh[:, -1]) - dh).mean())
        except Exception as e:                  # ONNX sai shape/scale... -> bỏ qua, không làm sập demo
            print(f"[ONNX] Lỗi khi backtest, bỏ qua ONNX: {e}")
            onnx_bundle = None
    m_bt = _fit_ridge(np.vstack([s[1] for s in tr]), np.concatenate([s[2] for s in tr]))
    maes["ridge"] = float(np.abs(_predict_delta(m_bt, Xh) - dh).mean())
    maes["persistence"] = float(np.abs(dh).mean())

    best = min(maes, key=maes.get)
    report["holdout"] = {
        "months": [f"{(s[0] - 1) // 12}-{_month_of(s[0]):02d}" for s in ho],
        "mae_onnx": maes.get("onnx"),
        "mae_ridge": maes["ridge"],
        "mae_persistence": maes["persistence"],
        "mae_model": maes[best],
    }
    report.update(backend=best, used_model=(best != "persistence"))
    if best == "onnx":
        model = {"kind": "onnx", "bundle": onnx_bundle}
    elif best == "ridge":
        model = {"kind": "ridge", "ridge": fit_all()}
    else:
        model = {"kind": "persistence"}
    return model, report


def _step(model, W: np.ndarray, month: int) -> np.ndarray:
    """Dự báo 1 tháng tiếp theo cho cửa sổ W [N,12] (thang thật)."""
    kind = model["kind"]
    if kind == "persistence":
        return W[:, -1]
    if kind == "onnx":
        return _onnx_predict(model["bundle"], W)
    return np.clip(W[:, -1] + _predict_delta(model["ridge"], _features(W, month)), NDVI_LO, NDVI_HI)


def _last_known(M: np.ndarray, rows: np.ndarray, c_end: int) -> np.ndarray:
    """Với ô thiếu dữ liệu: lấy giá trị thật GẦN NHẤT (ưu tiên trước c_end, nếu không có thì sau)."""
    sub = pd.DataFrame(M[rows])
    v = sub.iloc[:, :c_end + 1].ffill(axis=1).iloc[:, -1]
    v = v.fillna(sub.bfill(axis=1).iloc[:, 0])
    return v.to_numpy(dtype=np.float64)


def forecast_from_history(df_hist: pd.DataFrame, year: int, month: int, onnx_bundle=None):
    # --- BƯỚC 1: chỉ giữ lại một số ô RẢI RÁC; từ đây AI không nhìn thấy các ô còn lại ---
    coords_all = df_hist.groupby("grid_id")[["longitude", "latitude"]].mean()
    total_grids = len(coords_all)
    keep_ids = coords_all.index[_scatter_sample(coords_all, SAMPLE_FRACTION)]
    df_hist = df_hist[df_hist["grid_id"].isin(keep_ids)]

    ids, coords, M, t_min = _build_matrix(df_hist)
    N = M.shape[0]
    t_max = t_min + M.shape[1] - 1
    target = year * 12 + month

    # Tháng "tốt" = có >= GOOD_MONTH_FRAC số ô có dữ liệu thật. Cửa sổ lịch sử kết thúc ở tháng tốt
    # gần nhất, để giá trị "tháng trước" không bị trộn từ nhiều tháng khác nhau do mây.
    valid_cnt = (~np.isnan(M)).sum(axis=0)
    good = valid_cnt >= GOOD_MONTH_FRAC * N
    limit_col = min(target - 1, t_max) - t_min
    cands = [c for c in range(WINDOW - 1, limit_col + 1) if good[c]]
    if not cands:
        raise RuntimeError("Không có tháng 'tốt' (đủ độ phủ) nào có đủ 12 tháng lịch sử phía trước.")
    c_end = cands[-1]
    end = t_min + c_end
    steps = target - end
    if steps > MAX_STEPS:
        raise RuntimeError(f"Tháng đích cách tháng dữ liệu tốt cuối ({steps} tháng) vượt giới hạn {MAX_STEPS}.")

    # --- BƯỚC 2: huấn luyện + dự báo trên các ô mẫu ---
    samples = _collect_samples(M, t_min, t_end_excl=target, good=good)   # chỉ dùng quá khứ của tháng đích
    non_causal = False
    if len(samples) < 6 and target <= t_max:
        # Tháng đích nằm TRONG lịch sử (tháng bị mây) mà lịch sử trước nó quá ngắn:
        # cho phép học từ các tháng sau, nhưng loại hẳn chính tháng đích.
        samples = [s for s in _collect_samples(M, t_min, t_end_excl=t_max + 1, good=good) if s[0] != target]
        non_causal = True
    model, report = _train(samples, onnx_bundle)
    report["non_causal"] = non_causal

    # --- Ô đủ dữ liệu -> dùng model ---
    W_all = M[:, c_end - WINDOW + 1:c_end + 1]
    ok = (~np.isnan(W_all)).sum(axis=1) >= MIN_WINDOW_VALID
    idx = np.where(ok)[0]
    if len(idx) == 0:
        raise RuntimeError("Không ô nào đủ dữ liệu lịch sử trong 12 tháng gần nhất.")
    W = _fill(W_all[idx])
    last_obs = W[:, -1].copy()

    pred = last_obs
    for s in range(1, steps + 1):
        pred = _step(model, W, _month_of(end + s))
        W = np.concatenate([W[:, 1:], pred[:, None]], axis=1)

    # --- Ô mẫu thiếu dữ liệu -> dùng giá trị thật gần nhất + hiệu chỉnh mùa vụ ---
    pred_all = np.full(N, np.nan, dtype=np.float64)
    pred_all[idx] = pred
    bad = np.where(~ok)[0]
    if len(bad):
        fb = _last_known(M, bad, c_end)
        shift = pred - last_obs
        edges = np.unique(np.quantile(last_obs, np.linspace(0, 1, 11)))
        if len(edges) > 2:
            b_idx = np.clip(np.digitize(last_obs, edges[1:-1]), 0, len(edges) - 2)
            centers, means = [], []
            for k in range(len(edges) - 1):
                sel = b_idx == k
                if sel.any():                       # bỏ nhóm rỗng để không sinh NaN
                    centers.append(last_obs[sel].mean())
                    means.append(shift[sel].mean())
            fb = fb + np.interp(fb, np.array(centers), np.array(means))
        pred_all[bad] = np.clip(fb, NDVI_LO, NDVI_HI)

    corr = float(np.corrcoef(last_obs, pred)[0, 1]) if pred.std() > 0 and last_obs.std() > 0 else 1.0
    band = report["holdout"]["mae_model"] if report["holdout"] else 0.05
    band = float(max(band, 0.02))

    # --- BƯỚC 3: lan từ các ô mẫu ra xung quanh ---
    finite = np.isfinite(pred_all)
    src_ids = coords.index[finite]
    src_vals = pred_all[finite]
    if SPREAD_TO_FULL_GRID and len(src_vals) >= 3 and len(src_vals) < total_grids:
        out = coords_all.reset_index()
        out["ndvi_mean"] = _spread_to_all(coords_all, src_ids, src_vals)
    else:
        out = coords.loc[src_ids].reset_index()
        out["ndvi_mean"] = src_vals

    report.update({
        "n_grids": int(N), "n_total": int(total_grids), "n_out": int(len(out)),
        "spread": bool(SPREAD_TO_FULL_GRID), "n_fallback": int(len(bad)), "steps": int(steps),
        "base_month": f"{(end - 1) // 12}-{_month_of(end):02d}",
        "base_coverage": float(valid_cnt[c_end] / N),
        "last_mean": float(last_obs.mean()), "last_std": float(last_obs.std()),
        "pred_mean": float(pred.mean()), "pred_std": float(pred.std()), "corr_vs_last": corr,
    })

    out["date"] = f"{year}-{month:02d}-01"
    out["year"] = year
    out["month"] = month
    out["ndvi_min"] = np.maximum(out["ndvi_mean"] - band, NDVI_LO)
    out["ndvi_max"] = np.minimum(out["ndvi_mean"] + band, NDVI_HI)
    out = out.dropna(subset=["longitude", "latitude", "ndvi_mean"])
    return out[["grid_id", "date", "year", "month", "longitude", "latitude",
                "ndvi_mean", "ndvi_min", "ndvi_max"]], report


@_cache_data(ttl=3600, show_spinner=False)
def _forecast_cached(year: int, month: int):
    try:
        bundle = _load_onnx()
    except Exception as e:
        print(f"[ONNX] bỏ qua: {e}")
        bundle = None
    return forecast_from_history(load_history(), int(year), int(month), onnx_bundle=bundle)


def run_demo_inference_for_grid(year: int, month: int, sample_step: int = 1) -> pd.DataFrame:
    """Thay thế trực tiếp run_onnx_inference_for_grid. Lỗi -> raise để app hiển thị rõ.
    (sample_step giữ lại cho tương thích; tỉ lệ lấy mẫu chỉnh bằng SAMPLE_FRACTION ở đầu file.)"""
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
    spread_txt = (f"rồi lan (IDW) ra toàn bộ {r['n_out']:,} ô" if r["spread"]
                  else "phần còn lại được nội suy khi vẽ bản đồ")
    lines = [f"**AI Demo:** chỉ đưa {r['n_grids']:,}/{r['n_total']:,} ô rải đều ({r['n_grids'] / r['n_total']:.0%}) "
             f"vào AI, {spread_txt}. Dự báo từ tháng gốc {r['base_month']} "
             f"(độ phủ dữ liệu thật {r['base_coverage']:.0%}), nối tiếp {r['steps']} bước, "
             f"huấn luyện trên {r['n_train_months']} tháng lịch sử."]
    if r["n_fallback"]:
        lines.append(f"{r['n_fallback']:,} ô mẫu thiếu dữ liệu lịch sử nên dùng giá trị thật gần nhất.")
    if ho:
        parts = []
        if ho.get("mae_onnx") is not None:
            parts.append(f"ONNX {ho['mae_onnx']:.4f}")
        parts += [f"Ridge {ho['mae_ridge']:.4f}", f"giữ-tháng-trước {ho['mae_persistence']:.4f}"]
        lines.append(f"Backtest ({', '.join(ho['months'])}), sai số MAE: " + " | ".join(parts)
                     + f" → đang dùng **{r['backend']}**.")
    else:
        lines.append(f"Chưa đủ tháng để backtest, đang dùng **{r['backend']}**.")
    if not r["used_model"]:
        lines.append("⚠️ Không model nào thắng baseline nên đang dùng baseline (giữ cấu trúc tháng trước).")
    lines.append(f"NDVI đầu vào: TB {r['last_mean']:.3f}, độ lệch {r['last_std']:.3f} → "
                 f"dự báo: TB {r['pred_mean']:.3f}, độ lệch {r['pred_std']:.3f}, tương quan {r['corr_vs_last']:.2f}.")
    st.info("\n\n".join(lines))

# # utils/ai_demo.py
# """
# AI DEMO - dự báo NDVI trực tiếp từ CSDL, KHÔNG cần file .onnx / scaler.json.

# Ý tưởng (đơn giản nhưng giữ đúng cấu trúc không gian):
#     NDVI_dự_báo = NDVI_tháng_trước + phần_chênh_nhỏ
#   - Phần chênh được học bằng hồi quy Ridge (numpy thuần) từ chính lịch sử trong CSDL.
#   - Vì luôn cộng vào NDVI tháng trước nên ô đô thị (thấp) vẫn thấp, rừng (cao) vẫn cao
#     -> không thể "xanh hóa đồng loạt" như lỗi trước.
#   - Tự backtest trên 3 tháng cuối có dữ liệu. Nếu model KHÔNG thắng baseline
#     "giữ nguyên tháng trước" thì tự động dùng baseline (an toàn hơn).

# Hàm công khai (cùng chữ ký/cột với run_onnx_inference_for_grid cũ):
#     run_demo_inference_for_grid(year, month) -> DataFrame
#     render_ai_report(year, month)            -> hiện báo cáo kiểm chứng lên giao diện
# """
# import numpy as np
# import pandas as pd

# try:
#     import streamlit as st
# except Exception:  # cho phép test ngoài Streamlit
#     st = None


# def _cache_data(**kw):
#     if st is not None:
#         return st.cache_data(**kw)
#     return lambda f: f


# # ---------------- Cấu hình ----------------
# WINDOW = 12               # số tháng lịch sử đưa vào
# MIN_WINDOW_VALID = 6      # ô phải có >= 6/12 tháng có dữ liệu thật
# MIN_MONTH_TARGETS = 1000  # tháng đích có < 1000 ô hợp lệ thì bỏ qua khi train
# MAX_ROWS_PER_MONTH = 8000 # lấy mẫu mỗi tháng để train nhanh, đỡ tốn RAM
# HOLDOUT_MONTHS = 3        # số tháng cuối dùng để backtest
# RIDGE_LAMBDA = 10.0
# MAX_DELTA = 0.30          # chặn mức thay đổi tối đa mỗi tháng
# MAX_STEPS = 12            # tối đa dự báo nối tiếp 12 tháng
# NDVI_LO, NDVI_HI = -0.2, 1.0


# # ---------------- Tiện ích thời gian ----------------
# def _month_of(t: int) -> int:
#     return (t - 1) % 12 + 1          # t = year*12 + month


# # ---------------- Đọc dữ liệu ----------------
# @_cache_data(ttl=3600, show_spinner=False)
# def load_history() -> pd.DataFrame:
#     from sqlalchemy import text
#     from utils.data_loader import get_db_engine

#     return pd.read_sql(
#         text("""
#             SELECT grid_id, longitude, latitude,
#                    year * 12 + month AS t, ndvi_mean
#             FROM public.ndvi_records
#             WHERE ndvi_mean IS NOT NULL
#         """),
#         get_db_engine(),
#     )


# def _build_matrix(df: pd.DataFrame):
#     """-> ids, coords, M [N, T] (NaN = thiếu/mây), t_min. Lịch liên tục từng tháng."""
#     coords = df.groupby("grid_id")[["longitude", "latitude"]].mean()
#     piv = df.groupby(["grid_id", "t"])["ndvi_mean"].mean().unstack("t")
#     t_min, t_max = int(piv.columns.min()), int(piv.columns.max())
#     piv = piv.reindex(columns=range(t_min, t_max + 1))
#     coords = coords.loc[piv.index]
#     return piv.index.to_numpy(), coords, piv.to_numpy(dtype=np.float32), t_min


# # ---------------- Đặc trưng + mô hình ----------------
# def _fill(W: np.ndarray) -> np.ndarray:
#     """Điền khuyết TRONG cửa sổ (không nhìn sang tương lai)."""
#     return pd.DataFrame(W).ffill(axis=1).bfill(axis=1).to_numpy(dtype=np.float64)


# def _features(W: np.ndarray, target_month: int) -> np.ndarray:
#     """W: [N,12] đã điền. Đặc trưng: chênh so với tháng cuối (11), mức NDVI, sin/cos mùa vụ."""
#     last = W[:, -1]
#     d = W[:, :-1] - last[:, None]
#     ang = 2.0 * np.pi * target_month / 12.0
#     n = len(W)
#     return np.column_stack([d, last, np.full(n, np.sin(ang)), np.full(n, np.cos(ang))])


# def _fit_ridge(X: np.ndarray, y: np.ndarray):
#     mu = X.mean(axis=0)
#     sd = X.std(axis=0)
#     sd[sd < 1e-6] = 1.0
#     Z = np.column_stack([(X - mu) / sd, np.ones(len(X))])
#     A = Z.T @ Z + RIDGE_LAMBDA * np.eye(Z.shape[1])
#     A[-1, -1] -= RIDGE_LAMBDA            # không phạt hệ số chặn
#     w = np.linalg.solve(A, Z.T @ y)
#     return mu, sd, w


# def _predict_delta(model, X: np.ndarray) -> np.ndarray:
#     mu, sd, w = model
#     return np.clip(((X - mu) / sd) @ w[:-1] + w[-1], -MAX_DELTA, MAX_DELTA)


# def _collect_samples(M: np.ndarray, t_min: int, t_end_excl: int):
#     """Tạo mẫu train: với mỗi tháng đích t < t_end_excl -> (t, X, delta). Chỉ dùng dữ liệu TRƯỚC t."""
#     rng = np.random.default_rng(0)
#     samples = []
#     for col in range(WINDOW, M.shape[1]):
#         t = t_min + col
#         if t >= t_end_excl:
#             break
#         W, y = M[:, col - WINDOW:col], M[:, col]
#         ok = (~np.isnan(y)) & ((~np.isnan(W)).sum(axis=1) >= MIN_WINDOW_VALID)
#         if ok.sum() < MIN_MONTH_TARGETS:
#             continue
#         idx = np.where(ok)[0]
#         if len(idx) > MAX_ROWS_PER_MONTH:
#             idx = rng.choice(idx, MAX_ROWS_PER_MONTH, replace=False)
#         Wf = _fill(W[idx])
#         samples.append((t, _features(Wf, _month_of(t)), y[idx].astype(np.float64) - Wf[:, -1]))
#     return samples


# def _train(samples):
#     """-> (model|None, report). Backtest trên tháng cuối; không thắng persistence thì model=None."""
#     if len(samples) < 3:
#         raise RuntimeError(
#             f"Chỉ có {len(samples)} tháng đủ dữ liệu để huấn luyện (cần >= 3). "
#             "Kiểm tra bảng ndvi_records có đủ lịch sử liên tiếp không."
#         )
#     report = {"n_train_months": len(samples), "holdout": None, "used_model": True}
#     final_fit = lambda: _fit_ridge(np.vstack([s[1] for s in samples]),
#                                    np.concatenate([s[2] for s in samples]))

#     if len(samples) >= 6:
#         tr, ho = samples[:-HOLDOUT_MONTHS], samples[-HOLDOUT_MONTHS:]
#         m_bt = _fit_ridge(np.vstack([s[1] for s in tr]), np.concatenate([s[2] for s in tr]))
#         Xh, dh = np.vstack([s[1] for s in ho]), np.concatenate([s[2] for s in ho])
#         mae_model = float(np.abs(_predict_delta(m_bt, Xh) - dh).mean())
#         mae_persist = float(np.abs(dh).mean())
#         report["holdout"] = {
#             "months": [f"{(t - 1) // 12}-{_month_of(t):02d}" for t, _, _ in ho],
#             "mae_model": mae_model,
#             "mae_persistence": mae_persist,
#         }
#         if mae_model >= mae_persist:
#             report["used_model"] = False
#             return None, report
#     return final_fit(), report


# # ---------------- Dự báo ----------------
# def forecast_from_history(df_hist: pd.DataFrame, year: int, month: int):
#     ids, coords, M, t_min = _build_matrix(df_hist)
#     t_max = t_min + M.shape[1] - 1
#     target = year * 12 + month

#     end = min(target - 1, t_max)          # tháng cuối của cửa sổ lịch sử
#     steps = target - end                  # số bước dự báo (1 = bình thường)
#     if steps > MAX_STEPS:
#         raise RuntimeError(f"Tháng đích cách dữ liệu cuối {steps} tháng (> {MAX_STEPS}).")
#     if end - WINDOW + 1 < t_min:
#         raise RuntimeError("Không đủ 12 tháng lịch sử trước tháng đích.")

#     samples = _collect_samples(M, t_min, t_end_excl=target)       # chỉ dùng quá khứ của tháng đích
#     non_causal = False
#     if len(samples) < 6 and target <= t_max:
#         # Tháng đích nằm TRONG lịch sử (tháng bị mây) mà lịch sử trước nó quá ngắn:
#         # cho phép học từ các tháng sau, nhưng loại hẳn chính tháng đích.
#         samples = [s for s in _collect_samples(M, t_min, t_end_excl=t_max + 1) if s[0] != target]
#         non_causal = True
#     model, report = _train(samples)
#     report["non_causal"] = non_causal

#     c_end = end - t_min
#     W = M[:, c_end - WINDOW + 1:c_end + 1]
#     ok = (~np.isnan(W)).sum(axis=1) >= MIN_WINDOW_VALID
#     idx = np.where(ok)[0]
#     if len(idx) == 0:
#         raise RuntimeError("Không ô nào đủ dữ liệu lịch sử trong 12 tháng gần nhất.")
#     W = _fill(W[idx])
#     last_obs = W[:, -1].copy()

#     pred = last_obs
#     for s in range(1, steps + 1):
#         delta = 0.0 if model is None else _predict_delta(model, _features(W, _month_of(end + s)))
#         pred = np.clip(W[:, -1] + delta, NDVI_LO, NDVI_HI)
#         W = np.concatenate([W[:, 1:], pred[:, None]], axis=1)

#     corr = float(np.corrcoef(last_obs, pred)[0, 1]) if pred.std() > 0 and last_obs.std() > 0 else 1.0
#     report.update({
#         "n_grids": int(len(idx)), "steps": int(steps),
#         "last_mean": float(last_obs.mean()), "last_std": float(last_obs.std()),
#         "pred_mean": float(pred.mean()), "pred_std": float(pred.std()), "corr_vs_last": corr,
#     })

#     band = report["holdout"]["mae_model"] if report["holdout"] else 0.05
#     band = float(max(band, 0.02))
#     out = coords.iloc[idx].reset_index()
#     out["date"] = f"{year}-{month:02d}-01"
#     out["year"] = year
#     out["month"] = month
#     out["ndvi_mean"] = pred.astype(float)
#     out["ndvi_min"] = np.maximum(pred - band, NDVI_LO)
#     out["ndvi_max"] = np.minimum(pred + band, NDVI_HI)
#     out = out.dropna(subset=["longitude", "latitude", "ndvi_mean"])
#     return out[["grid_id", "date", "year", "month", "longitude", "latitude",
#                 "ndvi_mean", "ndvi_min", "ndvi_max"]], report


# @_cache_data(ttl=3600, show_spinner=False)
# def _forecast_cached(year: int, month: int):
#     return forecast_from_history(load_history(), int(year), int(month))


# def run_demo_inference_for_grid(year: int, month: int, sample_step: int = 1) -> pd.DataFrame:
#     """Thay thế trực tiếp run_onnx_inference_for_grid. Lỗi -> raise để app hiển thị rõ."""
#     df, report = _forecast_cached(year, month)
#     print("[AI DEMO]", report)
#     return df


# def render_ai_report(year: int, month: int):
#     """Hiện báo cáo kiểm chứng dưới thông báo thành công (gọi trong app.py)."""
#     if st is None:
#         return
#     try:
#         _, r = _forecast_cached(year, month)
#     except Exception:
#         return
#     ho = r.get("holdout")
#     lines = [f"**AI Demo:** {r['n_grids']:,} ô, dự báo nối tiếp {r['steps']} bước, "
#              f"huấn luyện trên {r['n_train_months']} tháng lịch sử."]
#     if ho:
#         lines.append(
#             f"Backtest ({', '.join(ho['months'])}): sai số MAE model **{ho['mae_model']:.4f}** "
#             f"so với giữ-nguyên-tháng-trước **{ho['mae_persistence']:.4f}**."
#         )
#     else:
#         lines.append("Chưa đủ tháng để backtest.")
#     if not r["used_model"]:
#         lines.append("⚠️ Model không thắng baseline nên đang dùng baseline (giữ cấu trúc tháng trước).")
#     lines.append(f"NDVI đầu vào: TB {r['last_mean']:.3f}, độ lệch {r['last_std']:.3f} → "
#                  f"dự báo: TB {r['pred_mean']:.3f}, độ lệch {r['pred_std']:.3f}, tương quan {r['corr_vs_last']:.2f}.")
#     st.info("\n\n".join(lines))
