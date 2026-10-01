# =============================================================================
# utils/ai_engine.py
# AI ENGINE - DỰ BÁO NDVI CHO WEBGIS HCM-34
# =============================================================================

import os
import numpy as np
import pandas as pd
import onnxruntime as ort

from utils.data_loader import get_db_engine


# =============================================================================
# 1. FALLBACK DATA
# =============================================================================

def generate_fallback_grid_data(year: int, month: int):
    """
    Tạo dữ liệu giả trong trường hợp không thể chạy model AI.

    Lưu ý:
    Đây chỉ là fallback để WebGIS không bị crash.
    Không dùng dữ liệu này cho kết quả nghiên cứu chính thức.
    """

    engine = get_db_engine()

    query = """
        SELECT DISTINCT
            grid_id,
            longitude,
            latitude
        FROM public.ndvi_records
        WHERE longitude IS NOT NULL
          AND latitude IS NOT NULL
        ORDER BY grid_id
        LIMIT 1000
    """

    df_grids = pd.read_sql(query, engine)

    if df_grids.empty:
        return pd.DataFrame(
            columns=[
                "grid_id",
                "longitude",
                "latitude",
                "year",
                "month",
                "ndvi_mean",
                "ndvi_min",
                "ndvi_max",
            ]
        )

    # Giá trị giả chỉ để WebGIS vẫn hiển thị được
    rng = np.random.default_rng(42)

    ndvi_values = rng.uniform(
        0.30,
        0.70,
        len(df_grids)
    )

    result = pd.DataFrame({
        "grid_id": df_grids["grid_id"].values,
        "longitude": df_grids["longitude"].astype(float).values,
        "latitude": df_grids["latitude"].astype(float).values,
        "year": year,
        "month": month,
        "ndvi_mean": ndvi_values,
    })

    result["ndvi_min"] = np.clip(
        result["ndvi_mean"] - 0.05,
        0,
        1
    )

    result["ndvi_max"] = np.clip(
        result["ndvi_mean"] + 0.05,
        0,
        1
    )

    return result


# =============================================================================
# 2. LẤY GRID
# =============================================================================

def load_base_grid(engine):
    """
    Lấy danh sách toàn bộ grid_id và tọa độ.

    Mỗi grid_id phải có một longitude/latitude cố định.
    """

    query = """
        SELECT
            grid_id,
            AVG(longitude) AS longitude,
            AVG(latitude) AS latitude
        FROM public.ndvi_records
        WHERE longitude IS NOT NULL
          AND latitude IS NOT NULL
        GROUP BY grid_id
        ORDER BY grid_id
    """

    df = pd.read_sql(query, engine)

    if df.empty:
        return df

    df["grid_id"] = df["grid_id"]
    df["longitude"] = pd.to_numeric(
        df["longitude"],
        errors="coerce"
    )
    df["latitude"] = pd.to_numeric(
        df["latitude"],
        errors="coerce"
    )

    df = df.dropna(
        subset=[
            "grid_id",
            "longitude",
            "latitude"
        ]
    )

    df = df.drop_duplicates(
        subset=["grid_id"]
    )

    return df.reset_index(drop=True)


# =============================================================================
# 3. LẤY 12 THÁNG LỊCH SỬ
# =============================================================================

def load_history_for_grids(
    engine,
    grid_ids,
    target_year: int,
    target_month: int
):
    """
    Lấy đúng 12 tháng trước thời điểm cần dự báo.

    Ví dụ:

    target = 2026-09

    input:

    2025-09
    2025-10
    ...
    2026-07
    2026-08

    Tổng cộng đúng 12 tháng.
    """

    target_date = pd.Timestamp(
        year=target_year,
        month=target_month,
        day=1
    )

    # 12 tháng trước target
    history_start = target_date - pd.DateOffset(months=12)

    # Tháng ngay trước target
    history_end = target_date - pd.DateOffset(months=1)

    start_year = history_start.year
    start_month = history_start.month

    end_year = history_end.year
    end_month = history_end.month

    if len(grid_ids) == 0:
        return pd.DataFrame()

    # Chuyển grid_id thành tuple để dùng IN (...)
    grid_ids_tuple = tuple(grid_ids)

    if len(grid_ids_tuple) == 1:
        grid_condition = f"= {repr(grid_ids_tuple[0])}"
    else:
        grid_condition = f"IN {grid_ids_tuple}"

    query = f"""
        SELECT
            grid_id,
            year,
            month,
            AVG(ndvi_mean) AS ndvi_mean
        FROM public.ndvi_records
        WHERE grid_id {grid_condition}

          AND ndvi_mean IS NOT NULL

          AND (
                year > {start_year}
                OR (
                    year = {start_year}
                    AND month >= {start_month}
                )
          )

          AND (
                year < {end_year}
                OR (
                    year = {end_year}
                    AND month <= {end_month}
                )
          )

        GROUP BY
            grid_id,
            year,
            month

        ORDER BY
            grid_id,
            year,
            month
    """

    df = pd.read_sql(query, engine)

    if df.empty:
        return df

    df["year"] = pd.to_numeric(
        df["year"],
        errors="coerce"
    )

    df["month"] = pd.to_numeric(
        df["month"],
        errors="coerce"
    )

    df["ndvi_mean"] = pd.to_numeric(
        df["ndvi_mean"],
        errors="coerce"
    )

    df = df.dropna(
        subset=[
            "grid_id",
            "year",
            "month",
            "ndvi_mean"
        ]
    )

    # Tạo cột date chuẩn để không bị nhầm thứ tự tháng
    df["date"] = pd.to_datetime(
        dict(
            year=df["year"].astype(int),
            month=df["month"].astype(int),
            day=1
        )
    )

    return df


# =============================================================================
# 4. TẠO MA TRẬN 12 THÁNG CHO TỪNG GRID
# =============================================================================

def build_sequences(
    df_history,
    df_grids,
    target_year: int,
    target_month: int
):
    """
    Đây là phần quan trọng nhất.

    Không dùng:

        values.reshape(-1, 12, 1)

    nữa.

    Thay vào đó:

        grid A -> đúng 12 tháng
        grid B -> đúng 12 tháng
        grid C -> đúng 12 tháng

    Sau đó mới đưa vào LSTM/GRU.
    """

    if df_history.empty:
        return None, None

    target_date = pd.Timestamp(
        year=target_year,
        month=target_month,
        day=1
    )

    # Chính xác 12 mốc thời gian cần cho model
    expected_dates = pd.date_range(
        start=target_date - pd.DateOffset(months=12),
        end=target_date - pd.DateOffset(months=1),
        freq="MS"
    )

    # Phải đúng 12 tháng
    if len(expected_dates) != 12:
        raise ValueError(
            f"Không tạo được đúng 12 tháng lịch sử: "
            f"{len(expected_dates)} tháng."
        )

    # -------------------------------------------------------------------------
    # Pivot:
    #
    # index  = grid_id
    # columns = tháng
    # values = NDVI
    #
    # Ví dụ:
    #
    # grid_id | 2025-09 | 2025-10 | ... | 2026-08
    # ------------------------------------------------
    # 10001   | 0.42    | 0.45    | ... | 0.51
    # 10002   | 0.31    | 0.34    | ... | 0.39
    # -------------------------------------------------------------------------

    pivot = df_history.pivot_table(
        index="grid_id",
        columns="date",
        values="ndvi_mean",
        aggfunc="mean"
    )

    # Ép thứ tự cột thành đúng 12 tháng
    pivot = pivot.reindex(
        columns=expected_dates
    )

    # Chỉ giữ grid có ĐỦ 12 tháng
    pivot = pivot.dropna(
        axis=0,
        how="any"
    )

    if pivot.empty:
        return None, None

    # -------------------------------------------------------------------------
    # Đảm bảo grid tồn tại trong bảng tọa độ
    # -------------------------------------------------------------------------

    valid_grid_ids = pivot.index

    coords = (
        df_grids[
            df_grids["grid_id"].isin(valid_grid_ids)
        ]
        .set_index("grid_id")
        .loc[valid_grid_ids]
        .reset_index()
    )

    # Nếu số grid không khớp thì dừng ngay
    if len(coords) != len(pivot):
        raise ValueError(
            "Số grid và số chuỗi NDVI không khớp."
        )

    # -------------------------------------------------------------------------
    # Chuyển thành input cho LSTM/GRU
    #
    # Shape:
    #
    # [số_grid, 12, 1]
    #
    # Ví dụ:
    #
    # [25000, 12, 1]
    # -------------------------------------------------------------------------

    X = pivot.to_numpy(
        dtype=np.float32
    )

    X = X[:, :, np.newaxis]

    return X, coords


# =============================================================================
# 5. CHẠY ONNX
# =============================================================================

def run_onnx_inference_for_grid(
    year: int,
    month: int,
    sample_step: int = 1,
    batch_size: int = 2048
):
    """
    Chạy model ONNX để dự báo NDVI cho toàn bộ grid.

    sample_step=1:
        dự đoán toàn bộ grid.

    batch_size=2048:
        tránh đưa toàn bộ 25k-28k grid vào ONNX một lần.
    """

    model_path = "HCM-34-Json/lstm_ndvi_hcm_model.onnx"

    # =========================================================================
    # MODEL KHÔNG TỒN TẠI
    # =========================================================================

    if not os.path.exists(model_path):

        print(
            f"[AI] Không tìm thấy model: {model_path}"
        )

        return generate_fallback_grid_data(
            year,
            month
        )

    try:

        print("=" * 70)
        print("[AI] BẮT ĐẦU DỰ BÁO NDVI")
        print("=" * 70)

        print(
            f"[AI] Target: {year}-{month:02d}"
        )

        # =====================================================================
        # 1. LOAD MODEL
        # =====================================================================

        ort_session = ort.InferenceSession(
            model_path,
            providers=["CPUExecutionProvider"]
        )

        input_info = ort_session.get_inputs()[0]
        output_info = ort_session.get_outputs()[0]

        input_name = input_info.name
        output_name = output_info.name

        print(
            f"[AI] Input name : {input_name}"
        )

        print(
            f"[AI] Input shape: {input_info.shape}"
        )

        print(
            f"[AI] Output name : {output_name}"
        )

        print(
            f"[AI] Output shape: {output_info.shape}"
        )

        # =====================================================================
        # 2. DATABASE
        # =====================================================================

        engine = get_db_engine()

        # =====================================================================
        # 3. LẤY TOÀN BỘ GRID
        # =====================================================================

        df_grids = load_base_grid(engine)

        if df_grids.empty:

            print(
                "[AI] Không tìm thấy grid."
            )

            return generate_fallback_grid_data(
                year,
                month
            )

        print(
            f"[AI] Tổng số grid: {len(df_grids):,}"
        )

        # =====================================================================
        # 4. SAMPLE
        # =====================================================================

        if sample_step > 1:

            df_grids = (
                df_grids
                .iloc[::sample_step]
                .reset_index(drop=True)
            )

        print(
            f"[AI] Grid đưa vào AI: {len(df_grids):,}"
        )

        grid_ids = df_grids["grid_id"].tolist()

        # =====================================================================
        # 5. LẤY 12 THÁNG LỊCH SỬ
        # =====================================================================

        df_history = load_history_for_grids(
            engine=engine,
            grid_ids=grid_ids,
            target_year=year,
            target_month=month
        )

        if df_history.empty:

            print(
                "[AI] Không có dữ liệu lịch sử."
            )

            return generate_fallback_grid_data(
                year,
                month
            )

        print(
            f"[AI] Số dòng history: "
            f"{len(df_history):,}"
        )

        # =====================================================================
        # 6. BUILD SEQUENCE
        # =====================================================================

        X, coords = build_sequences(
            df_history=df_history,
            df_grids=df_grids,
            target_year=year,
            target_month=month
        )

        if X is None or coords is None:

            print(
                "[AI] Không tạo được sequence 12 tháng."
            )

            return generate_fallback_grid_data(
                year,
                month
            )

        print(
            f"[AI] X shape: {X.shape}"
        )

        print(
            f"[AI] Grid hợp lệ: {len(coords):,}"
        )

        # =====================================================================
        # 7. KIỂM TRA INPUT
        # =====================================================================

        if X.ndim != 3:

            raise ValueError(
                f"Input AI phải có 3 chiều "
                f"[samples, 12, 1], nhưng nhận {X.shape}"
            )

        if X.shape[1] != 12:

            raise ValueError(
                f"Model cần 12 tháng nhưng nhận "
                f"{X.shape[1]} tháng."
            )

        # Kiểm tra NaN / Inf
        if not np.isfinite(X).all():

            raise ValueError(
                "Input AI chứa NaN hoặc Inf."
            )

        # =====================================================================
        # 8. CHẠY ONNX THEO BATCH
        # =====================================================================

        predictions = []

        total = len(X)

        for start in range(
            0,
            total,
            batch_size
        ):

            end = min(
                start + batch_size,
                total
            )

            X_batch = X[start:end]

            y_batch = ort_session.run(
                [output_name],
                {
                    input_name: X_batch
                }
            )[0]

            y_batch = np.asarray(
                y_batch
            ).reshape(-1)

            predictions.append(
                y_batch
            )

            print(
                f"[AI] Predict: "
                f"{end:,}/{total:,}"
            )

        raw_preds = np.concatenate(
            predictions
        )

        # =====================================================================
        # 9. KIỂM TRA OUTPUT
        # =====================================================================

        if len(raw_preds) != len(coords):

            raise ValueError(
                "Số prediction không bằng số grid!"
                f"\nPrediction: {len(raw_preds)}"
                f"\nGrid: {len(coords)}"
            )

        print(
            "[AI] Raw prediction:"
        )

        print(
            f"      min  = {np.nanmin(raw_preds):.6f}"
        )

        print(
            f"      max  = {np.nanmax(raw_preds):.6f}"
        )

        print(
            f"      mean = {np.nanmean(raw_preds):.6f}"
        )

        print(
            f"      std  = {np.nanstd(raw_preds):.6f}"
        )

        # =====================================================================
        # 10. KHÔNG PERCENTILE SCALE
        # =====================================================================
        #
        # QUAN TRỌNG:
        #
        # Không còn:
        #
        # np.percentile()
        # target_ndvi_min
        # target_ndvi_max
        #
        # Vì chúng làm thay đổi phân bố prediction.
        #
        # ---------------------------------------------------------------------
        #
        # Tạm thời giả định output ONNX đã là NDVI.
        #
        # Nếu model của bạn được train với MinMaxScaler thì phần này cần
        # inverse_transform bằng ĐÚNG scaler lúc train.
        # =====================================================================

        preds = raw_preds.astype(
            np.float32
        )

        # Giới hạn NDVI về khoảng hợp lệ
        preds = np.clip(
            preds,
            -1.0,
            1.0
        )

        # =====================================================================
        # 11. TẠO DATAFRAME KẾT QUẢ
        # =====================================================================

        result = coords.copy()

        result["year"] = int(year)

        result["month"] = int(month)

        result["ndvi_mean"] = preds

        result["ndvi_min"] = np.clip(
            result["ndvi_mean"] - 0.05,
            -1.0,
            1.0
        )

        result["ndvi_max"] = np.clip(
            result["ndvi_mean"] + 0.05,
            -1.0,
            1.0
        )

        # =====================================================================
        # 12. KIỂM TRA KẾT QUẢ
        # =====================================================================

        print(
            "[AI] Final prediction:"
        )

        print(
            f"      rows = {len(result):,}"
        )

        print(
            f"      min  = "
            f"{result['ndvi_mean'].min():.6f}"
        )

        print(
            f"      max  = "
            f"{result['ndvi_mean'].max():.6f}"
        )

        print(
            f"      mean = "
            f"{result['ndvi_mean'].mean():.6f}"
        )

        print(
            "=" * 70
        )

        return result.reset_index(
            drop=True
        )

    except Exception as e:

        print("=" * 70)
        print("[AI ERROR]")
        print(str(e))
        print("=" * 70)

        return generate_fallback_grid_data(
            year,
            month
        )

# import os
# import numpy as np
# import onnxruntime as ort
# import pandas as pd
# import streamlit as st


# def generate_ndvi_predictions():
#   """Giả lập hoặc chạy mô hình AI (LSTM/GRU) dự báo NDVI cho biểu đồ chuỗi thời gian 📈"""
#   np.random.seed(42)
#   dates = pd.date_range(start="2017-01-01", end="2026-09-01", freq="MS")
#   actual_ndvi = (
#       0.5
#       + 0.2 * np.sin(np.linspace(0, 20, len(dates)))
#       + np.random.normal(0, 0.03, len(dates))
#   )

#   future_dates = pd.date_range(start="2026-09-01", end="2027-06-01", freq="MS")
#   predicted_ndvi = 0.5 + 0.2 * np.sin(np.linspace(20, 22, len(future_dates)))

#   return dates, actual_ndvi, future_dates, predicted_ndvi


# def run_onnx_inference_for_grid(
#     year: int, month: int, sample_step: int = 12
# ) -> pd.DataFrame:
#   """1. Lấy danh sách toàn bộ ô lưới và LẤY MẪU RẢI RÁC (Spatial Sampling) theo sample_step 🎯.

#   2. Truy vấn 12 tháng lịch sử CHỈ cho các ô đại diện ⚡. 3. Chạy suy luận ONNX
#   theo dạng Batch 🧠. 4. Chuẩn hóa & Giãn dải NDVI (Min-Max Scaling) chống phai
#   màu / da cam toàn bản đồ 🎨.
#   """
#   from utils.data_loader import get_db_engine

#   model_path = "HCM-34-Json/lstm_ndvi_hcm_model.onnx"

#   if not os.path.exists(model_path):
#     return generate_fallback_grid_data(year, month)

#   try:
#     ort_session = ort.InferenceSession(model_path)
#     input_name = ort_session.get_inputs()[0].name

#     engine = get_db_engine()

#     # 1. Lấy toàn bộ danh sách grid cơ sở 🗄️
#     base_grid_query = """
#             SELECT DISTINCT grid_id, longitude, latitude 
#             FROM public.ndvi_records 
#             WHERE year = 2020 AND month = 11
#             ORDER BY grid_id
#         """
#     df_grids_all = pd.read_sql(base_grid_query, engine)

#     if df_grids_all.empty:
#       return generate_fallback_grid_data(year, month)

#     # 🎯 2. LẤY MẪU RẢI RÁC (~1.800 - 2.000 ô đại diện)
#     df_grids = df_grids_all.iloc[::sample_step].reset_index(drop=True)
#     sampled_grid_ids = tuple(df_grids["grid_id"].tolist())

#     if not sampled_grid_ids:
#       return pd.DataFrame()

#     # 3. Tính mốc 12 tháng lịch sử 📅
#     target_date = pd.Timestamp(year=year, month=month, day=1)
#     start_history_date = target_date - pd.DateOffset(months=12)
#     start_year, start_month = (
#         start_history_date.year,
#         start_history_date.month,
#     )

#     # 4. Truy vấn lịch sử 🚀
#     grid_filter_str = (
#         f"= {sampled_grid_ids[0]}"
#         if len(sampled_grid_ids) == 1
#         else f"IN {sampled_grid_ids}"
#     )

#     history_query = f"""
#             SELECT grid_id, year, month, ndvi_mean 
#             FROM public.ndvi_records 
#             WHERE grid_id {grid_filter_str}
#               AND ((year > {start_year} OR (year = {start_year} AND month >= {start_month}))
#               AND (year < {year} OR (year = {year} AND month < {month})))
#             ORDER BY grid_id, year, month
#         """
#     df_history = pd.read_sql(history_query, engine)

#     if df_history.empty:
#       st.warning("⚠️ Không tìm thấy dữ liệu lịch sử cho các ô đại diện!")
#       return pd.DataFrame()

#     # 5. Lọc grid đủ 12 tháng lịch sử 🔍
#     counts = df_history.groupby("grid_id").size()
#     valid_grids = counts[counts >= 12].index

#     if len(valid_grids) == 0:
#       st.warning(
#           "⚠️ Không có ô đại diện nào đủ 12 tháng lịch sử liên tục để chạy AI."
#       )
#       return pd.DataFrame()

#     df_valid = df_history[df_history["grid_id"].isin(valid_grids)].sort_values(
#         ["grid_id", "year", "month"]
#     )
#     df_grids_filtered = (
#         df_grids[df_grids["grid_id"].isin(valid_grids)]
#         .sort_values("grid_id")
#         .reset_index(drop=True)
#     )

#     # Ma trận Batch [N, 12, 1]
#     values_matrix = (
#         df_valid["ndvi_mean"].values.reshape(-1, 12, 1).astype(np.float32)
#     )

#     # 🚀 6. Chạy ONNX Batch Inference
#     outputs = ort_session.run(None, {input_name: values_matrix})
#     raw_preds = outputs[0].flatten()  # Mảng 1D chứa toàn bộ kết quả dự đoán

#     # 🪄 7. BỘ GIÃN DẢI MÀU TỰ ĐỘNG THEO PERCENTILE & STD (PHỤC HỒI TƯƠNG PHẢN ĐỘ THỊ - RỪNG) 🎨
#     # Lấy bách phân vị 2% và 98% để loại bỏ nhiễu Outlier min/max
#     q_low, q_high = np.percentile(raw_preds, 2), np.percentile(raw_preds, 98)
#     std_val = raw_preds.std()

#     # Nếu độ lệch chuẩn hẹp (std < 0.10) hoặc dải giá trị IQR bị nén (< 0.25)
#     if std_val < 0.10 or (q_high - q_low) < 0.25:
#         # Min-Max Scaling đưa dải bị nén về dải NDVI chuẩn tương phản của TP.HCM [0.10, 0.65]
#         target_ndvi_min, target_ndvi_max = 0.10, 0.65
#         scaled_preds = target_ndvi_min + (raw_preds - q_low) * (
#             target_ndvi_max - target_ndvi_min
#         ) / (q_high - q_low + 1e-6)
#         scaled_preds = np.clip(scaled_preds, 0.05, 0.75)
#     else:
#         scaled_preds = np.clip(raw_preds, 0.05, 0.85)
#     # 8. Đóng gói kết quả 📦
#     target_date_str = target_date.strftime("%Y-%m-%d")
#     predicted_rows = []

#     for i, row in df_grids_filtered.iterrows():
#       val = float(scaled_preds[i])

#       predicted_rows.append({
#           "grid_id": row["grid_id"],
#           "date": target_date_str,
#           "year": year,
#           "month": month,
#           "longitude": float(row["longitude"]),
#           "latitude": float(row["latitude"]),
#           "ndvi_mean": val,
#           "ndvi_min": max(val - 0.05, 0.0),
#           "ndvi_max": min(val + 0.05, 1.0),
#       })

#     df_result = pd.DataFrame(predicted_rows)

#     # 🛡️ Vệ sinh dữ liệu đầu ra
#     df_result["longitude"] = pd.to_numeric(
#         df_result["longitude"], errors="coerce"
#     )
#     df_result["latitude"] = pd.to_numeric(
#         df_result["latitude"], errors="coerce"
#     )
#     df_result = df_result.dropna(subset=["longitude", "latitude", "ndvi_mean"])

#     return df_result

#   except Exception as e:
#     print(f"⚠️ Lỗi chạy mô hình ONNX: {e}")
#     return generate_fallback_grid_data(year, month)


# def generate_fallback_grid_data(year, month):
#   """Hàm dự phòng tạo lưới tọa độ giả lập khi không tìm thấy model .onnx 🛠️"""
#   from utils.data_loader import get_db_engine

#   engine = get_db_engine()
#   try:
#     df_grids = pd.read_sql(
#         "SELECT DISTINCT grid_id, longitude, latitude FROM public.ndvi_records"
#         " LIMIT 1000",
#         engine,
#     )
#     if df_grids.empty:
#       return pd.DataFrame()

#     df_grids["date"] = f"{year}-{month:02d}-01"
#     df_grids["year"] = year
#     df_grids["month"] = month
#     df_grids["ndvi_mean"] = np.random.uniform(0.3, 0.7, len(df_grids))
#     df_grids["ndvi_min"] = df_grids["ndvi_mean"] - 0.1
#     df_grids["ndvi_max"] = df_grids["ndvi_mean"] + 0.1

#     df_grids["longitude"] = pd.to_numeric(
#         df_grids["longitude"], errors="coerce"
#     )
#     df_grids["latitude"] = pd.to_numeric(df_grids["latitude"], errors="coerce")
#     df_grids = df_grids.dropna(subset=["longitude", "latitude", "ndvi_mean"])

#     return df_grids
#   except:
#     return pd.DataFrame()
