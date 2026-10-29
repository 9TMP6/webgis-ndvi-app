import streamlit as st
import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine, text
from config import DATABASE_URL
from utils.ai_engine import run_onnx_inference_for_grid

from utils.ai_demo import run_demo_inference_for_grid 

class ModelError(Exception):
    """Lỗi khi chạy mô hình AI (không bị gói thành 'lỗi CSDL', không bị cache)."""


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
            SELECT o.grid_id, o.date, g.longitude, g.latitude,
                   o.ndvi_mean::float8 AS ndvi_mean, o.ndvi_min::float8 AS ndvi_min, o.ndvi_max::float8 AS ndvi_max
            FROM public.ndvi_observed o
            JOIN public.grid_cells g ON g.grid_id = o.grid_id
            WHERE o.date = make_date(:year, :month, 1)
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
        SELECT g.longitude, g.latitude, o.ndvi_mean::float8 AS ndvi_mean
        FROM public.ndvi_observed o
        JOIN public.grid_cells g ON g.grid_id = o.grid_id
        WHERE o.date = '{selected_date}-01'
    """
    
    try:
        df = pd.read_sql(query, engine)
        return df
    except Exception as e:
        st.error(f"⚠️ Lỗi khi truy vấn CSDL: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_ndvi_data_with_ai_fallback(year: int, month: int, min_valid_rows: int = 20000,
                                    model_name: str = "LSTM", force_ai: bool = False):
    engine = get_db_engine()
    try:
        if not force_ai:      # chế độ bình thường: ưu tiên dữ liệu quan trắc
            query = text("""
                SELECT o.grid_id, o.date, g.longitude, g.latitude,
                       o.ndvi_mean::float8 AS ndvi_mean, o.ndvi_min::float8 AS ndvi_min, o.ndvi_max::float8 AS ndvi_max
                FROM public.ndvi_observed o
                JOIN public.grid_cells g ON g.grid_id = o.grid_id
                WHERE o.date = make_date(:year, :month, 1)
            """)
            df = pd.read_sql(query, engine, params={"year": int(year), "month": int(month)})
            if not df.empty:
                df_valid = df.dropna(subset=['longitude', 'latitude', 'ndvi_mean'])
                if len(df_valid) >= min_valid_rows:
                    return df_valid, False
                st.warning(
                    f"⚠️ Dữ liệu tháng {month}/{year} trong CSDL bị khuyết nhiều do mây phủ "
                    f"(chỉ có {len(df_valid):,}/{len(df):,} ô hợp lệ). Đang tự động chuyển sang mô hình AI dự báo..."
                )

        st.info(f"Đang chạy mô hình AI dự báo cho tháng {month}/{year}...")
        try:
            df_predicted = run_demo_inference_for_grid(year, month, model_name=model_name)
        except Exception as e:
            raise ModelError(f"Không chạy được mô hình {model_name}: {e}") from e
        return df_predicted, True

    except ModelError:
        raise
    except Exception as e:
        st.error(f"❌ Lỗi truy vấn CSDL: {e}")
        return pd.DataFrame(), False


