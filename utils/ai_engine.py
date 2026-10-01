# =============================================================================
# utils/ai_engine.py
# GEO-NDVI INTELLIGENCE PLATFORM
# AI Engine - ONNX NDVI Spatial Prediction
# =============================================================================

import os
import numpy as np
import pandas as pd
import onnxruntime as ort
import streamlit as st


# =============================================================================
# 1. CẤU HÌNH
# =============================================================================

MODEL_PATH = "HCM-34-Json/lstm_ndvi_hcm_model.onnx"

HISTORY_MONTHS = 12

# Số ô lấy mẫu theo không gian.
# 1 = chạy toàn bộ grid.
# 4 = lấy 1/4 số grid.
#
# Khuyến nghị:
# - Nếu model + máy chủ đủ mạnh: 1
# - Nếu Streamlit Cloud yếu: 2 hoặc 4
#
# Không nên dùng 12 như code cũ vì sẽ quá thưa.
SPATIAL_SAMPLE_STEP = 2

# Giá trị NDVI hợp lệ
NDVI_MIN = -1.0
NDVI_MAX = 1.0


# =============================================================================
# 2. HÀM KIỂM TRA MODEL
# =============================================================================

def _load_onnx_model():
    """
    Load model ONNX.

    Trả về:
        ort_session, input_name

    hoặc:
        None, None nếu model không tồn tại.
    """

    if not os.path.exists(MODEL_PATH):
        print(f"[AI] Không tìm thấy model: {MODEL_PATH}")
        return None, None

    try:
        session = ort.InferenceSession(
            MODEL_PATH,
            providers=["CPUExecutionProvider"]
        )

        input_name = session.get_inputs()[0].name

        print("[AI] ONNX model loaded successfully.")
        print(f"[AI] Input name: {input_name}")

        return session, input_name

    except Exception as e:
        print(f"[AI] Không thể load ONNX model: {e}")
        return None, None


# =============================================================================
# 3. KIỂM TRA INPUT MODEL
# =============================================================================

def _inspect_model(session):
    """
    In thông tin input/output của model để debug.
    """

    try:
        input_info = session.get_inputs()[0]
        output_info = session.get_outputs()[0]

        print("========== ONNX MODEL ==========")
        print("Input name :", input_info.name)
        print("Input shape:", input_info.shape)
        print("Input type :", input_info.type)

        print("Output name :", output_info.name)
        print("Output shape:", output_info.shape)
        print("Output type :", output_info.type)

        print("================================")

    except Exception as e:
        print(f"[AI] Không thể inspect model: {e}")


# =============================================================================
# 4. CHUẨN HÓA OUTPUT AI
# =============================================================================

def _clean_prediction_values(values):
    """
    Làm sạch kết quả dự đoán.

    QUAN TRỌNG:
    Không Min-Max stretch toàn bộ bản đồ.

    Vì nếu stretch:
        vùng NDVI 0.35 -> có thể thành 0.65
        vùng NDVI 0.45 -> có thể thành 0.75

    dẫn tới màu bản đồ không còn phản ánh đúng output model.
    """

    values = np.asarray(values, dtype=np.float32).reshape(-1)

    values = np.nan_to_num(
        values,
        nan=0.0,
        posinf=1.0,
        neginf=-1.0
    )

    values = np.clip(
        values,
        NDVI_MIN,
        NDVI_MAX
    )

    return values


# =============================================================================
# 5. LẤY GRID
# =============================================================================

def _load_base_grid(engine):
    """
    Lấy danh sách grid + tọa độ.

    QUAN TRỌNG:
    grid_id là khóa không gian.

    Không được để kết quả AI bị ghép theo index.
    """

    query = """
        SELECT DISTINCT
            grid_id,
            longitude,
            latitude
        FROM public.ndvi_records
        WHERE longitude IS NOT NULL
          AND latitude IS NOT NULL
        ORDER BY grid_id
    """

    df = pd.read_sql(query, engine)

    if df.empty:
        return pd.DataFrame()

    df["grid_id"] = pd.to_numeric(
        df["grid_id"],
        errors="coerce"
    )

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
# 6. CHỌN GRID THEO KHÔNG GIAN
# =============================================================================

def _sample_grid(df_grid, sample_step):
    """
    Lấy mẫu grid.

    Lưu ý:
    Đây chỉ là bước giảm tải.

    grid_id vẫn được giữ nguyên để kết quả AI quay về đúng tọa độ.
    """

    if df_grid.empty:
        return df_grid

    if sample_step <= 1:
        return df_grid.copy()

    sampled = df_grid.iloc[::sample_step].copy()

    return sampled.reset_index(drop=True)


# =============================================================================
# 7. LẤY CHUỖI 12 THÁNG
# =============================================================================

def _load_history(
    engine,
    grid_ids,
    target_year,
    target_month
):
    """
    Lấy đúng 12 tháng lịch sử cho từng grid.

    Đây là phần QUAN TRỌNG NHẤT của file.

    Mỗi grid_id sẽ có một chuỗi:

        grid A
        2025-10
        2025-11
        ...
        2026-09

    Sau đó mới đưa vào model.
    """

    if not grid_ids:
        return pd.DataFrame()

    # -------------------------------------------------------------------------
    # Tạo danh sách ID an toàn
    # -------------------------------------------------------------------------

    grid_ids = [
        int(x)
        for x in grid_ids
        if pd.notna(x)
    ]

    if not grid_ids:
        return pd.DataFrame()

    ids_sql = ",".join(
        str(x)
        for x in grid_ids
    )

    target_date = pd.Timestamp(
        year=int(target_year),
        month=int(target_month),
        day=1
    )

    # 12 tháng trước tháng dự đoán
    history_end = target_date - pd.DateOffset(months=1)
    history_start = target_date - pd.DateOffset(
        months=HISTORY_MONTHS
    )

    query = f"""
        SELECT
            grid_id,
            year,
            month,
            ndvi_mean
        FROM public.ndvi_records
        WHERE grid_id IN ({ids_sql})
          AND MAKE_DATE(year, month, 1)
              BETWEEN '{history_start.strftime("%Y-%m-%d")}'
              AND '{history_end.strftime("%Y-%m-%d")}'
        ORDER BY
            grid_id,
            year,
            month
    """

    df = pd.read_sql(query, engine)

    if df.empty:
        return pd.DataFrame()

    # -------------------------------------------------------------------------
    # Chuẩn hóa kiểu dữ liệu
    # -------------------------------------------------------------------------

    df["grid_id"] = pd.to_numeric(
        df["grid_id"],
        errors="coerce"
    )

    df["year"] = pd.to_numeric(
        df["year"],
        errors="coerce"
    ).astype("Int64")

    df["month"] = pd.to_numeric(
        df["month"],
        errors="coerce"
    ).astype("Int64")

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

    # -------------------------------------------------------------------------
    # Loại NDVI ngoài khoảng
    # -------------------------------------------------------------------------

    df["ndvi_mean"] = np.clip(
        df["ndvi_mean"].astype(float),
        NDVI_MIN,
        NDVI_MAX
    )

    # -------------------------------------------------------------------------
    # Loại duplicate
    # -------------------------------------------------------------------------

    df = (
        df
        .sort_values(
            [
                "grid_id",
                "year",
                "month"
            ]
        )
        .drop_duplicates(
            subset=[
                "grid_id",
                "year",
                "month"
            ],
            keep="last"
        )
        .reset_index(drop=True)
    )

    return df


# =============================================================================
# 8. TẠO INPUT BATCH CHO MODEL
# =============================================================================

def _build_model_input(
    df_history,
    valid_grid_ids
):
    """
    Tạo ma trận:

        [N, 12, 1]

    với N = số grid hợp lệ.

    QUAN TRỌNG:
    Trả thêm grid_ids theo đúng thứ tự batch.

    Ví dụ:

        batch[0] -> grid 1001
        batch[1] -> grid 1005
        batch[2] -> grid 1012

    Sau inference:

        prediction[0] -> grid 1001
        prediction[1] -> grid 1005
        prediction[2] -> grid 1012
    """

    sequences = []
    ordered_grid_ids = []

    expected_months = HISTORY_MONTHS

    for grid_id in valid_grid_ids:

        grid_df = df_history[
            df_history["grid_id"] == grid_id
        ].copy()

        grid_df = grid_df.sort_values(
            ["year", "month"]
        )

        # -------------------------------------------------------------
        # Kiểm tra đúng số tháng
        # -------------------------------------------------------------

        if len(grid_df) != expected_months:
            continue

        # -------------------------------------------------------------
        # Kiểm tra tháng có liên tục không
        # -------------------------------------------------------------

        dates = pd.to_datetime(
            dict(
                year=grid_df["year"].astype(int),
                month=grid_df["month"].astype(int),
                day=1
            )
        )

        dates = dates.sort_values()

        expected_dates = pd.date_range(
            start=dates.iloc[0],
            periods=expected_months,
            freq="MS"
        )

        if not dates.reset_index(drop=True).equals(
            expected_dates.to_series().reset_index(drop=True)
        ):
            continue

        # -------------------------------------------------------------
        # Lấy NDVI
        # -------------------------------------------------------------

        values = (
            grid_df["ndvi_mean"]
            .astype(np.float32)
            .to_numpy()
        )

        if len(values) != HISTORY_MONTHS:
            continue

        if np.isnan(values).any():
            continue

        values = np.clip(
            values,
            NDVI_MIN,
            NDVI_MAX
        )

        # [12] -> [12, 1]
        sequence = values.reshape(
            HISTORY_MONTHS,
            1
        )

        sequences.append(sequence)

        # GIỮ NGUYÊN ID
        ordered_grid_ids.append(
            int(grid_id)
        )

    if not sequences:
        return (
            np.empty(
                (0, HISTORY_MONTHS, 1),
                dtype=np.float32
            ),
            []
        )

    X = np.stack(
        sequences,
        axis=0
    ).astype(np.float32)

    return X, ordered_grid_ids


# =============================================================================
# 9. CHẠY ONNX
# =============================================================================

def _run_onnx(
    session,
    input_name,
    X
):
    """
    Chạy inference.

    Input:
        [N, 12, 1]

    Output:
        [N]
    """

    if X is None or len(X) == 0:
        return np.array(
            [],
            dtype=np.float32
        )

    try:

        outputs = session.run(
            None,
            {
                input_name: X
            }
        )

        if not outputs:
            raise RuntimeError(
                "ONNX không trả về output."
            )

        predictions = outputs[0]

        predictions = np.asarray(
            predictions
        ).reshape(-1)

        if len(predictions) != len(X):
            raise RuntimeError(
                f"Số prediction ({len(predictions)}) "
                f"không khớp số input ({len(X)})."
            )

        predictions = _clean_prediction_values(
            predictions
        )

        return predictions

    except Exception as e:

        print(
            f"[AI] ONNX inference error: {e}"
        )

        raise


# =============================================================================
# 10. GHÉP PREDICTION VỚI GRID
# =============================================================================

def _build_prediction_dataframe(
    df_grid,
    ordered_grid_ids,
    predictions,
    year,
    month
):
    """
    Ghép prediction với tọa độ bằng grid_id.

    TUYỆT ĐỐI KHÔNG ghép bằng index của dataframe gốc.
    """

    if len(ordered_grid_ids) != len(predictions):

        raise RuntimeError(
            "Số grid_id và số prediction không bằng nhau."
        )

    prediction_df = pd.DataFrame(
        {
            "grid_id": ordered_grid_ids,
            "ndvi_mean": predictions
        }
    )

    # -------------------------------------------------------------------------
    # Ghép tọa độ bằng grid_id
    # -------------------------------------------------------------------------

    result = prediction_df.merge(
        df_grid[
            [
                "grid_id",
                "longitude",
                "latitude"
            ]
        ],
        on="grid_id",
        how="left",
        validate="one_to_one"
    )

    # -------------------------------------------------------------------------
    # Thông tin thời gian
    # -------------------------------------------------------------------------

    result["year"] = int(year)
    result["month"] = int(month)

    result["date"] = (
        pd.Timestamp(
            year=int(year),
            month=int(month),
            day=1
        )
        .strftime("%Y-%m-%d")
    )

    # -------------------------------------------------------------------------
    # Min / Max
    #
    # Đây chỉ là khoảng hiển thị phụ.
    # Không dùng để quyết định màu chính.
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # Chuẩn hóa tọa độ
    # -------------------------------------------------------------------------

    result["longitude"] = pd.to_numeric(
        result["longitude"],
        errors="coerce"
    )

    result["latitude"] = pd.to_numeric(
        result["latitude"],
        errors="coerce"
    )

    result["ndvi_mean"] = pd.to_numeric(
        result["ndvi_mean"],
        errors="coerce"
    )

    result = result.dropna(
        subset=[
            "longitude",
            "latitude",
            "ndvi_mean"
        ]
    )

    # -------------------------------------------------------------------------
    # Sắp xếp theo grid_id
    # -------------------------------------------------------------------------

    result = result.sort_values(
        "grid_id"
    ).reset_index(drop=True)

    return result


# =============================================================================
# 11. HÀM CHÍNH: RUN AI
# =============================================================================

def run_onnx_inference_for_grid(
    year: int,
    month: int,
    sample_step: int = SPATIAL_SAMPLE_STEP
) -> pd.DataFrame:

    from utils.data_loader import get_db_engine

    print(
        "\n"
        "==================================================\n"
        "           GEO-NDVI AI INFERENCE\n"
        "=================================================="
    )

    # =========================================================================
    # BƯỚC 1: LOAD MODEL
    # =========================================================================

    session, input_name = _load_onnx_model()

    if session is None:

        print(
            "[AI] Không có model ONNX -> fallback."
        )

        return generate_fallback_grid_data(
            year,
            month
        )

    _inspect_model(session)

    # =========================================================================
    # BƯỚC 2: DATABASE
    # =========================================================================

    try:

        engine = get_db_engine()

    except Exception as e:

        print(
            f"[AI] Không thể kết nối database: {e}"
        )

        return pd.DataFrame()

    # =========================================================================
    # BƯỚC 3: LOAD GRID
    # =========================================================================

    try:

        df_grid_all = _load_base_grid(
            engine
        )

    except Exception as e:

        print(
            f"[AI] Lỗi lấy grid: {e}"
        )

        return pd.DataFrame()

    if df_grid_all.empty:

        print(
            "[AI] Database không có grid."
        )

        return pd.DataFrame()

    print(
        f"[AI] Tổng số grid: "
        f"{len(df_grid_all):,}"
    )

    # =========================================================================
    # BƯỚC 4: SAMPLE GRID
    # =========================================================================

    df_grid_sampled = _sample_grid(
        df_grid_all,
        sample_step
    )

    print(
        f"[AI] Grid được đưa vào AI: "
        f"{len(df_grid_sampled):,}"
    )

    sampled_grid_ids = (
        df_grid_sampled["grid_id"]
        .astype(int)
        .tolist()
    )

    if not sampled_grid_ids:

        return pd.DataFrame()

    # =========================================================================
    # BƯỚC 5: LOAD 12 THÁNG LỊCH SỬ
    # =========================================================================

    try:

        df_history = _load_history(
            engine=engine,
            grid_ids=sampled_grid_ids,
            target_year=year,
            target_month=month
        )

    except Exception as e:

        print(
            f"[AI] Lỗi lấy lịch sử: {e}"
        )

        return pd.DataFrame()

    if df_history.empty:

        st.warning(
            "⚠️ Không tìm thấy dữ liệu "
            "12 tháng lịch sử cho AI."
        )

        return pd.DataFrame()

    # =========================================================================
    # BƯỚC 6: KIỂM TRA GRID ĐỦ 12 THÁNG
    # =========================================================================

    month_counts = (
        df_history
        .groupby("grid_id")
        .size()
    )

    valid_grid_ids = (
        month_counts[
            month_counts == HISTORY_MONTHS
        ]
        .index
        .astype(int)
        .tolist()
    )

    print(
        f"[AI] Grid đủ 12 tháng: "
        f"{len(valid_grid_ids):,}"
    )

    if not valid_grid_ids:

        st.warning(
            "⚠️ Không có grid nào đủ "
            "12 tháng lịch sử liên tục."
        )

        return pd.DataFrame()

    # =========================================================================
    # BƯỚC 7: BUILD INPUT
    # =========================================================================

    X, ordered_grid_ids = _build_model_input(
        df_history=df_history,
        valid_grid_ids=valid_grid_ids
    )

    if X.shape[0] == 0:

        st.warning(
            "⚠️ Không thể tạo chuỗi "
            "12 tháng hợp lệ cho AI."
        )

        return pd.DataFrame()

    print(
        f"[AI] Input shape: {X.shape}"
    )

    # =========================================================================
    # BƯỚC 8: INFERENCE
    # =========================================================================

    try:

        predictions = _run_onnx(
            session=session,
            input_name=input_name,
            X=X
        )

    except Exception:

        return generate_fallback_grid_data(
            year,
            month
        )

    # =========================================================================
    # BƯỚC 9: DEBUG OUTPUT
    # =========================================================================

    print(
        "\n========== AI OUTPUT =========="
    )

    print(
        pd.Series(
            predictions
        ).describe()
    )

    print(
        "Min:",
        float(predictions.min())
    )

    print(
        "Max:",
        float(predictions.max())
    )

    print(
        "Mean:",
        float(predictions.mean())
    )

    print(
        "Std:",
        float(predictions.std())
    )

    print(
        "================================"
    )

    # =========================================================================
    # BƯỚC 10: BUILD RESULT
    # =========================================================================

    df_result = _build_prediction_dataframe(
        df_grid=df_grid_sampled,
        ordered_grid_ids=ordered_grid_ids,
        predictions=predictions,
        year=year,
        month=month
    )

    if df_result.empty:

        return pd.DataFrame()

    # =========================================================================
    # BƯỚC 11: KIỂM TRA KHÔNG GIAN
    # =========================================================================

    print(
        "\n========== SPATIAL CHECK =========="
    )

    print(
        "Longitude:",
        df_result["longitude"].min(),
        "->",
        df_result["longitude"].max()
    )

    print(
        "Latitude:",
        df_result["latitude"].min(),
        "->",
        df_result["latitude"].max()
    )

    print(
        "NDVI:",
        df_result["ndvi_mean"].min(),
        "->",
        df_result["ndvi_mean"].max()
    )

    print(
        "===================================="
    )

    # =========================================================================
    # BƯỚC 12: TRẢ KẾT QUẢ
    # =========================================================================

    return df_result


# =============================================================================
# 12. FALLBACK
# =============================================================================

def generate_fallback_grid_data(
    year: int,
    month: int
) -> pd.DataFrame:
    """
    Fallback khi không thể chạy model.

    LƯU Ý:
    Đây chỉ là dữ liệu dự phòng để WebGIS không bị crash.
    Không phải kết quả AI thật.
    """

    from utils.data_loader import get_db_engine

    try:

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
            LIMIT 2000
        """

        df = pd.read_sql(
            query,
            engine
        )

        if df.empty:
            return pd.DataFrame()

        # ---------------------------------------------------------------------
        # Random chỉ để fallback
        # ---------------------------------------------------------------------

        rng = np.random.default_rng(
            seed=int(year * 100 + month)
        )

        df["ndvi_mean"] = rng.uniform(
            0.30,
            0.70,
            len(df)
        )

        df["ndvi_min"] = np.clip(
            df["ndvi_mean"] - 0.05,
            -1,
            1
        )

        df["ndvi_max"] = np.clip(
            df["ndvi_mean"] + 0.05,
            -1,
            1
        )

        df["year"] = int(year)
        df["month"] = int(month)

        df["date"] = (
            pd.Timestamp(
                year=int(year),
                month=int(month),
                day=1
            )
            .strftime("%Y-%m-%d")
        )

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
                "longitude",
                "latitude",
                "ndvi_mean"
            ]
        )

        return df.reset_index(
            drop=True
        )

    except Exception as e:

        print(
            f"[AI FALLBACK ERROR]: {e}"
        )

        return pd.DataFrame()


# =============================================================================
# 13. HÀM DEMO CHUỖI THỜI GIAN
# =============================================================================

def generate_ndvi_predictions():
    """
    Hàm demo cho biểu đồ nếu cần.

    Không ảnh hưởng đến inference không gian.
    """

    np.random.seed(42)

    dates = pd.date_range(
        start="2017-01-01",
        end="2026-09-01",
        freq="MS"
    )

    actual_ndvi = (
        0.5
        + 0.2
        * np.sin(
            np.linspace(
                0,
                20,
                len(dates)
            )
        )
        + np.random.normal(
            0,
            0.03,
            len(dates)
        )
    )

    future_dates = pd.date_range(
        start="2026-09-01",
        end="2027-06-01",
        freq="MS"
    )

    predicted_ndvi = (
        0.5
        + 0.2
        * np.sin(
            np.linspace(
                20,
                22,
                len(future_dates)
            )
        )
    )

    return (
        dates,
        actual_ndvi,
        future_dates,
        predicted_ndvi
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
