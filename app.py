import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd

# 1. Cấu hình giao diện chuẩn Dark Mode
st.set_page_config(layout="wide", page_title="GEO BIG DATA PLATFORM")

# CSS tùy chỉnh màu tối chuẩn Dashboard
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stSidebar"] { background-color: #161b22; }
    h1, h2, h3, p { color: #e6edf3; }
    </style>
""", unsafe_allow_html=True)

# 2. Thanh Menu Bên Trái (Sidebar)
st.sidebar.title(" BỘ LỌC TRUY VẤN KHÔNG GIAN")

huyen_list = {
    "Toàn TP. Hồ Chí Minh": [10.7769, 106.7009, 10],
    "Phường Long Nguyên": [11.1230, 106.6540, 13],
    "Huyện Chợ Mới": [10.5000, 105.5500, 12]
}

selected_huyen = st.sidebar.selectbox("Chọn Vùng / Huyện / Phường:", list(huyen_list.keys()))
time_range = st.sidebar.date_input("Khoảng thời gian (Time Series):", [])
btn_predict = st.sidebar.button("🚀 CHẠY DỰ BÁO AI")

# 3. Khu Vực Bản Đồ Chính (Main Area)
st.title("🌐 GEO BIG DATA PLATFORM v2.4")
st.caption("Hệ thống lưu trữ, truy vấn & dự báo chỉ số vệ tinh NDVI")

col_map, col_info = st.columns([3, 1])

with col_map:
    # Lấy tọa độ tâm và mức zoom
    lat, lng, zoom = huyen_list[selected_huyen]
    
    # Khởi tạo bản đồ vệ tinh Esri
    m = folium.Map(location=[lat, lng], zoom_start=zoom, tiles="Esri WorldImagery")
    
    # Hiển thị bản đồ lên Streamlit
    st_folium(m, width="100%", height=450)

with col_info:
    st.subheader("📊 Bảng Thông Số")
    st.info(f"Đang xem khu vực: **{selected_huyen}**")
    st.metric(label="Tổng số ô Grid", value="27,981")
    st.metric(label="Độ phân giải", value="10m x 10m")

# 4. Hàng Biểu Đồ Phía Dưới
st.subheader("📈 Biến Động Chỉ Số Giải Đoán Theo Thời Gian")
st.write("*(Biểu đồ sẽ kết nối CSDL Supabase để vẽ tại đây)*")
