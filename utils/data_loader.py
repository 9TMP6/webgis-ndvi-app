import streamlit as st
import geopandas as gpd

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
