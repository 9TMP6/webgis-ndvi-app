# components/chart_view.py
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

def render_chart_and_summary(selected_district, selected_province, selected_time, df=None):
    st.markdown("---")
    
    # Tiêu đề hiển thị động theo mốc thời gian người dùng chọn
    time_str = selected_time.strftime('%m/%Y')
    st.markdown(f"<p style='font-weight: bold; font-size: 0.9rem;'>📈 BIẾN ĐỘNG NDVI (12 THÁNG QUA ĐẾN MỐC {time_str})</p>", unsafe_allow_html=True)

    # 1. Chuẩn bị dữ liệu 12 tháng trước đến tháng được chọn
    historical_dates = []
    historical_ndvi = []
    
    # Chuyển selected_time về dạng Period/Timestamp chuẩn tháng để lọc
    target_date = pd.to_datetime(selected_time).to_period('M')
    start_date = (target_date - 12).to_timestamp() # Lùi về 12 tháng trước
    end_date = target_date.to_timestamp()        # Tháng được chọn

    if df is not None and not df.empty and 'date' in df.columns and 'ndvi_mean' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        # Lọc dữ liệu trong khoảng 12 tháng tính đến tháng được chọn
        mask = (df['date'] >= start_date) & (df['date'] <= end_date)
        df_filtered = df.loc[mask].groupby('date')['ndvi_mean'].mean().reset_index().sort_values('date')
        
        historical_dates = df_filtered['date']
        historical_ndvi = df_filtered['ndvi_mean']

    # Nếu không đủ dữ liệu thực tế trong DataFrame, tạo dữ liệu mẫu mô phỏng 12 tháng
    if len(historical_dates) == 0:
        historical_dates = pd.date_range(end=end_date, periods=12, freq='ME')
        # Giả lập giá trị NDVI dao động nhẹ quanh mức 0.5 - 0.7 cho sinh động
        import numpy as np
        historical_ndvi = pd.Series(0.5 + 0.1 * np.sin(np.linspace(0, 3*np.pi, 12)))

    # Lấy giá trị NDVI mới nhất tại mốc thời gian được chọn
    latest_ndvi = float(historical_ndvi.iloc[-1]) if len(historical_ndvi) > 0 else 0.5

    # 2. Vẽ biểu đồ đường với Plotly (Tập trung vào 12 tháng biến động)
    fig_chart = go.Figure()
    fig_chart.add_trace(go.Scatter(
        x=historical_dates, 
        y=historical_ndvi, 
        mode="lines+markers", 
        name="Chuỗi NDVI (12 tháng)", 
        line=dict(color="#38BDF8", width=2),
        marker=dict(size=6)
    ))

    fig_chart.update_layout(
        template="plotly_dark", 
        paper_bgcolor="#151D2A", 
        plot_bgcolor="#151D2A",
        height=240, 
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=True, gridcolor="#26334D"),
        yaxis=dict(showgrid=True, gridcolor="#26334D", range=[-0.1, 1.0]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_chart, use_container_width=True)

    # 3. Đánh giá trạng thái sức khỏe thảm thực vật
    if latest_ndvi >= 0.5:
        health_status = "Sức khỏe TỐT 🟢"
    elif latest_ndvi >= 0.2:
        health_status = "Trung bình 🟡"
    else:
        health_status = "Cần chú ý 🔴"

    # 4. Các thẻ thông tin bên dưới biểu đồ
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.info(f"**Vùng:** {selected_district}")
    with c2: st.info(f"**Tỉnh/TP:** {selected_province}")
    with c3: st.info(f"**Đánh giá:** {health_status}")
    with c4: st.info(f"**Mốc:** {selected_time.strftime('%m/%Y')}")
