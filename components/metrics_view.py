import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from utils.map_utils import NDVI_STOPS, NDVI_VMIN, NDVI_VMAX


def render_metrics(df=None):
    st.markdown("<p class='panel-title'>Các chỉ số vùng</p>", unsafe_allow_html=True)

    has_data = df is not None and not df.empty and 'ndvi_mean' in df.columns

    # 1. Tính chỉ số từ dữ liệu thật; chưa có dữ liệu thì hiển thị "—" (không dùng số giả)
    if has_data:
        mean_val = f"{df['ndvi_mean'].mean():.3f}"
        max_col = 'ndvi_max' if 'ndvi_max' in df.columns else 'ndvi_mean'
        min_col = 'ndvi_min' if 'ndvi_min' in df.columns else 'ndvi_mean'
        max_val = f"{df[max_col].max():.3f}"
        min_val = f"{df[min_col].min():.3f}"
        cell_count = f"{len(df):,}"
        veg_pct = int(round((df['ndvi_mean'] >= 0.3).sum() / len(df) * 100))
    else:
        mean_val = max_val = min_val = cell_count = "—"
        veg_pct = None

    # 2. Thẻ chỉ số
    st.markdown(f"""
        <div class="stat-grid">
            <div class="stat-box wide"><div class="stat-title">NDVI trung bình</div>
                <div class="stat-value" style="color:#15803D;">{mean_val}</div></div>
            <div class="stat-box"><div class="stat-title">NDVI lớn nhất</div>
                <div class="stat-value" style="color:#10B981;">{max_val}</div></div>
            <div class="stat-box"><div class="stat-title">NDVI nhỏ nhất</div>
                <div class="stat-value" style="color:#EF4444;">{min_val}</div></div>
            <div class="stat-box wide"><div class="stat-title">Số ô lưới</div>
                <div class="stat-value" style="color:#14532D;">{cell_count}</div></div>
        </div>
    """, unsafe_allow_html=True)

    # 3. Biểu đồ vòng: độ phủ thực vật
    if veg_pct is None:
        values, colors, label = [0, 100], ["#10B981", "#E3EFE6"], "—"
    else:
        values = [veg_pct, 100 - veg_pct]
        colors = ["#10B981" if veg_pct >= 50 else "#F59E0B", "#E3EFE6"]
        label = f"{veg_pct}%"

    fig_ring = go.Figure(go.Pie(
        values=values, hole=0.75, showlegend=False, hoverinfo="none", textinfo="none",
        marker=dict(colors=colors), sort=False,
    ))
    fig_ring.add_annotation(text=f"<b>{label}</b>", x=0.5, y=0.5,
                            font=dict(size=15, color="#14532D"), showarrow=False)
    fig_ring.update_layout(height=120, margin=dict(l=0, r=0, t=0, b=0),
                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_ring, use_container_width=True, config={'displayModeBar': False})
    st.markdown("<p class='ring-caption'>Độ phủ thực vật</p>", unsafe_allow_html=True)

    # 4. Chú giải
    span = NDVI_VMAX - NDVI_VMIN
    grad = ", ".join(f"{c} {(v - NDVI_VMIN) / span * 100:.0f}%" for v, c in NDVI_STOPS)
    ticks = "".join(
        f"<span style='position:absolute;left:{k*25}%;transform:translateX(-{k*25}%);'>"
        f"{round(NDVI_VMIN + span * k / 4, 2)}</span>"
        for k in range(5)
    )
    st.markdown(f"""
        <div class="legend-panel">
            <div style="font-weight:700;font-size:0.82rem;margin-bottom:6px;color:#15803D;">Chú giải chỉ số NDVI</div>
            <div style="height:14px;border-radius:4px;background:linear-gradient(to right,{grad});"></div>
            <div style="position:relative;height:16px;font-size:0.72rem;color:#5B7A66;margin-top:2px;">{ticks}</div>
            <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:#3F5B49;">
                <span>Thấp (đất trống, đô thị)</span><span>Cao (thực vật dày)</span>
            </div>
        </div>
    """, unsafe_allow_html=True)


def render_csv_export_button(df_result: pd.DataFrame, selected_date: str):
    """Nút xuất CSV chuẩn UTF-8 (tương thích Excel)."""
    if df_result is None or df_result.empty:
        st.warning("⚠️ Không có dữ liệu để xuất file CSV.")
        return

    csv_bytes = df_result.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 Tải xuống dữ liệu CSV",
        data=csv_bytes,
        file_name=f"ndvi_data_{selected_date}.csv",
        mime="text/csv",
        help="Tải file CSV chứa dữ liệu đã truy vấn và dự báo",
    )



# import streamlit as st
# import plotly.graph_objects as go
# import pandas as pd
# from utils.map_utils import NDVI_STOPS, NDVI_VMIN, NDVI_VMAX

# def render_metrics(df=None):
#     st.markdown("<p style='font-weight: bold; margin-bottom: 5px; color: #5B7A66;'>📈 CHỈ SỐ VÙNG</p>", unsafe_allow_html=True)

#     # 1. Tính toán giá trị thực tế từ Supabase DataFrame
#     if df is not None and not df.empty and 'ndvi_mean' in df.columns:
#         ndvi_mean_val = df['ndvi_mean'].mean()
#         ndvi_max_val = df['ndvi_max'].max() if 'ndvi_max' in df.columns else df['ndvi_mean'].max()
#         ndvi_min_val = df['ndvi_min'].min() if 'ndvi_min' in df.columns else df['ndvi_mean'].min()
        
#         # Tính % độ phủ thực vật (Tỷ lệ điểm có NDVI >= 0.3)
#         veg_count = (df['ndvi_mean'] >= 0.3).sum()
#         total_count = len(df)
#         veg_pct = int((veg_count / total_count) * 100) if total_count > 0 else 0
#     else:
#         # Giá trị mặc định khi chưa có dữ liệu
#         ndvi_mean_val, ndvi_max_val, ndvi_min_val = 0.642, 0.891, -0.120
#         veg_pct = 75

#     # 2. Hiển thị 3 Stat Box
#     st.markdown(f"""
#         <div class="stat-box"><div class="stat-title">NDVI Mean</div><div class="stat-value" style="color: #15803D;">{ndvi_mean_val:.3f}</div></div>
#         <div class="stat-box"><div class="stat-title">NDVI Max</div><div class="stat-value" style="color: #10B981;">{ndvi_max_val:.3f}</div></div>
#         <div class="stat-box"><div class="stat-title">NDVI Min</div><div class="stat-value" style="color: #EF4444;">{ndvi_min_val:.3f}</div></div>
#     """, unsafe_allow_html=True)

#     # 3. Biểu đồ Donut Ring động theo % độ phủ thực vật
#     fig_ring = go.Figure(go.Pie(
#         values=[veg_pct, 100 - veg_pct], hole=0.75, showlegend=False, hoverinfo="none", textinfo="none",
#         marker=dict(colors=["#10B981" if veg_pct >= 50 else "#F59E0B", "#E3EFE6"])
#     ))
#     fig_ring.add_annotation(text=f"<b>{veg_pct} %</b>", x=0.5, y=0.5, font=dict(size=15, color="#14532D"), showarrow=False)
#     fig_ring.update_layout(height=120, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    
#     st.plotly_chart(fig_ring, use_container_width=True, config={'displayModeBar': False})
#     st.markdown("<p style='text-align: center; color: #5B7A66; font-size: 0.75rem; margin-top: -12px;'>Độ phủ thực vật</p>", unsafe_allow_html=True)

#     span = NDVI_VMAX - NDVI_VMIN
#     grad = ", ".join(f"{c} {(v - NDVI_VMIN) / span * 100:.0f}%" for v, c in NDVI_STOPS)
#     ticks = "".join(
#         f"<span style='position:absolute;left:{k*25}%;transform:translateX(-{k*25}%);'>{round(NDVI_VMIN + span * k / 4, 2)}</span>"
#         for k in range(5)
#     )
#     st.markdown(f"""
#         <div class="legend-panel">
#             <div style="font-weight: bold; font-size: 0.75rem; margin-bottom: 6px; color: #15803D;">Chú giải chỉ số NDVI</div>
#             <div style="height:14px;border-radius:4px;background:linear-gradient(to right,{grad});"></div>
#             <div style="position:relative;height:16px;font-size:0.68rem;color:#5B7A66;margin-top:2px;">{ticks}</div>
#             <div style="display:flex;justify-content:space-between;font-size:0.72rem;color:#3F5B49;">
#                 <span>Thấp (đất trống, đô thị)</span><span>Cao (thực vật dày)</span>
#             </div>
#         </div>
#     """, unsafe_allow_html=True)
# def render_csv_export_button(df_result: pd.DataFrame, selected_date: str):
#     """
#     Tạo nút xuất file CSV chuẩn UTF-8 tương thích tốt với Excel 📥
#     """
#     if df_result is None or df_result.empty:
#         st.warning("⚠️ Không có dữ liệu để xuất file CSV.")
#         return

#     # Chuẩn hóa định dạng CSV hỗ trợ Tiếng Việt trong Excel (utf-8-sig)
#     csv_bytes = df_result.to_csv(index=False).encode('utf-8-sig')

#     st.download_button(
#         label="📥 Tải xuống dữ liệu CSV",
#         data=csv_bytes,
#         file_name=f"ndvi_data_{selected_date}.csv",
#         mime="text/csv",
#         help="Bấm để tải file CSV chứa các trường dữ liệu đã truy vấn và dự báo ✨"
#     )
