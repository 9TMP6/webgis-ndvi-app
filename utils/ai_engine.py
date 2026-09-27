import os
import onnxruntime as ort
import numpy as np
import pandas as pd
import streamlit as st

# =============================================================================
# CẤU HÌNH
# =============================================================================
MODEL_PATH = "HCM-34-Json/lstm_ndvi_hcm_model.onnx"
HISTORY_LENGTH = 12
DEBUG = True


# =============================================================================
# 1. DỮ LIỆU DỰ PHÒNG (FALLBACK)
# =============================================================================
def generate_fallback_grid_data(year: int, month: int) -> pd.DataFrame:
    """Dùng khi không tìm thấy model hoặc xảy ra lỗi kết nối."""
    from utils.data_loader import get_db_engine

    try:
        engine = get_db_engine()
        query = """
            SELECT DISTINCT grid_id, longitude, latitude
            FROM public.ndvi_records
            WHERE longitude IS NOT NULL AND latitude IS NOT NULL
            ORDER BY grid_id LIMIT 1000
        """
        df = pd.read_sql(query, engine)
        if df.empty:
            return pd.DataFrame()

        rng = np.random.default_rng(42)
        df["date"] = f"{year}-{month:02d}-01"
        df["year"] = year
        df["month"] = month
        df["ndvi_mean"] = rng.uniform(0.30, 0.70, len(df))
        df["ndvi_min"] = np.maximum(df["ndvi_mean"] - 0.10, 0.0)
        df["ndvi_max"] = np.minimum(df["ndvi_mean"] + 0.10, 1.0)

        df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
        df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
        df["ndvi_mean"] = pd.to_numeric(df["ndvi_mean"], errors="coerce")

        return df.dropna(subset=["longitude", "latitude", "ndvi_mean"]).reset_index(drop=True)

    except Exception as e:
        print(f"[FALLBACK ERROR] {type(e).__name__}: {e}")
        return pd.DataFrame()


# =============================================================================
# 2. TẠO DANH SÁCH 12 THÁNG LỊCH SỬ
# =============================================================================
def create_history_dates(year: int, month: int, history_length: int = HISTORY_LENGTH) -> pd.DatetimeIndex:
    """Tạo chính xác 12 tháng lịch sử cần đưa vào model trước tháng mục tiêu."""
    target_date = pd.Timestamp(year=year, month=month, day=1)
    start_date = target_date - pd.DateOffset(months=history_length)
    return pd.date_range(start=start_date, periods=history_length, freq="MS")


# =============================================================================
# 3. LẤY GRID CƠ SỞ
# =============================================================================
def load_base_grids(engine) -> pd.DataFrame:
    """Lấy danh sách grid và tọa độ gốc."""
    query = """
        SELECT grid_id, longitude, latitude
        FROM public.ndvi_records
        WHERE year = 2020 AND month = 11 
          AND longitude IS NOT NULL AND latitude IS NOT NULL
        GROUP BY grid_id, longitude, latitude
        ORDER BY grid_id
    """
    df = pd.read_sql(query, engine)
    if df.empty:
        return pd.DataFrame()

    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    return df.dropna(subset=["longitude", "latitude"]).reset_index(drop=True)


# =============================================================================
# 4. LẤY DỮ LIỆU LỊCH SỬ
# =============================================================================
def load_history_data(engine, history_dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Lấy toàn bộ NDVI trong khoảng 12 tháng lịch sử."""
    start_date = history_dates[0]
    end_date = history_dates[-1]

    query = f"""
        SELECT grid_id, year, month, ndvi_mean
        FROM public.ndvi_records
        WHERE (year > {start_date.year} OR (year = {start_date.year} AND month >= {start_date.month}))
          AND (year < {end_date.year} OR (year = {end_date.year} AND month <= {end_date.month}))
        ORDER BY grid_id, year, month
    """
    df = pd.read_sql(query, engine)
    if df.empty:
        return pd.DataFrame()

    df["ndvi_mean"] = pd.to_numeric(df["ndvi_mean"], errors="coerce")
    return df.dropna(subset=["ndvi_mean"]).reset_index(drop=True)


# =============================================================================
# 5. CHUẨN HÓA DATAFRAME THÀNH CHUỖI [N, 12, 1]
# =============================================================================
def build_valid_sequences(df_history: pd.DataFrame, history_dates: pd.DatetimeIndex):
    """Kiểm tra và lọc các grid đủ đúng 12 tháng liên tục để tạo batch đầu vào."""
    if df_history.empty:
        return np.empty((0, HISTORY_LENGTH, 1), dtype=np.float32), []

    df_history = df_history.copy()
    df_history["date"] = pd.to_datetime(dict(year=df_history["year"], month=df_history["month"], day=1))
    expected_dates = list(history_dates)

    sequences = []
    valid_grid_ids = []

    for grid_id, group in df_history.groupby("grid_id", sort=True):
        group = group.sort_values("date").reset_index(drop=True)

        if group["date"].duplicated().any():
            if DEBUG: print(f"[SKIP] grid {grid_id}: trùng lặp tháng")
            continue

        if len(group) != HISTORY_LENGTH:
            if DEBUG: print(f"[SKIP] grid {grid_id}: có {len(group)} tháng, cần {HISTORY_LENGTH}")
            continue

        if list(group["date"]) != expected_dates:
            if DEBUG: print(f"[SKIP] grid {grid_id}: chuỗi thời gian không liên tục")
            continue

        values = group["ndvi_mean"].to_numpy(dtype=np.float32)
        if not np.isfinite(values).all() or np.any(values < -1.0) or np.any(values > 1.0):
            if DEBUG: print(f"[SKIP] grid {grid_id}: giá trị NDVI không hợp lệ hoặc ngoài khoảng [-1, 1]")
            continue

        sequences.append(values.reshape(HISTORY_LENGTH, 1))
        valid_grid_ids.append(grid_id)

    if not sequences:
        return np.empty((0, HISTORY_LENGTH, 1), dtype=np.float32), []

    return np.stack(sequences, axis=0).astype(np.float32), valid_grid_ids


# =============================================================================
# 6 & 7. DEBUG INPUT / OUTPUT
# =============================================================================
def debug_tensor_info(name: str, arr: np.ndarray):
    """Hàm phụ trợ gom nhóm debug để code ngắn gọn hơn."""
    if arr.size == 0: return
    print(f"\n==================== ONNX {name} DEBUG ====================")
    print(f"Shape : {arr.shape}")
    print(f"Min   : {float(arr.min())}")
    print(f"Max   : {float(arr.max())}")
    print(f"Mean  : {float(arr.mean())}")
    print(f"Std   : {float(arr.std())}")
    print("=========================================================\n")


# =============================================================================
# 8. CHẠY ONNX INFERENCE
# =============================================================================
def run_onnx_inference_for_grid(year: int, month: int) -> pd.DataFrame:
    """Thực hiện toàn bộ quy trình: Load DB -> Kiểm tra chuỗi -> Chạy ONNX -> Trả về DataFrame kết quả."""
    from utils.data_loader import get_db_engine

    if not os.path.exists(MODEL_PATH):
        st.warning("⚠️ Không tìm thấy file ONNX. WebGIS đang dùng dữ liệu dự phòng.")
        return generate_fallback_grid_data(year, month)

    try:
        ort_session = ort.InferenceSession(MODEL_PATH)
        input_name = ort_session.get_inputs()[0].name

        if DEBUG:
            print(f"\n[INFO] Model: {MODEL_PATH} | Input: {input_name} | Shape: {ort_session.get_inputs()[0].shape}")

        engine = get_db_engine()
        target_date = pd.Timestamp(year=year, month=month, day=1)
        history_dates = create_history_dates(year, month, HISTORY_LENGTH)

        df_grids = load_base_grids(engine)
        if df_grids.empty:
            st.warning("⚠️ Không tìm thấy grid cơ sở trong database.")
            return generate_fallback_grid_data(year, month)

        df_history = load_history_data(engine, history_dates)
        if df_history.empty:
            st.warning("⚠️ Không tìm thấy dữ liệu 12 tháng lịch sử.")
            return pd.DataFrame()

        values_matrix, valid_grid_ids = build_valid_sequences(df_history, history_dates)
        if not valid_grid_ids:
            st.warning("⚠️ Không có grid nào đủ 12 tháng dữ liệu liên tục.")
            return pd.DataFrame()

        if DEBUG: debug_tensor_info("INPUT", values_matrix)

        # Chạy suy luận mô hình
        outputs = ort_session.run(None, {input_name: values_matrix})
        preds = outputs[0]

        if DEBUG: debug_tensor_info("OUTPUT", preds)

        preds_flat = np.asarray(preds, dtype=np.float32).reshape(-1)
        if len(preds_flat) != len(valid_grid_ids):
            raise ValueError(f"Số prediction ({len(preds_flat)}) không khớp số grid ({len(valid_grid_ids)})!")

        # Tổng hợp kết quả và tọa độ
        df_result = df_grids.merge(
            pd.DataFrame({"grid_id": valid_grid_ids, "ndvi_mean": preds_flat}),
            on="grid_id", how="inner"
        )

        # Làm sạch và định dạng giới hạn giá trị NDVI
        df_result["ndvi_mean"] = pd.to_numeric(df_result["ndvi_mean"], errors="coerce")
        df_result["longitude"] = pd.to_numeric(df_result["longitude"], errors="coerce")
        df_result["latitude"] = pd.to_numeric(df_result["latitude"], errors="coerce")
        
        df_result = df_result.dropna(subset=["grid_id", "longitude", "latitude", "ndvi_mean"])
        
        df_result["ndvi_mean"] = df_result["ndvi_mean"].clip(lower=-1.0, upper=1.0)
        df_result["ndvi_min"] = (df_result["ndvi_mean"] - 0.05).clip(lower=-1.0, upper=1.0)
        df_result["ndvi_max"] = (df_result["ndvi_mean"] + 0.05).clip(lower=-1.0, upper=1.0)

        df_result["date"] = target_date.strftime("%Y-%m-%d")
        df_result["year"] = year
        df_result["month"] = month

        return df_result.sort_values("grid_id").reset_index(drop=True)

    except Exception as e:
        print(f"\n[ONNX INFERENCE ERROR] {type(e).__name__}: {e}\n")
        st.error(f"⚠️ Lỗi khi chạy mô hình AI: {e}")
        return generate_fallback_grid_data(year, month)


# =============================================================================
# 9. HÀM GIẢ LẬP BIỂU ĐỒ CHUỖI THỜI GIAN
# =============================================================================
def generate_ndvi_predictions():
    """Chỉ dùng cho biểu đồ chuỗi thời gian demo."""
    np.random.seed(42)
    dates = pd.date_range(start="2017-01-01", end="2026-09-01", freq="MS")
    actual_ndvi = 0.5 + 0.2 * np.sin(np.linspace(0, 20, len(dates))) + np.random.normal(0, 0.03, len(dates))

    future_dates = pd.date_range(start="2026-09-01", end="2027-06-01", freq="MS")
    predicted_ndvi = 0.5 + 0.2 * np.sin(np.linspace(20, 22, len(future_dates)))

    return dates, actual_ndvi, future_dates, predicted_ndvi


# import os
# import onnxruntime as ort
# import numpy as np
# import pandas as pd
# import streamlit as st

# def generate_ndvi_predictions():
#     """Giả lập hoặc chạy mô hình AI (LSTM/GRU) dự báo NDVI cho biểu đồ chuỗi thời gian"""
#     np.random.seed(42)
#     dates = pd.date_range(start="2017-01-01", end="2026-09-01", freq="MS")
#     actual_ndvi = 0.5 + 0.2 * np.sin(np.linspace(0, 20, len(dates))) + np.random.normal(0, 0.03, len(dates))

#     future_dates = pd.date_range(start="2026-09-01", end="2027-06-01", freq="MS")
#     predicted_ndvi = 0.5 + 0.2 * np.sin(np.linspace(20, 22, len(future_dates)))
    
#     return dates, actual_ndvi, future_dates, predicted_ndvi

# def run_onnx_inference_for_grid(year: int, month: int) -> pd.DataFrame:
#     """
#     1. Lấy dữ liệu 12 tháng lịch sử của toàn bộ grid và gom thành mảng Batch.
#     2. Đảm bảo khớp chuẩn trật tự grid và thời gian.
#     3. Chạy suy luận ONNX theo dạng Batch chuẩn xác 100%.
#     """
#     from utils.data_loader import get_db_engine

#     model_path = "HCM-34-Json/lstm_ndvi_hcm_model.onnx"
    
#     if not os.path.exists(model_path):
#         return generate_fallback_grid_data(year, month)

#     try:
#         ort_session = ort.InferenceSession(model_path)
#         input_name = ort_session.get_inputs()[0].name
        
#         engine = get_db_engine()
        
#         # 1. Lấy danh sách các grid cơ sở và sắp xếp theo grid_id để đảm bảo đồng nhất thứ tự
#         base_grid_query = """
#             SELECT DISTINCT grid_id, longitude, latitude 
#             FROM public.ndvi_records 
#             WHERE year = 2020 AND month = 11
#             ORDER BY grid_id
#         """
#         df_grids = pd.read_sql(base_grid_query, engine)
        
#         if df_grids.empty:
#             return generate_fallback_grid_data(year, month)

#         # 2. Tính mốc thời gian 12 tháng ngược về trước
#         target_date = pd.Timestamp(year=year, month=month, day=1)
#         start_history_date = target_date - pd.DateOffset(months=12)
#         start_year, start_month = start_history_date.year, start_history_date.month

#         # Truy vấn lịch sử 12 tháng
#         history_query = f"""
#             SELECT grid_id, year, month, ndvi_mean 
#             FROM public.ndvi_records 
#             WHERE (year > {start_year} OR (year = {start_year} AND month >= {start_month}))
#               AND (year < {year} OR (year = {year} AND month < {month}))
#             ORDER BY grid_id, year, month
#         """
#         df_history = pd.read_sql(history_query, engine)

#         if df_history.empty:
#             st.warning("⚠️ Không tìm thấy dữ liệu lịch sử để dự báo!")
#             return pd.DataFrame()

#         # 3. Lọc chính xác các grid có ĐỦ đúng 12 tháng lịch sử
#         counts = df_history.groupby('grid_id').size()
#         valid_grids = counts[counts >= 12].index
        
#         if len(valid_grids) == 0:
#             st.warning("⚠️ Không có grid nào đủ 12 tháng lịch sử liên tục để chạy mô hình AI.")
#             return pd.DataFrame()

#         # Chỉ giữ lại lịch sử của các valid_grids và sắp xếp chuẩn trật tự
#         df_valid = df_history[df_history['grid_id'].isin(valid_grids)].sort_values(['grid_id', 'year', 'month'])
        
#         # Lọc danh sách grid khớp hoàn toàn với thứ tự của df_valid
#         df_grids_filtered = df_grids[df_grids['grid_id'].isin(valid_grids)].sort_values('grid_id').reset_index(drop=True)

#         # Đảm bảo shape đầu vào đúng chuẩn ma trận Batch [N, 12, 1]
#         values_matrix = df_valid['ndvi_mean'].values.reshape(-1, 12, 1).astype(np.float32)

#         # 🚀 Chạy ONNX Batch Inference
#         outputs = ort_session.run(None, {input_name: values_matrix})
#         preds = outputs[0]  # Shape: [Batch_Size, 1] hoặc [Batch_Size]
#         #st.info(f"📊 Debug ONNX Output -> Min: {preds.min():.4f} | Max: {preds.max():.4f} | Mean: {preds.mean():.4f}")
#         # 4. Xử lý kết quả trả về an toàn tuyệt đối
#         target_date_str = target_date.strftime("%Y-%m-%d")
#         predicted_rows = []

#         for i, row in df_grids_filtered.iterrows():
#             # Trích xuất giá trị an toàn từ mảng dự đoán bất kể shape thế nào
#             raw_p = preds[i]
#             pred_val = float(raw_p.item() if hasattr(raw_p, "item") else (raw_p[0] if len(raw_p) > 0 else raw_p))
            
#             # Chặn ngưỡng an toàn NDVI thực tế (tránh bị lệch màu hoặc tràn số)
#             val = max(min(pred_val, 0.85), 0.0)
            
#             predicted_rows.append({
#                 "grid_id": row["grid_id"],
#                 "date": target_date_str,
#                 "year": year,
#                 "month": month,
#                 "longitude": float(row["longitude"]),
#                 "latitude": float(row["latitude"]),
#                 "ndvi_mean": val,
#                 "ndvi_min": max(val - 0.05, 0.0),
#                 "ndvi_max": min(val + 0.05, 1.0)
#             })

#         df_result = pd.DataFrame(predicted_rows)
        
#         # 🛡️ Vệ sinh dữ liệu đầu ra: Ép kiểu số và loại bỏ NaN để chống lỗi lệch góc bản đồ
#         df_result['longitude'] = pd.to_numeric(df_result['longitude'], errors='coerce')
#         df_result['latitude'] = pd.to_numeric(df_result['latitude'], errors='coerce')
#         df_result = df_result.dropna(subset=['longitude', 'latitude', 'ndvi_mean'])

#         return df_result

#     except Exception as e:
#         print(f"⚠️ Lỗi chạy mô hình ONNX: {e}")
#         return generate_fallback_grid_data(year, month)

# def generate_fallback_grid_data(year, month):
#     """Hàm dự phòng tạo lưới tọa độ giả lập khi không tìm thấy model .onnx"""
#     from utils.data_loader import get_db_engine
    
#     engine = get_db_engine()
#     try:
#         df_grids = pd.read_sql("SELECT DISTINCT grid_id, longitude, latitude FROM public.ndvi_records LIMIT 1000", engine)
#         if df_grids.empty:
#             return pd.DataFrame()
            
#         df_grids['date'] = f"{year}-{month:02d}-01"
#         df_grids['year'] = year
#         df_grids['month'] = month
#         df_grids['ndvi_mean'] = np.random.uniform(0.3, 0.7, len(df_grids))
#         df_grids['ndvi_min'] = df_grids['ndvi_mean'] - 0.1
#         df_grids['ndvi_max'] = df_grids['ndvi_mean'] + 0.1
        
#         # 🛡️ Ép kiểu và làm sạch tọa độ chống lỗi lệch góc
#         df_grids['longitude'] = pd.to_numeric(df_grids['longitude'], errors='coerce')
#         df_grids['latitude'] = pd.to_numeric(df_grids['latitude'], errors='coerce')
#         df_grids = df_grids.dropna(subset=['longitude', 'latitude', 'ndvi_mean'])
        
#         return df_grids
#     except:
#         return pd.DataFrame()
