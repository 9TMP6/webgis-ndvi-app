import streamlit as st
import pandas as pd
from config import LOCATION_DATA
from utils.styles import CUSTOM_CSS
from utils.dark_theme import DARK_CSS, is_dark_theme
from components.layout import (
    APP_NAME, APP_FULL_NAME, SEO_DESCRIPTION,
    inject_ui_effects, render_header, render_section_title, render_footer, format_period,
)
from components.sidebar import render_sidebar, render_sidebar_export, render_admin_panel
from components.map_view import render_map
from components.ward_panels import render_ndvi_range_filter, render_ward_ranking
from components.metrics_view import render_metrics
from components.chart_view import render_chart_and_summary
from components.compare_view import render_compare_view
from utils.data_loader import load_ndvi_data_with_ai_fallback, ModelError
from utils import ai_demo
from utils.db_writer import save_predictions
from utils.app_settings import get_force_ai
# True: ai chạy dự báo cũng tự lưu vào CSDL (ô trống) | False: chỉ admin mới tự lưu
AUTO_SAVE_FOR_CLIENTS = False

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

# 2. Session state
for k, v in (("ndvi_df", pd.DataFrame()), ("ndvi_is_ai", None), ("ndvi_period", None),
             ("ndvi_model", None), ("view_mode", "map"), ("is_admin", False)):
    if k not in st.session_state:
        st.session_state[k] = v
if st.session_state["view_mode"] == "compare" and not st.session_state["is_admin"]:
    st.session_state["view_mode"] = "map"

# 3. Sidebar (mô hình lấy từ CSDL: do admin chọn)
selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict, selected_model = render_sidebar()
force_ai = get_force_ai()
# 4. Header
render_header(selected_model)

# 5. Chỉ truy vấn khi bấm nút "CHẠY DỰ BÁO AI"
if btn_predict:
    st.session_state["view_mode"] = "map"   # đang ở màn so sánh thì quay lại bản đồ
    year, month = selected_time.year, selected_time.month

    status_box = st.empty()
    model_error = None
    with status_box.container():
        with st.spinner(f"Đang kiểm tra CSDL và chạy AI cho tháng {month}/{year}..."):
            try:
                df_result, is_ai_generated = load_ndvi_data_with_ai_fallback(year=year, month=month, model_name=selected_model, force_ai=force_ai)
            except ModelError as e:
                df_result, is_ai_generated = pd.DataFrame(), False
                model_error = str(e)
    status_box.empty()
    if model_error:
        st.error(f"❌ {model_error}")

    st.session_state["ndvi_df"] = df_result
    st.session_state["ndvi_is_ai"] = is_ai_generated if not df_result.empty else None
    st.session_state["ndvi_period"] = selected_time if not df_result.empty else None
    st.session_state["ndvi_model"] = selected_model if not df_result.empty else None

    if df_result.empty:
        st.toast(f"Không thể tạo dữ liệu cho tháng {month}/{year}", icon="❌")
        st.warning(f"⚠️ Không có dữ liệu và không thể dự báo cho tháng **{month}/{year}**.")
    elif is_ai_generated:
        st.toast(f"AI đã dự báo thành công {len(df_result):,} ô lưới NDVI!", icon="🤖")
        _, ai_report = ai_demo._forecast_cached(year, month, selected_model)
        st.session_state["ai_report"] = ai_report
        if AUTO_SAVE_FOR_CLIENTS or st.session_state["is_admin"]:
            save_res = save_predictions(df_result, selected_model, year, month, report=ai_report)
            st.toast(save_res["message"])
    else:
        st.toast(f"Tải thành công {len(df_result):,} điểm NDVI từ CSDL!", icon="✅")

ndvi_df = st.session_state["ndvi_df"]

# 6. Phần cuối sidebar (vẽ SAU khi dự báo để dùng dữ liệu mới nhất)
render_sidebar_export(selected_district, selected_time, ndvi_df)
render_admin_panel(ndvi_df)

is_ai = st.session_state["ndvi_is_ai"]
data_period = st.session_state["ndvi_period"] or selected_time

# Bộ lọc NDVI + bản đồ và bảng xếp hạng chạy trong "fragment": kéo thanh trượt hay đổi kiểu sắp xếp
# chỉ vẽ lại đúng khối đó, không chạy lại cả trang (bản Streamlit cũ không có fragment thì chạy lại cả trang như bình thường).
_fragment = getattr(st, "fragment", None) or getattr(st, "experimental_fragment", None) or (lambda f: f)


@_fragment
def _map_panel(lat, lng, zoom, basemap_choice, show_boundaries, ndvi_df, data_period, selected_district):
    """Bản đồ (trái) + chỉ số vùng, chú giải, bộ lọc NDVI (phải). Cả hai cột cùng nằm trong 1 fragment
    nên kéo thanh lọc chỉ vẽ lại khối này. Cột phải chạy TRƯỚC để có khoảng NDVI truyền cho bản đồ."""
    col_map, col_metrics = st.columns([3.7, 1.0], gap="medium")
    with col_metrics:
        render_metrics(df=ndvi_df)
        ndvi_range = render_ndvi_range_filter(ndvi_df)
    with col_map:
        render_map(lat, lng, zoom, basemap_choice, show_boundaries, df=ndvi_df,
                   selected_time=data_period, selected_district=selected_district, ndvi_range=ndvi_range)


@_fragment
def _ranking_panel(ndvi_df, data_period):
    render_ward_ranking(ndvi_df, format_period(data_period))


# 7. Nội dung bên phải: bản đồ hoặc so sánh mô hình
if st.session_state["view_mode"] == "compare":
    render_compare_view()
else:
    lat, lng, zoom = LOCATION_DATA[selected_province][selected_district]
    area_label = "toàn TP. Hồ Chí Minh" if selected_district == "Toàn tỉnh/TP" else selected_district.strip()
    has_data = not ndvi_df.empty

    shown_model = st.session_state["ndvi_model"]
    _rep = st.session_state.get("ai_report")
    if is_ai and _rep and _rep.get("backend") not in (None, "onnx"):
        shown_model = {"ridge": "Ridge (thuật toán dự phòng)", "persistence": "Persistence (giữ nguyên tháng trước)"}.get(
            _rep["backend"], _rep["backend"])

    render_section_title(
        title=f"🛰️ Bản đồ phân bố NDVI tháng {format_period(data_period)} – {area_label}",
        subtitle="Bản đồ chỉ số thực vật theo ô lưới, kết hợp bảng chỉ số vùng và chú giải màu.",
        source=("ai" if is_ai else "db") if has_data else None,
        model=shown_model,
    )

    if not has_data:
        st.markdown(
            "<div class='empty-hint'><b>Bắt đầu:</b> chọn khu vực, tháng và năm ở thanh bên trái, "
            "sau đó nhấn <b>Chạy dự báo AI</b> để hiển thị lớp NDVI trên bản đồ.</div>",
            unsafe_allow_html=True,
        )

    _map_panel(lat, lng, zoom, basemap_choice, show_boundaries, ndvi_df, data_period, selected_district)

    _ranking_panel(ndvi_df, data_period)     # bảng xếp hạng 167 phường/xã, đặt ngay trên biểu đồ 12 tháng
    render_chart_and_summary(selected_district, selected_province, selected_time, df=ndvi_df)

# 8. Footer
render_footer()


# import streamlit as st
# import pandas as pd
# from config import LOCATION_DATA
# from utils.styles import CUSTOM_CSS
# from utils.dark_theme import DARK_CSS, is_dark_theme
# from components.layout import (
#     APP_NAME, APP_FULL_NAME, SEO_DESCRIPTION,
#     inject_ui_effects, render_header, render_section_title, render_footer, format_period,
# )
# from components.sidebar import render_sidebar, render_sidebar_export, render_admin_panel
# from components.map_view import render_map
# from components.ward_panels import render_ndvi_range_filter, render_ward_ranking
# from components.metrics_view import render_metrics
# from components.chart_view import render_chart_and_summary
# from components.compare_view import render_compare_view
# from utils.data_loader import load_ndvi_data_with_ai_fallback, ModelError
# from utils import ai_demo
# from utils.db_writer import save_predictions
# from utils.app_settings import get_force_ai
# # True: ai chạy dự báo cũng tự lưu vào CSDL (ô trống) | False: chỉ admin mới tự lưu
# AUTO_SAVE_FOR_CLIENTS = False

# # 1. Cấu hình trang
# st.set_page_config(
#     layout="wide",
#     page_title=f"{APP_NAME} | Dự báo chỉ số thực vật NDVI – TP. Hồ Chí Minh",
#     page_icon="🌿",
#     initial_sidebar_state="expanded",
#     menu_items={"About": f"**{APP_NAME} – {APP_FULL_NAME}**\n\n{SEO_DESCRIPTION}"},
# )
# st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
# if is_dark_theme():
#     st.markdown(DARK_CSS, unsafe_allow_html=True)
# inject_ui_effects()

# # 2. Session state
# for k, v in (("ndvi_df", pd.DataFrame()), ("ndvi_is_ai", None), ("ndvi_period", None),
#              ("ndvi_model", None), ("view_mode", "map"), ("is_admin", False)):
#     if k not in st.session_state:
#         st.session_state[k] = v
# if st.session_state["view_mode"] == "compare" and not st.session_state["is_admin"]:
#     st.session_state["view_mode"] = "map"

# # 3. Sidebar (mô hình lấy từ CSDL: do admin chọn)
# selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict, selected_model = render_sidebar()
# force_ai = get_force_ai()
# # 4. Header
# render_header(selected_model)

# # 5. Chỉ truy vấn khi bấm nút "CHẠY DỰ BÁO AI"
# if btn_predict:
#     st.session_state["view_mode"] = "map"   # đang ở màn so sánh thì quay lại bản đồ
#     year, month = selected_time.year, selected_time.month

#     status_box = st.empty()
#     model_error = None
#     with status_box.container():
#         with st.spinner(f"Đang kiểm tra CSDL và chạy AI cho tháng {month}/{year}..."):
#             try:
#                 df_result, is_ai_generated = load_ndvi_data_with_ai_fallback(year=year, month=month, model_name=selected_model, force_ai=force_ai)
#             except ModelError as e:
#                 df_result, is_ai_generated = pd.DataFrame(), False
#                 model_error = str(e)
#     status_box.empty()
#     if model_error:
#         st.error(f"❌ {model_error}")

#     st.session_state["ndvi_df"] = df_result
#     st.session_state["ndvi_is_ai"] = is_ai_generated if not df_result.empty else None
#     st.session_state["ndvi_period"] = selected_time if not df_result.empty else None
#     st.session_state["ndvi_model"] = selected_model if not df_result.empty else None

#     if df_result.empty:
#         st.toast(f"Không thể tạo dữ liệu cho tháng {month}/{year}", icon="❌")
#         st.warning(f"⚠️ Không có dữ liệu và không thể dự báo cho tháng **{month}/{year}**.")
#     elif is_ai_generated:
#         st.toast(f"AI đã dự báo thành công {len(df_result):,} ô lưới NDVI!", icon="🤖")
#         _, ai_report = ai_demo._forecast_cached(year, month, selected_model)
#         st.session_state["ai_report"] = ai_report
#         if AUTO_SAVE_FOR_CLIENTS or st.session_state["is_admin"]:
#             save_res = save_predictions(df_result, selected_model, year, month, report=ai_report)
#             st.toast(save_res["message"])
#     else:
#         st.toast(f"Tải thành công {len(df_result):,} điểm NDVI từ CSDL!", icon="✅")

# ndvi_df = st.session_state["ndvi_df"]

# # 6. Phần cuối sidebar (vẽ SAU khi dự báo để dùng dữ liệu mới nhất)
# render_sidebar_export(selected_district, selected_time, ndvi_df)
# render_admin_panel(ndvi_df)

# is_ai = st.session_state["ndvi_is_ai"]
# data_period = st.session_state["ndvi_period"] or selected_time

# # Bộ lọc NDVI + bản đồ và bảng xếp hạng chạy trong "fragment": kéo thanh trượt hay đổi kiểu sắp xếp
# # chỉ vẽ lại đúng khối đó, không chạy lại cả trang (bản Streamlit cũ không có fragment thì chạy lại cả trang như bình thường).
# _fragment = getattr(st, "fragment", None) or getattr(st, "experimental_fragment", None) or (lambda f: f)


# @_fragment
# def _map_panel(lat, lng, zoom, basemap_choice, show_boundaries, ndvi_df, data_period, selected_district):
#     ndvi_range = render_ndvi_range_filter(ndvi_df)
#     render_map(lat, lng, zoom, basemap_choice, show_boundaries, df=ndvi_df,
#                selected_time=data_period, selected_district=selected_district, ndvi_range=ndvi_range)


# @_fragment
# def _ranking_panel(ndvi_df, data_period):
#     render_ward_ranking(ndvi_df, format_period(data_period))


# # 7. Nội dung bên phải: bản đồ hoặc so sánh mô hình
# if st.session_state["view_mode"] == "compare":
#     render_compare_view()
# else:
#     lat, lng, zoom = LOCATION_DATA[selected_province][selected_district]
#     area_label = "toàn TP. Hồ Chí Minh" if selected_district == "Toàn tỉnh/TP" else selected_district.strip()
#     has_data = not ndvi_df.empty

#     shown_model = st.session_state["ndvi_model"]
#     _rep = st.session_state.get("ai_report")
#     if is_ai and _rep and _rep.get("backend") not in (None, "onnx"):
#         shown_model = {"ridge": "Ridge (thuật toán dự phòng)", "persistence": "Persistence (giữ nguyên tháng trước)"}.get(
#             _rep["backend"], _rep["backend"])

#     render_section_title(
#         title=f"🛰️ Bản đồ phân bố NDVI tháng {format_period(data_period)} – {area_label}",
#         subtitle="Bản đồ chỉ số thực vật theo ô lưới, kết hợp bảng chỉ số vùng và chú giải màu.",
#         source=("ai" if is_ai else "db") if has_data else None,
#         model=shown_model,
#     )

#     if not has_data:
#         st.markdown(
#             "<div class='empty-hint'><b>Bắt đầu:</b> chọn khu vực, tháng và năm ở thanh bên trái, "
#             "sau đó nhấn <b>Chạy dự báo AI</b> để hiển thị lớp NDVI trên bản đồ.</div>",
#             unsafe_allow_html=True,
#         )

#     col_map, col_metrics = st.columns([3.7, 1.0], gap="medium")
#     with col_map:
#         _map_panel(lat, lng, zoom, basemap_choice, show_boundaries, ndvi_df, data_period, selected_district)
#     with col_metrics:
#         render_metrics(df=ndvi_df)

#     _ranking_panel(ndvi_df, data_period)     # bảng xếp hạng 167 phường/xã, đặt ngay trên biểu đồ 12 tháng
#     render_chart_and_summary(selected_district, selected_province, selected_time, df=ndvi_df)

# # 8. Footer
# render_footer()





# # import streamlit as st
# # import pandas as pd
# # from config import LOCATION_DATA
# # from utils.styles import CUSTOM_CSS
# # from utils.dark_theme import DARK_CSS, is_dark_theme
# # from components.layout import (
# #     APP_NAME, APP_FULL_NAME, SEO_DESCRIPTION,
# #     inject_ui_effects, render_header, render_section_title, render_footer, format_period,
# # )
# # from components.sidebar import render_sidebar, render_sidebar_export, render_admin_panel
# # from components.map_view import render_map
# # from components.metrics_view import render_metrics
# # from components.chart_view import render_chart_and_summary
# # from components.compare_view import render_compare_view
# # from utils.data_loader import load_ndvi_data_with_ai_fallback, ModelError
# # from utils import ai_demo
# # from utils.db_writer import save_predictions
# # from utils.app_settings import get_force_ai
# # # True: ai chạy dự báo cũng tự lưu vào CSDL (ô trống) | False: chỉ admin mới tự lưu
# # AUTO_SAVE_FOR_CLIENTS = False

# # # 1. Cấu hình trang
# # st.set_page_config(
# #     layout="wide",
# #     page_title=f"{APP_NAME} | Dự báo chỉ số thực vật NDVI – TP. Hồ Chí Minh",
# #     page_icon="🌿",
# #     initial_sidebar_state="expanded",
# #     menu_items={"About": f"**{APP_NAME} – {APP_FULL_NAME}**\n\n{SEO_DESCRIPTION}"},
# # )
# # st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
# # if is_dark_theme():
# #     st.markdown(DARK_CSS, unsafe_allow_html=True)
# # inject_ui_effects()

# # # 2. Session state
# # for k, v in (("ndvi_df", pd.DataFrame()), ("ndvi_is_ai", None), ("ndvi_period", None),
# #              ("ndvi_model", None), ("view_mode", "map"), ("is_admin", False)):
# #     if k not in st.session_state:
# #         st.session_state[k] = v
# # if st.session_state["view_mode"] == "compare" and not st.session_state["is_admin"]:
# #     st.session_state["view_mode"] = "map"

# # # 3. Sidebar (mô hình lấy từ CSDL: do admin chọn)
# # selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict, selected_model = render_sidebar()
# # force_ai = get_force_ai()
# # # 4. Header
# # render_header(selected_model)

# # # 5. Chỉ truy vấn khi bấm nút "CHẠY DỰ BÁO AI"
# # if btn_predict:
# #     st.session_state["view_mode"] = "map"   # đang ở màn so sánh thì quay lại bản đồ
# #     year, month = selected_time.year, selected_time.month

# #     status_box = st.empty()
# #     model_error = None
# #     with status_box.container():
# #         with st.spinner(f"Đang kiểm tra CSDL và chạy AI cho tháng {month}/{year}..."):
# #             try:
# #                 df_result, is_ai_generated = load_ndvi_data_with_ai_fallback(year=year, month=month, model_name=selected_model, force_ai=force_ai)
# #             except ModelError as e:
# #                 df_result, is_ai_generated = pd.DataFrame(), False
# #                 model_error = str(e)
# #     status_box.empty()
# #     if model_error:
# #         st.error(f"❌ {model_error}")

# #     st.session_state["ndvi_df"] = df_result
# #     st.session_state["ndvi_is_ai"] = is_ai_generated if not df_result.empty else None
# #     st.session_state["ndvi_period"] = selected_time if not df_result.empty else None
# #     st.session_state["ndvi_model"] = selected_model if not df_result.empty else None

# #     if df_result.empty:
# #         st.toast(f"Không thể tạo dữ liệu cho tháng {month}/{year}", icon="❌")
# #         st.warning(f"⚠️ Không có dữ liệu và không thể dự báo cho tháng **{month}/{year}**.")
# #     elif is_ai_generated:
# #         st.toast(f"AI đã dự báo thành công {len(df_result):,} ô lưới NDVI!", icon="🤖")
# #         _, ai_report = ai_demo._forecast_cached(year, month, selected_model)
# #         st.session_state["ai_report"] = ai_report
# #         if AUTO_SAVE_FOR_CLIENTS or st.session_state["is_admin"]:
# #             save_res = save_predictions(df_result, selected_model, year, month, report=ai_report)
# #             st.toast(save_res["message"])
# #     else:
# #         st.toast(f"Tải thành công {len(df_result):,} điểm NDVI từ CSDL!", icon="✅")

# # ndvi_df = st.session_state["ndvi_df"]

# # # 6. Phần cuối sidebar (vẽ SAU khi dự báo để dùng dữ liệu mới nhất)
# # render_sidebar_export(selected_district, selected_time, ndvi_df)
# # render_admin_panel(ndvi_df)

# # is_ai = st.session_state["ndvi_is_ai"]
# # data_period = st.session_state["ndvi_period"] or selected_time

# # # 7. Nội dung bên phải: bản đồ hoặc so sánh mô hình
# # if st.session_state["view_mode"] == "compare":
# #     render_compare_view()
# # else:
# #     lat, lng, zoom = LOCATION_DATA[selected_province][selected_district]
# #     area_label = "toàn TP. Hồ Chí Minh" if selected_district == "Toàn tỉnh/TP" else selected_district.strip()
# #     has_data = not ndvi_df.empty

# #     shown_model = st.session_state["ndvi_model"]
# #     _rep = st.session_state.get("ai_report")
# #     if is_ai and _rep and _rep.get("backend") not in (None, "onnx"):
# #         shown_model = {"ridge": "Ridge (thuật toán dự phòng)", "persistence": "Persistence (giữ nguyên tháng trước)"}.get(
# #             _rep["backend"], _rep["backend"])

# #     render_section_title(
# #         title=f"🛰️ Bản đồ phân bố NDVI tháng {format_period(data_period)} – {area_label}",
# #         subtitle="Bản đồ chỉ số thực vật theo ô lưới, kết hợp bảng chỉ số vùng và chú giải màu.",
# #         source=("ai" if is_ai else "db") if has_data else None,
# #         model=shown_model,
# #     )

# #     if not has_data:
# #         st.markdown(
# #             "<div class='empty-hint'><b>Bắt đầu:</b> chọn khu vực, tháng và năm ở thanh bên trái, "
# #             "sau đó nhấn <b>Chạy dự báo AI</b> để hiển thị lớp NDVI trên bản đồ.</div>",
# #             unsafe_allow_html=True,
# #         )

# #     col_map, col_metrics = st.columns([3.7, 1.0], gap="medium")
# #     with col_map:
# #         render_map(lat, lng, zoom, basemap_choice, show_boundaries, df=ndvi_df,
# #                    selected_time=data_period, selected_district=selected_district)
# #     with col_metrics:
# #         render_metrics(df=ndvi_df)

# #     render_chart_and_summary(selected_district, selected_province, selected_time, df=ndvi_df)

# # # 8. Footer
# # render_footer()



# # # import streamlit as st
# # # import pandas as pd
# # # from config import LOCATION_DATA
# # # from utils.styles import CUSTOM_CSS
# # # from utils.dark_theme import DARK_CSS, is_dark_theme
# # # from components.layout import (
# # #     APP_NAME, APP_FULL_NAME, SEO_DESCRIPTION,
# # #     inject_ui_effects, render_header, render_section_title, render_footer, format_period,
# # # )
# # # from components.sidebar import render_sidebar, render_sidebar_export
# # # from components.map_view import render_map
# # # from components.metrics_view import render_metrics
# # # from components.chart_view import render_chart_and_summary
# # # from utils.data_loader import load_ndvi_data_with_ai_fallback, ModelError
# # # from utils import ai_demo
# # # from utils.db_writer import save_predictions
# # # import hmac

# # # # 1. Cấu hình trang
# # # st.set_page_config(
# # #     layout="wide",
# # #     page_title=f"{APP_NAME} | Dự báo chỉ số thực vật NDVI – TP. Hồ Chí Minh",
# # #     page_icon="🌿",
# # #     initial_sidebar_state="expanded",
# # #     menu_items={"About": f"**{APP_NAME} – {APP_FULL_NAME}**\n\n{SEO_DESCRIPTION}"},
# # # )
# # # st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
# # # if is_dark_theme():
# # #     st.markdown(DARK_CSS, unsafe_allow_html=True)
# # # inject_ui_effects()

# # # # 2. Sidebar (gọi trước header để header hiển thị đúng mô hình đang chọn)
# # # selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict, selected_model = render_sidebar()

# # # # 3. Header
# # # render_header(selected_model)

# # # # 4. Session state
# # # if "ndvi_df" not in st.session_state:
# # #     st.session_state["ndvi_df"] = pd.DataFrame()
# # # if "ndvi_is_ai" not in st.session_state:
# # #     st.session_state["ndvi_is_ai"] = None
# # # if "ndvi_period" not in st.session_state:
# # #     st.session_state["ndvi_period"] = None
# # # if "ndvi_model" not in st.session_state:
# # #     st.session_state["ndvi_model"] = None

# # # # 5. Chỉ truy vấn khi bấm nút "CHẠY DỰ BÁO AI"
# # # if btn_predict:
# # #     year, month = selected_time.year, selected_time.month

# # #     # Các thông báo trạng thái (spinner, "đang chạy AI"...) chỉ hiện trong lúc xử lý, xong sẽ tự ẩn
# # #     status_box = st.empty()
# # #     model_error = None
# # #     with status_box.container():
# # #         with st.spinner(f"Đang kiểm tra CSDL và chạy AI cho tháng {month}/{year}..."):
# # #             try:
# # #                 df_result, is_ai_generated = load_ndvi_data_with_ai_fallback(year=year, month=month, model_name=selected_model)
# # #             except ModelError as e:
# # #                 df_result, is_ai_generated = pd.DataFrame(), False
# # #                 model_error = str(e)
# # #     status_box.empty()
# # #     if model_error:
# # #         st.error(f"❌ {model_error}")

# # #     st.session_state["ndvi_df"] = df_result
# # #     st.session_state["ndvi_is_ai"] = is_ai_generated if not df_result.empty else None
# # #     st.session_state["ndvi_period"] = selected_time if not df_result.empty else None
# # #     st.session_state["ndvi_model"] = selected_model if not df_result.empty else None

# # #     if df_result.empty:
# # #         st.toast(f"Không thể tạo dữ liệu cho tháng {month}/{year}", icon="❌")
# # #         st.warning(f"⚠️ Không có dữ liệu và không thể dự báo cho tháng **{month}/{year}**.")
# # #     elif is_ai_generated:
# # #         st.toast(f"AI đã dự báo thành công {len(df_result):,} ô lưới NDVI!", icon="")
# # #         # Lấy báo cáo của lần chạy này (đã được cache nên không chạy lại AI) để biết backend thật sự là gì
# # #         _, ai_report = ai_demo._forecast_cached(year, month, selected_model)
# # #         st.session_state["ai_report"] = ai_report
# # #         # Tự động lưu: bỏ qua nếu CSDL đã có, và không lưu nếu kết quả không phải do mô hình ONNX tạo ra
# # #         save_res = save_predictions(df_result, selected_model, year, month, report=ai_report)
# # #         st.toast(save_res["message"])
# # #     else:
# # #         st.toast(f"Tải thành công {len(df_result):,} điểm NDVI từ CSDL!", icon="")

# # # ndvi_df = st.session_state["ndvi_df"]

# # # # Vẽ phần xuất CSV/PNG SAU khi dự báo để nút tải luôn lấy dữ liệu mới nhất
# # # render_sidebar_export(selected_district, selected_time, ndvi_df)

# # # # Nút ghi đè vào CSDL: chỉ hiện khi đang xem kết quả AI, và cần mật khẩu quản trị
# # # if st.session_state.get("ndvi_is_ai") and st.session_state.get("ai_report") is not None:
# # #     with st.sidebar.expander("Lưu kết quả vào CSDL", expanded=False):
# # #         try:
# # #             admin_pw = st.secrets.get("admin_password", None)
# # #         except Exception:
# # #             admin_pw = None
# # #         if not admin_pw:
# # #             st.caption("Chưa cấu hình `admin_password` trong secrets nên tính năng ghi đè đang tắt.")
# # #         else:
# # #             st.caption("Ghi đè dự đoán của mô hình đang xem lên CSDL (dù đã có hay chưa).")
# # #             typed_pw = st.text_input("Mật khẩu quản trị", type="password", key="admin_pw_input")
# # #             if st.button("Ghi đè vào CSDL", use_container_width=True, key="btn_overwrite_db"):
# # #                 if hmac.compare_digest(str(typed_pw), str(admin_pw)):
# # #                     _per = st.session_state["ndvi_period"]
# # #                     res = save_predictions(
# # #                         ndvi_df, st.session_state["ndvi_model"], _per.year, _per.month,
# # #                         report=st.session_state["ai_report"], overwrite=True,
# # #                     )
# # #                     (st.success if res["status"] == "saved" else st.warning)(res["message"])
# # #                 else:
# # #                     st.error("Sai mật khẩu.")
# # # is_ai = st.session_state["ndvi_is_ai"]
# # # data_period = st.session_state["ndvi_period"] or selected_time

# # # # 6. Tọa độ khu vực chọn
# # # lat, lng, zoom = LOCATION_DATA[selected_province][selected_district]

# # # # 7. Khu vực bản đồ (ưu tiên chiếm diện tích lớn nhất)
# # # area_label = "toàn TP. Hồ Chí Minh" if selected_district == "Toàn tỉnh/TP" else selected_district.strip()
# # # has_data = not ndvi_df.empty

# # # # Kết quả AI luôn do mô hình đã chọn tạo ra
# # # shown_model = st.session_state["ndvi_model"]
# # # quality_note = None
# # # _rep = st.session_state.get("ai_report")
# # # if is_ai and _rep and _rep.get("backend") not in (None, "onnx"):
# # #     shown_model = {"ridge": "Ridge (thuật toán dự phòng)", "persistence": "Persistence (giữ nguyên tháng trước)"}.get(
# # #         _rep["backend"], _rep["backend"])
# # # # if is_ai and _rep:
# # # #     quality_note = (
# # # #         f"Dựa trên tháng dữ liệu {_rep.get('base_month')}, dự báo {_rep.get('steps')} bước; "
# # # #         f"{_rep.get('n_fallback', 0)}/{_rep.get('n_grids')} ô mẫu thiếu dữ liệu nên dùng giá trị gần nhất có hiệu chỉnh mùa vụ."
# # # #     )

# # # render_section_title(
# # #     title=f"🛰️ Bản đồ phân bố NDVI tháng {format_period(data_period)} – {area_label}",
# # #     subtitle="Bản đồ chỉ số thực vật theo ô lưới, kết hợp bảng chỉ số vùng và chú giải màu.",
# # #     source=("ai" if is_ai else "db") if has_data else None,
# # #     model=shown_model,
# # # )

# # # if quality_note:
# # #     st.caption(quality_note)

# # # if not has_data:
# # #     st.markdown(
# # #         "<div class='empty-hint'><b>Bắt đầu:</b> chọn khu vực, tháng và năm ở thanh bên trái, "
# # #         "sau đó nhấn <b>Chạy dự báo AI</b> để hiển thị lớp NDVI trên bản đồ.</div>",
# # #         unsafe_allow_html=True,
# # #     )

# # # col_map, col_metrics = st.columns([3.7, 1.0], gap="medium")
# # # with col_map:
# # #     render_map(
# # #         lat, lng, zoom, basemap_choice, show_boundaries, df=ndvi_df,
# # #         selected_time=data_period, selected_district=selected_district,
# # #     )
# # # with col_metrics:
# # #     render_metrics(df=ndvi_df)

# # # # 8. Biểu đồ & thống kê
# # # render_chart_and_summary(selected_district, selected_province, selected_time, df=ndvi_df)

# # # # 9. Footer
# # # render_footer()


# # # # import streamlit as st
# # # # import pandas as pd
# # # # from config import LOCATION_DATA
# # # # from utils.styles import CUSTOM_CSS
# # # # from utils.dark_theme import DARK_CSS, is_dark_theme
# # # # from components.layout import (
# # # #     APP_NAME, APP_FULL_NAME, SEO_DESCRIPTION,
# # # #     inject_ui_effects, render_header, render_section_title, render_footer, format_period,
# # # # )
# # # # from components.sidebar import render_sidebar, render_sidebar_export
# # # # from components.map_view import render_map
# # # # from components.metrics_view import render_metrics
# # # # from components.chart_view import render_chart_and_summary
# # # # from utils.data_loader import load_ndvi_data_with_ai_fallback, ModelError
# # # # from utils import ai_demo
# # # # from utils.db_writer import save_predictions
# # # # import hmac

# # # # # 1. Cấu hình trang
# # # # st.set_page_config(
# # # #     layout="wide",
# # # #     page_title=f"{APP_NAME} | Dự báo chỉ số thực vật NDVI – TP. Hồ Chí Minh",
# # # #     page_icon="🌿",
# # # #     initial_sidebar_state="expanded",
# # # #     menu_items={"About": f"**{APP_NAME} – {APP_FULL_NAME}**\n\n{SEO_DESCRIPTION}"},
# # # # )
# # # # st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
# # # # if is_dark_theme():
# # # #     st.markdown(DARK_CSS, unsafe_allow_html=True)
# # # # inject_ui_effects()

# # # # # 2. Sidebar (gọi trước header để header hiển thị đúng mô hình đang chọn)
# # # # selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict, selected_model = render_sidebar()

# # # # # 3. Header
# # # # render_header(selected_model)

# # # # # 4. Session state
# # # # if "ndvi_df" not in st.session_state:
# # # #     st.session_state["ndvi_df"] = pd.DataFrame()
# # # # if "ndvi_is_ai" not in st.session_state:
# # # #     st.session_state["ndvi_is_ai"] = None
# # # # if "ndvi_period" not in st.session_state:
# # # #     st.session_state["ndvi_period"] = None
# # # # if "ndvi_model" not in st.session_state:
# # # #     st.session_state["ndvi_model"] = None

# # # # # 5. Chỉ truy vấn khi bấm nút "CHẠY DỰ BÁO AI"
# # # # if btn_predict:
# # # #     year, month = selected_time.year, selected_time.month

# # # #     # Các thông báo trạng thái (spinner, "đang chạy AI"...) chỉ hiện trong lúc xử lý, xong sẽ tự ẩn
# # # #     status_box = st.empty()
# # # #     model_error = None
# # # #     with status_box.container():
# # # #         with st.spinner(f"Đang kiểm tra CSDL và chạy AI cho tháng {month}/{year}..."):
# # # #             try:
# # # #                 df_result, is_ai_generated = load_ndvi_data_with_ai_fallback(year=year, month=month, model_name=selected_model)
# # # #             except ModelError as e:
# # # #                 df_result, is_ai_generated = pd.DataFrame(), False
# # # #                 model_error = str(e)
# # # #     status_box.empty()
# # # #     if model_error:
# # # #         st.error(f"❌ {model_error}")

# # # #     st.session_state["ndvi_df"] = df_result
# # # #     st.session_state["ndvi_is_ai"] = is_ai_generated if not df_result.empty else None
# # # #     st.session_state["ndvi_period"] = selected_time if not df_result.empty else None
# # # #     st.session_state["ndvi_model"] = selected_model if not df_result.empty else None

# # # #     if df_result.empty:
# # # #         st.toast(f"Không thể tạo dữ liệu cho tháng {month}/{year}", icon="❌")
# # # #         st.warning(f"⚠️ Không có dữ liệu và không thể dự báo cho tháng **{month}/{year}**.")
# # # #     elif is_ai_generated:
# # # #         st.toast(f"AI đã dự báo thành công {len(df_result):,} ô lưới NDVI!", icon="")
# # # #         # Lấy báo cáo của lần chạy này (đã được cache nên không chạy lại AI) để biết backend thật sự là gì
# # # #         _, ai_report = ai_demo._forecast_cached(year, month, selected_model)
# # # #         st.session_state["ai_report"] = ai_report
# # # #         # Tự động lưu: bỏ qua nếu CSDL đã có, và không lưu nếu kết quả không phải do mô hình ONNX tạo ra
# # # #         save_res = save_predictions(df_result, selected_model, year, month, report=ai_report)
# # # #         st.toast(save_res["message"])
# # # #     else:
# # # #         st.toast(f"Tải thành công {len(df_result):,} điểm NDVI từ CSDL!", icon="")

# # # # ndvi_df = st.session_state["ndvi_df"]

# # # # # Vẽ phần xuất CSV/PNG SAU khi dự báo để nút tải luôn lấy dữ liệu mới nhất
# # # # render_sidebar_export(selected_district, selected_time, ndvi_df)

# # # # # Nút ghi đè vào CSDL: chỉ hiện khi đang xem kết quả AI, và cần mật khẩu quản trị
# # # # if st.session_state.get("ndvi_is_ai") and st.session_state.get("ai_report") is not None:
# # # #     with st.sidebar.expander("Lưu kết quả vào CSDL", expanded=False):
# # # #         try:
# # # #             admin_pw = st.secrets.get("admin_password", None)
# # # #         except Exception:
# # # #             admin_pw = None
# # # #         if not admin_pw:
# # # #             st.caption("Chưa cấu hình `admin_password` trong secrets nên tính năng ghi đè đang tắt.")
# # # #         else:
# # # #             st.caption("Ghi đè dự đoán của mô hình đang xem lên CSDL (dù đã có hay chưa).")
# # # #             typed_pw = st.text_input("Mật khẩu quản trị", type="password", key="admin_pw_input")
# # # #             if st.button("Ghi đè vào CSDL", use_container_width=True, key="btn_overwrite_db"):
# # # #                 if hmac.compare_digest(str(typed_pw), str(admin_pw)):
# # # #                     _per = st.session_state["ndvi_period"]
# # # #                     res = save_predictions(
# # # #                         ndvi_df, st.session_state["ndvi_model"], _per.year, _per.month,
# # # #                         report=st.session_state["ai_report"], overwrite=True,
# # # #                     )
# # # #                     (st.success if res["status"] == "saved" else st.warning)(res["message"])
# # # #                 else:
# # # #                     st.error("Sai mật khẩu.")
# # # # is_ai = st.session_state["ndvi_is_ai"]
# # # # data_period = st.session_state["ndvi_period"] or selected_time

# # # # # 6. Tọa độ khu vực chọn
# # # # lat, lng, zoom = LOCATION_DATA[selected_province][selected_district]

# # # # # 7. Khu vực bản đồ (ưu tiên chiếm diện tích lớn nhất)
# # # # area_label = "toàn TP. Hồ Chí Minh" if selected_district == "Toàn tỉnh/TP" else selected_district.strip()
# # # # has_data = not ndvi_df.empty

# # # # # Kết quả AI luôn do mô hình đã chọn tạo ra
# # # # shown_model = st.session_state["ndvi_model"]
# # # # quality_note = None
# # # # _rep = st.session_state.get("ai_report")
# # # # if is_ai and _rep and _rep.get("backend") not in (None, "onnx"):
# # # #     shown_model = {"ridge": "Ridge (thuật toán dự phòng)", "persistence": "Persistence (giữ nguyên tháng trước)"}.get(
# # # #         _rep["backend"], _rep["backend"])
# # # # if is_ai and _rep:
# # # #     quality_note = (
# # # #         f"Dựa trên tháng dữ liệu {_rep.get('base_month')}, dự báo {_rep.get('steps')} bước; "
# # # #         f"{_rep.get('n_fallback', 0)}/{_rep.get('n_grids')} ô mẫu thiếu dữ liệu nên dùng giá trị gần nhất có hiệu chỉnh mùa vụ."
# # # #     )

# # # # render_section_title(
# # # #     title=f"🛰️ Bản đồ phân bố NDVI tháng {format_period(data_period)} – {area_label}",
# # # #     subtitle="Bản đồ chỉ số thực vật theo ô lưới, kết hợp bảng chỉ số vùng và chú giải màu.",
# # # #     source=("ai" if is_ai else "db") if has_data else None,
# # # #     model=shown_model,
# # # # )

# # # # if quality_note:
# # # #     st.caption(quality_note)

# # # # if not has_data:
# # # #     st.markdown(
# # # #         "<div class='empty-hint'><b>Bắt đầu:</b> chọn khu vực, tháng và năm ở thanh bên trái, "
# # # #         "sau đó nhấn <b>Chạy dự báo AI</b> để hiển thị lớp NDVI trên bản đồ.</div>",
# # # #         unsafe_allow_html=True,
# # # #     )

# # # # col_map, col_metrics = st.columns([3.7, 1.0], gap="medium")
# # # # with col_map:
# # # #     render_map(
# # # #         lat, lng, zoom, basemap_choice, show_boundaries, df=ndvi_df,
# # # #         selected_time=data_period, selected_district=selected_district,
# # # #     )
# # # # with col_metrics:
# # # #     render_metrics(df=ndvi_df)

# # # # # 8. Biểu đồ & thống kê
# # # # render_chart_and_summary(selected_district, selected_province, selected_time, df=ndvi_df)

# # # # # 9. Footer
# # # # render_footer()




# # # # import streamlit as st
# # # # import pandas as pd
# # # # from config import LOCATION_DATA
# # # # from utils.styles import CUSTOM_CSS
# # # # from utils.dark_theme import DARK_CSS, is_dark_theme
# # # # from components.layout import (
# # # #     APP_NAME, APP_FULL_NAME, SEO_DESCRIPTION,
# # # #     inject_ui_effects, render_header, render_section_title, render_footer, format_period,
# # # # )
# # # # from components.sidebar import render_sidebar, render_sidebar_export
# # # # from components.map_view import render_map
# # # # from components.metrics_view import render_metrics
# # # # from components.chart_view import render_chart_and_summary
# # # # from utils.data_loader import load_ndvi_data_with_ai_fallback
# # # # from utils import ai_demo
# # # # from utils.db_writer import save_predictions
# # # # import hmac

# # # # # 1. Cấu hình trang
# # # # st.set_page_config(
# # # #     layout="wide",
# # # #     page_title=f"{APP_NAME} | Dự báo chỉ số thực vật NDVI – TP. Hồ Chí Minh",
# # # #     page_icon="🌿",
# # # #     initial_sidebar_state="expanded",
# # # #     menu_items={"About": f"**{APP_NAME} – {APP_FULL_NAME}**\n\n{SEO_DESCRIPTION}"},
# # # # )
# # # # st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
# # # # if is_dark_theme():
# # # #     st.markdown(DARK_CSS, unsafe_allow_html=True)
# # # # inject_ui_effects()

# # # # # 2. Sidebar (gọi trước header để header hiển thị đúng mô hình đang chọn)
# # # # selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict, selected_model = render_sidebar()

# # # # # 3. Header
# # # # render_header(selected_model)

# # # # # 4. Session state
# # # # if "ndvi_df" not in st.session_state:
# # # #     st.session_state["ndvi_df"] = pd.DataFrame()
# # # # if "ndvi_is_ai" not in st.session_state:
# # # #     st.session_state["ndvi_is_ai"] = None
# # # # if "ndvi_period" not in st.session_state:
# # # #     st.session_state["ndvi_period"] = None
# # # # if "ndvi_model" not in st.session_state:
# # # #     st.session_state["ndvi_model"] = None

# # # # # 5. Chỉ truy vấn khi bấm nút "CHẠY DỰ BÁO AI"
# # # # if btn_predict:
# # # #     year, month = selected_time.year, selected_time.month

# # # #     # Các thông báo trạng thái (spinner, "đang chạy AI"...) chỉ hiện trong lúc xử lý, xong sẽ tự ẩn
# # # #     status_box = st.empty()
# # # #     with status_box.container():
# # # #         with st.spinner(f"Đang kiểm tra CSDL và chạy AI cho tháng {month}/{year}..."):
# # # #             df_result, is_ai_generated = load_ndvi_data_with_ai_fallback(year=year, month=month, model_name=selected_model)
# # # #     status_box.empty()

# # # #     st.session_state["ndvi_df"] = df_result
# # # #     st.session_state["ndvi_is_ai"] = is_ai_generated if not df_result.empty else None
# # # #     st.session_state["ndvi_period"] = selected_time if not df_result.empty else None
# # # #     st.session_state["ndvi_model"] = selected_model if not df_result.empty else None

# # # #     if df_result.empty:
# # # #         st.toast(f"Không thể tạo dữ liệu cho tháng {month}/{year}", icon="❌")
# # # #         st.warning(f"⚠️ Không có dữ liệu và không thể dự báo cho tháng **{month}/{year}**.")
# # # #     elif is_ai_generated:
# # # #         st.toast(f"AI đã dự báo thành công {len(df_result):,} ô lưới NDVI!", icon="")
# # # #         # Lấy báo cáo của lần chạy này (đã được cache nên không chạy lại AI) để biết backend thật sự là gì
# # # #         _, ai_report = ai_demo._forecast_cached(year, month, selected_model)
# # # #         st.session_state["ai_report"] = ai_report
# # # #         # Tự động lưu: bỏ qua nếu CSDL đã có, và không lưu nếu kết quả không phải do mô hình ONNX tạo ra
# # # #         save_res = save_predictions(df_result, selected_model, year, month, report=ai_report)
# # # #         st.toast(save_res["message"])
# # # #     else:
# # # #         st.toast(f"Tải thành công {len(df_result):,} điểm NDVI từ CSDL!", icon="")

# # # # ndvi_df = st.session_state["ndvi_df"]

# # # # # Vẽ phần xuất CSV/PNG SAU khi dự báo để nút tải luôn lấy dữ liệu mới nhất
# # # # render_sidebar_export(selected_district, selected_time, ndvi_df)

# # # # # Nút ghi đè vào CSDL: chỉ hiện khi đang xem kết quả AI, và cần mật khẩu quản trị
# # # # if st.session_state.get("ndvi_is_ai") and st.session_state.get("ai_report") is not None:
# # # #     with st.sidebar.expander("Lưu kết quả vào CSDL", expanded=False):
# # # #         try:
# # # #             admin_pw = st.secrets.get("admin_password", None)
# # # #         except Exception:
# # # #             admin_pw = None
# # # #         if not admin_pw:
# # # #             st.caption("Chưa cấu hình `admin_password` trong secrets nên tính năng ghi đè đang tắt.")
# # # #         else:
# # # #             st.caption("Ghi đè dự đoán của mô hình đang xem lên CSDL (dù đã có hay chưa).")
# # # #             typed_pw = st.text_input("Mật khẩu quản trị", type="password", key="admin_pw_input")
# # # #             if st.button("Ghi đè vào CSDL", use_container_width=True, key="btn_overwrite_db"):
# # # #                 if hmac.compare_digest(str(typed_pw), str(admin_pw)):
# # # #                     _per = st.session_state["ndvi_period"]
# # # #                     res = save_predictions(
# # # #                         ndvi_df, st.session_state["ndvi_model"], _per.year, _per.month,
# # # #                         report=st.session_state["ai_report"], overwrite=True,
# # # #                     )
# # # #                     (st.success if res["status"] == "saved" else st.warning)(res["message"])
# # # #                 else:
# # # #                     st.error("Sai mật khẩu.")
# # # # is_ai = st.session_state["ndvi_is_ai"]
# # # # data_period = st.session_state["ndvi_period"] or selected_time

# # # # # 6. Tọa độ khu vực chọn
# # # # lat, lng, zoom = LOCATION_DATA[selected_province][selected_district]

# # # # # 7. Khu vực bản đồ (ưu tiên chiếm diện tích lớn nhất)
# # # # area_label = "toàn TP. Hồ Chí Minh" if selected_district == "Toàn tỉnh/TP" else selected_district.strip()
# # # # has_data = not ndvi_df.empty

# # # # # Tên phương án THẬT SỰ tạo ra kết quả (có thể là Ridge/persistence nếu mô hình ONNX không thắng kiểm thử)
# # # # shown_model = st.session_state["ndvi_model"]
# # # # fallback_note = None
# # # # _rep = st.session_state.get("ai_report")
# # # # if is_ai and _rep and _rep.get("backend") in ("ridge", "persistence"):
# # # #     _names = {"ridge": "Ridge (thuật toán dự phòng)", "persistence": "Persistence (giữ nguyên tháng trước)"}
# # # #     shown_model = _names[_rep["backend"]]
# # # #     _ho = _rep.get("holdout") or {}
# # # #     _chosen = st.session_state["ndvi_model"]
# # # #     if not _rep.get("onnx_loaded", True):
# # # #         _why = f"không nạp được file mô hình/scaler của {_chosen}"
# # # #     elif _ho.get("mae_onnx") is None:
# # # #         _why = f"mô hình {_chosen} bị lỗi khi chạy kiểm thử (xem log của app)"
# # # #     else:
# # # #         _why = (f"sai số kiểm thử (MAE) của {_chosen} là {_ho['mae_onnx']:.4f}, "
# # # #                 f"cao hơn {_rep['backend']} ({_ho.get('mae_' + _rep['backend'], float('nan')):.4f})")
# # # #     fallback_note = f"Kết quả không do {_chosen} tạo ra: {_why}."

# # # # render_section_title(
# # # #     title=f"🛰️ Bản đồ phân bố NDVI tháng {format_period(data_period)} – {area_label}",
# # # #     subtitle="Bản đồ chỉ số thực vật theo ô lưới, kết hợp bảng chỉ số vùng và chú giải màu.",
# # # #     source=("ai" if is_ai else "db") if has_data else None,
# # # #     model=shown_model,
# # # # )

# # # # if fallback_note:
# # # #     st.caption(fallback_note)

# # # # if not has_data:
# # # #     st.markdown(
# # # #         "<div class='empty-hint'><b>Bắt đầu:</b> chọn khu vực, tháng và năm ở thanh bên trái, "
# # # #         "sau đó nhấn <b>Chạy dự báo AI</b> để hiển thị lớp NDVI trên bản đồ.</div>",
# # # #         unsafe_allow_html=True,
# # # #     )

# # # # col_map, col_metrics = st.columns([3.7, 1.0], gap="medium")
# # # # with col_map:
# # # #     render_map(
# # # #         lat, lng, zoom, basemap_choice, show_boundaries, df=ndvi_df,
# # # #         selected_time=data_period, selected_district=selected_district,
# # # #     )
# # # # with col_metrics:
# # # #     render_metrics(df=ndvi_df)

# # # # # 8. Biểu đồ & thống kê
# # # # render_chart_and_summary(selected_district, selected_province, selected_time, df=ndvi_df)

# # # # # 9. Footer
# # # # render_footer()




# # # # import streamlit as st
# # # # import pandas as pd
# # # # from config import LOCATION_DATA
# # # # from utils.styles import CUSTOM_CSS
# # # # from utils.dark_theme import DARK_CSS, is_dark_theme
# # # # from components.layout import (
# # # #     APP_NAME, APP_FULL_NAME, SEO_DESCRIPTION,
# # # #     inject_ui_effects, render_header, render_section_title, render_footer, format_period,
# # # # )
# # # # from components.sidebar import render_sidebar, render_sidebar_export
# # # # from components.map_view import render_map
# # # # from components.metrics_view import render_metrics
# # # # from components.chart_view import render_chart_and_summary
# # # # from utils.data_loader import load_ndvi_data_with_ai_fallback
# # # # from utils import ai_demo
# # # # from utils.db_writer import save_predictions
# # # # import hmac

# # # # # 1. Cấu hình trang
# # # # st.set_page_config(
# # # #     layout="wide",
# # # #     page_title=f"{APP_NAME} | Dự báo chỉ số thực vật NDVI – TP. Hồ Chí Minh",
# # # #     page_icon="🌿",
# # # #     initial_sidebar_state="expanded",
# # # #     menu_items={"About": f"**{APP_NAME} – {APP_FULL_NAME}**\n\n{SEO_DESCRIPTION}"},
# # # # )
# # # # st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
# # # # if is_dark_theme():
# # # #     st.markdown(DARK_CSS, unsafe_allow_html=True)
# # # # inject_ui_effects()

# # # # # 2. Sidebar (gọi trước header để header hiển thị đúng mô hình đang chọn)
# # # # selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict, selected_model = render_sidebar()

# # # # # 3. Header
# # # # render_header(selected_model)

# # # # # 4. Session state
# # # # if "ndvi_df" not in st.session_state:
# # # #     st.session_state["ndvi_df"] = pd.DataFrame()
# # # # if "ndvi_is_ai" not in st.session_state:
# # # #     st.session_state["ndvi_is_ai"] = None
# # # # if "ndvi_period" not in st.session_state:
# # # #     st.session_state["ndvi_period"] = None
# # # # if "ndvi_model" not in st.session_state:
# # # #     st.session_state["ndvi_model"] = None

# # # # # 5. Chỉ truy vấn khi bấm nút "CHẠY DỰ BÁO AI"
# # # # if btn_predict:
# # # #     year, month = selected_time.year, selected_time.month

# # # #     # Các thông báo trạng thái (spinner, "đang chạy AI"...) chỉ hiện trong lúc xử lý, xong sẽ tự ẩn
# # # #     status_box = st.empty()
# # # #     with status_box.container():
# # # #         with st.spinner(f"Đang kiểm tra CSDL và chạy AI cho tháng {month}/{year}..."):
# # # #             df_result, is_ai_generated = load_ndvi_data_with_ai_fallback(year=year, month=month, model_name=selected_model)
# # # #     status_box.empty()

# # # #     st.session_state["ndvi_df"] = df_result
# # # #     st.session_state["ndvi_is_ai"] = is_ai_generated if not df_result.empty else None
# # # #     st.session_state["ndvi_period"] = selected_time if not df_result.empty else None
# # # #     st.session_state["ndvi_model"] = selected_model if not df_result.empty else None

# # # #     if df_result.empty:
# # # #         st.toast(f"Không thể tạo dữ liệu cho tháng {month}/{year}", icon="❌")
# # # #         st.warning(f"⚠️ Không có dữ liệu và không thể dự báo cho tháng **{month}/{year}**.")
# # # #     elif is_ai_generated:
# # # #         st.toast(f"AI đã dự báo thành công {len(df_result):,} ô lưới NDVI!", icon="")
# # # #         # Lấy báo cáo của lần chạy này (đã được cache nên không chạy lại AI) để biết backend thật sự là gì
# # # #         _, ai_report = ai_demo._forecast_cached(year, month, selected_model)
# # # #         st.session_state["ai_report"] = ai_report
# # # #         # Tự động lưu: bỏ qua nếu CSDL đã có, và không lưu nếu kết quả không phải do mô hình ONNX tạo ra
# # # #         save_res = save_predictions(df_result, selected_model, year, month, report=ai_report)
# # # #         st.toast(save_res["message"])
# # # #     else:
# # # #         st.toast(f"Tải thành công {len(df_result):,} điểm NDVI từ CSDL!", icon="")

# # # # ndvi_df = st.session_state["ndvi_df"]

# # # # # Vẽ phần xuất CSV/PNG SAU khi dự báo để nút tải luôn lấy dữ liệu mới nhất
# # # # render_sidebar_export(selected_district, selected_time, ndvi_df)

# # # # # Nút ghi đè vào CSDL: chỉ hiện khi đang xem kết quả AI, và cần mật khẩu quản trị
# # # # if st.session_state.get("ndvi_is_ai") and st.session_state.get("ai_report") is not None:
# # # #     with st.sidebar.expander("Lưu kết quả vào CSDL", expanded=False):
# # # #         try:
# # # #             admin_pw = st.secrets.get("admin_password", None)
# # # #         except Exception:
# # # #             admin_pw = None
# # # #         if not admin_pw:
# # # #             st.caption("Chưa cấu hình `admin_password` trong secrets nên tính năng ghi đè đang tắt.")
# # # #         else:
# # # #             st.caption("Ghi đè dự đoán của mô hình đang xem lên CSDL (dù đã có hay chưa).")
# # # #             typed_pw = st.text_input("Mật khẩu quản trị", type="password", key="admin_pw_input")
# # # #             if st.button("Ghi đè vào CSDL", use_container_width=True, key="btn_overwrite_db"):
# # # #                 if hmac.compare_digest(str(typed_pw), str(admin_pw)):
# # # #                     _per = st.session_state["ndvi_period"]
# # # #                     res = save_predictions(
# # # #                         ndvi_df, st.session_state["ndvi_model"], _per.year, _per.month,
# # # #                         report=st.session_state["ai_report"], overwrite=True,
# # # #                     )
# # # #                     (st.success if res["status"] == "saved" else st.warning)(res["message"])
# # # #                 else:
# # # #                     st.error("Sai mật khẩu.")
# # # # is_ai = st.session_state["ndvi_is_ai"]
# # # # data_period = st.session_state["ndvi_period"] or selected_time

# # # # # 6. Tọa độ khu vực chọn
# # # # lat, lng, zoom = LOCATION_DATA[selected_province][selected_district]

# # # # # 7. Khu vực bản đồ (ưu tiên chiếm diện tích lớn nhất)
# # # # area_label = "toàn TP. Hồ Chí Minh" if selected_district == "Toàn tỉnh/TP" else selected_district.strip()
# # # # has_data = not ndvi_df.empty

# # # # render_section_title(
# # # #     title=f"🛰️ Bản đồ phân bố NDVI tháng {format_period(data_period)} – {area_label}",
# # # #     subtitle="Bản đồ chỉ số thực vật theo ô lưới, kết hợp bảng chỉ số vùng và chú giải màu.",
# # # #     source=("ai" if is_ai else "db") if has_data else None,
# # # #     model=st.session_state["ndvi_model"],
# # # # )

# # # # if not has_data:
# # # #     st.markdown(
# # # #         "<div class='empty-hint'><b>Bắt đầu:</b> chọn khu vực, tháng và năm ở thanh bên trái, "
# # # #         "sau đó nhấn <b>Chạy dự báo AI</b> để hiển thị lớp NDVI trên bản đồ.</div>",
# # # #         unsafe_allow_html=True,
# # # #     )

# # # # col_map, col_metrics = st.columns([3.7, 1.0], gap="medium")
# # # # with col_map:
# # # #     render_map(
# # # #         lat, lng, zoom, basemap_choice, show_boundaries, df=ndvi_df,
# # # #         selected_time=data_period, selected_district=selected_district,
# # # #     )
# # # # with col_metrics:
# # # #     render_metrics(df=ndvi_df)

# # # # # 8. Biểu đồ & thống kê
# # # # render_chart_and_summary(selected_district, selected_province, selected_time, df=ndvi_df)

# # # # # 9. Footer
# # # # render_footer()




# # # # import streamlit as st
# # # # import pandas as pd
# # # # from config import LOCATION_DATA
# # # # from utils.styles import CUSTOM_CSS
# # # # from utils.dark_theme import DARK_CSS, is_dark_theme
# # # # from components.layout import (
# # # #     APP_NAME, APP_FULL_NAME, SEO_DESCRIPTION,
# # # #     inject_ui_effects, render_header, render_section_title, render_footer, format_period,
# # # # )
# # # # from components.sidebar import render_sidebar, render_sidebar_export
# # # # from components.map_view import render_map
# # # # from components.metrics_view import render_metrics
# # # # from components.chart_view import render_chart_and_summary
# # # # from utils.data_loader import load_ndvi_data_with_ai_fallback

# # # # # 1. Cấu hình trang
# # # # st.set_page_config(
# # # #     layout="wide",
# # # #     page_title=f"{APP_NAME} | Dự báo chỉ số thực vật NDVI – TP. Hồ Chí Minh",
# # # #     page_icon="🌿",
# # # #     initial_sidebar_state="expanded",
# # # #     menu_items={"About": f"**{APP_NAME} – {APP_FULL_NAME}**\n\n{SEO_DESCRIPTION}"},
# # # # )
# # # # st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
# # # # if is_dark_theme():
# # # #     st.markdown(DARK_CSS, unsafe_allow_html=True)
# # # # inject_ui_effects()

# # # # # 2. Sidebar (gọi trước header để header hiển thị đúng mô hình đang chọn)
# # # # selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict, selected_model = render_sidebar()

# # # # # 3. Header
# # # # render_header(selected_model)

# # # # # 4. Session state
# # # # if "ndvi_df" not in st.session_state:
# # # #     st.session_state["ndvi_df"] = pd.DataFrame()
# # # # if "ndvi_is_ai" not in st.session_state:
# # # #     st.session_state["ndvi_is_ai"] = None
# # # # if "ndvi_period" not in st.session_state:
# # # #     st.session_state["ndvi_period"] = None
# # # # if "ndvi_model" not in st.session_state:
# # # #     st.session_state["ndvi_model"] = None

# # # # # 5. Chỉ truy vấn khi bấm nút "CHẠY DỰ BÁO AI"
# # # # if btn_predict:
# # # #     year, month = selected_time.year, selected_time.month

# # # #     # Các thông báo trạng thái (spinner, "đang chạy AI"...) chỉ hiện trong lúc xử lý, xong sẽ tự ẩn
# # # #     status_box = st.empty()
# # # #     with status_box.container():
# # # #         with st.spinner(f"Đang kiểm tra CSDL và chạy AI cho tháng {month}/{year}..."):
# # # #             df_result, is_ai_generated = load_ndvi_data_with_ai_fallback(year=year, month=month, model_name=selected_model)
# # # #     status_box.empty()

# # # #     st.session_state["ndvi_df"] = df_result
# # # #     st.session_state["ndvi_is_ai"] = is_ai_generated if not df_result.empty else None
# # # #     st.session_state["ndvi_period"] = selected_time if not df_result.empty else None
# # # #     st.session_state["ndvi_model"] = selected_model if not df_result.empty else None

# # # #     if df_result.empty:
# # # #         st.toast(f"Không thể tạo dữ liệu cho tháng {month}/{year}", icon="❌")
# # # #         st.warning(f"⚠️ Không có dữ liệu và không thể dự báo cho tháng **{month}/{year}**.")
# # # #     elif is_ai_generated:
# # # #         st.toast(f"AI đã dự báo thành công {len(df_result):,} ô lưới NDVI!", icon="")
# # # #     else:
# # # #         st.toast(f"Tải thành công {len(df_result):,} điểm NDVI từ CSDL!", icon="")

# # # # ndvi_df = st.session_state["ndvi_df"]

# # # # # Vẽ phần xuất CSV/PNG SAU khi dự báo để nút tải luôn lấy dữ liệu mới nhất
# # # # render_sidebar_export(selected_district, selected_time, ndvi_df)
# # # # is_ai = st.session_state["ndvi_is_ai"]
# # # # data_period = st.session_state["ndvi_period"] or selected_time

# # # # # 6. Tọa độ khu vực chọn
# # # # lat, lng, zoom = LOCATION_DATA[selected_province][selected_district]

# # # # # 7. Khu vực bản đồ (ưu tiên chiếm diện tích lớn nhất)
# # # # area_label = "toàn TP. Hồ Chí Minh" if selected_district == "Toàn tỉnh/TP" else selected_district.strip()
# # # # has_data = not ndvi_df.empty

# # # # render_section_title(
# # # #     title=f"🛰️ Bản đồ phân bố NDVI tháng {format_period(data_period)} – {area_label}",
# # # #     subtitle="Bản đồ chỉ số thực vật theo ô lưới, kết hợp bảng chỉ số vùng và chú giải màu.",
# # # #     source=("ai" if is_ai else "db") if has_data else None,
# # # #     model=st.session_state["ndvi_model"],
# # # # )

# # # # if not has_data:
# # # #     st.markdown(
# # # #         "<div class='empty-hint'><b>Bắt đầu:</b> chọn khu vực, tháng và năm ở thanh bên trái, "
# # # #         "sau đó nhấn <b>Chạy dự báo AI</b> để hiển thị lớp NDVI trên bản đồ.</div>",
# # # #         unsafe_allow_html=True,
# # # #     )

# # # # col_map, col_metrics = st.columns([3.7, 1.0], gap="medium")
# # # # with col_map:
# # # #     render_map(
# # # #         lat, lng, zoom, basemap_choice, show_boundaries, df=ndvi_df,
# # # #         selected_time=data_period, selected_district=selected_district,
# # # #     )
# # # # with col_metrics:
# # # #     render_metrics(df=ndvi_df)

# # # # # 8. Biểu đồ & thống kê
# # # # render_chart_and_summary(selected_district, selected_province, selected_time, df=ndvi_df)

# # # # # 9. Footer
# # # # render_footer()

