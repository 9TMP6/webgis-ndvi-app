# components/chart_view.py
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
from utils.data_loader import get_db_engine

def render_chart_and_summary(selected_district, selected_province, selected_time, df=None):
    st.markdown("---")
    
    # Tiêu đề hiển thị động theo mốc thời gian người dùng chọn
    time_str = selected_time.strftime('%m/%Y')
    st.markdown(f"<p style='font-weight: bold; font-size: 0.9rem;'>📈 BIẾN ĐỘNG NDVI (12 THÁNG QUA ĐẾN MỐC {time_str})</p>", unsafe_allow_html=True)

    # Chuẩn hóa mốc thời gian mục tiêu (đầu tháng)
    target_date = pd.to_datetime(selected_time).replace(day=1)
    start_date = target_date - pd.DateOffset(months=12)

    historical_dates = []
    historical_ndvi = []

    # 1. Lấy 12 tháng lịch sử THẬT trực tiếp từ Database PostgreSQL
    try:
        engine = get_db_engine()
        query = f"""
            SELECT 
                TO_CHAR(MAKE_DATE(year, month, 1), 'YYYY-MM-DD') AS date,
                AVG(ndvi_mean) AS ndvi_mean
            FROM public.ndvi_records
            WHERE (year = {start_date.year} AND month >= {start_date.month})
               OR (year > {start_date.year} AND year < {target_date.year})
               OR (year = {target_date.year} AND month <= {target_date.month})
            GROUP BY year, month
            ORDER BY year, month
        """
        df_real = pd.read_sql(query, engine)
        
        if not df_real.empty:
            df_real['date'] = pd.to_datetime(df_real['date'])
            # Lọc đúng 12 tháng gần nhất tính đến tháng mục tiêu
            mask = (df_real['date'] >= start_date) & (df_real['date'] <= target_date)
            df_filtered = df_real.loc[mask].sort_values('date')
            
            if not df_filtered.empty:
                historical_dates = df_filtered['date'].tolist()
                historical_ndvi = df_filtered['ndvi_mean'].tolist()
    except Exception as e:
        print(f"[DB CHART ERROR]: {e}")

    # 2. Nếu có kết quả dự đoán từ AI (df truyền vào), cập nhật điểm cuối cùng thành giá trị dự đoán thật
    if df is not None and not df.empty and 'ndvi_mean' in df.columns:
        ai_latest_val = float(df['ndvi_mean'].mean())
        if len(historical_ndvi) > 0:
            # Gán điểm cuối cùng thành giá trị AI dự đoán cho tháng mục tiêu
            historical_ndvi[-1] = ai_latest_val
        else:
            # Fallback an toàn nếu DB trống
            historical_dates = [target_date]
            historical_ndvi = [ai_latest_val]

    # Chuyển đổi sang Series/Index để Plotly vẽ biểu đồ
    dates_series = pd.Series(historical_dates)
    ndvi_series = pd.Series(historical_ndvi)

    latest_ndvi = float(ndvi_series.iloc[-1]) if len(ndvi_series) > 0 else 0.5

    # 3. Vẽ biểu đồ đường với Plotly
    fig_chart = go.Figure()
    fig_chart.add_trace(go.Scatter(
        x=dates_series, 
        y=ndvi_series, 
        mode="lines+markers", 
        name="Chuỗi NDVI (12 tháng thật)", 
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

    # 4. Đánh giá trạng thái sức khỏe thảm thực vật
    if latest_ndvi >= 0.5:
        health_status = "Sức khỏe TỐT 🟢"
    elif latest_ndvi >= 0.2:
        health_status = "Trung bình 🟡"
    else:
        health_status = "Cần chú ý 🔴"

    # 5. Các thẻ thông tin bên dưới biểu đồ
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.info(f"**Vùng:** {selected_district}")
    with c2: st.info(f"**Tỉnh/TP:** {selected_province}")
    with c3: st.info(f"**Đánh giá:** {health_status}")
    with c4: st.info(f"**Mốc:** {selected_time.strftime('%m/%Y')}")
