import streamlit as st
from config import LOCATION_DATA, CUSTOM_CSS
from components.sidebar import render_sidebar
from components.map_view import render_map
from components.metrics_view import render_metrics
from components.chart_view import render_chart_and_summary

# 1. Cấu hình Trang
st.set_page_config(layout="wide", page_title="GEO-NDVI INTELLIGENCE PLATFORM", page_icon="🌐", initial_sidebar_state="expanded")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# 2. Top Header
st.markdown("""
    <div class="top-header">
        <div class="brand-title">🌐 GEO-NDVI INTELLIGENCE PLATFORM</div>
        <div class="status-badge">🟢 AI ENGINE ONLINE</div>
    </div>
""", unsafe_allow_html=True)

# 3. Sidebar
selected_province, selected_district, selected_time, basemap_choice, show_boundaries = render_sidebar()

# 4. Tọa độ chính
lat, lng, zoom = LOCATION_DATA[selected_province][selected_district]

# 5. Bản đồ & Chỉ số
col_map, col_metrics = st.columns([3.3, 1.0])
with col_map:
    render_map(lat, lng, zoom, basemap_choice, show_boundaries)
with col_metrics:
    render_metrics()

# 6. Biểu đồ AI & Thống kê
render_chart_and_summary(selected_district, selected_province, selected_time)
