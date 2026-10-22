# components/chart_view.py
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from utils.data_loader import get_db_engine
from components.layout import render_section_title


def render_chart_and_summary(selected_district, selected_province, selected_time, df=None):
    target_date = pd.to_datetime(selected_time).replace(day=1)
    start_date = target_date - pd.DateOffset(months=12)
    time_str = target_date.strftime('%m/%Y')

    render_section_title(
        title=f"📈 Biến động NDVI 12 tháng đến mốc {time_str}",
        subtitle="Giá trị NDVI trung bình toàn TP. Hồ Chí Minh theo từng tháng.",
    )

    historical_dates, historical_ndvi = [], []

    # 1. Lấy 12 tháng lịch sử từ CSDL
    try:
        engine = get_db_engine()
        query = f"""
            SELECT TO_CHAR(date, 'YYYY-MM-DD') AS date, AVG(ndvi_mean) AS ndvi_mean
            FROM public.ndvi_observed
            WHERE date >= '{start_date.strftime('%Y-%m-%d')}'
              AND date <= '{target_date.strftime('%Y-%m-%d')}'
            GROUP BY date
            ORDER BY date
        """
        df_real = pd.read_sql(query, engine)
        if not df_real.empty:
            df_real['date'] = pd.to_datetime(df_real['date'])
            df_real = df_real.sort_values('date')
            historical_dates = df_real['date'].tolist()
            historical_ndvi = df_real['ndvi_mean'].astype(float).tolist()
    except Exception as e:
        print(f"[DB CHART ERROR]: {e}")

    # 2. Gắn giá trị của tháng mục tiêu (từ dữ liệu đang hiển thị trên bản đồ)
    has_target = False
    if df is not None and not df.empty and 'ndvi_mean' in df.columns:
        target_val = float(df['ndvi_mean'].mean())
        if historical_dates and pd.Timestamp(historical_dates[-1]) == target_date:
            historical_ndvi[-1] = target_val  # tháng mục tiêu đã có trong CSDL -> ghi đè
        else:
            historical_dates.append(target_date)  # chưa có -> thêm điểm mới (tránh ghi đè nhầm tháng khác)
            historical_ndvi.append(target_val)
        has_target = True

    is_ai = bool(st.session_state.get("ndvi_is_ai"))
    latest_ndvi = float(historical_ndvi[-1]) if historical_ndvi else None

    # 3. Vẽ biểu đồ
    fig = go.Figure()
    if historical_dates:
        fig.add_trace(go.Scatter(
            x=historical_dates, y=historical_ndvi, mode="lines+markers",
            name="NDVI trung bình tháng",
            line=dict(color="#16A34A", width=2.5), marker=dict(size=7),
            fill="tozeroy", fillcolor="rgba(34,197,94,0.10)",
            hovertemplate="Tháng %{x|%m/%Y}<br>NDVI: %{y:.3f}<extra></extra>",
        ))
        if has_target:
            fig.add_trace(go.Scatter(
                x=[historical_dates[-1]], y=[historical_ndvi[-1]], mode="markers",
                name="Dự báo AI (mốc đã chọn)" if is_ai else "Mốc đã chọn",
                marker=dict(size=13, color="#F59E0B" if is_ai else "#14532D",
                            symbol="diamond", line=dict(width=2, color="#FFFFFF")),
                hovertemplate="Mốc %{x|%m/%Y}<br>NDVI: %{y:.3f}<extra></extra>",
            ))

    fig.update_layout(
        template="plotly_white", paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        height=300, margin=dict(l=10, r=10, t=30, b=10),
        font=dict(family="Be Vietnam Pro, Segoe UI, sans-serif", size=12, color="#14301F"),
        xaxis=dict(title="Thời gian", showgrid=True, gridcolor="#E3EFE6", tickformat="%m/%Y"),
        yaxis=dict(title="NDVI", showgrid=True, gridcolor="#E3EFE6", range=[-0.1, 1.0]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )
    if not historical_dates:
        fig.add_annotation(text="Chưa có dữ liệu để hiển thị biểu đồ", x=0.5, y=0.5,
                           xref="paper", yref="paper", showarrow=False,
                           font=dict(size=14, color="#5B7A66"))
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})

    # 4. Đánh giá trạng thái thảm thực vật
    if latest_ndvi is None:
        health_status = "Chưa có dữ liệu"
    elif latest_ndvi >= 0.5:
        health_status = "Tốt 🟢"
    elif latest_ndvi >= 0.2:
        health_status = "Trung bình 🟡"
    else:
        health_status = "Cần chú ý 🔴"

    # 5. Thẻ thông tin
    ndvi_text = f"{latest_ndvi:.3f}" if latest_ndvi is not None else "—"
    st.markdown(f"""
        <div class="info-grid">
            <div class="info-card"><div class="lbl">Khu vực</div><div class="val">{selected_district.strip()}</div></div>
            <div class="info-card"><div class="lbl">Tỉnh / Thành phố</div><div class="val">{selected_province}</div></div>
            <div class="info-card"><div class="lbl">Tình trạng thảm thực vật</div><div class="val">{health_status}</div></div>
            <div class="info-card"><div class="lbl">NDVI tại mốc {time_str}</div><div class="val">{ndvi_text}</div></div>
        </div>
    """, unsafe_allow_html=True)
