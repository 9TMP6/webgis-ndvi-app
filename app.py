import streamlit as st
import pandas as pd
from config import LOCATION_DATA, CUSTOM_CSS
from components.sidebar import render_sidebar
from components.map_view import render_map
from components.metrics_view import render_metrics
from components.chart_view import render_chart_and_summary
from utils.data_loader import load_ndvi_data

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

# 3. Sidebar (Đã khớp đủ 6 biến trả về từ render_sidebar)
selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict = render_sidebar()

# Khởi tạo session state lưu trữ dữ liệu
if "ndvi_df" not in st.session_state:
    st.session_state["ndvi_df"] = pd.DataFrame()

# 4. Chỉ truy vấn CSDL khi bấm nút "🚀 CHẠY DỰ BÁO AI"
if btn_predict:
    year = selected_time.year
    month = selected_time.month
    
    with st.spinner(f"🌐 Đang truy vấn CSDL cho tháng {month}/{year}..."):
        df_result = load_ndvi_data(year=year, month=month)
        st.session_state["ndvi_df"] = df_result

        # Thông báo Toast Alert trạng thái
        if df_result.empty:
            st.toast(f"⚠️ Không tìm thấy dữ liệu cho tháng {month}/{year}", icon="❌")
            st.warning(f"⚠️ **Không có dữ liệu:** Tháng **{month}/{year}** chưa có bản ghi NDVI trong CSDL Supabase. Bạn thử chọn mốc **Tháng 11/2020** nhé!")
        else:
            st.toast(f"✅ Tải thành công {len(df_result):,} điểm NDVI!", icon="🛰️")
            st.success(f"🎉 **Truy vấn thành công:** Đã tải **{len(df_result):,}** ô tọa độ NDVI cho Tháng **{month}/{year}**!")

ndvi_df = st.session_state["ndvi_df"]

# 5. Tọa độ chính
lat, lng, zoom = LOCATION_DATA[selected_province][selected_district]

# 6. Bản đồ & Chỉ số
col_map, col_metrics = st.columns([3.3, 1.0])
with col_map:
    render_map(lat, lng, zoom, basemap_choice, show_boundaries, df=ndvi_df, selected_time=selected_time)
with col_metrics:
    render_metrics(df=ndvi_df) # 🟢 Đã truyền df=ndvi_df để cập nhật chỉ số động

# 7. Biểu đồ AI & Thống kê
render_chart_and_summary(selected_district, selected_province, selected_time, df=ndvi_df)
