# components/ward_panels.py
"""
Hai khối giao diện (chỉ HIỂN THỊ, không đổi dữ liệu/mô hình):
- render_ndvi_range_filter: thanh chọn khoảng NDVI đặt trên bản đồ -> trả về (thấp, cao, kiểu) cho render_map.
- render_ward_ranking:      bảng xếp hạng NDVI của các phường/xã (chọn tăng dần / giảm dần).
Cả hai đọc thống kê NDVI từng phường/xã đã được tính sẵn (cùng nguồn với popup trên bản đồ).
"""
import pandas as pd
import streamlit as st
from utils.map_utils import NDVI_VMIN, NDVI_VMAX
from utils.ward_info import get_ward_stats, build_ranking_table
from components.layout import render_section_title



def _reset_range():
    st.session_state["ndvi_range_rev"] = st.session_state.get("ndvi_range_rev", 0) + 1   # đổi key -> thanh trượt về mặc định


def render_ndvi_range_filter(df):
    """
    Bộ lọc gọn đặt dưới ô chú giải: thanh trượt + nút đặt lại + 1 dòng đếm số phường/xã.
    Trả về (thấp, cao, "highlight") khi đã thu hẹp khoảng NDVI, trả về None khi chưa có dữ liệu hoặc để nguyên toàn thang.
    """
    stats, _, gdf = get_ward_stats(df)
    if stats is None:
        return None
    total = len(gdf)
    rev = st.session_state.setdefault("ndvi_range_rev", 0)
    full = (float(NDVI_VMIN), float(NDVI_VMAX))

    try:
        box = st.container(key="ndvi_filter")          # Streamlit mới: gán class để CSS nhắm đúng khung này
    except TypeError:
        box = st.container(border=True)                # Streamlit cũ: CSS tìm khung qua thẻ đánh dấu bên dưới

    with box:
        st.markdown("<span class='rf-marker'></span>", unsafe_allow_html=True)
        st.markdown("<div class='rf-title'>Lọc phường/xã theo NDVI</div>", unsafe_allow_html=True)
        lo, hi = st.slider(
            "Lọc phường/xã theo NDVI", min_value=full[0], max_value=full[1], value=full, step=0.01,
            format="%.2f", key=f"ndvi_range_{rev}", label_visibility="collapsed",
        )
        st.button("↺ Đặt lại", key="ndvi_range_reset", on_click=_reset_range, use_container_width=True)

        lo, hi = round(float(lo), 2), round(float(hi), 2)
        active = (lo, hi) != full
        if active:
            n_in = int(((stats["ndvi_mean"] >= lo) & (stats["ndvi_mean"] <= hi)).sum())
            st.markdown(f"<div class='rf-count'><b>{n_in}/{total}</b> đơn vị có NDVI từ <b>{lo:.2f}</b> đến <b>{hi:.2f}</b></div>",
                        unsafe_allow_html=True)
        else:
            st.markdown("<div class='rf-count'>Kéo thanh trượt để lọc phường/xã theo NDVI.</div>", unsafe_allow_html=True)
    return (lo, hi, "highlight") if active else None


def render_ward_ranking(df, period_label=""):
    """Bảng xếp hạng NDVI các phường/xã. Chỉ hiện sau khi đã có dữ liệu (bấm Chạy dự báo AI)."""
    if df is None or df.empty:
        return
    stats, _, gdf = get_ward_stats(df)
    if gdf is None or stats is None:
        return

    table = build_ranking_table(stats, gdf)
    title = f"🏆 Xếp hạng NDVI theo phường/xã – tháng {period_label}" if period_label else "🏆 Xếp hạng NDVI theo phường/xã"
    render_section_title(
        title=title,
        subtitle=f"{len(table)} đơn vị hành chính, xếp theo NDVI trung bình của các ô lưới nằm trong ranh giới. "
                 "Bấm tiêu đề cột để sắp xếp theo tiêu chí khác.",
    )
    # Mặc định xếp NDVI giảm dần (hạng 1 ở đầu); muốn đổi thì bấm tiêu đề cột của bảng
    table = table.sort_values(["NDVI TB", "Đơn vị"], ascending=[False, True], na_position="last", kind="mergesort")

    st.dataframe(
        table, hide_index=True, use_container_width=True, height=420,
        column_config={
            "Hạng": st.column_config.NumberColumn("Hạng", format="%d", width="small",
                                                  help="Hạng theo NDVI trung bình (1 = xanh nhất)"),
            "Đơn vị": st.column_config.TextColumn("Đơn vị", width="medium"),
            "NDVI TB": st.column_config.ProgressColumn("NDVI TB", min_value=float(NDVI_VMIN), max_value=float(NDVI_VMAX),
                                                       format="%.3f"),
            "Đánh giá": st.column_config.TextColumn("Đánh giá", width="small"),
            "Độ phủ TV (%)": st.column_config.NumberColumn("Độ phủ TV (%)", format="%.0f",
                                                           help="Tỷ lệ ô lưới có NDVI ≥ 0.3"),
            "Số ô lưới": st.column_config.NumberColumn("Số ô lưới", format="%d"),
            "Diện tích (km²)": st.column_config.NumberColumn("Diện tích (km²)", format="%.2f"),
            "Dân số": st.column_config.NumberColumn("Dân số", format="%d"),
        },
    )
    have = table.dropna(subset=["NDVI TB"])
    if not have.empty:
        top, low = have.loc[have["NDVI TB"].idxmax()], have.loc[have["NDVI TB"].idxmin()]
        missing = len(table) - len(have)
        st.caption(
            f"Cao nhất: **{top['Đơn vị']}** ({top['NDVI TB']:.3f}) · Thấp nhất: **{low['Đơn vị']}** ({low['NDVI TB']:.3f})"
            + (f" · {missing} đơn vị chưa có ô lưới NDVI (nằm cuối bảng)." if missing else "")
        )




# # components/ward_panels.py
# """
# Hai khối giao diện (chỉ HIỂN THỊ, không đổi dữ liệu/mô hình):
# - render_ndvi_range_filter: thanh chọn khoảng NDVI đặt trên bản đồ -> trả về (thấp, cao, kiểu) cho render_map.
# - render_ward_ranking:      bảng xếp hạng NDVI của các phường/xã (chọn tăng dần / giảm dần).
# Cả hai đọc thống kê NDVI từng phường/xã đã được tính sẵn (cùng nguồn với popup trên bản đồ).
# """
# import pandas as pd
# import streamlit as st
# from utils.map_utils import NDVI_VMIN, NDVI_VMAX
# from utils.ward_info import get_ward_stats, build_ranking_table
# from components.layout import render_section_title



# def _reset_range():
#     st.session_state["ndvi_range_rev"] = st.session_state.get("ndvi_range_rev", 0) + 1   # đổi key -> thanh trượt về mặc định


# def render_ndvi_range_filter(df):
#     """
#     Bộ lọc gọn đặt dưới ô chú giải: thanh trượt + nút đặt lại + 1 dòng đếm số phường/xã.
#     Trả về (thấp, cao, "highlight") khi đã thu hẹp khoảng NDVI, trả về None khi chưa có dữ liệu hoặc để nguyên toàn thang.
#     """
#     stats, _, gdf = get_ward_stats(df)
#     if stats is None:
#         return None
#     total = len(gdf)
#     rev = st.session_state.setdefault("ndvi_range_rev", 0)
#     full = (float(NDVI_VMIN), float(NDVI_VMAX))

#     with st.container(border=True):
#         st.markdown("<span class='rf-marker'></span>", unsafe_allow_html=True)   # đánh dấu để CSS thu nhỏ khung này
#         lo, hi = st.slider(
#             "Lọc phường/xã theo NDVI", min_value=full[0], max_value=full[1], value=full, step=0.01,
#             format="%.2f", key=f"ndvi_range_{rev}",
#             help="Kéo hai đầu để chọn khoảng NDVI. Phường/xã có NDVI trung bình trong khoảng sẽ được tô sáng trên bản đồ.",
#         )
#         st.button("↺ Đặt lại", key="ndvi_range_reset", on_click=_reset_range, use_container_width=True)

#         lo, hi = round(float(lo), 2), round(float(hi), 2)
#         active = (lo, hi) != full
#         if active:
#             n_in = int(((stats["ndvi_mean"] >= lo) & (stats["ndvi_mean"] <= hi)).sum())
#             st.markdown(f"<div class='rf-count'><b>{n_in}/{total}</b> đơn vị có NDVI từ <b>{lo:.2f}</b> đến <b>{hi:.2f}</b></div>",
#                         unsafe_allow_html=True)
#         else:
#             st.markdown("<div class='rf-count'>Kéo thanh trượt để lọc phường/xã theo NDVI.</div>", unsafe_allow_html=True)
#     return (lo, hi, "highlight") if active else None


# def render_ward_ranking(df, period_label=""):
#     """Bảng xếp hạng NDVI các phường/xã. Chỉ hiện sau khi đã có dữ liệu (bấm Chạy dự báo AI)."""
#     if df is None or df.empty:
#         return
#     stats, _, gdf = get_ward_stats(df)
#     if gdf is None or stats is None:
#         return

#     table = build_ranking_table(stats, gdf)
#     title = f"🏆 Xếp hạng NDVI theo phường/xã – tháng {period_label}" if period_label else "🏆 Xếp hạng NDVI theo phường/xã"
#     render_section_title(
#         title=title,
#         subtitle=f"{len(table)} đơn vị hành chính, xếp theo NDVI trung bình của các ô lưới nằm trong ranh giới. "
#                  "Bấm tiêu đề cột để sắp xếp theo tiêu chí khác.",
#     )
#     # order = st.radio("Sắp xếp theo NDVI:", ["Giảm dần (cao nhất trước)", "Tăng dần (thấp nhất trước)"],
#     #                  horizontal=True, key="ward_rank_order")
#     # asc = order.startswith("Tăng")
#     # table = table.sort_values(["NDVI TB", "Đơn vị"], ascending=[asc, True], na_position="last", kind="mergesort")

#     table = table.sort_values(["NDVI TB", "Đơn vị"], ascending=[False, True], na_position="last", kind="mergesort")
    
#     st.dataframe(
#         table, hide_index=True, use_container_width=True, height=420,
#         column_config={
#             "Hạng": st.column_config.NumberColumn("Hạng", format="%d", width="small",
#                                                   help="Hạng theo NDVI trung bình (1 = xanh nhất)"),
#             "Đơn vị": st.column_config.TextColumn("Đơn vị", width="medium"),
#             "NDVI TB": st.column_config.ProgressColumn("NDVI TB", min_value=float(NDVI_VMIN), max_value=float(NDVI_VMAX),
#                                                        format="%.3f"),
#             "Đánh giá": st.column_config.TextColumn("Đánh giá", width="small"),
#             "Độ phủ TV (%)": st.column_config.NumberColumn("Độ phủ TV (%)", format="%.0f",
#                                                            help="Tỷ lệ ô lưới có NDVI ≥ 0.3"),
#             "Số ô lưới": st.column_config.NumberColumn("Số ô lưới", format="%d"),
#             "Diện tích (km²)": st.column_config.NumberColumn("Diện tích (km²)", format="%.2f"),
#             "Dân số": st.column_config.NumberColumn("Dân số", format="%d"),
#         },
#     )
#     have = table.dropna(subset=["NDVI TB"])
#     if not have.empty:
#         top, low = have.loc[have["NDVI TB"].idxmax()], have.loc[have["NDVI TB"].idxmin()]
#         missing = len(table) - len(have)
#         st.caption(
#             f"Cao nhất: **{top['Đơn vị']}** ({top['NDVI TB']:.3f}) · Thấp nhất: **{low['Đơn vị']}** ({low['NDVI TB']:.3f})"
#             + (f" · {missing} đơn vị chưa có ô lưới NDVI (nằm cuối bảng)." if missing else "")
#         )




# # # components/ward_panels.py
# # """
# # Hai khối giao diện (chỉ HIỂN THỊ, không đổi dữ liệu/mô hình):
# # - render_ndvi_range_filter: thanh chọn khoảng NDVI đặt trên bản đồ -> trả về (thấp, cao, kiểu) cho render_map.
# # - render_ward_ranking:      bảng xếp hạng NDVI của các phường/xã (chọn tăng dần / giảm dần).
# # Cả hai đọc thống kê NDVI từng phường/xã đã được tính sẵn (cùng nguồn với popup trên bản đồ).
# # """
# # import pandas as pd
# # import streamlit as st
# # from utils.map_utils import NDVI_STOPS, NDVI_VMIN, NDVI_VMAX
# # from utils.ward_info import get_ward_stats, build_ranking_table
# # from components.layout import render_section_title

# # _SPAN = NDVI_VMAX - NDVI_VMIN
# # _GRAD = ", ".join(f"{c} {(v - NDVI_VMIN) / _SPAN * 100:.0f}%" for v, c in NDVI_STOPS)
# # MODES = {"Tô sáng": "highlight", "Ẩn ngoài khoảng": "hide"}


# # def _reset_range():
# #     st.session_state["ndvi_range_rev"] = st.session_state.get("ndvi_range_rev", 0) + 1   # đổi key -> thanh trượt về mặc định


# # def render_ndvi_range_filter(df):
# #     """
# #     Trả về (thấp, cao, "highlight" | "hide") khi người dùng đã thu hẹp khoảng NDVI,
# #     trả về None khi chưa có dữ liệu hoặc đang để nguyên toàn thang (không lọc).
# #     """
# #     stats, _, gdf = get_ward_stats(df)
# #     if stats is None:
# #         return None
# #     total = len(gdf)
# #     rev = st.session_state.setdefault("ndvi_range_rev", 0)
# #     full = (float(NDVI_VMIN), float(NDVI_VMAX))

# #     with st.container(border=True):
# #         c_slider, c_mode = st.columns([3, 1.6])
# #         with c_slider:
# #             lo, hi = st.slider(
# #                 "Khoảng NDVI cần xem", min_value=full[0], max_value=full[1], value=full, step=0.01,
# #                 key=f"ndvi_range_{rev}",
# #                 help="Kéo hai đầu để chọn khoảng NDVI. Phường/xã có NDVI trung bình nằm trong khoảng sẽ được làm nổi bật.",
# #             )
# #         with c_mode:
# #             mode_label = st.radio("Cách hiển thị", list(MODES), key="ndvi_range_mode", horizontal=True)
# #             st.button("↺ Đặt lại", key="ndvi_range_reset", on_click=_reset_range, use_container_width=True)

# #         lo, hi = round(float(lo), 2), round(float(hi), 2)
# #         active = (lo, hi) != full
# #         lo_pct, hi_pct = (lo - NDVI_VMIN) / _SPAN * 100, (hi - NDVI_VMIN) / _SPAN * 100
# #         st.markdown(
# #             f"<div class='rf-bar' style='background:linear-gradient(to right,{_GRAD})'>"
# #             f"<div class='rf-mask' style='left:0;width:{lo_pct:.1f}%'></div>"
# #             f"<div class='rf-mask' style='right:0;width:{100 - hi_pct:.1f}%'></div></div>"
# #             f"<div class='rf-scale'><span>{NDVI_VMIN:g}</span><span>{NDVI_VMIN + _SPAN / 2:g}</span><span>{NDVI_VMAX:g}</span></div>",
# #             unsafe_allow_html=True,
# #         )
# #         if active:
# #             n_in = int(((stats["ndvi_mean"] >= lo) & (stats["ndvi_mean"] <= hi)).sum())
# #             n_missing = total - len(stats)
# #             extra = f" · {n_missing} đơn vị chưa có dữ liệu NDVI nên bị làm mờ" if n_missing else ""
# #             st.markdown(f"<div class='rf-count'>Có <b>{n_in}/{total}</b> đơn vị có NDVI từ <b>{lo:.2f}</b> đến <b>{hi:.2f}</b>{extra}</div>",
# #                         unsafe_allow_html=True)
# #         else:
# #             st.markdown("<div class='rf-count'>Kéo hai đầu thanh trượt để chọn khoảng NDVI cần xem trên bản đồ.</div>",
# #                         unsafe_allow_html=True)
# #     return (lo, hi, MODES[mode_label]) if active else None


# # def render_ward_ranking(df, period_label=""):
# #     """Bảng xếp hạng NDVI các phường/xã. Chỉ hiện sau khi đã có dữ liệu (bấm Chạy dự báo AI)."""
# #     if df is None or df.empty:
# #         return
# #     stats, _, gdf = get_ward_stats(df)
# #     if gdf is None or stats is None:
# #         return

# #     table = build_ranking_table(stats, gdf)
# #     title = f"🏆 Xếp hạng NDVI theo phường/xã – tháng {period_label}" if period_label else "🏆 Xếp hạng NDVI theo phường/xã"
# #     render_section_title(
# #         title=title,
# #         subtitle=f"{len(table)} đơn vị hành chính, xếp theo NDVI trung bình của các ô lưới nằm trong ranh giới. "
# #                  "Bấm tiêu đề cột để sắp xếp theo tiêu chí khác.",
# #     )
# #     order = st.radio("Sắp xếp theo NDVI:", ["Giảm dần (cao nhất trước)", "Tăng dần (thấp nhất trước)"],
# #                      horizontal=True, key="ward_rank_order")
# #     asc = order.startswith("Tăng")
# #     table = table.sort_values(["NDVI TB", "Đơn vị"], ascending=[asc, True], na_position="last", kind="mergesort")

# #     st.dataframe(
# #         table, hide_index=True, use_container_width=True, height=420,
# #         column_config={
# #             "Hạng": st.column_config.NumberColumn("Hạng", format="%d", width="small",
# #                                                   help="Hạng theo NDVI trung bình (1 = xanh nhất)"),
# #             "Đơn vị": st.column_config.TextColumn("Đơn vị", width="medium"),
# #             "NDVI TB": st.column_config.ProgressColumn("NDVI TB", min_value=float(NDVI_VMIN), max_value=float(NDVI_VMAX),
# #                                                        format="%.3f"),
# #             "Đánh giá": st.column_config.TextColumn("Đánh giá", width="small"),
# #             "Độ phủ TV (%)": st.column_config.NumberColumn("Độ phủ TV (%)", format="%.0f",
# #                                                            help="Tỷ lệ ô lưới có NDVI ≥ 0.3"),
# #             "Số ô lưới": st.column_config.NumberColumn("Số ô lưới", format="%d"),
# #             "Diện tích (km²)": st.column_config.NumberColumn("Diện tích (km²)", format="%.2f"),
# #             "Dân số": st.column_config.NumberColumn("Dân số", format="%d"),
# #         },
# #     )
# #     have = table.dropna(subset=["NDVI TB"])
# #     if not have.empty:
# #         top, low = have.loc[have["NDVI TB"].idxmax()], have.loc[have["NDVI TB"].idxmin()]
# #         missing = len(table) - len(have)
# #         st.caption(
# #             f"Cao nhất: **{top['Đơn vị']}** ({top['NDVI TB']:.3f}) · Thấp nhất: **{low['Đơn vị']}** ({low['NDVI TB']:.3f})"
# #             + (f" · {missing} đơn vị chưa có ô lưới NDVI (nằm cuối bảng)." if missing else "")
# #         )
