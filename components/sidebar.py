import io
import hmac
import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw
from config import LOCATION_DATA
from utils.app_settings import MODELS, get_default_model, set_default_model
from utils.db_writer import save_predictions


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
def _build_export_png(df: pd.DataFrame, date_label: str, source_label: str = ""):
    """Vẽ ảnh bản đồ PNG một lần rồi nhớ kết quả (tránh vẽ lại mỗi lần trang chạy lại)."""
    from utils.map_utils import generate_ndvi_raster_for_export
    return generate_ndvi_raster_for_export(df, date_label=date_label, source_label=source_label)


@st.cache_data(show_spinner=False, max_entries=2)
def _build_export_tiff(df: pd.DataFrame, date_label: str):
    """Tạo GeoTIFF một lần rồi nhớ kết quả (date_label chỉ để tách khóa cache theo tháng)."""
    from utils.tiff_export import generate_ndvi_geotiff
    return generate_ndvi_geotiff(df)


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
                selected_year = st.selectbox("Năm:", list(range(2018, 2028)), index=8)

            selected_time = pd.to_datetime(f"{selected_year}-{selected_month:02d}-01")
            # Mô hình do admin chọn (lưu trong CSDL, ai vào cũng thấy giống nhau)
            selected_model = get_default_model()
            st.caption(f"🤖 Mô hình dự báo hiện tại: **{selected_model}** (do quản trị viên chọn)")
            btn_predict = st.button("🚀 Chạy dự báo AI", use_container_width=True, type="primary",
                                    help="Lấy dữ liệu NDVI từ CSDL, nếu thiếu sẽ tự dùng AI để dự báo")

        with st.expander("⚙️ Cấu hình bản đồ", expanded=False):
            basemap_choice = st.radio("Lớp bản đồ nền:", ["Ảnh vệ tinh Esri", "Google Hybrid"])
            show_boundaries = st.checkbox("🗺️ Hiển thị ranh giới hành chính (HCM-34)", value=True)

    return selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict, selected_model


def render_sidebar_export(selected_district, selected_time, df=None):
    """
    Phần XUẤT DỮ LIỆU (CSV/PNG) + hướng dẫn.
    Phải gọi SAU khi chạy dự báo xong (trong app.py) để nút tải luôn dùng dữ liệu MỚI NHẤT.
    (Nếu vẽ trong render_sidebar thì nó chạy trước bước dự báo -> lần bấm đầu tải ra dữ liệu cũ.)
    """
    if df is None:
        df = st.session_state.get("ndvi_df", None)
    has_data = df is not None and not df.empty

    # Tên file / nhãn ảnh theo THÁNG CỦA DỮ LIỆU ĐÃ TẢI (không phải ô chọn tháng đang hiển thị)
    period = st.session_state.get("ndvi_period") or selected_time
    selected_year, selected_month = period.year, period.month

    with st.sidebar:
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
                    if st.session_state.get("ndvi_is_ai"):
                        src = f"Dự báo AI ({st.session_state.get('ndvi_model') or ''})"
                    else:
                        src = "Quan trắc vệ tinh"
                    png_bytes = _build_export_png(df, f"{selected_month:02d}/{selected_year}", src)
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

            # 3. GeoTIFF (giá trị NDVI thật, có toạ độ) - chỉ hiện khi đã có dữ liệu
            if has_data:
                try:
                    tiff_bytes = _build_export_tiff(df, f"{selected_month:02d}/{selected_year}")
                except Exception as e:
                    print(f"[TIFF] {e}")
                    tiff_bytes = None
                if tiff_bytes:
                    st.download_button(
                        label="🛰️ Xuất GeoTIFF (.TIF)", data=tiff_bytes,
                        file_name=f"ndvi_{selected_district}_{selected_year}_{selected_month:02d}.tif",
                        mime="image/tiff", use_container_width=True,
                        help="Ảnh NDVI float32 có toạ độ WGS84, mở được trong QGIS/ArcGIS",
                    )
                else:
                    st.caption("Không tạo được file GeoTIFF cho dữ liệu này.")

        with st.expander("ℹ️ Hướng dẫn sử dụng", expanded=False):
            st.markdown(
                "1. Chọn **khu vực**, **tháng** và **năm**.\n"
                "2. Nhấn **Chạy dự báo AI** để tải dữ liệu hoặc dự báo.\n"
                "3. Xem lớp NDVI trên bản đồ, đổi lớp nền ở mục *Cấu hình bản đồ*.\n"
                "4. Xuất CSV hoặc ảnh PNG ở mục *Xuất dữ liệu và báo cáo*."
            )




# ===================== TRUY CẬP ADMIN =====================
def _admin_password() -> str:
    try:
        return str(st.secrets.get("admin_password", "tmp"))   # mặc định "tmp" nếu chưa cấu hình secrets
    except Exception:
        return "tmp"


def _try_unlock():
    typed = st.session_state.get("admin_pw_input", "")
    ok = hmac.compare_digest(str(typed).encode(), _admin_password().encode())
    st.session_state["is_admin"] = ok
    st.session_state["admin_pw_error"] = not ok
    st.session_state["admin_pw_input"] = ""


def _logout():
    st.session_state["is_admin"] = False
    st.session_state["view_mode"] = "map"


def _on_model_change():
    if st.session_state.get("is_admin"):
        model = st.session_state["admin_model_select"]
        if set_default_model(model):
            st.toast(f"Đã đặt {model} làm mô hình mặc định cho mọi người dùng.", icon="✅")
        else:
            st.toast("Không lưu được mô hình mặc định vào CSDL.", icon="❌")


def _open_compare():
    st.session_state["view_mode"] = "compare"


def render_admin_panel(df: pd.DataFrame = None):
    """
    Menu 'Truy cập admin' (đặt cuối sidebar). Chưa nhập đúng mật khẩu thì các ô bị mờ (disabled).
    Gọi SAU khi chạy dự báo để nút ghi đè luôn dùng kết quả mới nhất.
    """
    is_admin = bool(st.session_state.get("is_admin"))

    with st.sidebar.expander("🔐 Truy cập admin", expanded=is_admin):
        if not is_admin:
            with st.form("admin_login", border=False):
                st.text_input("Mật khẩu admin", type="password", key="admin_pw_input")
                st.form_submit_button("Mở khóa", use_container_width=True, on_click=_try_unlock)
            if st.session_state.get("admin_pw_error"):
                st.error("Sai mật khẩu.")
        else:
            st.success("Đang ở chế độ admin")
            st.button("Đăng xuất admin", use_container_width=True, on_click=_logout, key="btn_admin_logout")

        st.divider()

        # 1. Chọn mô hình mặc định (áp dụng cho tất cả người dùng)
        current = get_default_model()
        if st.session_state.get("admin_model_select") != current:
            st.session_state["admin_model_select"] = current
        st.selectbox("Mô hình AI mặc định:", MODELS, key="admin_model_select",
                     disabled=not is_admin, on_change=_on_model_change,
                     help="Mô hình này sẽ được dùng cho mọi người dùng khi cần dự báo bằng AI")

        # 2. Lưu (ghi đè) kết quả dự báo đang xem vào CSDL
        has_ai = (bool(st.session_state.get("ndvi_is_ai")) and st.session_state.get("ai_report") is not None
                  and df is not None and not df.empty)
        overwrite = st.checkbox("Ghi đè dữ liệu đã có", value=False, key="admin_overwrite",
                                disabled=not (is_admin and has_ai),
                                help="Tắt: chỉ điền các ô còn trống. Bật: ghi đè toàn bộ.")
        if st.button("💾 Lưu kết quả vào CSDL", use_container_width=True, key="btn_overwrite_db",
                     disabled=not (is_admin and has_ai)):
            per = st.session_state["ndvi_period"]
            res = save_predictions(df, st.session_state["ndvi_model"], per.year, per.month,
                                   report=st.session_state["ai_report"], overwrite=overwrite)
            (st.success if res["status"] == "saved" else st.warning)(res["message"])
        if is_admin and not has_ai:
            st.caption("Nút lưu chỉ bật khi đang xem kết quả do AI dự báo.")

        # 3. So sánh các mô hình (thay phần bên phải bằng biểu đồ)
        st.button("📊 So sánh mô hình", use_container_width=True, key="btn_open_compare",
                  disabled=not is_admin, on_click=_open_compare)



# import io
# import hmac
# import streamlit as st
# import pandas as pd
# from PIL import Image, ImageDraw
# from config import LOCATION_DATA
# from utils.app_settings import MODELS, get_default_model, set_default_model
# from utils.db_writer import save_predictions


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
#                 <p class="name">🌿 GEO-NDVI</p>
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
#                 selected_year = st.selectbox("Năm:", list(range(2018, 2028)), index=8)

#             selected_time = pd.to_datetime(f"{selected_year}-{selected_month:02d}-01")
#             # Mô hình do admin chọn (lưu trong CSDL, ai vào cũng thấy giống nhau)
#             selected_model = get_default_model()
#             st.caption(f"")
#             btn_predict = st.button("🚀 Chạy dự báo AI", use_container_width=True, type="primary",
#                                     help="Lấy dữ liệu NDVI từ CSDL, nếu thiếu sẽ tự dùng AI để dự báo")

#         with st.expander("⚙️ Cấu hình bản đồ", expanded=False):
#             basemap_choice = st.radio("Lớp bản đồ nền:", ["Ảnh vệ tinh Esri", "Google Hybrid"])
#             show_boundaries = st.checkbox("🗺️ Hiển thị ranh giới hành chính (HCM-34)", value=True)

#     return selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict, selected_model


# def render_sidebar_export(selected_district, selected_time, df=None):
#     """
#     Phần XUẤT DỮ LIỆU (CSV/PNG) + hướng dẫn.
#     Phải gọi SAU khi chạy dự báo xong (trong app.py) để nút tải luôn dùng dữ liệu MỚI NHẤT.
#     (Nếu vẽ trong render_sidebar thì nó chạy trước bước dự báo -> lần bấm đầu tải ra dữ liệu cũ.)
#     """
#     if df is None:
#         df = st.session_state.get("ndvi_df", None)
#     has_data = df is not None and not df.empty

#     # Tên file / nhãn ảnh theo THÁNG CỦA DỮ LIỆU ĐÃ TẢI (không phải ô chọn tháng đang hiển thị)
#     period = st.session_state.get("ndvi_period") or selected_time
#     selected_year, selected_month = period.year, period.month

#     with st.sidebar:
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
#                 st.toast("Bạn vừa tải file CSV mẫu. Hãy nhấn 'Chạy dự báo AI' để có dữ liệu thực tế!", icon="🔔")

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




# # ===================== TRUY CẬP ADMIN =====================
# def _admin_password() -> str:
#     try:
#         return str(st.secrets.get("admin_password", "tmp"))   # mặc định "tmp" nếu chưa cấu hình secrets
#     except Exception:
#         return "tmp"


# def _try_unlock():
#     typed = st.session_state.get("admin_pw_input", "")
#     ok = hmac.compare_digest(str(typed).encode(), _admin_password().encode())
#     st.session_state["is_admin"] = ok
#     st.session_state["admin_pw_error"] = not ok
#     st.session_state["admin_pw_input"] = ""


# def _logout():
#     st.session_state["is_admin"] = False
#     st.session_state["view_mode"] = "map"


# def _on_model_change():
#     if st.session_state.get("is_admin"):
#         model = st.session_state["admin_model_select"]
#         if set_default_model(model):
#             st.toast(f"Đã đặt {model} làm mô hình mặc định cho mọi người dùng.", icon="✅")
#         else:
#             st.toast("Không lưu được mô hình mặc định vào CSDL.", icon="❌")


# def _open_compare():
#     st.session_state["view_mode"] = "compare"


# def render_admin_panel(df: pd.DataFrame = None):
#     """
#     Menu 'Truy cập admin' (đặt cuối sidebar). Chưa nhập đúng mật khẩu thì các ô bị mờ (disabled).
#     Gọi SAU khi chạy dự báo để nút ghi đè luôn dùng kết quả mới nhất.
#     """
#     is_admin = bool(st.session_state.get("is_admin"))

#     with st.sidebar.expander("🔐 Truy cập admin", expanded=is_admin):
#         if not is_admin:
#             with st.form("admin_login", border=False):
#                 st.text_input("Mật khẩu admin", type="password", key="admin_pw_input")
#                 st.form_submit_button("Mở khóa", use_container_width=True, on_click=_try_unlock)
#             if st.session_state.get("admin_pw_error"):
#                 st.error("Sai mật khẩu.")
#         else:
#             st.success("Đang ở chế độ admin")
#             st.button("Đăng xuất admin", use_container_width=True, on_click=_logout, key="btn_admin_logout")

#         st.divider()

#         # 1. Chọn mô hình mặc định (áp dụng cho tất cả người dùng)
#         current = get_default_model()
#         if st.session_state.get("admin_model_select") != current:
#             st.session_state["admin_model_select"] = current
#         st.selectbox("Mô hình AI mặc định:", MODELS, key="admin_model_select",
#                      disabled=not is_admin, on_change=_on_model_change,
#                      help="Mô hình này sẽ được dùng cho mọi người dùng khi cần dự báo bằng AI")

#         # 2. Lưu (ghi đè) kết quả dự báo đang xem vào CSDL
#         has_ai = (bool(st.session_state.get("ndvi_is_ai")) and st.session_state.get("ai_report") is not None
#                   and df is not None and not df.empty)
#         if st.button("💾 Lưu kết quả vào CSDL (ghi đè)", use_container_width=True, key="btn_overwrite_db",
#                      disabled=not (is_admin and has_ai)):
#             per = st.session_state["ndvi_period"]
#             res = save_predictions(df, st.session_state["ndvi_model"], per.year, per.month,
#                                    report=st.session_state["ai_report"], overwrite=True)
#             (st.success if res["status"] == "saved" else st.warning)(res["message"])
#         if is_admin and not has_ai:
#             st.caption("Nút lưu chỉ bật khi đang xem kết quả do AI dự báo.")

#         # 3. So sánh các mô hình (thay phần bên phải bằng biểu đồ)
#         st.button("📊 So sánh mô hình", use_container_width=True, key="btn_open_compare",
#                   disabled=not is_admin, on_click=_open_compare)


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
#                 <p class="name">🌿 GEO-NDVI</p>
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
#                 selected_year = st.selectbox("Năm:", list(range(2018, 2028)), index=8)

#             selected_time = pd.to_datetime(f"{selected_year}-{selected_month:02d}-01")
#             selected_model = st.selectbox(
#                 "Mô hình AI dự báo:", ["LSTM", "GRU", "CNNLSTM"],
#                 help="Chỉ áp dụng khi tháng đã chọn không đủ dữ liệu quan trắc trong CSDL và cần dự báo bằng AI",
#             )
#             btn_predict = st.button("🚀 Chạy dự báo AI", use_container_width=True, type="primary",
#                                     help="Lấy dữ liệu NDVI từ CSDL, nếu thiếu sẽ tự dùng AI để dự báo")

#         with st.expander("⚙️ Cấu hình bản đồ", expanded=False):
#             basemap_choice = st.radio("Lớp bản đồ nền:", ["Ảnh vệ tinh Esri", "Google Hybrid"])
#             show_boundaries = st.checkbox("🗺️ Hiển thị ranh giới hành chính (HCM-34)", value=True)

#     return selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict, selected_model


# def render_sidebar_export(selected_district, selected_time, df=None):
#     """
#     Phần XUẤT DỮ LIỆU (CSV/PNG) + hướng dẫn.
#     Phải gọi SAU khi chạy dự báo xong (trong app.py) để nút tải luôn dùng dữ liệu MỚI NHẤT.
#     (Nếu vẽ trong render_sidebar thì nó chạy trước bước dự báo -> lần bấm đầu tải ra dữ liệu cũ.)
#     """
#     if df is None:
#         df = st.session_state.get("ndvi_df", None)
#     has_data = df is not None and not df.empty

#     # Tên file / nhãn ảnh theo THÁNG CỦA DỮ LIỆU ĐÃ TẢI (không phải ô chọn tháng đang hiển thị)
#     period = st.session_state.get("ndvi_period") or selected_time
#     selected_year, selected_month = period.year, period.month

#     with st.sidebar:
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
#                 st.toast("Bạn vừa tải file CSV mẫu. Hãy nhấn 'Chạy dự báo AI' để có dữ liệu thực tế!", icon="🔔")

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


