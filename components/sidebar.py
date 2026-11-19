import io
import re
import hmac
import calendar
import unicodedata
import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw
from config import LOCATION_DATA
from components.layout import APP_NAME, APP_FULL_NAME
from utils.app_settings import MODELS, get_default_model, set_default_model, get_force_ai, set_force_ai
from utils.db_writer import save_predictions
from utils.gee_loader import render_gee_panel
from utils.timeline import render_timeline_controls


def _safe(name: str) -> str:
    """Tên khu vực -> chuỗi dùng được trong tên file (bỏ dấu, thay / và khoảng trắng bằng _)."""
    t = str(name).replace("Đ", "D").replace("đ", "d")
    t = unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_").lower() or "khu_vuc"


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
def _build_map_sheet(df: pd.DataFrame, when_text: str, source_label: str, source_kind: str):
    """Tờ bản đồ chuẩn (tên, lưới tọa độ, chú giải, hướng Bắc, tỷ lệ); dựng một lần rồi nhớ kết quả."""
    from utils.map_layout import generate_ndvi_map_sheet
    return generate_ndvi_map_sheet(df, when_text=when_text, source_label=source_label, source_kind=source_kind)


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
        st.markdown(f"""
            <div class="side-brand">
                <p class="name">🌿 {APP_NAME}</p>
                <p class="desc">Giám sát nhiệt độ bề mặt – thực vật – khô hạn</p>
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

            # ---- Dự báo theo ngày (MÔ PHỎNG): selected_time vẫn là ngày 1, ngày chọn lưu riêng trong session ----
            daily_on = st.checkbox("📅 Dự báo theo ngày (mô phỏng)", key="daily_mode_cb",
                                   help="Dựng NDVI từng ngày bằng cách nội suy giữa các tháng liền kề rồi cộng dao động nhỏ. "
                                        "Đây là mô phỏng để minh họa, không phải mô hình dự báo theo ngày.")
            if daily_on:
                days_in_month = calendar.monthrange(selected_year, selected_month)[1]
                raw_day = st.selectbox("Ngày:", list(range(1, 32)), index=14, key="daily_day_sel")
                selected_day = min(int(raw_day), days_in_month)
                if selected_day != raw_day:
                    st.caption(f"Tháng {selected_month}/{selected_year} chỉ có {days_in_month} ngày, dùng ngày {selected_day}.")
                st.session_state["sim_day"] = selected_day
            else:
                st.session_state["sim_day"] = None

            # Mô hình do admin chọn (lưu trong CSDL, ai vào cũng thấy giống nhau)
            selected_model = get_default_model()
            st.caption(f"Mô hình tối ưu nhất đang được sử dụng")

            btn_predict = st.button("🚀 Chạy dự báo AI", use_container_width=True, type="primary",
                                    help="Lấy dữ liệu NDVI từ CSDL, nếu thiếu sẽ tự dùng AI để dự báo")

        with st.expander("⚙️ Cấu hình bản đồ", expanded=False):
            basemap_choice = st.radio("Lớp bản đồ nền:", ["Ảnh vệ tinh Esri", "Google Hybrid"])
            show_boundaries = st.checkbox("🗺️ Hiển thị ranh giới hành chính (HCM-34)", value=True)

        render_timeline_controls()  # 🎞️ Diễn biến theo thời gian: từ tháng/năm, đến tháng/năm, nút Xem

    return selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict, selected_model


def _render_report_buttons(df: pd.DataFrame, period: pd.Timestamp):
    """Báo cáo Word/PDF: chỉ tạo khi bấm nút (không tạo lại mỗi lần trang chạy lại); lỗi thì hiện rõ nguyên nhân."""
    import traceback

    is_ai = bool(st.session_state.get("ndvi_is_ai"))
    model = st.session_state.get("ndvi_model") or ""
    label = f"{period.month:02d}/{period.year}"
    sig = (label, is_ai, model, len(df), round(float(df["ndvi_mean"].mean()), 6))   # dữ liệu đổi -> bắt tạo lại
    cache = st.session_state.get("report_files")

    st.markdown("**📄 Báo cáo Word / PDF**")
    if st.button("📝 Tạo báo cáo", use_container_width=True, key="btn_make_report",
                 help="Tạo báo cáo tổng hợp NDVI (Word và PDF) cho dữ liệu đang xem"):
        from utils.report_export import generate_ndvi_report_docx
        from utils.report_pdf import generate_ndvi_report_pdf
        from utils.ward_info import get_ward_stats, build_ranking_table

        out = {"sig": sig, "docx": None, "pdf": None, "err": []}
        with st.spinner("Đang tạo báo cáo..."):
            ranking = None
            try:
                stats, _, gdf = get_ward_stats(df)
                if stats is not None and gdf is not None:
                    ranking = build_ranking_table(stats, gdf)
            except Exception as e:
                out["err"].append(f"Bảng xếp hạng phường/xã: {e}")
            map_png = None
            try:
                src = f"Dự báo AI ({model})" if is_ai else "Quan trắc vệ tinh"
                map_png = _build_export_png(df, label, src)
            except Exception as e:
                out["err"].append(f"Ảnh bản đồ: {e}")
            kw = dict(ranking=ranking, map_png=map_png, period_label=label,
                      source_kind="ai" if is_ai else "observed", model_name=model)
            for ext, fn in (("docx", generate_ndvi_report_docx), ("pdf", generate_ndvi_report_pdf)):
                try:
                    out[ext] = fn(df, **kw)
                except Exception as e:
                    out["err"].append(f"{ext.upper()}: {type(e).__name__}: {e}\n{traceback.format_exc()[-1200:]}")
        st.session_state["report_files"] = out
        cache = out

    if cache and cache.get("sig") == sig:
        base = f"bao_cao_ndvi_{period.year}_{period.month:02d}"
        if cache.get("docx"):
            st.download_button("📘 Tải báo cáo Word (.docx)", data=cache["docx"], file_name=base + ".docx",
                               mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                               use_container_width=True, key="dl_report_docx")
        if cache.get("pdf"):
            st.download_button("📕 Tải báo cáo PDF (.pdf)", data=cache["pdf"], file_name=base + ".pdf",
                               mime="application/pdf", use_container_width=True, key="dl_report_pdf")
        if cache.get("err"):
            with st.expander("⚠️ Chi tiết lỗi tạo báo cáo"):
                for msg in cache["err"]:
                    st.code(msg)
    else:
        st.caption("Bấm “Tạo báo cáo” để tạo file Word và PDF cho dữ liệu đang xem.")


def render_sidebar_export(selected_district, selected_time, df=None):
    """
    Phần XUẤT DỮ LIỆU (CSV/PNG/TIF/Word/PDF) + hướng dẫn.
    Phải gọi SAU khi chạy dự báo xong (trong app.py) để nút tải luôn dùng dữ liệu MỚI NHẤT.
    """
    if df is None:
        df = st.session_state.get("ndvi_df", None)
    has_data = df is not None and not df.empty

    # Tên file / nhãn ảnh theo THÁNG (và NGÀY nếu mô phỏng theo ngày) CỦA DỮ LIỆU ĐÃ TẢI
    period = st.session_state.get("ndvi_period") or selected_time
    selected_year, selected_month = period.year, period.month
    day = st.session_state.get("ndvi_day")                 # None = dữ liệu theo tháng
    date_label = f"{day:02d}/{selected_month:02d}/{selected_year}" if day else f"{selected_month:02d}/{selected_year}"
    file_stamp = f"{selected_year}_{selected_month:02d}" + (f"_{day:02d}" if day else "")
    dist = _safe(selected_district)
    model_txt = st.session_state.get("ndvi_model") or ""
    kind = "daily_sim" if day else ("ai" if st.session_state.get("ndvi_is_ai") else "observed")
    src = {"daily_sim": f"Mô phỏng theo ngày ({model_txt})", "ai": f"Dự báo AI ({model_txt})",
           "observed": "Quan trắc vệ tinh"}[kind]
    when_text = (f"ngày {date_label} (mô phỏng)" if day else f"tháng {date_label}")

    with st.sidebar:
        with st.expander("📊 Xuất dữ liệu và báo cáo", expanded=False):
            # 1. CSV
            if has_data:
                csv_bytes = df.to_csv(index=False).encode('utf-8-sig')
                file_name_csv = f"du_lieu_ndvi_{dist}_{file_stamp}.csv"
            else:
                csv_default = "Trạng_thái,Thông_báo\nCHƯA_DỰ_BÁO,Vui lòng nhấn 'Chạy dự báo AI' để cập nhật dữ liệu NDVI."
                csv_bytes = csv_default.encode('utf-8-sig')
                file_name_csv = f"du_lieu_ndvi_{dist}_mau_mac_dinh.csv"

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
                    png_bytes = _build_export_png(df, date_label, src)
                except Exception:
                    png_bytes = None
            if png_bytes is None:
                png_bytes = create_placeholder_png()
                file_name_png = f"anh_ndvi_{dist}_mac_dinh.png"
            else:
                file_name_png = f"anh_ndvi_{dist}_{file_stamp}.png"

            btn_png = st.download_button(
                label="🖼️ Xuất ảnh NDVI (.PNG)", data=png_bytes, file_name=file_name_png,
                mime="image/png", use_container_width=True, help="Tải ảnh bản đồ NDVI (PNG) về máy",
            )
            if btn_png and not has_data:
                st.toast("Bạn vừa tải ảnh mẫu. Hãy bấm '🚀 Chạy dự báo AI' để tạo bản đồ NDVI!", icon="🖼️")

            # 2b. Bản đồ chuẩn (tên, lưới tọa độ, chú giải, hướng Bắc, tỷ lệ) - chỉ hiện khi đã có dữ liệu
            if has_data:
                try:
                    sheet_bytes = _build_map_sheet(df, when_text, src, kind)
                except Exception as e:
                    print(f"[MAP] {e}")
                    sheet_bytes = None
                if sheet_bytes:
                    st.download_button(
                        label="🗺️ Xuất bản đồ chuẩn (.PNG)", data=sheet_bytes,
                        file_name=f"ban_do_ndvi_{dist}_{file_stamp}.png",
                        mime="image/png", use_container_width=True,
                        help="Tờ bản đồ A4 có tên bản đồ, lưới tọa độ, chú giải, hướng Bắc và tỷ lệ",
                    )
                else:
                    st.caption("Không tạo được bản đồ chuẩn cho dữ liệu này.")

            # 3. GeoTIFF (giá trị NDVI thật, có toạ độ) - chỉ hiện khi đã có dữ liệu
            if has_data:
                try:
                    tiff_bytes = _build_export_tiff(df, date_label)
                except Exception as e:
                    print(f"[TIFF] {e}")
                    tiff_bytes = None
                if tiff_bytes:
                    st.download_button(
                        label="🛰️ Xuất GeoTIFF (.TIF)", data=tiff_bytes,
                        file_name=f"geotiff_ndvi_{dist}_{file_stamp}.tif",
                        mime="image/tiff", use_container_width=True,
                        help="Ảnh NDVI float32 có toạ độ WGS84, mở được trong QGIS/ArcGIS",
                    )
                else:
                    st.caption("Không tạo được file GeoTIFF cho dữ liệu này.")

            # 4. Báo cáo Word / PDF (nút mới)
            if has_data:
                _render_report_buttons(df, period)

        with st.expander("ℹ️ Hướng dẫn sử dụng", expanded=False):
            st.markdown(
                "1. Chọn **khu vực**, **tháng** và **năm** (muốn xem theo ngày thì bật **Dự báo theo ngày (mô phỏng)** rồi chọn ngày).\n"
                "2. Nhấn **Chạy dự báo AI** để tải dữ liệu hoặc dự báo.\n"
                "3. Xem lớp NDVI trên bản đồ, đổi lớp nền ở mục *Cấu hình bản đồ*.\n"
                "4. Xuất CSV, ảnh PNG, **bản đồ chuẩn**, GeoTIFF hoặc **báo cáo Word / PDF** ở mục *Xuất dữ liệu và báo cáo*."
            )


# ===================== TRUY CẬP ADMIN =====================
def _admin_password() -> str:
    try:
        return str(st.secrets.get("admin_password", "tmp"))  # mặc định "tmp" nếu chưa cấu hình secrets
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


def _on_force_ai_change():
    if st.session_state.get("is_admin"):
        flag = bool(st.session_state["admin_force_ai"])
        if set_force_ai(flag):
            st.toast("Đã BẬT chế độ luôn dùng AI cho dự báo." if flag
                     else "Đã TẮT chế độ luôn dùng AI cho dự báo.", icon="✅")
        else:
            st.toast("Không lưu được cài đặt vào CSDL.", icon="❌")


def _open_compare():
    st.session_state["view_mode"] = "compare"


def render_admin_panel(df: pd.DataFrame = None):
    """
    Menu 'Truy cập admin' (cuối sidebar).
    Chưa mở khóa: CHỈ hiện ô nhập mật khẩu, các chức năng admin hoàn toàn không được vẽ ra.
    """
    is_admin = bool(st.session_state.get("is_admin"))
    with st.sidebar.expander("🔐 Truy cập admin", expanded=is_admin):
        if not is_admin:
            with st.form("admin_login", border=False):
                st.text_input("Mật khẩu admin", type="password", key="admin_pw_input")
                st.form_submit_button("Mở khóa", use_container_width=True, on_click=_try_unlock)
            if st.session_state.get("admin_pw_error"):
                st.error("Sai mật khẩu.")
            return  # <- dừng ở đây: client không thấy gì thêm

        # ---------- Từ đây trở xuống chỉ admin đã mở khóa mới thấy ----------
        st.success("Đang ở chế độ admin")
        st.button("Đăng xuất admin", use_container_width=True, on_click=_logout, key="btn_admin_logout")
        st.divider()

        # 1. Mô hình mặc định (áp dụng cho tất cả người dùng)
        current = get_default_model()
        if st.session_state.get("admin_model_select") != current:
            st.session_state["admin_model_select"] = current
        st.selectbox("Mô hình AI mặc định:", MODELS, key="admin_model_select",
                     on_change=_on_model_change,
                     help="Mô hình này sẽ được dùng cho mọi người dùng khi cần dự báo bằng AI")

        # 2. Chế độ nạp dữ liệu: luôn dùng AI
        cur_force = get_force_ai()
        if st.session_state.get("admin_force_ai") != cur_force:
            st.session_state["admin_force_ai"] = cur_force
        st.checkbox("Luôn dùng AI dự báo mọi thời điểm", key="admin_force_ai",
                    on_change=_on_force_ai_change,
                    help="Bật: mọi tháng đều chạy AI, không lấy dữ liệu quan trắc. Áp dụng cho tất cả người dùng.")

        # 3. Lưu kết quả dự báo đang xem vào CSDL
        has_ai = (bool(st.session_state.get("ndvi_is_ai")) and st.session_state.get("ai_report") is not None
                  and df is not None and not df.empty)
        overwrite = st.checkbox("Ghi đè dữ liệu đã có", value=False, key="admin_overwrite",
                                disabled=not has_ai,
                                help="Tắt: chỉ điền các ô còn trống. Bật: ghi đè toàn bộ.")
        if st.button("💾 Lưu kết quả vào CSDL", use_container_width=True, key="btn_overwrite_db",
                     disabled=not has_ai):
            per = st.session_state["ndvi_period"]
            res = save_predictions(df, st.session_state["ndvi_model"], per.year, per.month,
                                   report=st.session_state["ai_report"], overwrite=overwrite)
            (st.success if res["status"] == "saved" else st.warning)(res["message"])
        if not has_ai:
            if st.session_state.get("ndvi_day"):
                st.caption("Kết quả mô phỏng theo ngày không được lưu vào CSDL.")
            else:
                st.caption("Nút lưu chỉ bật khi đang xem kết quả do AI dự báo.")

        # 4. So sánh các mô hình
        st.button("📊 So sánh mô hình", use_container_width=True, key="btn_open_compare",
                  on_click=_open_compare)

        st.divider()
        render_gee_panel()



# import io
# import re
# import hmac
# import calendar
# import unicodedata
# import streamlit as st
# import pandas as pd
# from PIL import Image, ImageDraw
# from config import LOCATION_DATA
# from components.layout import APP_NAME, APP_FULL_NAME
# from utils.app_settings import MODELS, get_default_model, set_default_model, get_force_ai, set_force_ai
# from utils.db_writer import save_predictions
# from utils.gee_loader import render_gee_panel
# from utils.timeline import render_timeline_controls


# def _safe(name: str) -> str:
#     """Tên khu vực -> chuỗi dùng được trong tên file (bỏ dấu, thay / và khoảng trắng bằng _)."""
#     t = str(name).replace("Đ", "D").replace("đ", "d")
#     t = unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode()
#     return re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_").lower() or "khu_vuc"


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
# def _build_export_png(df: pd.DataFrame, date_label: str, source_label: str = ""):
#     """Vẽ ảnh bản đồ PNG một lần rồi nhớ kết quả (tránh vẽ lại mỗi lần trang chạy lại)."""
#     from utils.map_utils import generate_ndvi_raster_for_export
#     return generate_ndvi_raster_for_export(df, date_label=date_label, source_label=source_label)


# @st.cache_data(show_spinner=False, max_entries=2)
# def _build_map_sheet(df: pd.DataFrame, when_text: str, source_label: str, source_kind: str):
#     """Tờ bản đồ chuẩn (tên, lưới tọa độ, chú giải, hướng Bắc, tỷ lệ); dựng một lần rồi nhớ kết quả."""
#     from utils.map_layout import generate_ndvi_map_sheet
#     return generate_ndvi_map_sheet(df, when_text=when_text, source_label=source_label, source_kind=source_kind)


# @st.cache_data(show_spinner=False, max_entries=2)
# def _build_export_tiff(df: pd.DataFrame, date_label: str):
#     """Tạo GeoTIFF một lần rồi nhớ kết quả (date_label chỉ để tách khóa cache theo tháng)."""
#     from utils.tiff_export import generate_ndvi_geotiff
#     return generate_ndvi_geotiff(df)


# @st.cache_data(show_spinner=False, max_entries=2)
# def _build_report_docx(df: pd.DataFrame, period_label: str, source_kind: str, model_name: str,
#                        png_bytes: bytes = None):
#     """Dựng báo cáo Word một lần rồi nhớ kết quả. Bảng phường/xã lấy cùng nguồn với bảng xếp hạng trên web."""
#     from utils.report_export import generate_ndvi_report_docx
#     ranking = None
#     try:
#         from utils.ward_info import get_ward_stats, build_ranking_table
#         stats, _, gdf = get_ward_stats(df)
#         if stats is not None and gdf is not None:
#             ranking = build_ranking_table(stats, gdf)
#     except Exception as e:      # thiếu bảng phường/xã thì báo cáo vẫn có phần tổng quan
#         print(f"[REPORT] không lấy được bảng phường/xã: {e}")
#     return generate_ndvi_report_docx(df, ranking=ranking, map_png=png_bytes, period_label=period_label,
#                                      source_kind=source_kind, model_name=model_name,
#                                      system_name=APP_FULL_NAME, brand=APP_NAME)


# def render_sidebar(df: pd.DataFrame = None):
#     """Thanh bên: bộ lọc dự báo, cấu hình bản đồ, xuất dữ liệu CSV/PNG."""
#     if df is None or df.empty:
#         df = st.session_state.get("ndvi_df", None)
#     has_data = df is not None and not df.empty

#     with st.sidebar:
#         st.markdown(f"""
#             <div class="side-brand">
#                 <p class="name">🌿 {APP_NAME}</p>
#                 <p class="desc">Giám sát nhiệt độ bề mặt – thực vật – khô hạn</p>
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

#             # ---- Dự báo theo ngày (MÔ PHỎNG): selected_time vẫn là ngày 1, ngày chọn lưu riêng trong session ----
#             daily_on = st.checkbox("📅 Dự báo theo ngày (mô phỏng)", key="daily_mode_cb",
#                                    help="Dựng NDVI từng ngày bằng cách nội suy giữa các tháng liền kề rồi cộng dao động nhỏ. "
#                                         "Đây là mô phỏng để minh họa, không phải mô hình dự báo theo ngày.")
#             if daily_on:
#                 days_in_month = calendar.monthrange(selected_year, selected_month)[1]
#                 raw_day = st.selectbox("Ngày:", list(range(1, 32)), index=14, key="daily_day_sel")
#                 selected_day = min(int(raw_day), days_in_month)
#                 if selected_day != raw_day:
#                     st.caption(f"Tháng {selected_month}/{selected_year} chỉ có {days_in_month} ngày, dùng ngày {selected_day}.")
#                 st.session_state["sim_day"] = selected_day
#             else:
#                 st.session_state["sim_day"] = None

#             # Mô hình do admin chọn (lưu trong CSDL, ai vào cũng thấy giống nhau)
#             selected_model = get_default_model()
#             st.caption(f"Mô hình tối ưu nhất đang được sử dụng")

#             btn_predict = st.button("🚀 Chạy dự báo AI", use_container_width=True, type="primary",
#                                     help="Lấy dữ liệu NDVI từ CSDL, nếu thiếu sẽ tự dùng AI để dự báo")

#         with st.expander("⚙️ Cấu hình bản đồ", expanded=False):
#             basemap_choice = st.radio("Lớp bản đồ nền:", ["Ảnh vệ tinh Esri", "Google Hybrid"])
#             show_boundaries = st.checkbox("🗺️ Hiển thị ranh giới hành chính (HCM-34)", value=True)

#         render_timeline_controls()  # 🎞️ Diễn biến theo thời gian: từ tháng/năm, đến tháng/năm, nút Xem

#     return selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict, selected_model

# def _render_report_buttons(df: pd.DataFrame, period: pd.Timestamp):
#     """Báo cáo Word/PDF: chỉ tạo khi bấm nút (không tạo lại mỗi lần trang chạy lại); lỗi thì hiện rõ nguyên nhân."""
#     import traceback

#     is_ai = bool(st.session_state.get("ndvi_is_ai"))
#     model = st.session_state.get("ndvi_model") or ""
#     label = f"{period.month:02d}/{period.year}"
#     sig = (label, is_ai, model, len(df), round(float(df["ndvi_mean"].mean()), 6))   # dữ liệu đổi -> bắt tạo lại
#     cache = st.session_state.get("report_files")

#     st.markdown("**📄 Báo cáo Word / PDF**")
#     if st.button("📝 Tạo báo cáo", use_container_width=True, key="btn_make_report",
#                  help="Tạo báo cáo tổng hợp NDVI (Word và PDF) cho dữ liệu đang xem"):
#         from utils.report_export import generate_ndvi_report_docx
#         from utils.report_pdf import generate_ndvi_report_pdf
#         from utils.ward_info import get_ward_stats, build_ranking_table

#         out = {"sig": sig, "docx": None, "pdf": None, "err": []}
#         with st.spinner("Đang tạo báo cáo..."):
#             ranking = None
#             try:
#                 stats, _, gdf = get_ward_stats(df)
#                 if stats is not None and gdf is not None:
#                     ranking = build_ranking_table(stats, gdf)
#             except Exception as e:
#                 out["err"].append(f"Bảng xếp hạng phường/xã: {e}")
#             map_png = None
#             try:
#                 src = f"Dự báo AI ({model})" if is_ai else "Quan trắc vệ tinh"
#                 map_png = _build_export_png(df, label, src)
#             except Exception as e:
#                 out["err"].append(f"Ảnh bản đồ: {e}")
#             kw = dict(ranking=ranking, map_png=map_png, period_label=label,
#                       source_kind="ai" if is_ai else "observed", model_name=model)
#             for ext, fn in (("docx", generate_ndvi_report_docx), ("pdf", generate_ndvi_report_pdf)):
#                 try:
#                     out[ext] = fn(df, **kw)
#                 except Exception as e:
#                     out["err"].append(f"{ext.upper()}: {type(e).__name__}: {e}\n{traceback.format_exc()[-1200:]}")
#         st.session_state["report_files"] = out
#         cache = out

#     if cache and cache.get("sig") == sig:
#         base = f"bao_cao_ndvi_{period.year}_{period.month:02d}"
#         if cache.get("docx"):
#             st.download_button("📘 Tải báo cáo Word (.docx)", data=cache["docx"], file_name=base + ".docx",
#                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
#                                use_container_width=True, key="dl_report_docx")
#         if cache.get("pdf"):
#             st.download_button("📕 Tải báo cáo PDF (.pdf)", data=cache["pdf"], file_name=base + ".pdf",
#                                mime="application/pdf", use_container_width=True, key="dl_report_pdf")
#         if cache.get("err"):
#             with st.expander("⚠️ Chi tiết lỗi tạo báo cáo"):
#                 for msg in cache["err"]:
#                     st.code(msg)
#     else:
#         st.caption("Bấm “Tạo báo cáo” để tạo file Word và PDF cho dữ liệu đang xem.")



# def render_sidebar_export(selected_district, selected_time, df=None):
#     """
#     Phần XUẤT DỮ LIỆU (CSV/PNG/TIF/Word) + hướng dẫn.
#     Phải gọi SAU khi chạy dự báo xong (trong app.py) để nút tải luôn dùng dữ liệu MỚI NHẤT.
#     (Nếu vẽ trong render_sidebar thì nó chạy trước bước dự báo -> lần bấm đầu tải ra dữ liệu cũ.)
#     """
#     if df is None:
#         df = st.session_state.get("ndvi_df", None)
#     has_data = df is not None and not df.empty

#     # Tên file / nhãn ảnh theo THÁNG (và NGÀY nếu mô phỏng theo ngày) CỦA DỮ LIỆU ĐÃ TẢI
#     period = st.session_state.get("ndvi_period") or selected_time
#     selected_year, selected_month = period.year, period.month
#     day = st.session_state.get("ndvi_day")                 # None = dữ liệu theo tháng
#     date_label = f"{day:02d}/{selected_month:02d}/{selected_year}" if day else f"{selected_month:02d}/{selected_year}"
#     file_stamp = f"{selected_year}_{selected_month:02d}" + (f"_{day:02d}" if day else "")
#     dist = _safe(selected_district)
#     model_txt = st.session_state.get("ndvi_model") or ""
#     kind = "daily_sim" if day else ("ai" if st.session_state.get("ndvi_is_ai") else "observed")
#     src = {"daily_sim": f"Mô phỏng theo ngày ({model_txt})", "ai": f"Dự báo AI ({model_txt})",
#            "observed": "Quan trắc vệ tinh"}[kind]
#     when_text = (f"ngày {date_label} (mô phỏng)" if day else f"tháng {date_label}")

#     with st.sidebar:
#         with st.expander("📊 Xuất dữ liệu và báo cáo", expanded=False):
#             # 1. CSV
#             if has_data:
#                 csv_bytes = df.to_csv(index=False).encode('utf-8-sig')
#                 file_name_csv = f"du_lieu_ndvi_{dist}_{file_stamp}.csv"
#             else:
#                 csv_default = "Trạng_thái,Thông_báo\nCHƯA_DỰ_BÁO,Vui lòng nhấn 'Chạy dự báo AI' để cập nhật dữ liệu NDVI."
#                 csv_bytes = csv_default.encode('utf-8-sig')
#                 file_name_csv = f"du_lieu_ndvi_{dist}_mau_mac_dinh.csv"

#             btn_csv = st.download_button(
#                 label="📥 Xuất dữ liệu CSV", data=csv_bytes, file_name=file_name_csv,
#                 mime="text/csv", use_container_width=True, help="Tải dữ liệu NDVI (CSV) về máy",
#             )
#             if btn_csv and not has_data:
#                 st.toast("Bạn vừa tải file CSV mẫu. Hãy nhấn 'Chạy dự báo AI' để có dữ liệu thực tế!", icon="🔔")

#             # 2. PNG
#             png_bytes = None
#             real_png = None
#             if has_data:
#                 try:
#                     png_bytes = _build_export_png(df, date_label, src)
#                     real_png = png_bytes
#                 except Exception:
#                     png_bytes = None
#             if png_bytes is None:
#                 png_bytes = create_placeholder_png()
#                 file_name_png = f"anh_ndvi_{dist}_mac_dinh.png"
#             else:
#                 file_name_png = f"anh_ndvi_{dist}_{file_stamp}.png"

#             btn_png = st.download_button(
#                 label="🖼️ Xuất ảnh NDVI (.PNG)", data=png_bytes, file_name=file_name_png,
#                 mime="image/png", use_container_width=True, help="Tải ảnh bản đồ NDVI (PNG) về máy",
#             )
#             if btn_png and not has_data:
#                 st.toast("Bạn vừa tải ảnh mẫu. Hãy bấm '🚀 Chạy dự báo AI' để tạo bản đồ NDVI!", icon="🖼️")

#             # 2b. Bản đồ chuẩn (tên, lưới tọa độ, chú giải, hướng Bắc, tỷ lệ) - chỉ hiện khi đã có dữ liệu
#             if has_data:
#                 try:
#                     sheet_bytes = _build_map_sheet(df, when_text, src, kind)
#                 except Exception as e:
#                     print(f"[MAP] {e}")
#                     sheet_bytes = None
#                 if sheet_bytes:
#                     st.download_button(
#                         label="🗺️ Xuất bản đồ chuẩn (.PNG)", data=sheet_bytes,
#                         file_name=f"ban_do_ndvi_{dist}_{file_stamp}.png",
#                         mime="image/png", use_container_width=True,
#                         help="Tờ bản đồ A4 có tên bản đồ, lưới tọa độ, chú giải, hướng Bắc và tỷ lệ",
#                     )
#                 else:
#                     st.caption("Không tạo được bản đồ chuẩn cho dữ liệu này.")

#             # 3. GeoTIFF (giá trị NDVI thật, có toạ độ) - chỉ hiện khi đã có dữ liệu
#             if has_data:
#                 try:
#                     tiff_bytes = _build_export_tiff(df, date_label)
#                 except Exception as e:
#                     print(f"[TIFF] {e}")
#                     tiff_bytes = None
#                 if tiff_bytes:
#                     st.download_button(
#                         label="🛰️ Xuất GeoTIFF (.TIF)", data=tiff_bytes,
#                         file_name=f"geotiff_ndvi_{dist}_{file_stamp}.tif",
#                         mime="image/tiff", use_container_width=True,
#                         help="Ảnh NDVI float32 có toạ độ WGS84, mở được trong QGIS/ArcGIS",
#                     )
#                     #update
#                     if has_data:
#                         _render_report_buttons(df, period)
#                 else:
#                     st.caption("Không tạo được file GeoTIFF cho dữ liệu này.")

#                 # 4. Báo cáo Word (.docx): tiêu đề, ảnh bản đồ, thống kê, bảng phường/xã, nhận xét
#                 try:
#                     report_bytes = _build_report_docx(df, date_label, kind, model_txt, real_png)
#                 except Exception as e:
#                     print(f"[REPORT] {e}")
#                     report_bytes = None
#                 if report_bytes:
#                     st.download_button(
#                         label="📝 Xuất báo cáo Word (.DOCX)", data=report_bytes,
#                         file_name=f"bao_cao_ndvi_{file_stamp}.docx",
#                         mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
#                         use_container_width=True,
#                         help="Báo cáo có tiêu đề, ảnh bản đồ, thống kê chung, bảng NDVI theo phường/xã và phần nhận xét",
#                     )
#                 else:
#                     st.caption("Không tạo được báo cáo Word cho dữ liệu này.")

#         with st.expander("ℹ️ Hướng dẫn sử dụng", expanded=False):
#             st.markdown(
#                 "1. Chọn **khu vực**, **tháng** và **năm** (muốn xem theo ngày thì bật **Dự báo theo ngày (mô phỏng)** rồi chọn ngày).\n"
#                 "2. Nhấn **Chạy dự báo AI** để tải dữ liệu hoặc dự báo.\n"
#                 "3. Xem lớp NDVI trên bản đồ, đổi lớp nền ở mục *Cấu hình bản đồ*.\n"
#                 "4. Xuất CSV, ảnh PNG, **bản đồ chuẩn**, GeoTIFF hoặc **báo cáo Word** ở mục *Xuất dữ liệu và báo cáo*."
#             )


# # ===================== TRUY CẬP ADMIN =====================
# def _admin_password() -> str:
#     try:
#         return str(st.secrets.get("admin_password", "tmp"))  # mặc định "tmp" nếu chưa cấu hình secrets
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


# def _on_force_ai_change():
#     if st.session_state.get("is_admin"):
#         flag = bool(st.session_state["admin_force_ai"])
#         if set_force_ai(flag):
#             st.toast("Đã BẬT chế độ luôn dùng AI cho dự báo." if flag
#                      else "Đã TẮT chế độ luôn dùng AI cho dự báo.", icon="✅")
#         else:
#             st.toast("Không lưu được cài đặt vào CSDL.", icon="❌")


# def _open_compare():
#     st.session_state["view_mode"] = "compare"


# def render_admin_panel(df: pd.DataFrame = None):
#     """
#     Menu 'Truy cập admin' (cuối sidebar).
#     Chưa mở khóa: CHỈ hiện ô nhập mật khẩu, các chức năng admin hoàn toàn không được vẽ ra.
#     """
#     is_admin = bool(st.session_state.get("is_admin"))
#     with st.sidebar.expander("🔐 Truy cập admin", expanded=is_admin):
#         if not is_admin:
#             with st.form("admin_login", border=False):
#                 st.text_input("Mật khẩu admin", type="password", key="admin_pw_input")
#                 st.form_submit_button("Mở khóa", use_container_width=True, on_click=_try_unlock)
#             if st.session_state.get("admin_pw_error"):
#                 st.error("Sai mật khẩu.")
#             return  # <- dừng ở đây: client không thấy gì thêm

#         # ---------- Từ đây trở xuống chỉ admin đã mở khóa mới thấy ----------
#         st.success("Đang ở chế độ admin")
#         st.button("Đăng xuất admin", use_container_width=True, on_click=_logout, key="btn_admin_logout")
#         st.divider()

#         # 1. Mô hình mặc định (áp dụng cho tất cả người dùng)
#         current = get_default_model()
#         if st.session_state.get("admin_model_select") != current:
#             st.session_state["admin_model_select"] = current
#         st.selectbox("Mô hình AI mặc định:", MODELS, key="admin_model_select",
#                      on_change=_on_model_change,
#                      help="Mô hình này sẽ được dùng cho mọi người dùng khi cần dự báo bằng AI")

#         # 2. Chế độ nạp dữ liệu: luôn dùng AI
#         cur_force = get_force_ai()
#         if st.session_state.get("admin_force_ai") != cur_force:
#             st.session_state["admin_force_ai"] = cur_force
#         st.checkbox("Luôn dùng AI dự báo mọi thời điểm", key="admin_force_ai",
#                     on_change=_on_force_ai_change,
#                     help="Bật: mọi tháng đều chạy AI, không lấy dữ liệu quan trắc. Áp dụng cho tất cả người dùng.")

#         # 3. Lưu kết quả dự báo đang xem vào CSDL
#         has_ai = (bool(st.session_state.get("ndvi_is_ai")) and st.session_state.get("ai_report") is not None
#                   and df is not None and not df.empty)
#         overwrite = st.checkbox("Ghi đè dữ liệu đã có", value=False, key="admin_overwrite",
#                                 disabled=not has_ai,
#                                 help="Tắt: chỉ điền các ô còn trống. Bật: ghi đè toàn bộ.")
#         if st.button("💾 Lưu kết quả vào CSDL", use_container_width=True, key="btn_overwrite_db",
#                      disabled=not has_ai):
#             per = st.session_state["ndvi_period"]
#             res = save_predictions(df, st.session_state["ndvi_model"], per.year, per.month,
#                                    report=st.session_state["ai_report"], overwrite=overwrite)
#             (st.success if res["status"] == "saved" else st.warning)(res["message"])
#         if not has_ai:
#             if st.session_state.get("ndvi_day"):
#                 st.caption("Kết quả mô phỏng theo ngày không được lưu vào CSDL.")
#             else:
#                 st.caption("Nút lưu chỉ bật khi đang xem kết quả do AI dự báo.")

#         # 4. So sánh các mô hình
#         st.button("📊 So sánh mô hình", use_container_width=True, key="btn_open_compare",
#                   on_click=_open_compare)

#         st.divider()
#         render_gee_panel()




# # import io
# # import hmac
# # import calendar
# # import streamlit as st
# # import pandas as pd
# # from PIL import Image, ImageDraw
# # from config import LOCATION_DATA
# # from utils.app_settings import MODELS, get_default_model, set_default_model, get_force_ai, set_force_ai
# # from utils.db_writer import save_predictions
# # from utils.gee_loader import render_gee_panel
# # from utils.timeline import render_timeline_controls


# # def create_placeholder_png() -> bytes:
# #     """Tạo ảnh PNG mặc định khi người dùng bấm tải ảnh trước khi có dữ liệu."""
# #     img = Image.new('RGB', (600, 350), color='#F1F8F3')
# #     draw = ImageDraw.Draw(img)
# #     draw.rectangle([15, 15, 585, 335], outline='#15803D', width=2)
# #     # Font mặc định của PIL không hỗ trợ dấu tiếng Việt nên dùng chữ không dấu
# #     draw.text((200, 130), "CHUA CO DU LIEU DU BAO", fill='#B45309')
# #     draw.text((120, 170), "Vui long nhan 'CHAY DU BAO AI' de tao anh NDVI!", fill='#5B7A66')
# #     buf = io.BytesIO()
# #     img.save(buf, format='PNG')
# #     return buf.getvalue()


# # @st.cache_data(show_spinner=False, max_entries=3)
# # def _build_export_png(df: pd.DataFrame, date_label: str, source_label: str = ""):
# #     """Vẽ ảnh bản đồ PNG một lần rồi nhớ kết quả (tránh vẽ lại mỗi lần trang chạy lại)."""
# #     from utils.map_utils import generate_ndvi_raster_for_export
# #     return generate_ndvi_raster_for_export(df, date_label=date_label, source_label=source_label)


# # @st.cache_data(show_spinner=False, max_entries=2)
# # def _build_export_tiff(df: pd.DataFrame, date_label: str):
# #     """Tạo GeoTIFF một lần rồi nhớ kết quả (date_label chỉ để tách khóa cache theo tháng)."""
# #     from utils.tiff_export import generate_ndvi_geotiff
# #     return generate_ndvi_geotiff(df)


# # @st.cache_data(show_spinner=False, max_entries=2)
# # def _build_report_docx(df: pd.DataFrame, period_label: str, source_kind: str, model_name: str,
# #                        png_bytes: bytes = None):
# #     """Dựng báo cáo Word một lần rồi nhớ kết quả. Bảng phường/xã lấy cùng nguồn với bảng xếp hạng trên web."""
# #     from utils.report_export import generate_ndvi_report_docx
# #     ranking = None
# #     try:
# #         from utils.ward_info import get_ward_stats, build_ranking_table
# #         stats, _, gdf = get_ward_stats(df)
# #         if stats is not None and gdf is not None:
# #             ranking = build_ranking_table(stats, gdf)
# #     except Exception as e:      # thiếu bảng phường/xã thì báo cáo vẫn có phần tổng quan
# #         print(f"[REPORT] không lấy được bảng phường/xã: {e}")
# #     return generate_ndvi_report_docx(df, ranking=ranking, map_png=png_bytes, period_label=period_label,
# #                                      source_kind=source_kind, model_name=model_name)


# # def render_sidebar(df: pd.DataFrame = None):
# #     """Thanh bên: bộ lọc dự báo, cấu hình bản đồ, xuất dữ liệu CSV/PNG."""
# #     if df is None or df.empty:
# #         df = st.session_state.get("ndvi_df", None)
# #     has_data = df is not None and not df.empty

# #     with st.sidebar:
# #         st.markdown("""
# #             <div class="side-brand">
# #                 <p class="name">🌿 GEO-NDVI</p>
# #                 <p class="desc">Nền tảng viễn thám và AI giám sát thực vật</p>
# #             </div>
# #         """, unsafe_allow_html=True)

# #         st.markdown("### Bảng điều khiển")

# #         with st.expander("🔮 Bộ lọc dự báo", expanded=True):
# #             selected_province = st.selectbox("Tỉnh / Thành phố:", list(LOCATION_DATA.keys()))
# #             district_options = list(LOCATION_DATA[selected_province].keys())
# #             selected_district = st.selectbox("Quận / Huyện / Phường:", district_options)

# #             col_m, col_y = st.columns(2)
# #             with col_m:
# #                 selected_month = st.selectbox("Tháng:", list(range(1, 13)), index=8)
# #             with col_y:
# #                 selected_year = st.selectbox("Năm:", list(range(2018, 2028)), index=8)
# #             selected_time = pd.to_datetime(f"{selected_year}-{selected_month:02d}-01")

# #             # ---- Dự báo theo ngày (MÔ PHỎNG): selected_time vẫn là ngày 1, ngày chọn lưu riêng trong session ----
# #             daily_on = st.checkbox("Dự báo theo ngày ", key="daily_mode_cb",
# #                                    help="Dựng NDVI từng ngày bằng cách nội suy giữa các tháng liền kề rồi cộng dao động nhỏ. "
# #                                         "Đây là mô phỏng để minh họa, không phải mô hình dự báo theo ngày.")
# #             if daily_on:
# #                 days_in_month = calendar.monthrange(selected_year, selected_month)[1]
# #                 raw_day = st.selectbox("Ngày:", list(range(1, 32)), index=14, key="daily_day_sel")
# #                 selected_day = min(int(raw_day), days_in_month)
# #                 if selected_day != raw_day:
# #                     st.caption(f"Tháng {selected_month}/{selected_year} chỉ có {days_in_month} ngày, dùng ngày {selected_day}.")
# #                 st.session_state["sim_day"] = selected_day
# #             else:
# #                 st.session_state["sim_day"] = None

# #             # Mô hình do admin chọn (lưu trong CSDL, ai vào cũng thấy giống nhau)
# #             selected_model = get_default_model()
# #             st.caption(f"Mô hình tối ưu nhất đang được sử dụng")

# #             btn_predict = st.button("🚀 Chạy dự báo AI", use_container_width=True, type="primary",
# #                                     help="Lấy dữ liệu NDVI từ CSDL, nếu thiếu sẽ tự dùng AI để dự báo")

# #         with st.expander("⚙️ Cấu hình bản đồ", expanded=False):
# #             basemap_choice = st.radio("Lớp bản đồ nền:", ["Ảnh vệ tinh Esri", "Google Hybrid"])
# #             show_boundaries = st.checkbox("🗺️ Hiển thị ranh giới hành chính (HCM-34)", value=True)

# #         render_timeline_controls()  # 🎞️ Diễn biến theo thời gian: từ tháng/năm, đến tháng/năm, nút Xem

# #     return selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict, selected_model


# # def render_sidebar_export(selected_district, selected_time, df=None):
# #     """
# #     Phần XUẤT DỮ LIỆU (CSV/PNG/TIF/Word) + hướng dẫn.
# #     Phải gọi SAU khi chạy dự báo xong (trong app.py) để nút tải luôn dùng dữ liệu MỚI NHẤT.
# #     (Nếu vẽ trong render_sidebar thì nó chạy trước bước dự báo -> lần bấm đầu tải ra dữ liệu cũ.)
# #     """
# #     if df is None:
# #         df = st.session_state.get("ndvi_df", None)
# #     has_data = df is not None and not df.empty

# #     # Tên file / nhãn ảnh theo THÁNG (và NGÀY nếu mô phỏng theo ngày) CỦA DỮ LIỆU ĐÃ TẢI
# #     period = st.session_state.get("ndvi_period") or selected_time
# #     selected_year, selected_month = period.year, period.month
# #     day = st.session_state.get("ndvi_day")                 # None = dữ liệu theo tháng
# #     date_label = f"{day:02d}/{selected_month:02d}/{selected_year}" if day else f"{selected_month:02d}/{selected_year}"
# #     file_stamp = f"{selected_year}_{selected_month:02d}" + (f"_{day:02d}" if day else "")

# #     with st.sidebar:
# #         with st.expander("📊 Xuất dữ liệu và báo cáo", expanded=False):
# #             # 1. CSV
# #             if has_data:
# #                 csv_bytes = df.to_csv(index=False).encode('utf-8-sig')
# #                 file_name_csv = f"ndvi_{selected_district}_{file_stamp}.csv"
# #             else:
# #                 csv_default = "Trạng_thái,Thông_báo\nCHƯA_DỰ_BÁO,Vui lòng nhấn 'Chạy dự báo AI' để cập nhật dữ liệu NDVI."
# #                 csv_bytes = csv_default.encode('utf-8-sig')
# #                 file_name_csv = f"ndvi_{selected_district}_mau_mac_dinh.csv"

# #             btn_csv = st.download_button(
# #                 label="📥 Xuất dữ liệu CSV", data=csv_bytes, file_name=file_name_csv,
# #                 mime="text/csv", use_container_width=True, help="Tải dữ liệu NDVI (CSV) về máy",
# #             )
# #             if btn_csv and not has_data:
# #                 st.toast("Bạn vừa tải file CSV mẫu. Hãy nhấn 'Chạy dự báo AI' để có dữ liệu thực tế!", icon="🔔")

# #             # 2. PNG
# #             png_bytes = None
# #             real_png = None
# #             if has_data:
# #                 try:
# #                     if day:
# #                         src = f"Mô phỏng theo ngày ({st.session_state.get('ndvi_model') or ''})"
# #                     elif st.session_state.get("ndvi_is_ai"):
# #                         src = f"Dự báo AI ({st.session_state.get('ndvi_model') or ''})"
# #                     else:
# #                         src = "Quan trắc vệ tinh"
# #                     png_bytes = _build_export_png(df, date_label, src)
# #                     real_png = png_bytes
# #                 except Exception:
# #                     png_bytes = None
# #             if png_bytes is None:
# #                 png_bytes = create_placeholder_png()
# #                 file_name_png = f"ndvi_map_{selected_district}_mac_dinh.png"
# #             else:
# #                 file_name_png = f"ndvi_map_{selected_district}_{file_stamp}.png"

# #             btn_png = st.download_button(
# #                 label="🖼️ Xuất ảnh NDVI (.PNG)", data=png_bytes, file_name=file_name_png,
# #                 mime="image/png", use_container_width=True, help="Tải ảnh bản đồ NDVI (PNG) về máy",
# #             )
# #             if btn_png and not has_data:
# #                 st.toast("Bạn vừa tải ảnh mẫu. Hãy bấm '🚀 Chạy dự báo AI' để tạo bản đồ NDVI!", icon="🖼️")

# #             # 3. GeoTIFF (giá trị NDVI thật, có toạ độ) - chỉ hiện khi đã có dữ liệu
# #             if has_data:
# #                 try:
# #                     tiff_bytes = _build_export_tiff(df, date_label)
# #                 except Exception as e:
# #                     print(f"[TIFF] {e}")
# #                     tiff_bytes = None
# #                 if tiff_bytes:
# #                     st.download_button(
# #                         label="🛰️ Xuất GeoTIFF (.TIF)", data=tiff_bytes,
# #                         file_name=f"ndvi_{selected_district}_{file_stamp}.tif",
# #                         mime="image/tiff", use_container_width=True,
# #                         help="Ảnh NDVI float32 có toạ độ WGS84, mở được trong QGIS/ArcGIS",
# #                     )
# #                 else:
# #                     st.caption("Không tạo được file GeoTIFF cho dữ liệu này.")

# #                 # 4. Báo cáo Word (.docx): tiêu đề, ảnh bản đồ, thống kê, bảng phường/xã, nhận xét
# #                 try:
# #                     if day:
# #                         kind = "daily_sim"
# #                     elif st.session_state.get("ndvi_is_ai"):
# #                         kind = "ai"
# #                     else:
# #                         kind = "observed"
# #                     report_bytes = _build_report_docx(df, date_label, kind,
# #                                                       st.session_state.get("ndvi_model") or "", real_png)
# #                 except Exception as e:
# #                     print(f"[REPORT] {e}")
# #                     report_bytes = None
# #                 if report_bytes:
# #                     st.download_button(
# #                         label="📝 Xuất báo cáo Word (.DOCX)", data=report_bytes,
# #                         file_name=f"bao_cao_ndvi_{file_stamp}.docx",
# #                         mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
# #                         use_container_width=True,
# #                         help="Báo cáo có tiêu đề, ảnh bản đồ, thống kê chung, bảng NDVI theo phường/xã và phần nhận xét",
# #                     )
# #                 else:
# #                     st.caption("Không tạo được báo cáo Word cho dữ liệu này.")

# #         with st.expander("ℹ️ Hướng dẫn sử dụng", expanded=False):
# #             st.markdown(
# #                 "1. Chọn **khu vực**, **tháng** và **năm** (muốn xem theo ngày thì bật **Dự báo theo ngày (mô phỏng)** rồi chọn ngày).\n"
# #                 "2. Nhấn **Chạy dự báo AI** để tải dữ liệu hoặc dự báo.\n"
# #                 "3. Xem lớp NDVI trên bản đồ, đổi lớp nền ở mục *Cấu hình bản đồ*.\n"
# #                 "4. Xuất CSV, ảnh PNG, GeoTIFF hoặc **báo cáo Word** ở mục *Xuất dữ liệu và báo cáo*."
# #             )


# # # ===================== TRUY CẬP ADMIN =====================
# # def _admin_password() -> str:
# #     try:
# #         return str(st.secrets.get("admin_password", "tmp"))  # mặc định "tmp" nếu chưa cấu hình secrets
# #     except Exception:
# #         return "tmp"


# # def _try_unlock():
# #     typed = st.session_state.get("admin_pw_input", "")
# #     ok = hmac.compare_digest(str(typed).encode(), _admin_password().encode())
# #     st.session_state["is_admin"] = ok
# #     st.session_state["admin_pw_error"] = not ok
# #     st.session_state["admin_pw_input"] = ""


# # def _logout():
# #     st.session_state["is_admin"] = False
# #     st.session_state["view_mode"] = "map"


# # def _on_model_change():
# #     if st.session_state.get("is_admin"):
# #         model = st.session_state["admin_model_select"]
# #         if set_default_model(model):
# #             st.toast(f"Đã đặt {model} làm mô hình mặc định cho mọi người dùng.", icon="✅")
# #         else:
# #             st.toast("Không lưu được mô hình mặc định vào CSDL.", icon="❌")


# # def _on_force_ai_change():
# #     if st.session_state.get("is_admin"):
# #         flag = bool(st.session_state["admin_force_ai"])
# #         if set_force_ai(flag):
# #             st.toast("Đã BẬT chế độ luôn dùng AI cho dự báo." if flag
# #                      else "Đã TẮT chế độ luôn dùng AI cho dự báo.", icon="✅")
# #         else:
# #             st.toast("Không lưu được cài đặt vào CSDL.", icon="❌")


# # def _open_compare():
# #     st.session_state["view_mode"] = "compare"


# # def render_admin_panel(df: pd.DataFrame = None):
# #     """
# #     Menu 'Truy cập admin' (cuối sidebar).
# #     Chưa mở khóa: CHỈ hiện ô nhập mật khẩu, các chức năng admin hoàn toàn không được vẽ ra.
# #     """
# #     is_admin = bool(st.session_state.get("is_admin"))
# #     with st.sidebar.expander("🔐 Truy cập admin", expanded=is_admin):
# #         if not is_admin:
# #             with st.form("admin_login", border=False):
# #                 st.text_input("Mật khẩu admin", type="password", key="admin_pw_input")
# #                 st.form_submit_button("Mở khóa", use_container_width=True, on_click=_try_unlock)
# #             if st.session_state.get("admin_pw_error"):
# #                 st.error("Sai mật khẩu.")
# #             return  # <- dừng ở đây: client không thấy gì thêm

# #         # ---------- Từ đây trở xuống chỉ admin đã mở khóa mới thấy ----------
# #         st.success("Đang ở chế độ admin")
# #         st.button("Đăng xuất admin", use_container_width=True, on_click=_logout, key="btn_admin_logout")
# #         st.divider()

# #         # 1. Mô hình mặc định (áp dụng cho tất cả người dùng)
# #         current = get_default_model()
# #         if st.session_state.get("admin_model_select") != current:
# #             st.session_state["admin_model_select"] = current
# #         st.selectbox("Mô hình AI mặc định:", MODELS, key="admin_model_select",
# #                      on_change=_on_model_change,
# #                      help="Mô hình này sẽ được dùng cho mọi người dùng khi cần dự báo bằng AI")

# #         # 2. Chế độ nạp dữ liệu: luôn dùng AI
# #         cur_force = get_force_ai()
# #         if st.session_state.get("admin_force_ai") != cur_force:
# #             st.session_state["admin_force_ai"] = cur_force
# #         st.checkbox("Luôn dùng AI dự báo mọi thời điểm", key="admin_force_ai",
# #                     on_change=_on_force_ai_change,
# #                     help="Bật: mọi tháng đều chạy AI, không lấy dữ liệu quan trắc. Áp dụng cho tất cả người dùng.")

# #         # 3. Lưu kết quả dự báo đang xem vào CSDL
# #         has_ai = (bool(st.session_state.get("ndvi_is_ai")) and st.session_state.get("ai_report") is not None
# #                   and df is not None and not df.empty)
# #         overwrite = st.checkbox("Ghi đè dữ liệu đã có", value=False, key="admin_overwrite",
# #                                 disabled=not has_ai,
# #                                 help="Tắt: chỉ điền các ô còn trống. Bật: ghi đè toàn bộ.")
# #         if st.button("💾 Lưu kết quả vào CSDL", use_container_width=True, key="btn_overwrite_db",
# #                      disabled=not has_ai):
# #             per = st.session_state["ndvi_period"]
# #             res = save_predictions(df, st.session_state["ndvi_model"], per.year, per.month,
# #                                    report=st.session_state["ai_report"], overwrite=overwrite)
# #             (st.success if res["status"] == "saved" else st.warning)(res["message"])
# #         if not has_ai:
# #             if st.session_state.get("ndvi_day"):
# #                 st.caption("Kết quả mô phỏng theo ngày không được lưu vào CSDL.")
# #             else:
# #                 st.caption("Nút lưu chỉ bật khi đang xem kết quả do AI dự báo.")

# #         # 4. So sánh các mô hình
# #         st.button("📊 So sánh mô hình", use_container_width=True, key="btn_open_compare",
# #                   on_click=_open_compare)

# #         st.divider()
# #         render_gee_panel()




# # # import io
# # # import hmac
# # # import streamlit as st
# # # import pandas as pd
# # # from PIL import Image, ImageDraw
# # # from config import LOCATION_DATA
# # # from utils.app_settings import MODELS, get_default_model, set_default_model, get_force_ai, set_force_ai
# # # from utils.db_writer import save_predictions
# # # from utils.gee_loader import render_gee_panel
# # # from utils.timeline import render_timeline_controls


# # # def create_placeholder_png() -> bytes:
# # #     """Tạo ảnh PNG mặc định khi người dùng bấm tải ảnh trước khi có dữ liệu."""
# # #     img = Image.new('RGB', (600, 350), color='#F1F8F3')
# # #     draw = ImageDraw.Draw(img)
# # #     draw.rectangle([15, 15, 585, 335], outline='#15803D', width=2)
# # #     # Font mặc định của PIL không hỗ trợ dấu tiếng Việt nên dùng chữ không dấu
# # #     draw.text((200, 130), "CHUA CO DU LIEU DU BAO", fill='#B45309')
# # #     draw.text((120, 170), "Vui long nhan 'CHAY DU BAO AI' de tao anh NDVI!", fill='#5B7A66')
# # #     buf = io.BytesIO()
# # #     img.save(buf, format='PNG')
# # #     return buf.getvalue()


# # # @st.cache_data(show_spinner=False, max_entries=3)
# # # def _build_export_png(df: pd.DataFrame, date_label: str, source_label: str = ""):
# # #     """Vẽ ảnh bản đồ PNG một lần rồi nhớ kết quả (tránh vẽ lại mỗi lần trang chạy lại)."""
# # #     from utils.map_utils import generate_ndvi_raster_for_export
# # #     return generate_ndvi_raster_for_export(df, date_label=date_label, source_label=source_label)


# # # @st.cache_data(show_spinner=False, max_entries=2)
# # # def _build_export_tiff(df: pd.DataFrame, date_label: str):
# # #     """Tạo GeoTIFF một lần rồi nhớ kết quả (date_label chỉ để tách khóa cache theo tháng)."""
# # #     from utils.tiff_export import generate_ndvi_geotiff
# # #     return generate_ndvi_geotiff(df)


# # # def render_sidebar(df: pd.DataFrame = None):
# # #     """Thanh bên: bộ lọc dự báo, cấu hình bản đồ, xuất dữ liệu CSV/PNG."""
# # #     if df is None or df.empty:
# # #         df = st.session_state.get("ndvi_df", None)
# # #     has_data = df is not None and not df.empty

# # #     with st.sidebar:
# # #         st.markdown("""
# # #             <div class="side-brand">
# # #                 <p class="name">🌿 GEO-NDVI</p>
# # #                 <p class="desc">Nền tảng viễn thám và AI giám sát thực vật</p>
# # #             </div>
# # #         """, unsafe_allow_html=True)

# # #         st.markdown("### Bảng điều khiển")

# # #         with st.expander("🔮 Bộ lọc dự báo", expanded=True):
# # #             selected_province = st.selectbox("Tỉnh / Thành phố:", list(LOCATION_DATA.keys()))
# # #             district_options = list(LOCATION_DATA[selected_province].keys())
# # #             selected_district = st.selectbox("Quận / Huyện / Phường:", district_options)

# # #             col_m, col_y = st.columns(2)
# # #             with col_m:
# # #                 selected_month = st.selectbox("Tháng:", list(range(1, 13)), index=8)
# # #             with col_y:
# # #                 selected_year = st.selectbox("Năm:", list(range(2018, 2028)), index=8)

# # #             selected_time = pd.to_datetime(f"{selected_year}-{selected_month:02d}-01")
# # #             # Mô hình do admin chọn (lưu trong CSDL, ai vào cũng thấy giống nhau)
# # #             selected_model = get_default_model()
# # #             st.caption(f"Mô hình tối ưu nhất đang được sử dụng")
# # #             btn_predict = st.button("🚀 Chạy dự báo AI", use_container_width=True, type="primary",
# # #                                     help="Lấy dữ liệu NDVI từ CSDL, nếu thiếu sẽ tự dùng AI để dự báo")

# # #         with st.expander("⚙️ Cấu hình bản đồ", expanded=False):
# # #             basemap_choice = st.radio("Lớp bản đồ nền:", ["Ảnh vệ tinh Esri", "Google Hybrid"])
# # #             show_boundaries = st.checkbox("🗺️ Hiển thị ranh giới hành chính (HCM-34)", value=True)

# # #         render_timeline_controls()      # 🎞️ Diễn biến theo thời gian: từ tháng/năm, đến tháng/năm, nút Xem

# # #     return selected_province, selected_district, selected_time, basemap_choice, show_boundaries, btn_predict, selected_model


# # # def render_sidebar_export(selected_district, selected_time, df=None):
# # #     """
# # #     Phần XUẤT DỮ LIỆU (CSV/PNG) + hướng dẫn.
# # #     Phải gọi SAU khi chạy dự báo xong (trong app.py) để nút tải luôn dùng dữ liệu MỚI NHẤT.
# # #     (Nếu vẽ trong render_sidebar thì nó chạy trước bước dự báo -> lần bấm đầu tải ra dữ liệu cũ.)
# # #     """
# # #     if df is None:
# # #         df = st.session_state.get("ndvi_df", None)
# # #     has_data = df is not None and not df.empty

# # #     # Tên file / nhãn ảnh theo THÁNG CỦA DỮ LIỆU ĐÃ TẢI (không phải ô chọn tháng đang hiển thị)
# # #     period = st.session_state.get("ndvi_period") or selected_time
# # #     selected_year, selected_month = period.year, period.month

# # #     with st.sidebar:
# # #         with st.expander("📊 Xuất dữ liệu và báo cáo", expanded=False):
# # #             # 1. CSV
# # #             if has_data:
# # #                 csv_bytes = df.to_csv(index=False).encode('utf-8-sig')
# # #                 file_name_csv = f"ndvi_{selected_district}_{selected_year}_{selected_month:02d}.csv"
# # #             else:
# # #                 csv_default = "Trạng_thái,Thông_báo\nCHƯA_DỰ_BÁO,Vui lòng nhấn 'Chạy dự báo AI' để cập nhật dữ liệu NDVI."
# # #                 csv_bytes = csv_default.encode('utf-8-sig')
# # #                 file_name_csv = f"ndvi_{selected_district}_mau_mac_dinh.csv"

# # #             btn_csv = st.download_button(
# # #                 label="📥 Xuất dữ liệu CSV", data=csv_bytes, file_name=file_name_csv,
# # #                 mime="text/csv", use_container_width=True, help="Tải dữ liệu NDVI (CSV) về máy",
# # #             )
# # #             if btn_csv and not has_data:
# # #                 st.toast("Bạn vừa tải file CSV mẫu. Hãy nhấn 'Chạy dự báo AI' để có dữ liệu thực tế!", icon="🔔")

# # #             # 2. PNG
# # #             png_bytes = None
# # #             if has_data:
# # #                 try:
# # #                     if st.session_state.get("ndvi_is_ai"):
# # #                         src = f"Dự báo AI ({st.session_state.get('ndvi_model') or ''})"
# # #                     else:
# # #                         src = "Quan trắc vệ tinh"
# # #                     png_bytes = _build_export_png(df, f"{selected_month:02d}/{selected_year}", src)
# # #                 except Exception:
# # #                     png_bytes = None

# # #             if png_bytes is None:
# # #                 png_bytes = create_placeholder_png()
# # #                 file_name_png = f"ndvi_map_{selected_district}_mac_dinh.png"
# # #             else:
# # #                 file_name_png = f"ndvi_map_{selected_district}_{selected_year}_{selected_month:02d}.png"

# # #             btn_png = st.download_button(
# # #                 label="🖼️ Xuất ảnh NDVI (.PNG)", data=png_bytes, file_name=file_name_png,
# # #                 mime="image/png", use_container_width=True, help="Tải ảnh bản đồ NDVI (PNG) về máy",
# # #             )
# # #             if btn_png and not has_data:
# # #                 st.toast("Bạn vừa tải ảnh mẫu. Hãy bấm '🚀 Chạy dự báo AI' để tạo bản đồ NDVI!", icon="🖼️")

# # #             # 3. GeoTIFF (giá trị NDVI thật, có toạ độ) - chỉ hiện khi đã có dữ liệu
# # #             if has_data:
# # #                 try:
# # #                     tiff_bytes = _build_export_tiff(df, f"{selected_month:02d}/{selected_year}")
# # #                 except Exception as e:
# # #                     print(f"[TIFF] {e}")
# # #                     tiff_bytes = None
# # #                 if tiff_bytes:
# # #                     st.download_button(
# # #                         label="🛰️ Xuất GeoTIFF (.TIF)", data=tiff_bytes,
# # #                         file_name=f"ndvi_{selected_district}_{selected_year}_{selected_month:02d}.tif",
# # #                         mime="image/tiff", use_container_width=True,
# # #                         help="Ảnh NDVI float32 có toạ độ WGS84, mở được trong QGIS/ArcGIS",
# # #                     )
# # #                 else:
# # #                     st.caption("Không tạo được file GeoTIFF cho dữ liệu này.")

# # #         with st.expander("ℹ️ Hướng dẫn sử dụng", expanded=False):
# # #             st.markdown(
# # #                 "1. Chọn **khu vực**, **tháng** và **năm**.\n"
# # #                 "2. Nhấn **Chạy dự báo AI** để tải dữ liệu hoặc dự báo.\n"
# # #                 "3. Xem lớp NDVI trên bản đồ, đổi lớp nền ở mục *Cấu hình bản đồ*.\n"
# # #                 "4. Xuất CSV hoặc ảnh PNG ở mục *Xuất dữ liệu và báo cáo*."
# # #             )




# # # # ===================== TRUY CẬP ADMIN =====================
# # # def _admin_password() -> str:
# # #     try:
# # #         return str(st.secrets.get("admin_password", "tmp"))   # mặc định "tmp" nếu chưa cấu hình secrets
# # #     except Exception:
# # #         return "tmp"


# # # def _try_unlock():
# # #     typed = st.session_state.get("admin_pw_input", "")
# # #     ok = hmac.compare_digest(str(typed).encode(), _admin_password().encode())
# # #     st.session_state["is_admin"] = ok
# # #     st.session_state["admin_pw_error"] = not ok
# # #     st.session_state["admin_pw_input"] = ""


# # # def _logout():
# # #     st.session_state["is_admin"] = False
# # #     st.session_state["view_mode"] = "map"


# # # def _on_model_change():
# # #     if st.session_state.get("is_admin"):
# # #         model = st.session_state["admin_model_select"]
# # #         if set_default_model(model):
# # #             st.toast(f"Đã đặt {model} làm mô hình mặc định cho mọi người dùng.", icon="✅")
# # #         else:
# # #             st.toast("Không lưu được mô hình mặc định vào CSDL.", icon="❌")

# # # def _on_force_ai_change():
# # #     if st.session_state.get("is_admin"):
# # #         flag = bool(st.session_state["admin_force_ai"])
# # #         if set_force_ai(flag):
# # #             st.toast("Đã BẬT chế độ luôn dùng AI cho dự báo." if flag
# # #                      else "Đã TẮT chế độ luôn dùng AI cho dự báo.", icon="✅")
# # #         else:
# # #             st.toast("Không lưu được cài đặt vào CSDL.", icon="❌")

# # # def _open_compare():
# # #     st.session_state["view_mode"] = "compare"


# # # def render_admin_panel(df: pd.DataFrame = None):
# # #     """
# # #     Menu 'Truy cập admin' (cuối sidebar).
# # #     Chưa mở khóa: CHỈ hiện ô nhập mật khẩu, các chức năng admin hoàn toàn không được vẽ ra.
# # #     """
# # #     is_admin = bool(st.session_state.get("is_admin"))

# # #     with st.sidebar.expander("🔐 Truy cập admin", expanded=is_admin):
# # #         if not is_admin:
# # #             with st.form("admin_login", border=False):
# # #                 st.text_input("Mật khẩu admin", type="password", key="admin_pw_input")
# # #                 st.form_submit_button("Mở khóa", use_container_width=True, on_click=_try_unlock)
# # #             if st.session_state.get("admin_pw_error"):
# # #                 st.error("Sai mật khẩu.")
# # #             return                      # <- dừng ở đây: client không thấy gì thêm

# # #         # ---------- Từ đây trở xuống chỉ admin đã mở khóa mới thấy ----------
# # #         st.success("Đang ở chế độ admin")
# # #         st.button("Đăng xuất admin", use_container_width=True, on_click=_logout, key="btn_admin_logout")
# # #         st.divider()

# # #         # 1. Mô hình mặc định (áp dụng cho tất cả người dùng)
# # #         current = get_default_model()
# # #         if st.session_state.get("admin_model_select") != current:
# # #             st.session_state["admin_model_select"] = current
# # #         st.selectbox("Mô hình AI mặc định:", MODELS, key="admin_model_select",
# # #                      on_change=_on_model_change,
# # #                      help="Mô hình này sẽ được dùng cho mọi người dùng khi cần dự báo bằng AI")

# # #         # 2. Chế độ nạp dữ liệu: luôn dùng AI
# # #         cur_force = get_force_ai()
# # #         if st.session_state.get("admin_force_ai") != cur_force:
# # #             st.session_state["admin_force_ai"] = cur_force
# # #         st.checkbox("Luôn dùng AI dự báo mọi thời điểm", key="admin_force_ai",
# # #                     on_change=_on_force_ai_change,
# # #                     help="Bật: mọi tháng đều chạy AI, không lấy dữ liệu quan trắc. Áp dụng cho tất cả người dùng.")

# # #         # 3. Lưu kết quả dự báo đang xem vào CSDL
# # #         has_ai = (bool(st.session_state.get("ndvi_is_ai")) and st.session_state.get("ai_report") is not None
# # #                   and df is not None and not df.empty)
# # #         overwrite = st.checkbox("Ghi đè dữ liệu đã có", value=False, key="admin_overwrite",
# # #                                 disabled=not has_ai,
# # #                                 help="Tắt: chỉ điền các ô còn trống. Bật: ghi đè toàn bộ.")
# # #         if st.button("💾 Lưu kết quả vào CSDL", use_container_width=True, key="btn_overwrite_db",
# # #                      disabled=not has_ai):
# # #             per = st.session_state["ndvi_period"]
# # #             res = save_predictions(df, st.session_state["ndvi_model"], per.year, per.month,
# # #                                    report=st.session_state["ai_report"], overwrite=overwrite)
# # #             (st.success if res["status"] == "saved" else st.warning)(res["message"])
# # #         if not has_ai:
# # #             st.caption("Nút lưu chỉ bật khi đang xem kết quả do AI dự báo.")

# # #         # 4. So sánh các mô hình
# # #         st.button("📊 So sánh mô hình", use_container_width=True, key="btn_open_compare",
# # #                   on_click=_open_compare)
# # #         st.divider()
# # #         render_gee_panel()


