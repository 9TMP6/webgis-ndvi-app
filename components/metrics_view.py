import streamlit as st
import plotly.graph_objects as go

def render_metrics():
    st.markdown("<p style='font-weight: bold; margin-bottom: 5px; color: #94A3B8;'>📈 CHỈ SỐ VÙNG</p>", unsafe_allow_html=True)
    st.markdown("""
        <div class="stat-box"><div class="stat-title">NDVI Mean</div><div class="stat-value" style="color: #38BDF8;">0.642</div></div>
        <div class="stat-box"><div class="stat-title">NDVI Max</div><div class="stat-value" style="color: #10B981;">0.891</div></div>
        <div class="stat-box"><div class="stat-title">NDVI Min</div><div class="stat-value" style="color: #EF4444;">-0.120</div></div>
    """, unsafe_allow_html=True)

    fig_ring = go.Figure(go.Pie(
        values=[75, 25], hole=0.75, showlegend=False, hoverinfo="none", textinfo="none",
        marker=dict(colors=["#FF4D4D", "#1E293B"])
    ))
    fig_ring.add_annotation(text="<b>75 %</b>", x=0.5, y=0.5, font=dict(size=15, color="#FFFFFF"), showarrow=False)
    fig_ring.update_layout(height=120, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    
    st.plotly_chart(fig_ring, use_container_width=True, config={'displayModeBar': False})
    st.markdown("<p style='text-align: center; color: #94A3B8; font-size: 0.75rem; margin-top: -12px;'>Độ phủ thực vật</p>", unsafe_allow_html=True)

    st.markdown("""
        <div class="legend-panel">
            <div style="font-weight: bold; font-size: 0.75rem; margin-bottom: 6px; color: #38BDF8;">Chú giải chỉ số NDVI</div>
            <div class="legend-item"><span class="color-box" style="background: #d7191c;"></span> -1.0 - 0.0 (Nước / Đất)</div>
            <div class="legend-item"><span class="color-box" style="background: #ffffbf;"></span> 0.0 - 0.3 (Thực vật thưa)</div>
            <div class="legend-item"><span class="color-box" style="background: #1a9641;"></span> 0.3 - 1.0 (Thảm thực vật dày)</div>
        </div>
    """, unsafe_allow_html=True)
