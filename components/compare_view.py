# components/compare_view.py
# Màn hình "So sánh mô hình": thay thế bản đồ + chỉ số + biểu đồ 12 tháng (chỉ admin mới vào được).
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from components.layout import render_section_title
from utils.compare_data import (
    START_DATE, SERIES, get_last_month, load_monthly_comparison, load_model_metrics,
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


def _line_chart(df):
    fig = go.Figure()
    for s in SERIES:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df[s], name=s, mode="lines+markers", connectgaps=False,  # tháng thiếu -> đứt khúc
            line=dict(color=COLORS[s], width=3 if s == SERIES[0] else 2,
                      dash="solid" if s == SERIES[0] else "dot"),
            marker=dict(size=5),
            hovertemplate="%{y:.3f}<extra>" + s + "</extra>",
        ))
    return _layout(fig, "Biểu đồ đường")


def _bar_chart(df):
    fig = go.Figure()
    for s in SERIES:
        fig.add_trace(go.Bar(x=df["date"], y=df[s], name=s, marker_color=COLORS[s],
                             hovertemplate="%{y:.3f}<extra>" + s + "</extra>"))
    fig.update_layout(barmode="group", bargap=0.2)
    return _layout(fig, "Biểu đồ cột")


def _metrics_section(m: pd.DataFrame):
    st.markdown("<p class='panel-title'>📐 Độ chính xác của mô hình (đọc từ bảng model_metrics)</p>",
                unsafe_allow_html=True)
    if m.empty:
        st.info("Bảng model_metrics chưa có dữ liệu trong khoảng thời gian đã chọn.")
        return
    summary = (m.groupby("model")
                 .agg(**{"Số tháng": ("date", "nunique"), "R² TB": ("r2", "mean"),
                         "MAE TB": ("mae", "mean"), "RMSE TB": ("rmse", "mean"),
                         "Số ô TB": ("n_cells", "mean")})
                 .reset_index().rename(columns={"model": "Mô hình"}))
    st.dataframe(
        summary, hide_index=True, use_container_width=True,
        column_config={
            "R² TB": st.column_config.NumberColumn(format="%.4f"),
            "MAE TB": st.column_config.NumberColumn(format="%.4f"),
            "RMSE TB": st.column_config.NumberColumn(format="%.4f"),
            "Số ô TB": st.column_config.NumberColumn(format="%d"),
        },
    )
    with st.expander("Xem chi tiết từng tháng"):
        detail = m.assign(Tháng=m["date"].dt.strftime("%m/%Y")).drop(columns="date")
        detail = detail[["Tháng", "model", "r2", "mae", "rmse", "n_cells"]].rename(
            columns={"model": "Mô hình", "r2": "R²", "mae": "MAE", "rmse": "RMSE", "n_cells": "Số ô"})
        st.dataframe(detail, hide_index=True, use_container_width=True)


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

    if go_btn:
        start, end = pd.Timestamp(sy, sm, 1), pd.Timestamp(ey, em, 1)
        if start < START_DATE:
            start = START_DATE
        if start > end:
            st.error("Thời điểm bắt đầu phải trước hoặc bằng thời điểm kết thúc.")
            return
        if end > last:
            end = last
        with st.spinner("Đang lấy dữ liệu từ CSDL..."):
            st.session_state["cmp_result"] = {
                "start": start, "end": end,
                "monthly": load_monthly_comparison(str(start.date()), str(end.date())),
                "metrics": load_model_metrics(str(start.date()), str(end.date())),
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
    _metrics_section(res["metrics"])
