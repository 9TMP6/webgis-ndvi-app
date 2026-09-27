import streamlit as st
import plotly.graph_objects as go
from utils.ai_engine import generate_ndvi_predictions

def render_chart_and_summary(selected_district, selected_province, selected_time):
    st.markdown("---")
    st.markdown("<p style='font-weight: bold; font-size: 0.9rem;'>📈 DIỄN BIẾN CHUỖI THỜI GIAN & DỰ BÁO AI (2017 - 2027)</p>", unsafe_allow_html=True)

    dates, actual_ndvi, future_dates, predicted_ndvi = generate_ndvi_predictions()

    fig_chart = go.Figure()
    fig_chart.add_trace(go.Scatter(x=dates, y=actual_ndvi, mode="lines+markers", name="NDVI Thực tế", line=dict(color="#38BDF8", width=1.5)))
    fig_chart.add_trace(go.Scatter(x=future_dates, y=predicted_ndvi, mode="lines+markers", name="AI Dự báo tương lai", line=dict(color="#F59E0B", width=1.5, dash="dash")))

    fig_chart.update_layout(
        template="plotly_dark", paper_bgcolor="#151D2A", plot_bgcolor="#151D2A",
        height=240, margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=True, gridcolor="#26334D"),
        yaxis=dict(showgrid=True, gridcolor="#26334D", range=[-0.2, 1.0]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_chart, use_container_width=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.info(f"**Vùng:** {selected_district}")
    with c2: st.info(f"**Tỉnh/TP:** {selected_province}")
    with c3: st.info("**Đánh giá:** Sức khỏe TỐT 🟢")
    with c4: st.info(f"**Mốc:** {selected_time.strftime('%m/%Y')}")
