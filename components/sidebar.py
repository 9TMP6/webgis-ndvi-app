import streamlit as st
import pandas as pd
from config import LOCATION_DATA

def render_sidebar():
    with st.sidebar:
        with st.expander("🔮 BỘ LỌC DỰ BÁO", expanded=True):
            selected_province = st.selectbox("Tỉnh / Thành phố:", list(LOCATION_DATA.keys()))
            district_options = list(LOCATION_DATA[selected_province].keys())
            selected_district = st.selectbox("Quận / Huyện / Phường:", district_options)
            
            col_m, col_y = st.columns(2)
            with col_m:
                selected_month = st.selectbox("Tháng:", list(range(1, 13)), index=8)
            with col_y:
                selected_year = st.selectbox("Năm:", list(range(2017, 2028)), index=9)
                
            selected_time = pd.to_datetime(f"{selected_year}-{selected_month:02d}-01")
            btn_predict = st.button("🚀 CHẠY DỰ BÁO AI", use_container_width=True, type="primary")

        with st.expander("⚙️ CẤU HÌNH BẢN ĐỒ", expanded=False):
            basemap_choice = st.radio("Lớp bản đồ nền:", ["Esri Satellite", "Google Hybrid"])
            show_boundaries = st.checkbox("🗺️ Hiển thị ranh giới (HCM-34)", value=True)

        with st.expander("📊 XUẤT DỮ LIỆU & BÁO CÁO", expanded=False):
            sample_df = pd.DataFrame({
                "Lat": [LOCATION_DATA[selected_province][selected_district][0]],
                "Lng": [LOCATION_DATA[selected_province][selected_district][1]],
                "NDVI_Mean": [0.642],
                "Date": [selected_time.strftime("%Y-%m-%d")]
            })
            st.download_button(
                "📥 Xuất dữ liệu CSV",
                data=sample_df.to_csv(index=False).encode('utf-8'),
                file_name=f"ndvi_{selected_district}.csv",
                mime="text/csv",
                use_container_width=True
            )
            st.download_button(
                "🖼️ Xuất ảnh NDVI (.PNG)",
                data=b"PNG_DUMMY_BYTES",
                file_name=f"ndvi_map_{selected_district}.png",
                mime="image/png",
                use_container_width=True
            )
            if st.button("📄 Tạo báo cáo PDF", use_container_width=True):
                st.info("Chức năng kết xuất PDF đang được xử lý.")

    # 🟢 CẬP NHẬT: Thêm btn_predict vào danh sách trả về ở cuối hàm
    return selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict
