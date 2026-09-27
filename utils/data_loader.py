import streamlit as st
import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine, text
from config import DATABASE_URL

@st.cache_resource
def get_db_engine():
    return create_engine(DATABASE_URL)

@st.cache_data
def load_local_shapefile(shp_path="HCM-34-Json/HCM-34.geojson"): 
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
    Truy vấn TẤT CẢ các điểm GRID theo đúng Tháng & Năm được chọn từ Supabase
    Cấu trúc bảng: grid_id, date, day, month, year, longitude, latitude, ndvi_mean...
    """
    engine = get_db_engine()
    try:
        # Truy vấn trực tiếp theo cột year và month trong CSDL của bạn
        query = text("""
            SELECT longitude, latitude, ndvi_mean, ndvi_min, ndvi_max 
            FROM public.ndvi_records
            WHERE year = :year AND month = :month
        """)
        
        df = pd.read_sql(query, engine, params={"year": year, "month": month})

        # Nếu không tìm thấy theo month/year dạng số, thử fallback theo chuỗi date ('YYYY-MM')
        if df.empty:
            date_str = f"{year}-{month:02d}"
            query_fallback = text("""
                SELECT longitude, latitude, ndvi_mean, ndvi_min, ndvi_max 
                FROM public.ndvi_records
                WHERE date LIKE :date_str
            """)
            df = pd.read_sql(query_fallback, engine, params={"date_str": f"{date_str}%"})

        # Gom nhóm tọa độ trùng lặp để nội suy chính xác
        if not df.empty:
            df = df.groupby(['longitude', 'latitude'], as_index=False).agg({
                'ndvi_mean': 'mean',
                'ndvi_min': 'min',
                'ndvi_max': 'max'
            })

        return df

    except Exception as e:
        st.error(f"❌ Lỗi khi tải dữ liệu NDVI từ Supabase: {e}")
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
