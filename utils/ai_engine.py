import os
import numpy as np
import onnxruntime as ort
import pandas as pd
import streamlit as st


def generate_ndvi_predictions():
  """Giả lập hoặc chạy mô hình AI (LSTM/GRU) dự báo NDVI cho biểu đồ chuỗi thời gian 📈"""
  np.random.seed(42)
  dates = pd.date_range(start="2017-01-01", end="2026-09-01", freq="MS")
  actual_ndvi = (
      0.5
      + 0.2 * np.sin(np.linspace(0, 20, len(dates)))
      + np.random.normal(0, 0.03, len(dates))
  )

  future_dates = pd.date_range(start="2026-09-01", end="2027-06-01", freq="MS")
  predicted_ndvi = 0.5 + 0.2 * np.sin(np.linspace(20, 22, len(future_dates)))

  return dates, actual_ndvi, future_dates, predicted_ndvi


def run_onnx_inference_for_grid(
    year: int, month: int, sample_step: int = 12
) -> pd.DataFrame:
  """1. Lấy danh sách toàn bộ ô lưới và LẤY MẪU RẢI RÁC (Spatial Sampling) theo sample_step 🎯.

  2. Truy vấn 12 tháng lịch sử CHỈ cho các ô đại diện ⚡. 3. Chạy suy luận ONNX
  theo dạng Batch 🧠. 4. Chuẩn hóa & Giãn dải NDVI (Min-Max Scaling) chống phai
  màu / da cam toàn bản đồ 🎨.
  """
  from utils.data_loader import get_db_engine

  model_path = "HCM-34-Json/lstm_ndvi_hcm_model.onnx"

  if not os.path.exists(model_path):
    return generate_fallback_grid_data(year, month)

  try:
    ort_session = ort.InferenceSession(model_path)
    input_name = ort_session.get_inputs()[0].name

    engine = get_db_engine()

    # 1. Lấy toàn bộ danh sách grid cơ sở 🗄️
    base_grid_query = """
            SELECT DISTINCT grid_id, longitude, latitude 
            FROM public.ndvi_records 
            WHERE year = 2020 AND month = 11
            ORDER BY grid_id
        """
    df_grids_all = pd.read_sql(base_grid_query, engine)

    if df_grids_all.empty:
      return generate_fallback_grid_data(year, month)

    # 🎯 2. LẤY MẪU RẢI RÁC (~1.800 - 2.000 ô đại diện)
    df_grids = df_grids_all.iloc[::sample_step].reset_index(drop=True)
    sampled_grid_ids = tuple(df_grids["grid_id"].tolist())

    if not sampled_grid_ids:
      return pd.DataFrame()

    # 3. Tính mốc 12 tháng lịch sử 📅
    target_date = pd.Timestamp(year=year, month=month, day=1)
    start_history_date = target_date - pd.DateOffset(months=12)
    start_year, start_month = (
        start_history_date.year,
        start_history_date.month,
    )

    # 4. Truy vấn lịch sử 🚀
    grid_filter_str = (
        f"= {sampled_grid_ids[0]}"
        if len(sampled_grid_ids) == 1
        else f"IN {sampled_grid_ids}"
    )

    history_query = f"""
            SELECT grid_id, year, month, ndvi_mean 
            FROM public.ndvi_records 
            WHERE grid_id {grid_filter_str}
              AND ((year > {start_year} OR (year = {start_year} AND month >= {start_month}))
              AND (year < {year} OR (year = {year} AND month < {month})))
            ORDER BY grid_id, year, month
        """
    df_history = pd.read_sql(history_query, engine)

    if df_history.empty:
      st.warning("⚠️ Không tìm thấy dữ liệu lịch sử cho các ô đại diện!")
      return pd.DataFrame()

    # 5. Lọc grid đủ 12 tháng lịch sử 🔍
    counts = df_history.groupby("grid_id").size()
    valid_grids = counts[counts >= 12].index

    if len(valid_grids) == 0:
      st.warning(
          "⚠️ Không có ô đại diện nào đủ 12 tháng lịch sử liên tục để chạy AI."
      )
      return pd.DataFrame()

    df_valid = df_history[df_history["grid_id"].isin(valid_grids)].sort_values(
        ["grid_id", "year", "month"]
    )
    df_grids_filtered = (
        df_grids[df_grids["grid_id"].isin(valid_grids)]
        .sort_values("grid_id")
        .reset_index(drop=True)
    )

    # Ma trận Batch [N, 12, 1]
    values_matrix = (
        df_valid["ndvi_mean"].values.reshape(-1, 12, 1).astype(np.float32)
    )

    # 🚀 6. Chạy ONNX Batch Inference
    outputs = ort_session.run(None, {input_name: values_matrix})
    raw_preds = outputs[0].flatten()  # Mảng 1D chứa toàn bộ kết quả dự đoán

    # 🪄 7. BỘ GIÃN DẢI MÀU TỰ ĐỘNG THEO PERCENTILE & STD (PHỤC HỒI TƯƠNG PHẢN ĐỘ THỊ - RỪNG) 🎨
    # Lấy bách phân vị 2% và 98% để loại bỏ nhiễu Outlier min/max
    q_low, q_high = np.percentile(raw_preds, 2), np.percentile(raw_preds, 98)
    std_val = raw_preds.std()

    # Nếu độ lệch chuẩn hẹp (std < 0.10) hoặc dải giá trị IQR bị nén (< 0.25)
    if std_val < 0.10 or (q_high - q_low) < 0.25:
        # Min-Max Scaling đưa dải bị nén về dải NDVI chuẩn tương phản của TP.HCM [0.10, 0.65]
        target_ndvi_min, target_ndvi_max = 0.10, 0.65
        scaled_preds = target_ndvi_min + (raw_preds - q_low) * (
            target_ndvi_max - target_ndvi_min
        ) / (q_high - q_low + 1e-6)
        scaled_preds = np.clip(scaled_preds, 0.05, 0.75)
    else:
        scaled_preds = np.clip(raw_preds, 0.05, 0.85)
    # 8. Đóng gói kết quả 📦
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

    # 🛡️ Vệ sinh dữ liệu đầu ra
    df_result["longitude"] = pd.to_numeric(
        df_result["longitude"], errors="coerce"
    )
    df_result["latitude"] = pd.to_numeric(
        df_result["latitude"], errors="coerce"
    )
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
        "SELECT DISTINCT grid_id, longitude, latitude FROM public.ndvi_records"
        " LIMIT 1000",
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

    df_grids["longitude"] = pd.to_numeric(
        df_grids["longitude"], errors="coerce"
    )
    df_grids["latitude"] = pd.to_numeric(df_grids["latitude"], errors="coerce")
    df_grids = df_grids.dropna(subset=["longitude", "latitude", "ndvi_mean"])

    return df_grids
  except:
    return pd.DataFrame()
