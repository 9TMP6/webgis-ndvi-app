# components/compare_view.py
# Màn hình "So sánh mô hình": thay thế bản đồ + chỉ số + biểu đồ 12 tháng (chỉ admin mới vào được).
import html
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from components.layout import render_section_title
from utils.model_metrics import ensure_metrics
from utils.compare_data import (
    START_DATE, SERIES, get_last_month, load_monthly_comparison, load_model_metrics, load_deviation_sample,
)

COLORS = {"Quan trắc (CSDL)": "#14532D", "LSTM": "#F59E0B", "GRU": "#3B82F6", "CNNLSTM": "#A855F7"}
FONT = dict(family="Be Vietnam Pro, Segoe UI, sans-serif", size=12, color="#14301F")


def _layout(fig, title):
    fig.update_layout(
        title=dict(text=title, font=dict(size=14)), template="plotly_white",
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF", height=360,
        margin=dict(l=10, r=10, t=50, b=10), font=FONT, hovermode="x unified",
        xaxis=dict(title="Thời gian", tickformat="%m/%Y", showgrid=True, gridcolor="#E3EFE6"),
        yaxis=dict(title="NDVI trung bình", showgrid=True, gridcolor="#E3EFE6"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


# Mỗi series 1 kiểu riêng để khi các đường trùng nhau vẫn nhìn thấy được (đường dày vẽ trước, đường mảnh vẽ đè lên)
_LINE_STYLE = {
    "Quan trắc (CSDL)": dict(width=3, dash="solid", symbol="circle", size=6),
    "LSTM":             dict(width=5, dash="solid", symbol="circle-open", size=13),
    "GRU":              dict(width=2, dash="dot", symbol="diamond", size=7),
    "CNNLSTM":          dict(width=2, dash="dash", symbol="square", size=6),
}


def _line_chart(df):
    fig = go.Figure()
    for s in SERIES:
        st_ = _LINE_STYLE[s]
        fig.add_trace(go.Scatter(
            x=df["date"], y=df[s], name=s, mode="lines+markers", connectgaps=False,  # tháng thiếu -> đứt khúc
            line=dict(color=COLORS[s], width=st_["width"], dash=st_["dash"]),
            marker=dict(size=st_["size"], symbol=st_["symbol"], color=COLORS[s],
                        line=dict(width=2, color=COLORS[s])),
            hovertemplate="%{y:.4f}<extra>" + s + "</extra>",
        ))
    return _layout(fig, "Biểu đồ đường")


def _bar_chart(df):
    fig = go.Figure()
    for s in SERIES:
        fig.add_trace(go.Bar(x=df["date"], y=df[s], name=s, marker_color=COLORS[s],
                             hovertemplate="%{y:.3f}<extra>" + s + "</extra>"))
    fig.update_layout(barmode="group", bargap=0.2)
    return _layout(fig, "Biểu đồ cột")


MODEL_ORDER = ["LSTM", "CNNLSTM", "GRU"]
_TABLE_CSS = """
<style>
.mm-wrap { max-height: 560px; overflow: auto; border: 1px solid #D7E8DB; border-radius: 12px; background: #FFFFFF; }
table.mm { width: 100%; border-collapse: collapse; font-size: 0.88rem; color: #14301F; }
table.mm th { position: sticky; top: 0; z-index: 1; background: #15803D; color: #FFFFFF; padding: 9px 12px;
              text-align: right; font-weight: 700; white-space: nowrap; }
table.mm th.l { text-align: left; }
table.mm th small { font-weight: 500; opacity: .85; }
table.mm td { padding: 7px 12px; text-align: right; font-variant-numeric: tabular-nums; border-bottom: 1px solid #E3EFE6; }
table.mm td.l { text-align: left; }
table.mm td.mon { background: #DCFCE7; color: #14532D; font-weight: 800; text-align: center; vertical-align: middle;
                  border-right: 2px solid #86EFAC; white-space: nowrap; }
table.mm tr.g-a td:not(.mon) { background: #F0FDF4; }
table.mm tr.g-b td:not(.mon) { background: #FFFFFF; }
table.mm tr.first td { border-top: 3px solid #15803D; }
table.mm .best { background: #16A34A; color: #FFFFFF; font-weight: 700; padding: 2px 9px; border-radius: 999px; }
</style>
"""


def _fmt(v, nd=4):
    return "—" if pd.isna(v) else f"{v:.{nd}f}"


def _detail_table_html(m: pd.DataFrame) -> str:
    """Mỗi tháng 1 nhóm (tối đa 3 dòng: LSTM, CNNLSTM, GRU); ô tốt nhất trong nhóm được tô xanh."""
    m = m.copy()
    m["_o"] = m["model"].map(lambda x: MODEL_ORDER.index(x) if x in MODEL_ORDER else 99)
    m = m.sort_values(["date", "_o"])
    cols = (("r2", True, 4), ("mae", False, 4), ("rmse", False, 4))   # (cột, càng lớn càng tốt?, số lẻ)
    body = []
    for gi, (d, g) in enumerate(m.groupby("date", sort=True)):
        best = {}
        for c, high, _nd in cols:
            v = g[c].dropna()
            if len(v) >= 2:                                   # chỉ so sánh khi có từ 2 mô hình trở lên
                best[c] = round(float(v.max() if high else v.min()), 6)
        cls = "g-a" if gi % 2 == 0 else "g-b"
        for i, (_, r) in enumerate(g.iterrows()):
            tr_cls = f"{cls} first" if i == 0 else cls
            cells = []
            if i == 0:
                cells.append(f'<td class="mon" rowspan="{len(g)}">{d:%m/%Y}</td>')
            cells.append(f'<td class="l"><b>{html.escape(str(r["model"]))}</b></td>')
            for c, _high, nd in cols:
                v = r[c]
                txt = _fmt(v, nd)
                if c in best and pd.notna(v) and round(float(v), 6) == best[c]:
                    txt = f'<span class="best">{txt}</span>'
                cells.append(f"<td>{txt}</td>")
            n = "—" if pd.isna(r["n_cells"]) else f"{int(r['n_cells']):,}"
            cells.append(f"<td>{n}</td>")
            body.append(f'<tr class="{tr_cls}">{"".join(cells)}</tr>')
    head = ('<tr><th>Tháng</th><th class="l">Mô hình</th><th>R² <small>↑ cao tốt</small></th>'
            '<th>MAE <small>↓ thấp tốt</small></th><th>RMSE <small>↓ thấp tốt</small></th><th>Số ô</th></tr>')
    return f'{_TABLE_CSS}<div class="mm-wrap"><table class="mm"><thead>{head}</thead><tbody>{"".join(body)}</tbody></table></div>'


def _metrics_section(m: pd.DataFrame, info: dict = None):
    st.markdown("<p class='panel-title'>📐 Chỉ số chính xác của các mô hình theo tháng</p>", unsafe_allow_html=True)
    if info:
        if info.get("error"):
            st.error(f"Không tính/lưu được chỉ số vào CSDL: {info['error']}")
        elif info.get("computed"):
            st.success(f"Đã tự tính và lưu thêm {info['computed']} dòng chỉ số vào bảng model_metrics.")
    if m.empty:
        st.info("Chưa có tháng nào đủ dữ liệu để tính chỉ số: cần có dự đoán của mô hình trong ndvi_predictions "
                "và dữ liệu quan trắc cùng tháng để đối chiếu.")
        return

    summary = (m.groupby("model")
                 .agg(**{"Số tháng": ("date", "nunique"), "R² TB": ("r2", "mean"),
                         "MAE TB": ("mae", "mean"), "RMSE TB": ("rmse", "mean")})
                 .reset_index().rename(columns={"model": "Mô hình"}))
    sty = (summary.style
           .format({"R² TB": "{:.4f}", "MAE TB": "{:.4f}", "RMSE TB": "{:.4f}"})
           .highlight_max(subset=["R² TB"], color="#BBF7D0")
           .highlight_min(subset=["MAE TB", "RMSE TB"], color="#BBF7D0"))
    st.caption("Trung bình theo các tháng đã chọn (ô xanh = mô hình tốt nhất):")
    st.dataframe(sty, hide_index=True, use_container_width=True)

    st.caption("Chi tiết từng tháng (ô xanh đậm = tốt nhất trong tháng đó):")
    st.markdown(_detail_table_html(m), unsafe_allow_html=True)


DEV_MODELS = ["lstm", "cnnlstm", "gru"]
DEV_LABELS = {"lstm": "LSTM", "cnnlstm": "CNNLSTM", "gru": "GRU"}


def _deviation_table_html(d: pd.DataFrame) -> str:
    """Nhóm theo tháng; độ chênh = mô hình - quan trắc; ô xanh = mô hình sát quan trắc nhất ở dòng đó."""
    body = []
    for gi, (month, g) in enumerate(d.groupby("date", sort=True)):
        cls = "g-a" if gi % 2 == 0 else "g-b"
        for i, (_, r) in enumerate(g.iterrows()):
            vals = {m: r[m] for m in DEV_MODELS if pd.notna(r[m])}
            best = min(vals, key=lambda m: abs(vals[m])) if len(vals) >= 2 else None
            best_abs = round(abs(vals[best]), 6) if best else None
            cells = []
            if i == 0:
                cells.append(f'<td class="mon" rowspan="{len(g)}">{month:%m/%Y}</td>')
            cells.append(f'<td class="l">#{int(r["grid_id"])} <small style="opacity:.7">'
                         f'({r["lat"]:.3f}°N, {r["lon"]:.3f}°E)</small></td>')
            cells.append(f'<td><b>{r["obs"]:.4f}</b></td>')
            for m in DEV_MODELS:
                v = r[m]
                if pd.isna(v):
                    cells.append("<td>—</td>")
                    continue
                txt = f"{v:+.4f}"
                if best and round(abs(v), 6) == best_abs:
                    txt = f'<span class="best">{txt}</span>'
                cells.append(f"<td>{txt}</td>")
            body.append(f'<tr class="{cls}{" first" if i == 0 else ""}">{"".join(cells)}</tr>')
    head = ('<tr><th>Tháng</th><th class="l">Ô lưới</th><th>NDVI quan trắc</th>'
            + "".join(f"<th>Lệch {DEV_LABELS[m]}</th>" for m in DEV_MODELS) + "</tr>")
    return f'{_TABLE_CSS}<div class="mm-wrap"><table class="mm"><thead>{head}</thead><tbody>{"".join(body)}</tbody></table></div>'


def _deviation_section(res: dict):
    st.markdown("<p class='panel-title'>🔎 Độ chênh lệch 1 số vùng</p>", unsafe_allow_html=True)
    if st.button("🔀 Lấy mẫu khác", key="btn_resample_dev"):
        res["dev"] = load_deviation_sample(str(res["start"].date()), str(res["end"].date()))
    d = res.get("dev")
    if d is None or d.empty:
        st.info("Chưa có ô nào vừa có quan trắc vừa có dự đoán trong khoảng thời gian đã chọn.")
        return
    st.caption(f"{len(d)} ô lưới lấy ngẫu nhiên trong khoảng đã chọn. Độ chênh = dự đoán − quan trắc "
               "(dương: dự đoán cao hơn thực tế). Ô xanh = mô hình sát quan trắc nhất ở dòng đó. "
               "Đây chỉ là mẫu minh hoạ, không đại diện toàn bản đồ; đánh giá chung xem bảng chỉ số ở trên.")
    st.markdown(_deviation_table_html(d), unsafe_allow_html=True)


def render_compare_view():
    render_section_title(
        title="📊 So sánh quan trắc và các mô hình AI",
        subtitle="Chỉ đọc dữ liệu đã lưu trong CSDL, không chạy dự báo. Mỗi điểm = NDVI trung bình của các ô lưới trong tháng.",
        source="db",
    )
    if st.button("← Quay lại bản đồ", key="btn_back_map"):
        st.session_state["view_mode"] = "map"
        st.rerun()

    try:
        last = get_last_month()
    except Exception as e:
        st.error(f"❌ Không đọc được CSDL: {e}")
        return
    if last is None:
        st.warning("CSDL chưa có dữ liệu.")
        return

    years = list(range(START_DATE.year, last.year + 1))
    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1.3], vertical_alignment="bottom")
    sm = c1.selectbox("Tháng bắt đầu", range(1, 13), index=0, key="cmp_sm")
    sy = c2.selectbox("Năm bắt đầu", years, index=0, key="cmp_sy")
    em = c3.selectbox("Tháng kết thúc", range(1, 13), index=last.month - 1, key="cmp_em")
    ey = c4.selectbox("Năm kết thúc", years, index=len(years) - 1, key="cmp_ey")
    go_btn = c5.button("📊 So sánh", type="primary", use_container_width=True, key="btn_run_compare")
    recalc = st.checkbox("Tính lại chỉ số chính xác cho khoảng này (xoá và tính mới)", key="cmp_recalc")

    if go_btn:
        start, end = pd.Timestamp(sy, sm, 1), pd.Timestamp(ey, em, 1)
        if start < START_DATE:
            start = START_DATE
        if start > end:
            st.error("Thời điểm bắt đầu phải trước hoặc bằng thời điểm kết thúc.")
            return
        if end > last:
            end = last
        with st.spinner("Đang lấy dữ liệu và kiểm tra/tính chỉ số chính xác..."):
            info = ensure_metrics(start, end, force=recalc)   # tháng nào thiếu chỉ số thì tự tính
            st.session_state["cmp_result"] = {
                "start": start, "end": end, "info": info,
                "monthly": load_monthly_comparison(str(start.date()), str(end.date())),
                "metrics": load_model_metrics(str(start.date()), str(end.date())),
                "dev": load_deviation_sample(str(start.date()), str(end.date())),
            }

    res = st.session_state.get("cmp_result")
    if not res:
        st.markdown("<div class='empty-hint'>Chọn khoảng thời gian rồi nhấn <b>So sánh</b>.</div>",
                    unsafe_allow_html=True)
        return

    df = res["monthly"]
    if df[SERIES].isna().all().all():
        st.warning("Khoảng thời gian này không có tháng nào đủ dữ liệu để vẽ.")
    else:
        st.plotly_chart(_line_chart(df), use_container_width=True, config={"displaylogo": False})
        st.plotly_chart(_bar_chart(df), use_container_width=True, config={"displaylogo": False})
        missing = {s: int(df[s].isna().sum()) for s in SERIES}
        st.caption(f"Số tháng bị trống (không có hoặc chưa đủ ô lưới) trên tổng {len(df)} tháng: "
                   + " · ".join(f"{k}: {v}" for k, v in missing.items()))
    _metrics_section(res["metrics"], res.get("info"))
    _deviation_section(res)


# # components/compare_view.py
# # Màn hình "So sánh mô hình": thay thế bản đồ + chỉ số + biểu đồ 12 tháng (chỉ admin mới vào được).
# import html
# import pandas as pd
# import streamlit as st
# import plotly.graph_objects as go
# from components.layout import render_section_title
# from utils.model_metrics import ensure_metrics
# from utils.compare_data import (
#     START_DATE, SERIES, get_last_month, load_monthly_comparison, load_model_metrics,
# )

# COLORS = {"Quan trắc (CSDL)": "#14532D", "LSTM": "#F59E0B", "GRU": "#3B82F6", "CNNLSTM": "#A855F7"}
# FONT = dict(family="Be Vietnam Pro, Segoe UI, sans-serif", size=12, color="#14301F")


# def _layout(fig, title):
#     fig.update_layout(
#         title=dict(text=title, font=dict(size=14)), template="plotly_white",
#         paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF", height=360,
#         margin=dict(l=10, r=10, t=50, b=10), font=FONT, hovermode="x unified",
#         xaxis=dict(title="Thời gian", tickformat="%m/%Y", showgrid=True, gridcolor="#E3EFE6"),
#         yaxis=dict(title="NDVI trung bình", showgrid=True, gridcolor="#E3EFE6"),
#         legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
#     )
#     return fig


# def _line_chart(df):
#     fig = go.Figure()
#     for s in SERIES:
#         fig.add_trace(go.Scatter(
#             x=df["date"], y=df[s], name=s, mode="lines+markers", connectgaps=False,  # tháng thiếu -> đứt khúc
#             line=dict(color=COLORS[s], width=3 if s == SERIES[0] else 2,
#                       dash="solid" if s == SERIES[0] else "dot"),
#             marker=dict(size=5),
#             hovertemplate="%{y:.3f}<extra>" + s + "</extra>",
#         ))
#     return _layout(fig, "Biểu đồ đường")


# def _bar_chart(df):
#     fig = go.Figure()
#     for s in SERIES:
#         fig.add_trace(go.Bar(x=df["date"], y=df[s], name=s, marker_color=COLORS[s],
#                              hovertemplate="%{y:.3f}<extra>" + s + "</extra>"))
#     fig.update_layout(barmode="group", bargap=0.2)
#     return _layout(fig, "Biểu đồ cột")


# MODEL_ORDER = ["LSTM", "CNNLSTM", "GRU"]
# _TABLE_CSS = """
# <style>
# .mm-wrap { max-height: 560px; overflow: auto; border: 1px solid #D7E8DB; border-radius: 12px; background: #FFFFFF; }
# table.mm { width: 100%; border-collapse: collapse; font-size: 0.88rem; color: #14301F; }
# table.mm th { position: sticky; top: 0; z-index: 1; background: #15803D; color: #FFFFFF; padding: 9px 12px;
#               text-align: right; font-weight: 700; white-space: nowrap; }
# table.mm th.l { text-align: left; }
# table.mm th small { font-weight: 500; opacity: .85; }
# table.mm td { padding: 7px 12px; text-align: right; font-variant-numeric: tabular-nums; border-bottom: 1px solid #E3EFE6; }
# table.mm td.l { text-align: left; }
# table.mm td.mon { background: #DCFCE7; color: #14532D; font-weight: 800; text-align: center; vertical-align: middle;
#                   border-right: 2px solid #86EFAC; white-space: nowrap; }
# table.mm tr.g-a td:not(.mon) { background: #F0FDF4; }
# table.mm tr.g-b td:not(.mon) { background: #FFFFFF; }
# table.mm tr.first td { border-top: 3px solid #15803D; }
# table.mm .best { background: #16A34A; color: #FFFFFF; font-weight: 700; padding: 2px 9px; border-radius: 999px; }
# </style>
# """


# def _fmt(v, nd=4):
#     return "—" if pd.isna(v) else f"{v:.{nd}f}"


# def _detail_table_html(m: pd.DataFrame) -> str:
#     """Mỗi tháng 1 nhóm (tối đa 3 dòng: LSTM, CNNLSTM, GRU); ô tốt nhất trong nhóm được tô xanh."""
#     m = m.copy()
#     m["_o"] = m["model"].map(lambda x: MODEL_ORDER.index(x) if x in MODEL_ORDER else 99)
#     m = m.sort_values(["date", "_o"])
#     cols = (("r2", True, 4), ("mae", False, 4), ("rmse", False, 4))   # (cột, càng lớn càng tốt?, số lẻ)
#     body = []
#     for gi, (d, g) in enumerate(m.groupby("date", sort=True)):
#         best = {}
#         for c, high, _nd in cols:
#             v = g[c].dropna()
#             if len(v) >= 2:                                   # chỉ so sánh khi có từ 2 mô hình trở lên
#                 best[c] = round(float(v.max() if high else v.min()), 6)
#         cls = "g-a" if gi % 2 == 0 else "g-b"
#         for i, (_, r) in enumerate(g.iterrows()):
#             tr_cls = f"{cls} first" if i == 0 else cls
#             cells = []
#             if i == 0:
#                 cells.append(f'<td class="mon" rowspan="{len(g)}">{d:%m/%Y}</td>')
#             cells.append(f'<td class="l"><b>{html.escape(str(r["model"]))}</b></td>')
#             for c, _high, nd in cols:
#                 v = r[c]
#                 txt = _fmt(v, nd)
#                 if c in best and pd.notna(v) and round(float(v), 6) == best[c]:
#                     txt = f'<span class="best">{txt}</span>'
#                 cells.append(f"<td>{txt}</td>")
#             n = "—" if pd.isna(r["n_cells"]) else f"{int(r['n_cells']):,}"
#             cells.append(f"<td>{n}</td>")
#             body.append(f'<tr class="{tr_cls}">{"".join(cells)}</tr>')
#     head = ('<tr><th>Tháng</th><th class="l">Mô hình</th><th>R² <small>↑ cao tốt</small></th>'
#             '<th>MAE <small>↓ thấp tốt</small></th><th>RMSE <small>↓ thấp tốt</small></th><th>Số ô</th></tr>')
#     return f'{_TABLE_CSS}<div class="mm-wrap"><table class="mm"><thead>{head}</thead><tbody>{"".join(body)}</tbody></table></div>'


# def _metrics_section(m: pd.DataFrame, info: dict = None):
#     st.markdown("<p class='panel-title'> Chỉ số chính xác của các mô hình theo tháng</p>", unsafe_allow_html=True)
#     if info:
#         if info.get("error"):
#             st.error(f"Không tính/lưu được chỉ số vào CSDL: {info['error']}")
#         elif info.get("computed"):
#             st.success(f"Đã tự tính và lưu thêm {info['computed']} dòng chỉ số vào bảng model_metrics.")
#     if m.empty:
#         st.info("Chưa có tháng nào đủ dữ liệu để tính chỉ số: cần có dự đoán của mô hình trong ndvi_predictions "
#                 "và dữ liệu quan trắc cùng tháng để đối chiếu.")
#         return

#     summary = (m.groupby("model")
#                  .agg(**{"Số tháng": ("date", "nunique"), "R² TB": ("r2", "mean"),
#                          "MAE TB": ("mae", "mean"), "RMSE TB": ("rmse", "mean")})
#                  .reset_index().rename(columns={"model": "Mô hình"}))
#     sty = (summary.style
#            .format({"R² TB": "{:.4f}", "MAE TB": "{:.4f}", "RMSE TB": "{:.4f}"})
#            .highlight_max(subset=["R² TB"], color="#BBF7D0")
#            .highlight_min(subset=["MAE TB", "RMSE TB"], color="#BBF7D0"))
#     st.caption("Trung bình theo các tháng đã chọn:")
#     st.dataframe(sty, hide_index=True, use_container_width=True)

#     st.caption("Chi tiết từng tháng:")
#     st.markdown(_detail_table_html(m), unsafe_allow_html=True)


# def render_compare_view():
#     render_section_title(
#         title="So sánh quan trắc và các mô hình AI",
#         subtitle="Chỉ đọc dữ liệu đã lưu trong CSDL, không chạy dự báo. Mỗi điểm = NDVI trung bình của các ô lưới trong tháng.",
#         source="db",
#     )
#     if st.button("← Quay lại bản đồ", key="btn_back_map"):
#         st.session_state["view_mode"] = "map"
#         st.rerun()

#     try:
#         last = get_last_month()
#     except Exception as e:
#         st.error(f"❌ Không đọc được CSDL: {e}")
#         return
#     if last is None:
#         st.warning("CSDL chưa có dữ liệu.")
#         return

#     years = list(range(START_DATE.year, last.year + 1))
#     c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1.3], vertical_alignment="bottom")
#     sm = c1.selectbox("Tháng bắt đầu", range(1, 13), index=0, key="cmp_sm")
#     sy = c2.selectbox("Năm bắt đầu", years, index=0, key="cmp_sy")
#     em = c3.selectbox("Tháng kết thúc", range(1, 13), index=last.month - 1, key="cmp_em")
#     ey = c4.selectbox("Năm kết thúc", years, index=len(years) - 1, key="cmp_ey")
#     go_btn = c5.button("So sánh", type="primary", use_container_width=True, key="btn_run_compare")
#     recalc = st.checkbox("Luôn làm mới chỉ số", key="cmp_recalc")

#     if go_btn:
#         start, end = pd.Timestamp(sy, sm, 1), pd.Timestamp(ey, em, 1)
#         if start < START_DATE:
#             start = START_DATE
#         if start > end:
#             st.error("Thời điểm bắt đầu phải trước hoặc bằng thời điểm kết thúc.")
#             return
#         if end > last:
#             end = last
#         with st.spinner("Đang lấy dữ liệu và kiểm tra/tính chỉ số chính xác..."):
#             info = ensure_metrics(start, end, force=recalc)   # tháng nào thiếu chỉ số thì tự tính
#             st.session_state["cmp_result"] = {
#                 "start": start, "end": end, "info": info,
#                 "monthly": load_monthly_comparison(str(start.date()), str(end.date())),
#                 "metrics": load_model_metrics(str(start.date()), str(end.date())),
#             }

#     res = st.session_state.get("cmp_result")
#     if not res:
#         st.markdown("<div class='empty-hint'>Chọn khoảng thời gian rồi nhấn <b>So sánh</b>.</div>",
#                     unsafe_allow_html=True)
#         return

#     df = res["monthly"]
#     if df[SERIES].isna().all().all():
#         st.warning("Khoảng thời gian này không có tháng nào đủ dữ liệu để vẽ.")
#     else:
#         st.plotly_chart(_line_chart(df), use_container_width=True, config={"displaylogo": False})
#         st.plotly_chart(_bar_chart(df), use_container_width=True, config={"displaylogo": False})
#         missing = {s: int(df[s].isna().sum()) for s in SERIES}
#         st.caption(f"Số tháng bị trống trên tổng {len(df)} tháng: "
#                    + " · ".join(f"{k}: {v}" for k, v in missing.items()))
#     _metrics_section(res["metrics"], res.get("info"))


# # # components/compare_view.py
# # # Màn hình "So sánh mô hình": thay thế bản đồ + chỉ số + biểu đồ 12 tháng (chỉ admin mới vào được).
# # import pandas as pd
# # import streamlit as st
# # import plotly.graph_objects as go
# # from components.layout import render_section_title
# # from utils.compare_data import (
# #     START_DATE, SERIES, get_last_month, load_monthly_comparison, load_model_metrics,
# # )

# # COLORS = {"Quan trắc (CSDL)": "#14532D", "LSTM": "#F59E0B", "GRU": "#3B82F6", "CNNLSTM": "#A855F7"}
# # FONT = dict(family="Be Vietnam Pro, Segoe UI, sans-serif", size=12, color="#14301F")


# # def _layout(fig, title):
# #     fig.update_layout(
# #         title=dict(text=title, font=dict(size=14)), template="plotly_white",
# #         paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF", height=360,
# #         margin=dict(l=10, r=10, t=50, b=10), font=FONT, hovermode="x unified",
# #         xaxis=dict(title="Thời gian", tickformat="%m/%Y", showgrid=True, gridcolor="#E3EFE6"),
# #         yaxis=dict(title="NDVI trung bình", showgrid=True, gridcolor="#E3EFE6"),
# #         legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
# #     )
# #     return fig


# # def _line_chart(df):
# #     fig = go.Figure()
# #     for s in SERIES:
# #         fig.add_trace(go.Scatter(
# #             x=df["date"], y=df[s], name=s, mode="lines+markers", connectgaps=False,  # tháng thiếu -> đứt khúc
# #             line=dict(color=COLORS[s], width=3 if s == SERIES[0] else 2,
# #                       dash="solid" if s == SERIES[0] else "dot"),
# #             marker=dict(size=5),
# #             hovertemplate="%{y:.3f}<extra>" + s + "</extra>",
# #         ))
# #     return _layout(fig, "Biểu đồ đường")


# # def _bar_chart(df):
# #     fig = go.Figure()
# #     for s in SERIES:
# #         fig.add_trace(go.Bar(x=df["date"], y=df[s], name=s, marker_color=COLORS[s],
# #                              hovertemplate="%{y:.3f}<extra>" + s + "</extra>"))
# #     fig.update_layout(barmode="group", bargap=0.2)
# #     return _layout(fig, "Biểu đồ cột")


# # def _metrics_section(m: pd.DataFrame):
# #     st.markdown("<p class='panel-title'>📐 Độ chính xác của mô hình (đọc từ bảng model_metrics)</p>",
# #                 unsafe_allow_html=True)
# #     if m.empty:
# #         st.info("Bảng model_metrics chưa có dữ liệu trong khoảng thời gian đã chọn.")
# #         return
# #     summary = (m.groupby("model")
# #                  .agg(**{"Số tháng": ("date", "nunique"), "R² TB": ("r2", "mean"),
# #                          "MAE TB": ("mae", "mean"), "RMSE TB": ("rmse", "mean"),
# #                          "Số ô TB": ("n_cells", "mean")})
# #                  .reset_index().rename(columns={"model": "Mô hình"}))
# #     st.dataframe(
# #         summary, hide_index=True, use_container_width=True,
# #         column_config={
# #             "R² TB": st.column_config.NumberColumn(format="%.4f"),
# #             "MAE TB": st.column_config.NumberColumn(format="%.4f"),
# #             "RMSE TB": st.column_config.NumberColumn(format="%.4f"),
# #             "Số ô TB": st.column_config.NumberColumn(format="%d"),
# #         },
# #     )
# #     with st.expander("Xem chi tiết từng tháng"):
# #         detail = m.assign(Tháng=m["date"].dt.strftime("%m/%Y")).drop(columns="date")
# #         detail = detail[["Tháng", "model", "r2", "mae", "rmse", "n_cells"]].rename(
# #             columns={"model": "Mô hình", "r2": "R²", "mae": "MAE", "rmse": "RMSE", "n_cells": "Số ô"})
# #         st.dataframe(detail, hide_index=True, use_container_width=True)


# # def render_compare_view():
# #     render_section_title(
# #         title="📊 So sánh quan trắc và các mô hình AI",
# #         subtitle="Chỉ đọc dữ liệu đã lưu trong CSDL, không chạy dự báo. Mỗi điểm = NDVI trung bình của các ô lưới trong tháng.",
# #         source="db",
# #     )
# #     if st.button("← Quay lại bản đồ", key="btn_back_map"):
# #         st.session_state["view_mode"] = "map"
# #         st.rerun()

# #     try:
# #         last = get_last_month()
# #     except Exception as e:
# #         st.error(f"❌ Không đọc được CSDL: {e}")
# #         return
# #     if last is None:
# #         st.warning("CSDL chưa có dữ liệu.")
# #         return

# #     years = list(range(START_DATE.year, last.year + 1))
# #     c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1.3], vertical_alignment="bottom")
# #     sm = c1.selectbox("Tháng bắt đầu", range(1, 13), index=0, key="cmp_sm")
# #     sy = c2.selectbox("Năm bắt đầu", years, index=0, key="cmp_sy")
# #     em = c3.selectbox("Tháng kết thúc", range(1, 13), index=last.month - 1, key="cmp_em")
# #     ey = c4.selectbox("Năm kết thúc", years, index=len(years) - 1, key="cmp_ey")
# #     go_btn = c5.button("📊 So sánh", type="primary", use_container_width=True, key="btn_run_compare")

# #     if go_btn:
# #         start, end = pd.Timestamp(sy, sm, 1), pd.Timestamp(ey, em, 1)
# #         if start < START_DATE:
# #             start = START_DATE
# #         if start > end:
# #             st.error("Thời điểm bắt đầu phải trước hoặc bằng thời điểm kết thúc.")
# #             return
# #         if end > last:
# #             end = last
# #         with st.spinner("Đang lấy dữ liệu từ CSDL..."):
# #             st.session_state["cmp_result"] = {
# #                 "start": start, "end": end,
# #                 "monthly": load_monthly_comparison(str(start.date()), str(end.date())),
# #                 "metrics": load_model_metrics(str(start.date()), str(end.date())),
# #             }

# #     res = st.session_state.get("cmp_result")
# #     if not res:
# #         st.markdown("<div class='empty-hint'>Chọn khoảng thời gian rồi nhấn <b>So sánh</b>.</div>",
# #                     unsafe_allow_html=True)
# #         return

# #     df = res["monthly"]
# #     if df[SERIES].isna().all().all():
# #         st.warning("Khoảng thời gian này không có tháng nào đủ dữ liệu để vẽ.")
# #     else:
# #         st.plotly_chart(_line_chart(df), use_container_width=True, config={"displaylogo": False})
# #         st.plotly_chart(_bar_chart(df), use_container_width=True, config={"displaylogo": False})
# #         missing = {s: int(df[s].isna().sum()) for s in SERIES}
# #         st.caption(f"Số tháng bị trống (không có hoặc chưa đủ ô lưới) trên tổng {len(df)} tháng: "
# #                    + " · ".join(f"{k}: {v}" for k, v in missing.items()))
# #     _metrics_section(res["metrics"])
