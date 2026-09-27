import streamlit as st
import pandas as pd
from config import LOCATION_DATA


def render_sidebar(df: pd.DataFrame = None):
    """
    Render Sidebar bộ lọc, cấu hình bản đồ và xuất dữ liệu CSV thực tế 📊
    """
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
            # 🟢 XUẤT FILE CSV CHUẨN TỪ DỮ LIỆU TRUY VẤN THỰC TẾ
            if df is not None and not df.empty:
                # utf-8-sig giúp Excel đọc đúng font tiếng Việt không bị lỗi
                csv_bytes = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 Xuất dữ liệu CSV",
                    data=csv_bytes,
                    file_name=f"ndvi_{selected_district}_{selected_year}_{selected_month:02d}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    help="Click để tải về toàn bộ tập dữ liệu NDVI đã truy vấn"
                )
            else:
                st.download_button(
                    label="📥 Xuất dữ liệu CSV",
                    data=b"",
                    file_name=f"ndvi_{selected_district}.csv",
                    mime="text/csv",
                    disabled=True,
                    use_container_width=True,
                    help="Vui lòng nhấn '🚀 CHẠY DỰ BÁO AI' để có dữ liệu xuất CSV"
                )

            st.download_button(
                label="🖼️ Xuất ảnh NDVI (.PNG)",
                data=b"PNG_DUMMY_BYTES",
                file_name=f"ndvi_map_{selected_district}.png",
                mime="image/png",
                use_container_width=True
            )
            if st.button("📄 Tạo báo cáo PDF", use_container_width=True):
                st.info("Chức năng kết xuất PDF đang được xử lý.")

    return selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict
