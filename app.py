import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# -----------------------------------------------------------------------------
# 1. CẤU HÌNH TRANG & DARK MODE STYLING (STYLE NALIKA DARK ADMIN)
# -----------------------------------------------------------------------------
st.set_page_config(
    layout="wide",
    page_title="GEO BIG DATA - NDVI PREDICTION PLATFORM",
    page_icon="🌐"
)

# Custom CSS cho giao diện Dark Mode cao cấp
st.markdown("""
    <style>
    /* Dark background overall */
    .stApp {
        background-color: #121824;
        color: #E2E8F0;
    }
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #1A2332;
        border-right: 1px solid #2D3748;
    }
    /* Metric Cards Styling */
    div[data-testid="stMetricValue"] {
        color: #10B981 !important;
        font-weight: bold;
    }
    /* Custom Box styling */
    .stat-card {
        background-color: #1A2332;
        border: 1px solid #2D3748;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    .stat-card h4 {
        margin: 0;
        color: #A0AEC0;
        font-size: 0.85rem;
    }
    .stat-card h2 {
        margin: 5px 0 0 0;
        color: #38BDF8;
        font-size: 1.4rem;
    }
    </style>
""", unsafe_unsafe_html=True if hasattr(st, 'unsafe_html') else True)

# -----------------------------------------------------------------------------
# 2. THANH BÊN BÊN TRÁI (EXPANDABLE SIDEBAR MENU)
# -----------------------------------------------------------------------------
st.sidebar.title("🌐 GEO PLATFORM")
st.sidebar.caption("Hệ thống Phân tích & Dự báo Chỉ số Vệ tinh")

# Dữ liệu mẫu tọa độ các khu vực (FlyTo target)
LOCATION_DATA = {
    "TP. Hồ Chí Minh": {
        "Toàn tỉnh/TP": [10.7769, 106.7009, 10],
        "Phường Long Nguyên": [11.1230, 106.6540, 13],
        "Quận 1": [10.7756, 106.7004, 14],
        "Thành phố Thủ Đức": [10.8494, 106.7537, 12]
    },
    "An Giang": {
        "Toàn tỉnh/TP": [10.5361, 105.1325, 10],
        "Huyện Chợ Mới": [10.5000, 105.5500, 12],
        "TP. Long Xuyên": [10.3800, 105.4300, 13]
    }
}

# Menu dạng Expander (Xổ xuống dễ thêm tính năng sau này)
with st.sidebar.expander("🔮 DỰ BÁO CHỈ SỐ NDVI", expanded=True):
    # 1. Chọn Tỉnh / Thành phố
    selected_province = st.selectbox("Chọn Tỉnh / Thành phố:", list(LOCATION_DATA.keys()))
    
    # 2. Chọn Quận / Huyện / Phường / Xã
    district_options = list(LOCATION_DATA[selected_province].keys())
    selected_district = st.selectbox("Chọn Quận / Huyện / Phường / Xã:", district_options)
    
    # 3. Chọn Tháng/Năm dự đoán
    selected_time = st.date_input("Chọn Tháng / Năm hiển thị:", pd.to_datetime("2026-09-01"))
    
    st.markdown("---")
    # 4. Action Buttons
    btn_predict = st.button("🚀 CHẠY DỰ BÁO AI", use_container_width=True, type="primary")
    btn_export = st.button("📥 XUẤT GEOJSON / CSV", use_container_width=True)

with st.sidebar.expander("⚙️ CẤU HÌNH BẢN ĐỒ", expanded=False):
    basemap_choice = st.radio("Chọn Lớp Bản Đồ Nền:", ["Esri Satellite", "OpenStreetMap"])
    show_boundary = st.checkbox("Hiển thị Ranh giới Phường/Xã", value=True)

with st.sidebar.expander("📊 BÁO CÁO & THỐNG KÊ", expanded=False):
    st.write("• Lịch sử truy vấn dữ liệu")
    st.write("• Tải báo cáo PDF tổng hợp")

# -----------------------------------------------------------------------------
# 3. KHU VỰC BẢN ĐỒ CHÍNH (MAIN MAP AREA)
# -----------------------------------------------------------------------------
st.title("🛡️ BẢNG ĐIỀU KHIỂN GIÁM SÁT & DỰ BÁO THẢM THỰC VẬT (NDVI)")

col_map, col_metrics = st.columns([3, 1])

# Lấy thông tin vị trí chọn
lat, lng, zoom = LOCATION_DATA[selected_province][selected_district]

with col_map:
    st.subheader(f"📍 Bản đồ Vệ tinh: {selected_district} ({selected_province})")
    
    # Khởi tạo bản đồ Folium
    tile_provider = "Esri WorldImagery" if basemap_choice == "Esri Satellite" else "OpenStreetMap"
    m = folium.Map(location=[lat, lng], zoom_start=zoom, tiles=tile_provider)
    
    # Vẽ Legend chú giải màu NDVI
    legend_html = '''
     <div style="position: fixed; bottom: 30px; left: 30px; width: 180px; height: 90px; 
     background-color: rgba(26, 35, 50, 0.85); z-index:9999; font-size:12px; color: white;
     padding: 10px; border-radius: 6px; border: 1px solid #2D3748;">
     <b>Chú giải chỉ số NDVI</b><br>
     <i style="background: #d7191c; width: 12px; height: 12px; display: inline-block;"></i> -1.0 - 0.0 (Mặt nước/Đất)<br>
     <i style="background: #ffffbf; width: 12px; height: 12px; display: inline-block;"></i> 0.0 - 0.3 (Thực vật thưa)<br>
     <i style="background: #1a9641; width: 12px; height: 12px; display: inline-block;"></i> 0.3 - 1.0 (Thảm thực vật dầy)
     </div>
     '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Render Map
    st_folium(m, width="100%", height=460)

with col_metrics:
    st.subheader("📊 Thông Số Vùng")
    
    # Các ô vuông chỉ số NDVI
    st.markdown(f'''
        <div class="stat-card">
            <h4>NDVI MEAN (Trung bình)</h4>
            <h2>0.642</h2>
        </div><br>
        <div class="stat-card">
            <h4>NDVI MAX (Cao nhất)</h4>
            <h2 style="color: #10B981;">0.891</h2>
        </div><br>
        <div class="stat-card">
            <h4>NDVI MIN (Thấp nhất)</h4>
            <h2 style="color: #EF4444;">-0.120</h2>
        </div>
    ''', unsafe_allow_html=True)
    
    # Vòng tròn chỉ số sức khỏe thực vật (Gauge Chart)
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = 78,
        title = {'text': "Độ phủ xanh", 'font': {'size': 14, 'color': "#A0AEC0"}},
        number = {'suffix': "%", 'font': {'color': "#10B981", 'size': 20}},
        gauge = {
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#1A2332"},
            'bar': {'color': "#10B981"},
            'bgcolor': "#1A2332",
            'bordercolor': "#2D3748",
        }
    ))
    fig_gauge.update_layout(height=160, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_gauge, use_container_width=True)

# -----------------------------------------------------------------------------
# 4. BẢNG PHÂN TÍCH & BIỂU ĐỒ CHUỖI THỜI GIAN (BOTTOM PANEL)
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("📈 BIẾN ĐỘNG CHỈ SỐ NDVI THEO THỜI GIAN (2017 - 2026)")

# Tạo dữ liệu chuỗi thời gian giả lập
dates = pd.date_range(start="2017-01-01", end="2026-09-01", freq="MS")
actual_ndvi = 0.5 + 0.2 * np.sin(np.linspace(0, 20, len(dates))) + np.random.normal(0, 0.03, len(dates))

# Giả lập đường dự báo AI
future_dates = pd.date_range(start="2026-09-01", end="2027-06-01", freq="MS")
predicted_ndvi = 0.5 + 0.2 * np.sin(np.linspace(20, 22, len(future_dates)))

fig_chart = go.Figure()

# Đường nét liền: Giá trị NDVI thực tế
fig_chart.add_trace(go.Scatter(
    x=dates, y=actual_ndvi, 
    mode='lines+markers', 
    name='NDVI Thực tế',
    line=dict(color='#38BDF8', width=2)
))

# Đường nét đứt: Giá trị NDVI dự báo
fig_chart.add_trace(go.Scatter(
    x=future_dates, y=predicted_ndvi, 
    mode='lines+markers', 
    name='AI Dự báo tương lai',
    line=dict(color='#F59E0B', width=2, dash='dash')
))

fig_chart.update_layout(
    template="plotly_dark",
    paper_bgcolor='#1A2332',
    plot_bgcolor='#1A2332',
    height=320,
    margin=dict(l=20, r=20, t=20, b=20),
    xaxis=dict(showgrid=True, gridcolor='#2D3748'),
    yaxis=dict(showgrid=True, gridcolor='#2D3748', range=[-0.2, 1.0]),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

st.plotly_chart(fig_chart, use_container_width=True)

# 5. Thẻ Chỉ Số Nhanh / Báo Cáo Tóm Tắt (KPI Report Cards)
st.markdown("### 📋 BÁO CÁO TÓM TẮT KHU VỰC")
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.info(f"**Vùng theo dõi:**\n\n{selected_district}")
with c2:
    st.info(f"**Tỉnh / Thành phố:**\n\n{selected_province}")
with c3:
    st.info(f"**Đánh giá sức khỏe:**\n\nThảm thực vật phát triển TỐT 🟢")
with c4:
    st.info(f"**Mốc thời gian:**\n\n{selected_time.strftime('%m/%Y')}")
