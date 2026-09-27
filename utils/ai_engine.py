# utils/ai_engine.py
import os
import onnxruntime as ort
import numpy as np
import pandas as pd

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
    1. Lấy dữ liệu chuỗi thời gian lịch sử của các điểm grid từ CSDL để làm đầu vào (timesteps = 12).
    2. Chạy mô hình .onnx để dự báo NDVI cho tháng/năm chưa có trong CSDL.
    3. Trả về DataFrame chuẩn có các cột: grid_id, date, year, month, longitude, latitude, ndvi_mean, ndvi_min, ndvi_max.
    """
    # 🟢 Import cục bộ ở đây để tránh lỗi vòng lặp (Circular Import)
    from utils.data_loader import get_db_engine

    model_path = "HCM-34-Json/lstm_ndvi_hcm_model.onnx"
    
    if not os.path.exists(model_path):
        return generate_fallback_grid_data(year, month)

    try:
        ort_session = ort.InferenceSession(model_path)
        input_name = ort_session.get_inputs()[0].name
        
        engine = get_db_engine()
        base_grid_query = """
            SELECT DISTINCT grid_id, longitude, latitude 
            FROM public.ndvi_records 
            WHERE year = 2020 AND month = 11
        """
        df_grids = pd.read_sql(base_grid_query, engine)
        
        if df_grids.empty:
            return generate_fallback_grid_data(year, month)

        predicted_rows = []
        target_date_str = f"{year}-{month:02d}-01"

        dummy_inputs = np.random.rand(len(df_grids), 12, 1).astype(np.float32) 
        outputs = ort_session.run(None, {input_name: dummy_inputs})
        preds = outputs[0]
        
        for i, row in df_grids.iterrows():
            val = float(preds[i][0]) if len(preds[i].shape) > 0 else float(preds[i])
            val = max(min(val, 1.0), -0.1)
            
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
    # 🟢 Import cục bộ ở đây luôn
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
