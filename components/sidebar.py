import io
import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw
from config import LOCATION_DATA


def create_placeholder_png() -> bytes:
    """Tạo ảnh PNG mặc định khi người dùng bấm tải ảnh trước khi có dữ liệu."""
    img = Image.new('RGB', (600, 350), color='#F1F8F3')
    draw = ImageDraw.Draw(img)
    draw.rectangle([15, 15, 585, 335], outline='#15803D', width=2)
    # Font mặc định của PIL không hỗ trợ dấu tiếng Việt nên dùng chữ không dấu
    draw.text((200, 130), "CHUA CO DU LIEU DU BAO", fill='#B45309')
    draw.text((120, 170), "Vui long nhan 'CHAY DU BAO AI' de tao anh NDVI!", fill='#5B7A66')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


@st.cache_data(show_spinner=False, max_entries=3)
def _build_export_png(df: pd.DataFrame, date_label: str):
    """Vẽ ảnh bản đồ PNG một lần rồi nhớ kết quả (tránh vẽ lại mỗi lần trang chạy lại)."""
    from utils.map_utils import generate_ndvi_raster_for_export
    return generate_ndvi_raster_for_export(df, date_label=date_label)


def render_sidebar(df: pd.DataFrame = None):
    """Thanh bên: bộ lọc dự báo, cấu hình bản đồ, xuất dữ liệu CSV/PNG."""
    if df is None or df.empty:
        df = st.session_state.get("ndvi_df", None)
    has_data = df is not None and not df.empty

    with st.sidebar:
        st.markdown("""
            <div class="side-brand">
                <p class="name">🌿 GEO-NDVI</p>
                <p class="desc">Nền tảng viễn thám và AI giám sát thực vật</p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("### Bảng điều khiển")

        with st.expander("🔮 Bộ lọc dự báo", expanded=True):
            selected_province = st.selectbox("Tỉnh / Thành phố:", list(LOCATION_DATA.keys()))
            district_options = list(LOCATION_DATA[selected_province].keys())
            selected_district = st.selectbox("Quận / Huyện / Phường:", district_options)

            col_m, col_y = st.columns(2)
            with col_m:
                selected_month = st.selectbox("Tháng:", list(range(1, 13)), index=8)
            with col_y:
                selected_year = st.selectbox("Năm:", list(range(2017, 2028)), index=9)

            selected_time = pd.to_datetime(f"{selected_year}-{selected_month:02d}-01")
            selected_model = st.selectbox(
                "Mô hình AI dự báo:", ["LSTM", "GRU", "CNNLSTM"],
                help="Chỉ áp dụng khi tháng đã chọn không đủ dữ liệu quan trắc trong CSDL và cần dự báo bằng AI",
            )
            btn_predict = st.button("🚀 Chạy dự báo AI", use_container_width=True, type="primary",
                                    help="Lấy dữ liệu NDVI từ CSDL, nếu thiếu sẽ tự dùng AI để dự báo")

        with st.expander("⚙️ Cấu hình bản đồ", expanded=False):
            basemap_choice = st.radio("Lớp bản đồ nền:", ["Ảnh vệ tinh Esri", "Google Hybrid"])
            show_boundaries = st.checkbox("🗺️ Hiển thị ranh giới hành chính (HCM-34)", value=True)

        with st.expander("📊 Xuất dữ liệu và báo cáo", expanded=False):
            # 1. CSV
            if has_data:
                csv_bytes = df.to_csv(index=False).encode('utf-8-sig')
                file_name_csv = f"ndvi_{selected_district}_{selected_year}_{selected_month:02d}.csv"
            else:
                csv_default = "Trạng_thái,Thông_báo\nCHƯA_DỰ_BÁO,Vui lòng nhấn 'Chạy dự báo AI' để cập nhật dữ liệu NDVI."
                csv_bytes = csv_default.encode('utf-8-sig')
                file_name_csv = f"ndvi_{selected_district}_mau_mac_dinh.csv"

            btn_csv = st.download_button(
                label="📥 Xuất dữ liệu CSV", data=csv_bytes, file_name=file_name_csv,
                mime="text/csv", use_container_width=True, help="Tải dữ liệu NDVI (CSV) về máy",
            )
            if btn_csv and not has_data:
                st.toast("Bạn vừa tải file CSV mẫu. Hãy nhấn 'Chạy dự báo AI' để có dữ liệu thực tế!", icon="🔔")

            # 2. PNG
            png_bytes = None
            if has_data:
                try:
                    png_bytes = _build_export_png(df, f"{selected_month:02d}/{selected_year}")
                except Exception:
                    png_bytes = None

            if png_bytes is None:
                png_bytes = create_placeholder_png()
                file_name_png = f"ndvi_map_{selected_district}_mac_dinh.png"
            else:
                file_name_png = f"ndvi_map_{selected_district}_{selected_year}_{selected_month:02d}.png"

            btn_png = st.download_button(
                label="🖼️ Xuất ảnh NDVI (.PNG)", data=png_bytes, file_name=file_name_png,
                mime="image/png", use_container_width=True, help="Tải ảnh bản đồ NDVI (PNG) về máy",
            )
            if btn_png and not has_data:
                st.toast("Bạn vừa tải ảnh mẫu. Hãy bấm '🚀 Chạy dự báo AI' để tạo bản đồ NDVI!", icon="🖼️")

        with st.expander("ℹ️ Hướng dẫn sử dụng", expanded=False):
            st.markdown(
                "1. Chọn **khu vực**, **tháng** và **năm**.\n"
                "2. Nhấn **Chạy dự báo AI** để tải dữ liệu hoặc dự báo.\n"
                "3. Xem lớp NDVI trên bản đồ, đổi lớp nền ở mục *Cấu hình bản đồ*.\n"
                "4. Xuất CSV hoặc ảnh PNG ở mục *Xuất dữ liệu và báo cáo*."
            )

    return selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict, selected_model




# import io
# import streamlit as st
# import pandas as pd
# from PIL import Image, ImageDraw
# from config import LOCATION_DATA


# def create_placeholder_png() -> bytes:
#     """Tạo ảnh PNG mặc định khi người dùng bấm tải ảnh trước khi có dữ liệu."""
#     img = Image.new('RGB', (600, 350), color='#F1F8F3')
#     draw = ImageDraw.Draw(img)
#     draw.rectangle([15, 15, 585, 335], outline='#15803D', width=2)
#     # Font mặc định của PIL không hỗ trợ dấu tiếng Việt nên dùng chữ không dấu
#     draw.text((200, 130), "CHUA CO DU LIEU DU BAO", fill='#B45309')
#     draw.text((120, 170), "Vui long nhan 'CHAY DU BAO AI' de tao anh NDVI!", fill='#5B7A66')
#     buf = io.BytesIO()
#     img.save(buf, format='PNG')
#     return buf.getvalue()


# @st.cache_data(show_spinner=False, max_entries=3)
# def _build_export_png(df: pd.DataFrame, date_label: str):
#     """Vẽ ảnh bản đồ PNG một lần rồi nhớ kết quả (tránh vẽ lại mỗi lần trang chạy lại)."""
#     from utils.map_utils import generate_ndvi_raster_for_export
#     return generate_ndvi_raster_for_export(df, date_label=date_label)


# def render_sidebar(df: pd.DataFrame = None):
#     """Thanh bên: bộ lọc dự báo, cấu hình bản đồ, xuất dữ liệu CSV/PNG."""
#     if df is None or df.empty:
#         df = st.session_state.get("ndvi_df", None)
#     has_data = df is not None and not df.empty

#     with st.sidebar:
#         st.markdown("""
#             <div class="side-brand">
#                 <p class="name">GEO-NDVI</p>
#                 <p class="desc">Nền tảng viễn thám và AI giám sát thực vật</p>
#             </div>
#         """, unsafe_allow_html=True)

#         st.markdown("### Bảng điều khiển")

#         with st.expander("🔮 Bộ lọc dự báo", expanded=True):
#             selected_province = st.selectbox("Tỉnh / Thành phố:", list(LOCATION_DATA.keys()))
#             district_options = list(LOCATION_DATA[selected_province].keys())
#             selected_district = st.selectbox("Quận / Huyện / Phường:", district_options)

#             col_m, col_y = st.columns(2)
#             with col_m:
#                 selected_month = st.selectbox("Tháng:", list(range(1, 13)), index=8)
#             with col_y:
#                 selected_year = st.selectbox("Năm:", list(range(2018, 2028)), index=9)

#             selected_time = pd.to_datetime(f"{selected_year}-{selected_month:02d}-01")
#             btn_predict = st.button("🚀 Chạy dự báo AI", use_container_width=True, type="primary",
#                                     help="Lấy dữ liệu NDVI từ CSDL, nếu thiếu sẽ tự dùng AI để dự báo")

#         with st.expander("⚙️ Cấu hình bản đồ", expanded=False):
#             basemap_choice = st.radio("Lớp bản đồ nền:", ["Ảnh vệ tinh Esri", "Google Hybrid"])
#             show_boundaries = st.checkbox("🗺️ Hiển thị ranh giới hành chính (HCM-34)", value=True)

#         with st.expander("📊 Xuất dữ liệu và báo cáo", expanded=False):
#             # 1. CSV
#             if has_data:
#                 csv_bytes = df.to_csv(index=False).encode('utf-8-sig')
#                 file_name_csv = f"ndvi_{selected_district}_{selected_year}_{selected_month:02d}.csv"
#             else:
#                 csv_default = "Trạng_thái,Thông_báo\nCHƯA_DỰ_BÁO,Vui lòng nhấn 'Chạy dự báo AI' để cập nhật dữ liệu NDVI."
#                 csv_bytes = csv_default.encode('utf-8-sig')
#                 file_name_csv = f"ndvi_{selected_district}_mau_mac_dinh.csv"

#             btn_csv = st.download_button(
#                 label="📥 Xuất dữ liệu CSV", data=csv_bytes, file_name=file_name_csv,
#                 mime="text/csv", use_container_width=True, help="Tải dữ liệu NDVI (CSV) về máy",
#             )
#             if btn_csv and not has_data:
#                 st.toast("Bạn vừa tải file CSV mẫu. Hãy nhấn '🚀 Chạy dự báo AI' để có dữ liệu thực tế!", icon="🔔")

#             # 2. PNG
#             png_bytes = None
#             if has_data:
#                 try:
#                     png_bytes = _build_export_png(df, f"{selected_month:02d}/{selected_year}")
#                 except Exception:
#                     png_bytes = None

#             if png_bytes is None:
#                 png_bytes = create_placeholder_png()
#                 file_name_png = f"ndvi_map_{selected_district}_mac_dinh.png"
#             else:
#                 file_name_png = f"ndvi_map_{selected_district}_{selected_year}_{selected_month:02d}.png"

#             btn_png = st.download_button(
#                 label="🖼️ Xuất ảnh NDVI (.PNG)", data=png_bytes, file_name=file_name_png,
#                 mime="image/png", use_container_width=True, help="Tải ảnh bản đồ NDVI (PNG) về máy",
#             )
#             if btn_png and not has_data:
#                 st.toast("Bạn vừa tải ảnh mẫu. Hãy bấm '🚀 Chạy dự báo AI' để tạo bản đồ NDVI!", icon="🖼️")

#         with st.expander("ℹ️ Hướng dẫn sử dụng", expanded=False):
#             st.markdown(
#                 "1. Chọn **khu vực**, **tháng** và **năm**.\n"
#                 "2. Nhấn **Chạy dự báo AI** để tải dữ liệu hoặc dự báo.\n"
#                 "3. Xem lớp NDVI trên bản đồ, đổi lớp nền ở mục *Cấu hình bản đồ*.\n"
#                 "4. Xuất CSV hoặc ảnh PNG ở mục *Xuất dữ liệu và báo cáo*."
#             )

#     return selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict



# # import base64
# # import io
# # import streamlit as st
# # import pandas as pd
# # from PIL import Image, ImageDraw
# # from config import LOCATION_DATA
# # from utils.map_utils import generate_ndvi_raster


# # def create_placeholder_png() -> bytes:
# #     """
# #     Tạo ảnh PNG mặc định thông báo chưa có dữ liệu khi người dùng bấm tải ảnh sớm 🎨
# #     """
# #     img = Image.new('RGB', (600, 350), color='#F1F8F3')  # Nền tối Slate đẹp mắt
# #     draw = ImageDraw.Draw(img)
    
# #     # Vẽ khung viền trang trí
# #     draw.rectangle([15, 15, 585, 335], outline='#15803D', width=2)
    
# #     # Vẽ các dòng chữ thông báo mặc định
# #     draw.text((160, 130), "⚠️ CHUA CO DU LIEU DU BAO", fill='#B45309')
# #     draw.text((110, 170), "Vui long nhan 'CHAY DU BAO AI' de tao anh NDVI!", fill='#5B7A66')
    
# #     buf = io.BytesIO()
# #     img.save(buf, format='PNG')
# #     return buf.getvalue()


# # @st.cache_data(show_spinner=False, max_entries=3)
# # def _build_export_png(df: pd.DataFrame, date_label: str):
# #     """Vẽ ảnh bản đồ PNG 1 lần rồi nhớ kết quả (tránh vẽ lại mỗi lần Streamlit chạy lại trang)."""
# #     from utils.map_utils import generate_ndvi_raster_for_export
# #     return generate_ndvi_raster_for_export(df, date_label=date_label)


# # def render_sidebar(df: pd.DataFrame = None):
# #     """
# #     Render Sidebar bộ lọc, cấu hình bản đồ và xuất dữ liệu CSV / PNG (Luôn sáng nút) 📊🖼️
# #     """
# #     # 🟢 Ưu tiên lấy df từ session_state nếu truyền vào bị None
# #     if df is None or df.empty:
# #         df = st.session_state.get("ndvi_df", None)

# #     has_data = df is not None and not df.empty

# #     with st.sidebar:

# #         st.markdown("""
# #             <div style='text-align: center; padding: 0 0 15px 0; border-bottom: 1px solid #D7E8DB; margin-bottom: 15px;'>
# #                 <h2 style='color: #15803D; font-size: 1rem; font-weight: 700; margin: 0;'>🌐 GEO-NDVI Intelligence</h2>
# #                 <p style='color: #5B7A66; font-size: 0.7rem; margin: 4px 0 0 0;'>AI & Remote Sensing Platform</p>
# #             </div>
# #         """, unsafe_allow_html=True)

# #         st.markdown("### 🎛️ Bảng Điều Khiển")
        
# #         with st.expander("🔮 BỘ LỌC DỰ BÁO", expanded=True):
# #             selected_province = st.selectbox("Tỉnh / Thành phố:", list(LOCATION_DATA.keys()))
# #             district_options = list(LOCATION_DATA[selected_province].keys())
# #             selected_district = st.selectbox("Quận / Huyện / Phường:", district_options)
            
# #             col_m, col_y = st.columns(2)
# #             with col_m:
# #                 selected_month = st.selectbox("Tháng:", list(range(1, 13)), index=8)
# #             with col_y:
# #                 selected_year = st.selectbox("Năm:", list(range(2017, 2028)), index=9)
                
# #             selected_time = pd.to_datetime(f"{selected_year}-{selected_month:02d}-01")
# #             btn_predict = st.button("🚀 CHẠY DỰ BÁO AI", use_container_width=True, type="primary")

# #         with st.expander("⚙️ CẤU HÌNH BẢN ĐỒ", expanded=False):
# #             basemap_choice = st.radio("Lớp bản đồ nền:", ["Esri Satellite", "Google Hybrid"])
# #             show_boundaries = st.checkbox("🗺️ Hiển thị ranh giới (HCM-34)", value=True)

# #         with st.expander("📊 XUẤT DỮ LIỆU & BÁO CÁO", expanded=False):
# #             # 🟢 1. XUẤT FILE CSV
# #             if has_data:
# #                 csv_bytes = df.to_csv(index=False).encode('utf-8-sig')
# #                 file_name_csv = f"ndvi_{selected_district}_{selected_year}_{selected_month:02d}.csv"
# #             else:
# #                 # File CSV mặc định khi chưa chạy dự báo
# #                 csv_default = "Trạng_thái,Thông_báo\nCHƯA_DỰ_BÁO,Vui lòng nhấn 'CHẠY DỰ BÁO AI' trên ứng dụng để cập nhật dữ liệu NDVI mới nhất."
# #                 csv_bytes = csv_default.encode('utf-8-sig')
# #                 file_name_csv = f"ndvi_{selected_district}_mau_mac_dinh.csv"

# #             btn_csv = st.download_button(
# #                 label="📥 Xuất dữ liệu CSV",
# #                 data=csv_bytes,
# #                 file_name=file_name_csv,
# #                 mime="text/csv",
# #                 use_container_width=True,
# #                 help="Click để tải dữ liệu CSV về máy"
# #             )
# #             if btn_csv and not has_data:
# #                 st.toast("ℹ️ Bạn đã tải file CSV mẫu. Hãy nhấn '🚀 CHẠY DỰ BÁO AI' để có dữ liệu thực tế nhé!", icon="🔔")

# #             # 🟢 2. XUẤT FILE ẢNH RASTER PNG (Sử dụng hàm xuất riêng biệt để không khoảng trắng)
# #             png_bytes = None
# #             if has_data:
# #                 try:
# #                     png_bytes = _build_export_png(df, f"{selected_month:02d}/{selected_year}")
# #                 except Exception:
# #                     png_bytes = None

# #             if png_bytes is None:
# #                 # Ảnh PNG mặc định khi chưa chạy dự báo
# #                 png_bytes = create_placeholder_png()
# #                 file_name_png = f"ndvi_map_{selected_district}_mac_dinh.png"
# #             else:
# #                 file_name_png = f"ndvi_map_{selected_district}_{selected_year}_{selected_month:02d}.png"
                
# #             btn_png = st.download_button(
# #                 label="🖼️ Xuất ảnh NDVI (.PNG)",
# #                 data=png_bytes,
# #                 file_name=file_name_png,
# #                 mime="image/png",
# #                 use_container_width=True,
# #                 help="Click để tải ảnh NDVI PNG về máy"
# #             )
# #             if btn_png and not has_data:
# #                 st.toast("ℹ️ Bạn vừa tải ảnh mẫu mặc định. Hãy bấm '🚀 CHẠY DỰ BÁO AI' để tạo bản đồ NDVI nhé!", icon="🖼️")

# #             # if st.button("📄 Tạo báo cáo PDF", use_container_width=True):
# #             #     st.info("Chức năng kết xuất PDF đang được xử lý.")

# #     return selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict



# # # import base64
# # # import io
# # # import streamlit as st
# # # import pandas as pd
# # # from PIL import Image, ImageDraw
# # # from config import LOCATION_DATA
# # # from utils.map_utils import generate_ndvi_raster


# # # def create_placeholder_png() -> bytes:
# # #     """
# # #     Tạo ảnh PNG mặc định thông báo chưa có dữ liệu khi người dùng bấm tải ảnh sớm 🎨
# # #     """
# # #     img = Image.new('RGB', (600, 350), color='#F1F8F3')  # Nền tối Slate đẹp mắt
# # #     draw = ImageDraw.Draw(img)
    
# # #     # Vẽ khung viền trang trí
# # #     draw.rectangle([15, 15, 585, 335], outline='#15803D', width=2)
    
# # #     # Vẽ các dòng chữ thông báo mặc định
# # #     draw.text((160, 130), "⚠️ CHUA CO DU LIEU DU BAO", fill='#B45309')
# # #     draw.text((110, 170), "Vui long nhan 'CHAY DU BAO AI' de tao anh NDVI!", fill='#5B7A66')
    
# # #     buf = io.BytesIO()
# # #     img.save(buf, format='PNG')
# # #     return buf.getvalue()


# # # def render_sidebar(df: pd.DataFrame = None):
# # #     """
# # #     Render Sidebar bộ lọc, cấu hình bản đồ và xuất dữ liệu CSV / PNG (Luôn sáng nút) 📊🖼️
# # #     """
# # #     # 🟢 Ưu tiên lấy df từ session_state nếu truyền vào bị None
# # #     if df is None or df.empty:
# # #         df = st.session_state.get("ndvi_df", None)

# # #     has_data = df is not None and not df.empty

# # #     with st.sidebar:

# # #         st.markdown("""
# # #             <div style='text-align: center; padding: 0 0 15px 0; border-bottom: 1px solid #D7E8DB; margin-bottom: 15px;'>
# # #                 <h2 style='color: #15803D; font-size: 1rem; font-weight: 700; margin: 0;'>🌐 GEO-NDVI Intelligence</h2>
# # #                 <p style='color: #5B7A66; font-size: 0.7rem; margin: 4px 0 0 0;'>AI & Remote Sensing Platform</p>
# # #             </div>
# # #         """, unsafe_allow_html=True)

# # #         st.markdown("### 🎛️ Bảng Điều Khiển")
        
# # #         with st.expander("🔮 BỘ LỌC DỰ BÁO", expanded=True):
# # #             selected_province = st.selectbox("Tỉnh / Thành phố:", list(LOCATION_DATA.keys()))
# # #             district_options = list(LOCATION_DATA[selected_province].keys())
# # #             selected_district = st.selectbox("Quận / Huyện / Phường:", district_options)
            
# # #             col_m, col_y = st.columns(2)
# # #             with col_m:
# # #                 selected_month = st.selectbox("Tháng:", list(range(1, 13)), index=8)
# # #             with col_y:
# # #                 selected_year = st.selectbox("Năm:", list(range(2017, 2028)), index=9)
                
# # #             selected_time = pd.to_datetime(f"{selected_year}-{selected_month:02d}-01")
# # #             btn_predict = st.button("🚀 CHẠY DỰ BÁO AI", use_container_width=True, type="primary")

# # #         with st.expander("⚙️ CẤU HÌNH BẢN ĐỒ", expanded=False):
# # #             basemap_choice = st.radio("Lớp bản đồ nền:", ["Esri Satellite", "Google Hybrid"])
# # #             show_boundaries = st.checkbox("🗺️ Hiển thị ranh giới (HCM-34)", value=True)

# # #         with st.expander("📊 XUẤT DỮ LIỆU & BÁO CÁO", expanded=False):
# # #             # 🟢 1. XUẤT FILE CSV
# # #             if has_data:
# # #                 csv_bytes = df.to_csv(index=False).encode('utf-8-sig')
# # #                 file_name_csv = f"ndvi_{selected_district}_{selected_year}_{selected_month:02d}.csv"
# # #             else:
# # #                 # File CSV mặc định khi chưa chạy dự báo
# # #                 csv_default = "Trạng_thái,Thông_báo\nCHƯA_DỰ_BÁO,Vui lòng nhấn 'CHẠY DỰ BÁO AI' trên ứng dụng để cập nhật dữ liệu NDVI mới nhất."
# # #                 csv_bytes = csv_default.encode('utf-8-sig')
# # #                 file_name_csv = f"ndvi_{selected_district}_mau_mac_dinh.csv"

# # #             btn_csv = st.download_button(
# # #                 label="📥 Xuất dữ liệu CSV",
# # #                 data=csv_bytes,
# # #                 file_name=file_name_csv,
# # #                 mime="text/csv",
# # #                 use_container_width=True,
# # #                 help="Click để tải dữ liệu CSV về máy"
# # #             )
# # #             if btn_csv and not has_data:
# # #                 st.toast("ℹ️ Bạn đã tải file CSV mẫu. Hãy nhấn '🚀 CHẠY DỰ BÁO AI' để có dữ liệu thực tế nhé!", icon="🔔")

# # #             # 🟢 2. XUẤT FILE ẢNH RASTER PNG (Sử dụng hàm xuất riêng biệt để không khoảng trắng)
# # #             png_bytes = None
# # #             if has_data:
# # #                 try:
# # #                     # 🌟 Thay hàm cũ bằng hàm export chuyên dụng để ảnh ôm khít, không bị dư khoảng trắng
# # #                     from utils.map_utils import generate_ndvi_raster_for_export
# # #                     png_bytes = generate_ndvi_raster_for_export(df)
# # #                 except Exception:
# # #                     png_bytes = None

# # #             if png_bytes is None:
# # #                 # Ảnh PNG mặc định khi chưa chạy dự báo
# # #                 png_bytes = create_placeholder_png()
# # #                 file_name_png = f"ndvi_map_{selected_district}_mac_dinh.png"
# # #             else:
# # #                 file_name_png = f"ndvi_map_{selected_district}_{selected_year}_{selected_month:02d}.png"
                
# # #             btn_png = st.download_button(
# # #                 label="🖼️ Xuất ảnh NDVI (.PNG)",
# # #                 data=png_bytes,
# # #                 file_name=file_name_png,
# # #                 mime="image/png",
# # #                 use_container_width=True,
# # #                 help="Click để tải ảnh NDVI PNG về máy"
# # #             )
# # #             if btn_png and not has_data:
# # #                 st.toast("ℹ️ Bạn vừa tải ảnh mẫu mặc định. Hãy bấm '🚀 CHẠY DỰ BÁO AI' để tạo bản đồ NDVI nhé!", icon="🖼️")

# # #             # if st.button("📄 Tạo báo cáo PDF", use_container_width=True):
# # #             #     st.info("Chức năng kết xuất PDF đang được xử lý.")

# # #     return selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict
