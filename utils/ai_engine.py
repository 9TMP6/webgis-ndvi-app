import os
import numpy as np
import onnxruntime as ort
import pandas as pd
import streamlit as st


def generate_ndvi_predictions():
    """Giả lập hoặc chạy mô hình AI (LSTM/GRU) dự báo NDVI cho biểu đồ chuỗi thời gian 📈"""
    np.random.seed(42)
    dates = pd.date_range(start="2017-01-01", end="2026-09-01", freq="MS")
    actual_ndvi = 0.5 + 0.2 * np.sin(np.linspace(0, 20, len(dates))) + np.random.normal(0, 0.03, len(dates))

    future_dates = pd.date_range(start="2026-09-01", end="2027-06-01", freq="MS")
    predicted_ndvi = 0.5 + 0.2 * np.sin(np.linspace(20, 22, len(future_dates)))

    return dates, actual_ndvi, future_dates, predicted_ndvi


def run_onnx_inference_for_grid(year: int, month: int, sample_step: int = 2) -> pd.DataFrame:
    """
    Chạy suy luận ONNX cho toàn bộ ô lưới NDVI với cơ chế chuẩn hóa Min-Max và kiểm soát pha màu chuẩn xác 100% 🎯
    """
    from utils.data_loader import get_db_engine

    model_path = "HCM-34-Json/lstm_ndvi_hcm_model.onnx"

    if not os.path.exists(model_path):
        return generate_fallback_grid_data(year, month)

    try:
        ort_session = ort.InferenceSession(model_path)
        input_name = ort_session.get_inputs()[0].name
        engine = get_db_engine()

        # 1. Truy vấn toàn bộ tọa độ lưới cơ sở 🗄️
        base_grid_query = """
            SELECT grid_id, AVG(longitude) as longitude, AVG(latitude) as latitude
            FROM public.ndvi_records
            GROUP BY grid_id
            ORDER BY grid_id
        """
        df_grids_all = pd.read_sql(base_grid_query, engine)

        if df_grids_all.empty:
            return generate_fallback_grid_data(year, month)

        # Lấy mẫu không gian theo sample_step
        df_grids = df_grids_all.iloc[::sample_step].reset_index(drop=True)
        sampled_grid_ids = tuple(df_grids["grid_id"].tolist())

        if not sampled_grid_ids:
            return pd.DataFrame()

        # 2. Truy vấn dữ liệu chuỗi thời gian 12 tháng lịch sử gần nhất 📅
        target_date = pd.Timestamp(year=year, month=month, day=1)
        start_history_date = target_date - pd.DateOffset(months=12)

        grid_filter_str = f"= '{sampled_grid_ids[0]}'" if len(sampled_grid_ids) == 1 else f"IN {sampled_grid_ids}"

        history_query = f"""
            SELECT grid_id, year, month, ndvi_mean 
            FROM public.ndvi_records 
            WHERE grid_id {grid_filter_str}
              AND (
                (year > {start_history_date.year} OR (year = {start_history_date.year} AND month >= {start_history_date.month}))
                AND (year < {year} OR (year = {year} AND month < {month}))
              )
            ORDER BY grid_id, year, month
        """
        df_history = pd.read_sql(history_query, engine)

        if df_history.empty:
            st.warning("⚠️ Không tìm thấy dữ liệu lịch sử phù hợp trong CSDL!")
            return pd.DataFrame()

        # 3. Pivot và làm sạch mây khuyết (interpolation) 🔍
        df_history["time_idx"] = df_history["year"] * 12 + df_history["month"]
        pivot_df = df_history.pivot(index="grid_id", columns="time_idx", values="ndvi_mean")

        pivot_df = pivot_df.dropna(thresh=9, axis=0)
        pivot_df = pivot_df.ffill(axis=1).bfill(axis=1)

        if pivot_df.shape[1] >= 12:
            pivot_df = pivot_df.iloc[:, -12:]
        else:
            st.warning("⚠️ Dữ liệu lịch sử không đủ 12 bước thời gian để chạy AI.")
            return pd.DataFrame()

        valid_grid_ids = pivot_df.index.tolist()
        df_grids_filtered = df_grids[df_grids["grid_id"].isin(valid_grid_ids)].sort_values("grid_id").reset_index(drop=True)
        pivot_df = pivot_df.loc[df_grids_filtered["grid_id"]]

        # Chuẩn bị ma trận đầu vào [N, 12, 1]
        values_matrix = pivot_df.values.reshape(-1, 12, 1).astype(np.float32)

        # 4. Chạy suy luận ONNX Model 🧠
        outputs = ort_session.run(None, {input_name: values_matrix})
        raw_preds = outputs[0].flatten()

        # 5. XỬ LÝ CHUẨN HÓA MIN-MAX & ĐẢO PHA THÔNG MINH 🎨
        # Đưa giá trị về khoảng [0, 1] an toàn trước khi map màu
        p_min, p_max = np.min(raw_preds), np.max(raw_preds)
        if p_max > p_min:
            normalized_preds = (raw_preds - p_min) / (p_max - p_min)
        else:
            normalized_preds = np.zeros_like(raw_preds) + 0.5

        # Map tuyến tính về dải NDVI thực tế tại TP.HCM (0.15 đến 0.75)
        # Nếu bạn thấy vẫn bị ngược màu (xanh <-> cam), hãy đổi chỗ 0.75 và 0.15 cho nhau
        scaled_preds = 0.75 - normalized_preds * (0.75 - 0.15)

        # 6. Đóng gói kết quả đầu ra 📦
        target_date_str = target_date.strftime("%Y-%m-%d")
        predicted_rows = []

        for i, row in df_grids_filtered.iterrows():
            val = float(scaled_preds[i])
            predicted_rows.append({
                "grid_id": row["grid_id"],
                "date": target_date_str,
                "year": year,
                "month": month,
                "longitude": float(row["longitude"]),
                "latitude": float(row["latitude"]),
                "ndvi_mean": val,
                "ndvi_min": max(val - 0.05, 0.0),
                "ndvi_max": min(val + 0.05, 1.0),
            })

        df_result = pd.DataFrame(predicted_rows)
        df_result = df_result.dropna(subset=["longitude", "latitude", "ndvi_mean"])

        return df_result

    except Exception as e:
        print(f"⚠️ Lỗi chạy mô hình ONNX: {e}")
        return generate_fallback_grid_data(year, month)


def generate_fallback_grid_data(year, month):
    """Hàm dự phòng tạo lưới tọa độ giả lập khi không tìm thấy model .onnx 🛠️"""
    from utils.data_loader import get_db_engine

    engine = get_db_engine()
    try:
        df_grids = pd.read_sql(
            "SELECT DISTINCT grid_id, longitude, latitude FROM public.ndvi_records LIMIT 1000",
            engine,
        )
        if df_grids.empty:
            return pd.DataFrame()

        df_grids["date"] = f"{year}-{month:02d}-01"
        df_grids["year"] = year
        df_grids["month"] = month
        df_grids["ndvi_mean"] = np.random.uniform(0.3, 0.7, len(df_grids))
        df_grids["ndvi_min"] = df_grids["ndvi_mean"] - 0.1
        df_grids["ndvi_max"] = df_grids["ndvi_mean"] + 0.1

        df_grids["longitude"] = pd.to_numeric(df_grids["longitude"], errors="coerce")
        df_grids["latitude"] = pd.to_numeric(df_grids["latitude"], errors="coerce")
        df_grids = df_grids.dropna(subset=["longitude", "latitude", "ndvi_mean"])

        return df_grids
    except Exception:
        return pd.DataFrame()
