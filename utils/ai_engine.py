# =============================================================================
# utils/ai_engine.py
# GEO-NDVI INTELLIGENCE PLATFORM
#
# Ý tưởng:
#   1. Lấy toàn bộ grid 500x500 từ PostgreSQL
#   2. Chọn khoảng 1.500 grid đại diện, phân bố đều theo không gian
#   3. Với mỗi grid -> lấy đúng 12 tháng lịch sử
#   4. Đưa 12 tháng vào ONNX
#   5. Prediction vẫn gắn đúng grid_id
#   6. Trả khoảng 1.500 điểm cho map_utils.py
#   7. map_utils.py chịu trách nhiệm nội suy / lan NDVI ra toàn vùng
# =============================================================================

import os
import numpy as np
import pandas as pd
import onnxruntime as ort


# =============================================================================
# CẤU HÌNH
# =============================================================================

MODEL_PATH = "HCM-34-Json/lstm_ndvi_hcm_model.onnx"

# Số điểm AI cần dự đoán
TARGET_SAMPLE_COUNT = 1500

# Số tháng lịch sử đưa vào model
HISTORY_MONTHS = 12

# Khoảng NDVI hợp lệ
NDVI_MIN = -1.0
NDVI_MAX = 1.0


# =============================================================================
# 1. LOAD ONNX MODEL
# =============================================================================

def load_onnx_model():

    if not os.path.exists(MODEL_PATH):
        print(f"[AI ERROR] Không tìm thấy model: {MODEL_PATH}")
        return None, None

    try:

        session = ort.InferenceSession(
            MODEL_PATH,
            providers=["CPUExecutionProvider"]
        )

        input_name = session.get_inputs()[0].name

        print("========================================")
        print("[AI] ONNX MODEL LOADED")
        print("[AI] Input :", input_name)
        print("[AI] Shape :", session.get_inputs()[0].shape)
        print("[AI] Type  :", session.get_inputs()[0].type)
        print("========================================")

        return session, input_name

    except Exception as e:

        print(f"[AI ERROR] Không load được ONNX: {e}")

        return None, None


# =============================================================================
# 2. LẤY TOÀN BỘ GRID
# =============================================================================

def load_all_grids(engine):

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
# 3. CHỌN ~1500 ĐIỂM PHÂN BỐ ĐỀU KHÔNG GIAN
# =============================================================================

def select_spatial_samples(df_grid, target_count=1500):

    if df_grid.empty:
        return pd.DataFrame()

    total = len(df_grid)

    # Nếu tổng số grid <= target thì lấy toàn bộ
    if total <= target_count:
        return df_grid.copy()

    # -------------------------------------------------------------------------
    # KHÔNG dùng:
    #
    # df.iloc[::12]
    #
    # vì grid_id không đảm bảo phân bố đều về mặt không gian.
    #
    # -------------------------------------------------------------------------

    df = df_grid.copy()

    # Chia không gian thành các cell nhỏ.
    #
    # Sau đó lấy 1 grid đại diện ở mỗi cell.
    #
    # Đây là spatial sampling.
    # -------------------------------------------------------------------------

    lon_min = df["longitude"].min()
    lon_max = df["longitude"].max()

    lat_min = df["latitude"].min()
    lat_max = df["latitude"].max()

    # Tỷ lệ chiều rộng / chiều cao
    lon_range = lon_max - lon_min
    lat_range = lat_max - lat_min

    if lat_range == 0 or lon_range == 0:
        return df.iloc[
            np.linspace(
                0,
                len(df) - 1,
                target_count
            ).astype(int)
        ].copy()

    aspect = lon_range / lat_range

    # Tính số cell theo 2 chiều
    nx = int(
        np.sqrt(
            target_count * aspect
        )
    )

    ny = int(
        np.ceil(
            target_count / max(nx, 1)
        )
    )

    nx = max(nx, 1)
    ny = max(ny, 1)

    # Gán mỗi grid vào một spatial cell

    df["_cell_x"] = (
        (
            (df["longitude"] - lon_min)
            / lon_range
        )
        * nx
    ).astype(int)

    df["_cell_y"] = (
        (
            (df["latitude"] - lat_min)
            / lat_range
        )
        * ny
    ).astype(int)

    # Đưa giá trị biên vào cell cuối
    df["_cell_x"] = df["_cell_x"].clip(
        0,
        nx - 1
    )

    df["_cell_y"] = df["_cell_y"].clip(
        0,
        ny - 1
    )

    # -------------------------------------------------------------------------
    # Lấy grid gần tâm mỗi cell
    # -------------------------------------------------------------------------

    df["_center_x"] = (
        lon_min
        + (
            df["_cell_x"] + 0.5
        )
        / nx
        * lon_range
    )

    df["_center_y"] = (
        lat_min
        + (
            df["_cell_y"] + 0.5
        )
        / ny
        * lat_range
    )

    df["_distance"] = (
        (
            df["longitude"]
            - df["_center_x"]
        ) ** 2
        +
        (
            df["latitude"]
            - df["_center_y"]
        ) ** 2
    )

    sampled = (
        df.sort_values(
            "_distance"
        )
        .drop_duplicates(
            subset=[
                "_cell_x",
                "_cell_y"
            ]
        )
    )

    # -------------------------------------------------------------------------
    # Nếu spatial cells tạo ra ít hơn 1500 điểm
    # thì bổ sung bằng cách lấy đều trong grid còn lại.
    # -------------------------------------------------------------------------

    if len(sampled) < target_count:

        selected_ids = set(
            sampled["grid_id"].tolist()
        )

        remaining = df[
            ~df["grid_id"].isin(
                selected_ids
            )
        ].copy()

        need = target_count - len(sampled)

        if len(remaining) > 0:

            indices = np.linspace(
                0,
                len(remaining) - 1,
                min(
                    need,
                    len(remaining)
                )
            ).astype(int)

            sampled = pd.concat(
                [
                    sampled,
                    remaining.iloc[indices]
                ],
                ignore_index=True
            )

    # Nếu nhiều hơn 1500 thì lấy 1500
    if len(sampled) > target_count:

        sampled = sampled.iloc[
            np.linspace(
                0,
                len(sampled) - 1,
                target_count
            ).astype(int)
        ]

    # -------------------------------------------------------------------------
    # Xóa cột tạm
    # -------------------------------------------------------------------------

    temp_cols = [
        "_cell_x",
        "_cell_y",
        "_center_x",
        "_center_y",
        "_distance"
    ]

    sampled = sampled.drop(
        columns=[
            c
            for c in temp_cols
            if c in sampled.columns
        ]
    )

    sampled = sampled.drop_duplicates(
        subset=["grid_id"]
    )

    return sampled.reset_index(
        drop=True
    )


# =============================================================================
# 4. LẤY 12 THÁNG LỊCH SỬ
# =============================================================================

def load_history(
    engine,
    grid_ids,
    target_year,
    target_month
):

    if not grid_ids:
        return pd.DataFrame()

    ids = [
        int(x)
        for x in grid_ids
    ]

    ids_sql = ",".join(
        str(x)
        for x in ids
    )

    target_date = pd.Timestamp(
        year=int(target_year),
        month=int(target_month),
        day=1
    )

    # Ví dụ dự đoán 09/2026
    #
    # Lịch sử:
    # 09/2025
    # 10/2025
    # ...
    # 08/2026
    #

    start_date = (
        target_date
        - pd.DateOffset(
            months=HISTORY_MONTHS
        )
    )

    end_date = (
        target_date
        - pd.DateOffset(
            months=1
        )
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
              BETWEEN
              '{start_date.strftime("%Y-%m-%d")}'
              AND
              '{end_date.strftime("%Y-%m-%d")}'
        ORDER BY
            grid_id,
            year,
            month
    """

    df = pd.read_sql(
        query,
        engine
    )

    if df.empty:
        return pd.DataFrame()

    df["grid_id"] = pd.to_numeric(
        df["grid_id"],
        errors="coerce"
    )

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

    df["year"] = df["year"].astype(int)
    df["month"] = df["month"].astype(int)

    # NDVI chỉ giới hạn, KHÔNG stretch
    df["ndvi_mean"] = np.clip(
        df["ndvi_mean"],
        NDVI_MIN,
        NDVI_MAX
    )

    # Nếu database có duplicate
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
            [
                "grid_id",
                "year",
                "month"
            ],
            keep="last"
        )
    )

    return df.reset_index(drop=True)


# =============================================================================
# 5. TẠO INPUT CHO AI
# =============================================================================

def build_sequences(
    df_history,
    grid_ids
):

    sequences = []
    valid_grid_ids = []

    for grid_id in grid_ids:

        df_one = df_history[
            df_history["grid_id"] == grid_id
        ].copy()

        df_one = df_one.sort_values(
            [
                "year",
                "month"
            ]
        )

        # ---------------------------------------------------------------------
        # Chỉ cần đúng 12 tháng
        # ---------------------------------------------------------------------

        if len(df_one) != HISTORY_MONTHS:
            continue

        # ---------------------------------------------------------------------
        # Kiểm tra đúng chuỗi tháng
        # ---------------------------------------------------------------------

        dates = pd.to_datetime(
            df_one[
                ["year", "month"]
            ].assign(
                day=1
            )
        )

        expected = pd.date_range(
            start=dates.iloc[0],
            periods=HISTORY_MONTHS,
            freq="MS"
        )

        if not np.array_equal(
            dates.values.astype("datetime64[M]"),
            expected.values.astype("datetime64[M]")
        ):
            continue

        # ---------------------------------------------------------------------
        # Lấy NDVI
        # ---------------------------------------------------------------------

        values = (
            df_one["ndvi_mean"]
            .astype(np.float32)
            .to_numpy()
        )

        if np.isnan(values).any():
            continue

        # [12] -> [12,1]
        values = values.reshape(
            HISTORY_MONTHS,
            1
        )

        sequences.append(values)

        # CỰC KỲ QUAN TRỌNG
        # ID này nằm cùng vị trí với sequence.
        valid_grid_ids.append(
            int(grid_id)
        )

    if not sequences:

        return (
            np.empty(
                (
                    0,
                    HISTORY_MONTHS,
                    1
                ),
                dtype=np.float32
            ),
            []
        )

    X = np.stack(
        sequences
    ).astype(
        np.float32
    )

    return X, valid_grid_ids


# =============================================================================
# 6. CHẠY ONNX
# =============================================================================

def run_model(
    session,
    input_name,
    X
):

    if len(X) == 0:
        return np.array(
            [],
            dtype=np.float32
        )

    outputs = session.run(
        None,
        {
            input_name: X
        }
    )

    if not outputs:
        raise RuntimeError(
            "Model ONNX không trả output."
        )

    predictions = np.asarray(
        outputs[0]
    ).reshape(-1)

    if len(predictions) != len(X):

        raise RuntimeError(
            f"Model trả {len(predictions)} prediction "
            f"nhưng input có {len(X)} grid."
        )

    predictions = np.nan_to_num(
        predictions,
        nan=0.0,
        posinf=1.0,
        neginf=-1.0
    )

    predictions = np.clip(
        predictions,
        NDVI_MIN,
        NDVI_MAX
    )

    return predictions.astype(
        np.float32
    )


# =============================================================================
# 7. TẠO DATAFRAME KẾT QUẢ
# =============================================================================

def build_result(
    sampled_grid,
    valid_grid_ids,
    predictions,
    year,
    month
):

    # -------------------------------------------------------------------------
    # Tạo dataframe AI
    # -------------------------------------------------------------------------

    df_prediction = pd.DataFrame(
        {
            "grid_id": valid_grid_ids,
            "ndvi_mean": predictions
        }
    )

    # -------------------------------------------------------------------------
    # GHÉP BẰNG GRID_ID
    #
    # Không ghép bằng index.
    # Không lấy tọa độ từ grid khác.
    # -------------------------------------------------------------------------

    result = df_prediction.merge(
        sampled_grid[
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
    # Thời gian
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
    # Min / Max phụ
    # -------------------------------------------------------------------------

    result["ndvi_min"] = np.clip(
        result["ndvi_mean"] - 0.05,
        -1,
        1
    )

    result["ndvi_max"] = np.clip(
        result["ndvi_mean"] + 0.05,
        -1,
        1
    )

    # -------------------------------------------------------------------------
    # Kiểu dữ liệu
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

    result = result.reset_index(
        drop=True
    )

    return result


# =============================================================================
# 8. HÀM CHÍNH
# =============================================================================

def run_onnx_inference_for_grid(
    year: int,
    month: int,
    sample_step: int = None
):

    from utils.data_loader import get_db_engine

    print("\n")
    print("================================================")
    print("        GEO-NDVI AI SPATIAL PREDICTION")
    print("================================================")

    # =========================================================================
    # A. LOAD MODEL
    # =========================================================================

    session, input_name = load_onnx_model()

    if session is None:

        print(
            "[AI] Model không tồn tại."
        )

        return generate_fallback_grid_data(
            year,
            month
        )

    # =========================================================================
    # B. DATABASE
    # =========================================================================

    try:

        engine = get_db_engine()

    except Exception as e:

        print(
            f"[AI ERROR] Database: {e}"
        )

        return pd.DataFrame()

    # =========================================================================
    # C. LOAD GRID
    # =========================================================================

    print("[AI] Đang lấy toàn bộ grid...")

    try:

        df_all_grid = load_all_grids(
            engine
        )

    except Exception as e:

        print(
            f"[AI ERROR] Load grid: {e}"
        )

        return pd.DataFrame()

    if df_all_grid.empty:

        print(
            "[AI ERROR] Không có grid."
        )

        return pd.DataFrame()

    print(
        f"[AI] Tổng grid: {len(df_all_grid):,}"
    )

    # =========================================================================
    # D. CHỌN ~1500 GRID
    # =========================================================================

    sampled_grid = select_spatial_samples(
        df_all_grid,
        TARGET_SAMPLE_COUNT
    )

    print(
        f"[AI] Grid lấy mẫu: "
        f"{len(sampled_grid):,}"
    )

    if sampled_grid.empty:

        return pd.DataFrame()

    sampled_ids = (
        sampled_grid["grid_id"]
        .astype(int)
        .tolist()
    )

    # =========================================================================
    # E. LOAD 12 THÁNG
    # =========================================================================

    print(
        f"[AI] Đang lấy {HISTORY_MONTHS} tháng lịch sử..."
    )

    try:

        df_history = load_history(
            engine=engine,
            grid_ids=sampled_ids,
            target_year=year,
            target_month=month
        )

    except Exception as e:

        print(
            f"[AI ERROR] Load history: {e}"
        )

        return pd.DataFrame()

    if df_history.empty:

        print(
            "[AI ERROR] Không có dữ liệu lịch sử."
        )

        return pd.DataFrame()

    print(
        f"[AI] Số dòng lịch sử: "
        f"{len(df_history):,}"
    )

    # =========================================================================
    # F. BUILD SEQUENCE
    # =========================================================================

    X, valid_grid_ids = build_sequences(
        df_history,
        sampled_ids
    )

    print(
        f"[AI] Grid đủ 12 tháng: "
        f"{len(valid_grid_ids):,}"
    )

    print(
        f"[AI] Input shape: "
        f"{X.shape}"
    )

    if len(valid_grid_ids) == 0:

        print(
            "[AI ERROR] Không có grid đủ 12 tháng."
        )

        return pd.DataFrame()

    # =========================================================================
    # G. RUN AI
    # =========================================================================

    print(
        "[AI] Đang chạy ONNX..."
    )

    try:

        predictions = run_model(
            session,
            input_name,
            X
        )

    except Exception as e:

        print(
            f"[AI ERROR] ONNX inference: {e}"
        )

        return generate_fallback_grid_data(
            year,
            month
        )

    # =========================================================================
    # H. KIỂM TRA KẾT QUẢ
    # =========================================================================

    print("")
    print("========== AI RESULT ==========")

    print(
        f"Count : {len(predictions):,}"
    )

    print(
        f"Min   : {predictions.min():.4f}"
    )

    print(
        f"Max   : {predictions.max():.4f}"
    )

    print(
        f"Mean  : {predictions.mean():.4f}"
    )

    print(
        f"Std   : {predictions.std():.4f}"
    )

    print(
        "================================"
    )

    # =========================================================================
    # I. GHÉP GRID + TỌA ĐỘ
    # =========================================================================

    result = build_result(
        sampled_grid=sampled_grid,
        valid_grid_ids=valid_grid_ids,
        predictions=predictions,
        year=year,
        month=month
    )

    # =========================================================================
    # J. KIỂM TRA CUỐI
    # =========================================================================

    print("")
    print("========== SPATIAL RESULT ==========")

    print(
        f"Result rows : {len(result):,}"
    )

    if not result.empty:

        print(
            f"Longitude : "
            f"{result['longitude'].min():.6f}"
            f" -> "
            f"{result['longitude'].max():.6f}"
        )

        print(
            f"Latitude  : "
            f"{result['latitude'].min():.6f}"
            f" -> "
            f"{result['latitude'].max():.6f}"
        )

        print(
            f"NDVI      : "
            f"{result['ndvi_mean'].min():.4f}"
            f" -> "
            f"{result['ndvi_mean'].max():.4f}"
        )

    print(
        "===================================="
    )

    return result


# =============================================================================
# 9. FALLBACK
# =============================================================================

def generate_fallback_grid_data(
    year: int,
    month: int
):

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
            LIMIT 1500
        """

        df = pd.read_sql(
            query,
            engine
        )

        if df.empty:
            return pd.DataFrame()

        # ---------------------------------------------------------------------
        # Fallback chỉ để app không crash.
        # Không phải AI thật.
        # ---------------------------------------------------------------------

        rng = np.random.default_rng(
            seed=year * 100 + month
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
                year=year,
                month=month,
                day=1
            ).strftime(
                "%Y-%m-%d"
            )
        )

        return df

    except Exception as e:

        print(
            f"[FALLBACK ERROR] {e}"
        )

        return pd.DataFrame()


# =============================================================================
# 10. DEMO TIME SERIES
# =============================================================================

def generate_ndvi_predictions():

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
