# utils/ai_engine.py
import os
import onnxruntime as ort
import numpy as np
import pandas as pd
import streamlit as st

def generate_ndvi_predictions():
    """Giả lập hoặc chạy mô hình AI (LSTM/GRU) dự báo NDVI cho biểu đồ chuỗi thời gian"""
    np.random.seed(42)
    dates = pd.date_range(start="2017-01-01", end="2026-09-01", freq="MS")
    actual_ndvi = 0.5 + 0.2 * np.sin(np.linspace(0, 20, len(dates))) + np.random.normal(0, 0.03, len(dates))

    future_dates = pd.date_range(start="2026-09-01", end="2027-06-01", freq="MS")
    predicted_ndvi = 0.5 + 0.2 * np.sin(np.linspace(20, 22, len(future_dates)))
    
    return dates, actual_ndvi, future_dates, predicted_ndvi

def run_onnx_inference_for_grid(year: int, month: int) -> pd.DataFrame:
    """
    1. Lấy dữ liệu 12 tháng lịch sử của toàn bộ grid và gom thành mảng Batch.
    2. Kiểm tra tính đầy đủ của dữ liệu.
    3. Chạy suy luận ONNX theo dạng Batch (1 lần duy nhất cho tất cả các grid) để tăng tốc tối đa.
    """
    from utils.data_loader import get_db_engine

    model_path = "HCM-34-Json/lstm_ndvi_hcm_model.onnx"
    
    if not os.path.exists(model_path):
        return generate_fallback_grid_data(year, month)

    try:
        ort_session = ort.InferenceSession(model_path)
        input_name = ort_session.get_inputs()[0].name
        
        engine = get_db_engine()
        
        # 1. Lấy danh sách các grid cơ sở
        base_grid_query = """
            SELECT DISTINCT grid_id, longitude, latitude 
            FROM public.ndvi_records 
            WHERE year = 2020 AND month = 11
        """
        df_grids = pd.read_sql(base_grid_query, engine)
        
        if df_grids.empty:
            return generate_fallback_grid_data(year, month)

        # 2. Tính mốc thời gian 12 tháng ngược về trước
        target_date = pd.Timestamp(year=year, month=month, day=1)
        start_history_date = target_date - pd.DateOffset(months=12)
        start_year, start_month = start_history_date.year, start_history_date.month

        # Truy vấn lịch sử 12 tháng một lần duy nhất
        history_query = f"""
            SELECT grid_id, year, month, ndvi_mean 
            FROM public.ndvi_records 
            WHERE (year > {start_year} OR (year = {start_year} AND month >= {start_month}))
              AND (year < {year} OR (year = {year} AND month < {month}))
            ORDER BY grid_id, year, month
        """
        df_history = pd.read_sql(history_query, engine)

        if df_history.empty:
            st.warning("⚠️ Không tìm thấy dữ liệu lịch sử để dự báo!")
            return pd.DataFrame()

        # Kiểm tra nhanh số tháng có sẵn của grid đầu tiên
        first_grid_id = df_grids.iloc[0]['grid_id']
        sample_grid_count = df_history[df_history['grid_id'] == first_grid_id].shape[0]

        if sample_grid_count < 10:
            st.warning(f"⚠️ Không đủ dữ liệu lịch sử (chỉ tìm thấy {sample_grid_count}/12 tháng). Khoảng thời gian quá xa để dự báo!")
            return pd.DataFrame()

        # 3. Gom dữ liệu theo dạng Pivot / Matrix để chạy Batch Inference cực nhanh
        # Chỉ giữ lại các grid có đủ đúng 12 tháng lịch sử
        counts = df_history.groupby('grid_id').size()
        valid_grids = counts[counts >= 12].index
        
        df_valid = df_history[df_history['grid_id'].isin(valid_grids)].sort_values(['grid_id', 'year', 'month'])
        
        if df_valid.empty:
            return generate_fallback_grid_data(year, month)

        # Lọc lại danh sách grid khớp với dữ liệu hợp lệ
        df_grids_filtered = df_grids[df_grids['grid_id'].isin(valid_grids)].reset_index(drop=True)
        
        # Chuyển đổi thành mảng 3D [Batch_Size, 12, 1] một cách nhanh chóng bằng numpy
        values_matrix = df_valid['ndvi_mean'].values.reshape(-1, 12, 1).astype(np.float32)

        # 🚀 Chạy ONNX theo lô (Batch Inference) - Chỉ 1 dòng lệnh duy nhất cho toàn bộ hàng nghìn grid!
        outputs = ort_session.run(None, {input_name: values_matrix})
        preds = outputs[0]  # Shape: [Batch_Size, 1] hoặc [Batch_Size]

        # 4. Xử lý kết quả trả về
        target_date_str = target_date.strftime("%Y-%m-%d")
        predicted_rows = []

        for i, row in df_grids_filtered.iterrows():
            pred_val = float(preds[i][0]) if len(preds[i].shape) > 1 and len(preds[i][0].shape) > 0 else float(preds[i])
            
            # Chặn ngưỡng an toàn
            val = max(min(pred_val, 0.85), -0.1)
            
            predicted_rows.append({
                "grid_id": row["grid_id"],
                "date": target_date_str,
                "year": year,
                "month": month,
                "longitude": row["longitude"],
                "latitude": row["latitude"],
                "ndvi_mean": val,
                "ndvi_min": val - 0.05,
                "ndvi_max": val + 0.05
            })

        return pd.DataFrame(predicted_rows)

    except Exception as e:
        print(f"⚠️ Lỗi chạy mô hình ONNX: {e}")
        return generate_fallback_grid_data(year, month)

def generate_fallback_grid_data(year, month):
    """Hàm dự phòng tạo lưới tọa độ giả lập khi không tìm thấy model .onnx"""
    from utils.data_loader import get_db_engine
    
    engine = get_db_engine()
    try:
        df_grids = pd.read_sql("SELECT DISTINCT grid_id, longitude, latitude FROM public.ndvi_records LIMIT 1000", engine)
        if df_grids.empty:
            return pd.DataFrame()
        df_grids['date'] = f"{year}-{month:02d}-01"
        df_grids['year'] = year
        df_grids['month'] = month
        df_grids['ndvi_mean'] = np.random.uniform(0.3, 0.7, len(df_grids))
        df_grids['ndvi_min'] = df_grids['ndvi_mean'] - 0.1
        df_grids['ndvi_max'] = df_grids['ndvi_mean'] + 0.1
        return df_grids
    except:
        return pd.DataFrame()
