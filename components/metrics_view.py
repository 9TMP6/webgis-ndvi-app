import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from utils.map_utils import NDVI_STOPS, NDVI_VMIN, NDVI_VMAX

def render_metrics(df=None):
    st.markdown("<p style='font-weight: bold; margin-bottom: 5px; color: #5B7A66;'>📈 CHỈ SỐ VÙNG</p>", unsafe_allow_html=True)

    # 1. Tính toán giá trị thực tế từ Supabase DataFrame
    if df is not None and not df.empty and 'ndvi_mean' in df.columns:
        ndvi_mean_val = df['ndvi_mean'].mean()
        ndvi_max_val = df['ndvi_max'].max() if 'ndvi_max' in df.columns else df['ndvi_mean'].max()
        ndvi_min_val = df['ndvi_min'].min() if 'ndvi_min' in df.columns else df['ndvi_mean'].min()
        
        # Tính % độ phủ thực vật (Tỷ lệ điểm có NDVI >= 0.3)
        veg_count = (df['ndvi_mean'] >= 0.3).sum()
        total_count = len(df)
        veg_pct = int((veg_count / total_count) * 100) if total_count > 0 else 0
    else:
        # Giá trị mặc định khi chưa có dữ liệu
        ndvi_mean_val, ndvi_max_val, ndvi_min_val = 0.642, 0.891, -0.120
        veg_pct = 75

    # 2. Hiển thị 3 Stat Box
    st.markdown(f"""
        <div class="stat-box"><div class="stat-title">NDVI Mean</div><div class="stat-value" style="color: #15803D;">{ndvi_mean_val:.3f}</div></div>
        <div class="stat-box"><div class="stat-title">NDVI Max</div><div class="stat-value" style="color: #10B981;">{ndvi_max_val:.3f}</div></div>
        <div class="stat-box"><div class="stat-title">NDVI Min</div><div class="stat-value" style="color: #EF4444;">{ndvi_min_val:.3f}</div></div>
    """, unsafe_allow_html=True)

    # 3. Biểu đồ Donut Ring động theo % độ phủ thực vật
    fig_ring = go.Figure(go.Pie(
        values=[veg_pct, 100 - veg_pct], hole=0.75, showlegend=False, hoverinfo="none", textinfo="none",
        marker=dict(colors=["#10B981" if veg_pct >= 50 else "#F59E0B", "#E3EFE6"])
    ))
    fig_ring.add_annotation(text=f"<b>{veg_pct} %</b>", x=0.5, y=0.5, font=dict(size=15, color="#14532D"), showarrow=False)
    fig_ring.update_layout(height=120, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    
    st.plotly_chart(fig_ring, use_container_width=True, config={'displayModeBar': False})
    st.markdown("<p style='text-align: center; color: #5B7A66; font-size: 0.75rem; margin-top: -12px;'>Độ phủ thực vật</p>", unsafe_allow_html=True)

    span = NDVI_VMAX - NDVI_VMIN
    grad = ", ".join(f"{c} {(v - NDVI_VMIN) / span * 100:.0f}%" for v, c in NDVI_STOPS)
    ticks = "".join(
        f"<span style='position:absolute;left:{(v - NDVI_VMIN) / span * 100:.1f}%;transform:translateX(-50%);'>{v}</span>"
        for v in (0, 0.2, 0.4, 0.6)
    )
    st.markdown(f"""
        <div class="legend-panel">
            <div style="font-weight: bold; font-size: 0.75rem; margin-bottom: 6px; color: #15803D;">Chú giải chỉ số NDVI</div>
            <div style="height:12px;border-radius:3px;background:linear-gradient(to right,{grad});"></div>
            <div style="position:relative;height:14px;font-size:0.65rem;color:#5B7A66;">{ticks}</div>
            <div class="legend-item"><span class="color-box" style="background:#2b83ba;"></span> &lt; 0.0 (Sông hồ, mặt nước) 🌊</div>
            <div class="legend-item"><span class="color-box" style="background:#d73027;"></span> 0.00 - 0.18 (Đô thị, bê tông) 🏢</div>
            <div class="legend-item"><span class="color-box" style="background:#ef6a38;"></span> 0.18 - 0.30 (Đất trống, nhà thưa) 🏗️</div>
            <div class="legend-item"><span class="color-box" style="background:#d9ef8b;"></span> 0.30 - 0.45 (Cây xanh đô thị) 🍃</div><div class="legend-item"><span class="color-box" style="background:#1a9850;"></span> ≥ 0.48 (Rừng, cây trồng rậm) 🌳</div>
        </div>
    """, unsafe_allow_html=True)
def render_csv_export_button(df_result: pd.DataFrame, selected_date: str):
    """
    Tạo nút xuất file CSV chuẩn UTF-8 tương thích tốt với Excel 📥
    """
    if df_result is None or df_result.empty:
        st.warning("⚠️ Không có dữ liệu để xuất file CSV.")
        return

    # Chuẩn hóa định dạng CSV hỗ trợ Tiếng Việt trong Excel (utf-8-sig)
    csv_bytes = df_result.to_csv(index=False).encode('utf-8-sig')

    st.download_button(
        label="📥 Tải xuống dữ liệu CSV",
        data=csv_bytes,
        file_name=f"ndvi_data_{selected_date}.csv",
        mime="text/csv",
        help="Bấm để tải file CSV chứa các trường dữ liệu đã truy vấn và dự báo ✨"
    )
