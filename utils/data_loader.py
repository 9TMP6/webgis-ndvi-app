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
def load_ndvi_data(district_name: str = None, limit: int = 2000):
    """Lấy dữ liệu NDVI mới nhất từ Supabase theo khu vực"""
    engine = get_db_engine()
    try:
        query = """
            SELECT grid_id, date, longitude, latitude, ndvi_mean, ndvi_min, ndvi_max 
            FROM public.ndvi_records
        """
        
        # Lọc theo quận/huyện nếu có cột district trong database
        if district_name and district_name != "Toàn tỉnh/TP":
            query += f" WHERE district = :district"
            query += " ORDER BY date DESC LIMIT :limit;"
            df = pd.read_sql(text(query), engine, params={"district": district_name, "limit": limit})
        else:
            query += " ORDER BY date DESC LIMIT :limit;"
            df = pd.read_sql(text(query), engine, params={"limit": limit})

        if 'date' in df.columns and not df.empty:
            df['date'] = pd.to_datetime(df['date'])

        return df

    except Exception as e:
        st.error(f"❌ Lỗi khi tải dữ liệu từ Supabase Database: {e}")
        return pd.DataFrame()
