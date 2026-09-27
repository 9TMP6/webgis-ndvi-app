import streamlit as st
import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine, text
from config import DATABASE_URL
from utils.ai_engine import run_onnx_inference_for_grid

@st.cache_resource
def get_db_engine():
    return create_engine(DATABASE_URL)

@st.cache_data
def load_local_shapefile(shp_path="HCM-34-Json/HCM-34-v2.json"): 
    try:
        gdf = gpd.read_file(shp_path)
        if gdf.crs is not None and gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs(epsg=4326)
        return gdf
    except Exception as e:
        st.error(f"❌ Không thể tải dữ liệu ranh giới từ '{shp_path}': {e}")
        return None

@st.cache_data(ttl=300)
def load_ndvi_data(year: int, month: int):
    """
    Truy vấn tất cả các điểm GRID theo year và month từ CSDL Supabase
    """
    engine = get_db_engine()
    try:
        query = text("""
            SELECT grid_id, date, year, month, longitude, latitude, ndvi_mean, ndvi_min, ndvi_max 
            FROM public.ndvi_records
            WHERE year = :year AND month = :month
        """)
        
        df = pd.read_sql(query, engine, params={"year": int(year), "month": int(month)})

        if not df.empty:
            df = df.dropna(subset=['longitude', 'latitude', 'ndvi_mean'])

        return df

    except Exception as e:
        st.error(f"❌ Lỗi truy vấn CSDL Supabase: {e}")
        return pd.DataFrame()
        
@st.cache_data(ttl=3600)
def load_ndvi_by_date(selected_date: str) -> pd.DataFrame:
    """
    Truy vấn dữ liệu NDVI từ Supabase theo tháng/năm (VD: '2019-01')
    """
    db_url = st.secrets["postgres"]["url"]
    engine = create_engine(db_url)
    
    query = f"""
        SELECT longitude, latitude, ndvi_mean 
        FROM ndvi_records 
        WHERE date = '{selected_date}'
    """
    
    try:
        df = pd.read_sql(query, engine)
        return df
    except Exception as e:
        st.error(f"⚠️ Lỗi khi truy vấn CSDL: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def load_ndvi_data_with_ai_fallback(year: int, month: int):
    """
    1. Truy vấn CSDL Supabase trước.
    2. Nếu không có dữ liệu -> Tự động kích hoạt mô hình .ONNX suy luận và trả về kết quả cấu trúc y hệt CSDL.
    """
    engine = get_db_engine()
    try:
        query = text("""
            SELECT grid_id, date, year, month, longitude, latitude, ndvi_mean, ndvi_min, ndvi_max 
            FROM public.ndvi_records
            WHERE year = :year AND month = :month
        """)
        df = pd.read_sql(query, engine, params={"year": int(year), "month": int(month)})

        if not df.empty:
            df = df.dropna(subset=['longitude', 'latitude', 'ndvi_mean'])
            return df, False # False nghĩa là lấy trực tiếp từ CSDL
            
        # Nếu CSDL trống (tháng chưa có dữ liệu) -> Dùng AI ONNX dự đoán
        st.info(f"🤖 Không tìm thấy dữ liệu tháng {month}/{year} trong CSDL. Đang tiến hành chạy mô hình AI (.onnx) để suy luận không gian...")
        df_predicted = run_onnx_inference_for_grid(year, month)
        return df_predicted, True # True nghĩa là dữ liệu do AI suy luận

    except Exception as e:
        st.error(f"❌ Lỗi truy vấn CSDL: {e}")
        return pd.DataFrame(), False
