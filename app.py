import streamlit as st
import pandas as pd
from config import LOCATION_DATA
from utils.styles import CUSTOM_CSS
from components.layout import (
    APP_NAME, APP_FULL_NAME, SEO_DESCRIPTION,
    inject_ui_effects, render_header, render_section_title, render_footer, format_period,
)
from components.sidebar import render_sidebar
from components.map_view import render_map
from components.metrics_view import render_metrics
from components.chart_view import render_chart_and_summary
from utils.data_loader import load_ndvi_data_with_ai_fallback

# 1. Cấu hình trang
st.set_page_config(
    layout="wide",
    page_title=f"{APP_NAME} | Giám sát và dự báo chỉ số thực vật NDVI – TP. Hồ Chí Minh",
    page_icon="🌿",
    initial_sidebar_state="expanded",
    menu_items={"About": f"**{APP_NAME} – {APP_FULL_NAME}**\n\n{SEO_DESCRIPTION}"},
)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
inject_ui_effects()

# 2. Header
render_header()

# 3. Sidebar
selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict = render_sidebar()

# 4. Session state
if "ndvi_df" not in st.session_state:
    st.session_state["ndvi_df"] = pd.DataFrame()
if "ndvi_is_ai" not in st.session_state:
    st.session_state["ndvi_is_ai"] = None
if "ndvi_period" not in st.session_state:
    st.session_state["ndvi_period"] = None

# 5. Chỉ truy vấn khi bấm nút "CHẠY DỰ BÁO AI"
if btn_predict:
    year, month = selected_time.year, selected_time.month

    with st.spinner(f"🌐 Đang kiểm tra CSDL và chạy AI cho tháng {month}/{year}..."):
        df_result, is_ai_generated = load_ndvi_data_with_ai_fallback(year=year, month=month)
        st.session_state["ndvi_df"] = df_result
        st.session_state["ndvi_is_ai"] = is_ai_generated if not df_result.empty else None
        st.session_state["ndvi_period"] = selected_time if not df_result.empty else None

        if df_result.empty:
            st.toast(f"Không thể tạo dữ liệu cho tháng {month}/{year}", icon="❌")
            st.warning(f"⚠️ Không có dữ liệu và không thể dự báo cho tháng **{month}/{year}**.")
        elif is_ai_generated:
            st.toast(f"AI đã dự báo thành công {len(df_result):,} ô lưới NDVI!", icon="🤖")
            st.success(f"🚀 **Dự báo AI:** Đã dự báo **{len(df_result):,}** ô lưới NDVI cho tháng **{month}/{year}** bằng mô hình `.onnx`.")
        else:
            st.toast(f"Tải thành công {len(df_result):,} điểm NDVI từ CSDL!", icon="🛰️")
            st.success(f"🎉 **Truy vấn thành công:** Đã tải **{len(df_result):,}** ô lưới NDVI từ CSDL Supabase.")

ndvi_df = st.session_state["ndvi_df"]
is_ai = st.session_state["ndvi_is_ai"]
data_period = st.session_state["ndvi_period"] or selected_time

# 6. Tọa độ khu vực chọn
lat, lng, zoom = LOCATION_DATA[selected_province][selected_district]

# 7. Khu vực bản đồ (ưu tiên chiếm diện tích lớn nhất)
area_label = "toàn TP. Hồ Chí Minh" if selected_district == "Toàn tỉnh/TP" else selected_district.strip()
has_data = not ndvi_df.empty

render_section_title(
    title=f"🛰️ Bản đồ phân bố NDVI tháng {format_period(data_period)} – {area_label}",
    subtitle="Bản đồ chỉ số thực vật theo ô lưới, kết hợp bảng chỉ số vùng và chú giải màu.",
    source=("ai" if is_ai else "db") if has_data else None,
)

if not has_data:
    st.markdown(
        "<div class='empty-hint'>👈 <b>Bắt đầu:</b> chọn khu vực, tháng và năm ở thanh bên trái, "
        "sau đó nhấn <b>🚀 Chạy dự báo AI</b> để hiển thị lớp NDVI trên bản đồ.</div>",
        unsafe_allow_html=True,
    )

col_map, col_metrics = st.columns([3.7, 1.0], gap="medium")
with col_map:
    render_map(
        lat, lng, zoom, basemap_choice, show_boundaries, df=ndvi_df,
        selected_time=data_period, selected_district=selected_district,
    )
with col_metrics:
    render_metrics(df=ndvi_df)

# 8. Biểu đồ & thống kê
render_chart_and_summary(selected_district, selected_province, selected_time, df=ndvi_df)

# 9. Footer
render_footer()



# import streamlit as st
# import pandas as pd
# from config import LOCATION_DATA, CUSTOM_CSS
# from components.sidebar import render_sidebar
# from components.map_view import render_map
# from components.metrics_view import render_metrics
# from components.chart_view import render_chart_and_summary
# from utils.data_loader import load_ndvi_data
# from utils.data_loader import load_ndvi_data_with_ai_fallback

# # 1. Cấu hình Trang
# st.set_page_config(layout="wide", page_title="GEO-NDVI INTELLIGENCE PLATFORM", page_icon="🌐", initial_sidebar_state="expanded")
# st.markdown("""
#     <style>
#         /* Chỉ thu hẹp chiều rộng khi sidebar đang mở (expanded) */
#         [data-testid="stSidebar"][aria-expanded="true"] {
#             width: 250px !important;
#             min-width: 250px !important;
#             max-width: 250px !important;
#         }
        
#         /* Đảm bảo khi bấm thu gọn (collapsed) thì nó ẩn hoàn toàn để màn hình chính tự chiếm full */
#         [data-testid="stSidebar"][aria-expanded="false"] {
#             width: 0px !important;
#             min-width: 0px !important;
#         }
#     </style>
# """, unsafe_allow_html=True)
# st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# # 2. Top Header
# st.markdown("""
#     <div class="top-header">
#         <div class="brand-title">🌐 GEO-NDVI INTELLIGENCE PLATFORM</div>
#         <div class="status-badge">🟢 AI ENGINE ONLINE</div>
#     </div>
# """, unsafe_allow_html=True)

# # 3. Sidebar (Đã khớp đủ 6 biến trả về từ render_sidebar)
# selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict = render_sidebar()

# # Khởi tạo session state lưu trữ dữ liệu
# if "ndvi_df" not in st.session_state:
#     st.session_state["ndvi_df"] = pd.DataFrame()

# # 4. Chỉ truy vấn CSDL khi bấm nút "🚀 CHẠY DỰ BÁO AI"
# if btn_predict:
#     year = selected_time.year
#     month = selected_time.month
    
#     with st.spinner(f"🌐 Đang kiểm tra CSDL và chạy AI Engine cho tháng {month}/{year}..."):
#         # Gọi hàm kiểm tra CSDL kết hợp suy luận ONNX tự động
#         df_result, is_ai_generated = load_ndvi_data_with_ai_fallback(year=year, month=month)
#         st.session_state["ndvi_df"] = df_result

#         # Thông báo trạng thái linh hoạt
#         if df_result.empty:
#             st.toast(f"⚠️ Không thể tạo dữ liệu cho tháng {month}/{year}", icon="❌")
#             st.warning(f"⚠️ Không có dữ liệu và không thể suy luận cho tháng **{month}/{year}**.")
#         else:
#             if is_ai_generated:
#                 st.toast(f"✨ AI Engine đã suy luận thành công {len(df_result):,} ô lưới NDVI bằng mô hình ONNX!", icon="🤖")
#                 st.success(f"🚀 **AI Prediction:** Đã dự báo thành công **{len(df_result):,}** ô tọa độ NDVI cho Tháng **{month}/{year}** bằng mô hình `.onnx`!")
#             else:
#                 st.toast(f"✅ Tải thành công {len(df_result):,} điểm NDVI từ CSDL!", icon="🛰️")
#                 st.success(f"🎉 **Truy vấn thành công:** Đã tải **{len(df_result):,}** ô tọa độ NDVI từ Supabase!")
# ndvi_df = st.session_state["ndvi_df"]

# # 5. Tọa độ chính
# lat, lng, zoom = LOCATION_DATA[selected_province][selected_district]

# # ==========================================
# # PHẦN GIAO DIỆN CHÍNH (ĐÃ BỔ SUNG TIÊU ĐỀ)
# # ==========================================

# st.markdown("---")
# st.markdown("### 🛰️ Không gian Trực quan hóa & Phân tích Vệ tinh")
# st.markdown("<p style='color: #94A3B8; font-size: 0.85rem; margin-top: -10px;'>Bản đồ phân bố chỉ số thực vật thời gian thực kết hợp bảng điều khiển thông số trọng yếu.</p>", unsafe_allow_html=True)

# # 6. Bản đồ & Chỉ số
# col_map, col_metrics = st.columns([3.3, 1.0])
# with col_map:
#         render_map(lat, lng, zoom, basemap_choice, show_boundaries, df=ndvi_df,
#                selected_time=selected_time, selected_district=selected_district)
#     #render_map(lat, lng, zoom, basemap_choice, show_boundaries, df=ndvi_df, selected_time=selected_time)
# with col_metrics:
#     render_metrics(df=ndvi_df) # 🟢 Đã truyền df=ndvi_df để cập nhật chỉ số động

# # 7. Biểu đồ AI & Thống kê
# render_chart_and_summary(selected_district, selected_province, selected_time, df=ndvi_df)
