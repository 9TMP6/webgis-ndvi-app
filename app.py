import streamlit as st
import pandas as pd
from config import LOCATION_DATA
from utils.styles import CUSTOM_CSS
from utils.dark_theme import DARK_CSS, is_dark_theme
from components.layout import (
    APP_NAME, APP_FULL_NAME, SEO_DESCRIPTION,
    inject_ui_effects, render_header, render_section_title, render_footer, format_period,
)
from components.sidebar import render_sidebar, render_sidebar_export
from components.map_view import render_map
from components.metrics_view import render_metrics
from components.chart_view import render_chart_and_summary
from utils.data_loader import load_ndvi_data_with_ai_fallback

# 1. Cấu hình trang
st.set_page_config(
    layout="wide",
    page_title=f"{APP_NAME} | Dự báo chỉ số thực vật NDVI – TP. Hồ Chí Minh",
    page_icon="🌿",
    initial_sidebar_state="expanded",
    menu_items={"About": f"**{APP_NAME} – {APP_FULL_NAME}**\n\n{SEO_DESCRIPTION}"},
)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
if is_dark_theme():
    st.markdown(DARK_CSS, unsafe_allow_html=True)
inject_ui_effects()

# 2. Sidebar (gọi trước header để header hiển thị đúng mô hình đang chọn)
selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict, selected_model = render_sidebar()

# 3. Header
render_header(selected_model)

# 4. Session state
if "ndvi_df" not in st.session_state:
    st.session_state["ndvi_df"] = pd.DataFrame()
if "ndvi_is_ai" not in st.session_state:
    st.session_state["ndvi_is_ai"] = None
if "ndvi_period" not in st.session_state:
    st.session_state["ndvi_period"] = None
if "ndvi_model" not in st.session_state:
    st.session_state["ndvi_model"] = None

# 5. Chỉ truy vấn khi bấm nút "CHẠY DỰ BÁO AI"
if btn_predict:
    year, month = selected_time.year, selected_time.month

    # Các thông báo trạng thái (spinner, "đang chạy AI"...) chỉ hiện trong lúc xử lý, xong sẽ tự ẩn
    status_box = st.empty()
    with status_box.container():
        with st.spinner(f"Đang kiểm tra CSDL và chạy AI cho tháng {month}/{year}..."):
            df_result, is_ai_generated = load_ndvi_data_with_ai_fallback(year=year, month=month, model_name=selected_model)
    status_box.empty()

    st.session_state["ndvi_df"] = df_result
    st.session_state["ndvi_is_ai"] = is_ai_generated if not df_result.empty else None
    st.session_state["ndvi_period"] = selected_time if not df_result.empty else None
    st.session_state["ndvi_model"] = selected_model if not df_result.empty else None

    if df_result.empty:
        st.toast(f"Không thể tạo dữ liệu cho tháng {month}/{year}", icon="❌")
        st.warning(f"⚠️ Không có dữ liệu và không thể dự báo cho tháng **{month}/{year}**.")
    elif is_ai_generated:
        st.toast(f"AI đã dự báo thành công {len(df_result):,} ô lưới NDVI!", icon="")
    else:
        st.toast(f"Tải thành công {len(df_result):,} điểm NDVI từ CSDL!", icon="")

ndvi_df = st.session_state["ndvi_df"]

# Vẽ phần xuất CSV/PNG SAU khi dự báo để nút tải luôn lấy dữ liệu mới nhất
render_sidebar_export(selected_district, selected_time, ndvi_df)
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
    model=st.session_state["ndvi_model"],
)

if not has_data:
    st.markdown(
        "<div class='empty-hint'><b>Bắt đầu:</b> chọn khu vực, tháng và năm ở thanh bên trái, "
        "sau đó nhấn <b>Chạy dự báo AI</b> để hiển thị lớp NDVI trên bản đồ.</div>",
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

