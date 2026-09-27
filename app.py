import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# =============================================================================
# 1. CẤU HÌNH TRANG & CUSTOM CSS (CỐ ĐỊNH SIDEBAR LUÔN HIỆN)
# =============================================================================
st.set_page_config(
    layout="wide",
    page_title="GEO-NDVI INTELLIGENCE PLATFORM",
    page_icon="🌐",
    initial_sidebar_state="expanded"  # Mặc định luôn mở Sidebar 📌
)

st.markdown("""
    <style>
    /* 1. Ẩn Toolbar bên phải (Fork, GitHub, Menu 3 chấm) */
    [data-testid="stToolbar"] {
        visibility: hidden !important;
        height: 0px !important;
        position: absolute !important;
        right: -9999px !important;
    }
    [data-testid="stDecoration"] {
        display: none !important;
    }
    footer {
        display: none !important;
    }

    /* 2. ẨN HOÀN TOÀN NÚT THU / MỞ SIDEBAR (Nút << và >) -> Cố định Sidebar luôn hiện */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {
        display: none !important;
        visibility: hidden !important;
    }

    /* Header trong suốt */
    header[data-testid="stHeader"] {
        background: transparent !important;
    }

    /* Reset & Dark Background */
    html, body, [class*="css"] {
        font-size: 13px !important;
    }
    .stApp {
        background-color: #0B0F17;
        color: #E2E8F0;
    }
    
    /* Padding trang chính */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 0.8rem !important;
        padding-left: 1rem !important;
        padding-right: 0.5rem !important;
    }

    /* Top Header Bar Custom */
    .top-header {
        background: linear-gradient(90deg, #0F172A 0%, #1E293B 100%);
        padding: 8px 16px;
        border-radius: 8px;
        border: 1px solid #1E293B;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }
    .brand-title {
        font-size: 1.1rem !important;
        font-weight: 800;
        background: linear-gradient(135deg, #38BDF8 0%, #10B981 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .status-badge {
        background-color: rgba(16, 185, 129, 0.15);
        color: #10B981;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem !important;
        border: 1px solid rgba(16, 185, 129, 0.3);
        font-weight: 600;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #0F172A;
        border-right: 1px solid #1E293B;
        width: 300px !important; /* Đảm bảo độ rộng cố định chuẩn đẹp */
    }
    div[data-testid="stSidebarUserContent"] {
        padding-top: 1rem !important;
    }

    /* Metric Cards Cột Phải */
    .stat-box {
        background: #151D2A;
        border: 1px solid #26334D;
        border-radius: 6px;
        padding: 8px;
        text-align: center;
        margin-bottom: 8px;
    }
    .stat-title {
        color: #94A3B8;
        font-size: 0.7rem !important;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 2px;
    }
    .stat-value {
        font-size: 1.1rem !important;
        font-weight: 700;
    }

    /* Panel Chú thích NDVI */
    .legend-panel {
        background: #151D2A;
        border: 1px solid #26334D;
        border-radius: 6px;
        padding: 10px;
        margin-top: 10px;
    }
    .legend-item {
        display: flex;
        align-items: center;
        font-size: 0.75rem !important;
        margin-bottom: 4px;
        color: #CBD5E1;
    }
    .color-box {
        width: 12px;
        height: 12px;
        border-radius: 2px;
        margin-right: 6px;
        display: inline-block;
    }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# 2. TOP HEADER BAR
# =============================================================================
st.markdown("""
    <div class="top-header">
        <div class="brand-title">🌐 GEO-NDVI INTELLIGENCE PLATFORM</div>
        <div class="status-badge">🟢 AI ENGINE ONLINE</div>
    </div>
""", unsafe_allow_html=True)

# =============================================================================
# 3. DỮ LIỆU TỌA ĐỘ VỊ TRÍ
# =============================================================================
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

# =============================================================================
# 4. SIDEBAR - CỐ ĐỊNH BÊN TRÁI
# =============================================================================
with st.sidebar:
    st.markdown("<h3 style='color: #38BDF8; font-size: 1.1rem; font-weight: bold; margin-bottom: 15px;'>🎛️ BẢNG ĐIỀU KHIỂN</h3>", unsafe_allow_html=True)
    
    with st.expander("🔮 BỘ LỌC DỰ BÁO", expanded=True):
        selected_province = st.selectbox("Tỉnh / Thành phố:", list(LOCATION_DATA.keys()))
        district_options = list(LOCATION_DATA[selected_province].keys())
        selected_district = st.selectbox("Quận / Huyện / Phường:", district_options)
        selected_time = st.date_input("Mốc thời gian:", value=pd.to_datetime("2026-09-01"))
        
        btn_predict = st.button("🚀 CHẠY DỰ BÁO AI", use_container_width=True, type="primary")

    with st.expander("⚙️ CẤU HÌNH BẢN ĐỒ", expanded=False):
        basemap_choice = st.radio(
            "Lớp bản đồ nền:",
            ["Esri Satellite", "OpenStreetMap", "CartoDB Dark", "Google Hybrid"]
        )

    with st.expander("📊 XUẤT DỮ LIỆU & BÁO CÁO", expanded=False):
        sample_df = pd.DataFrame({
            "Lat": [LOCATION_DATA[selected_province][selected_district][0]],
            "Lng": [LOCATION_DATA[selected_province][selected_district][1]],
            "NDVI_Mean": [0.642],
            "Date": [selected_time.strftime("%Y-%m-%d")]
        })
        csv_data = sample_df.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="📥 Xuất dữ liệu CSV",
            data=csv_data,
            file_name=f"ndvi_{selected_district}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        st.download_button(
            label="🖼️ Xuất ảnh NDVI (.PNG)",
            data=b"PNG_DUMMY_BYTES",
            file_name=f"ndvi_map_{selected_district}.png",
            mime="image/png",
            use_container_width=True
        )
        
        if st.button("📄 Tạo báo cáo PDF", use_container_width=True):
            st.info("Chức năng kết xuất PDF đang được xử lý.")

lat, lng, zoom = LOCATION_DATA[selected_province][selected_district]

# =============================================================================
# 5. CHÍNH DIỆN: BẢN ĐỒ & CỘT CHỈ SỐ BÊN PHẢI
# =============================================================================
col_map, col_metrics = st.columns([3.3, 1.0])

with col_map:
    m = folium.Map(location=[lat, lng], zoom_start=zoom, tiles=None)
    
    if basemap_choice == "Esri Satellite":
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri", name="Esri Satellite"
        ).add_to(m)
    elif basemap_choice == "CartoDB Dark":
        folium.TileLayer(
            tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
            attr="CartoDB", name="CartoDB Dark"
        ).add_to(m)
    elif basemap_choice == "Google Hybrid":
        folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
            attr="Google", name="Google Hybrid"
        ).add_to(m)
    else:
        folium.TileLayer(tiles="OpenStreetMap", name="OpenStreetMap").add_to(m)

    folium.LayerControl().add_to(m)
    st_folium(m, width="100%", height=500)

with col_metrics:
    st.markdown("<p style='font-weight: bold; margin-bottom: 5px; color: #94A3B8;'>📈 CHỈ SỐ VÙNG</p>", unsafe_allow_html=True)
    
    st.markdown("""
        <div class="stat-box">
            <div class="stat-title">NDVI Mean</div>
            <div class="stat-value" style="color: #38BDF8;">0.642</div>
        </div>
        <div class="stat-box">
            <div class="stat-title">NDVI Max</div>
            <div class="stat-value" style="color: #10B981;">0.891</div>
        </div>
        <div class="stat-box">
            <div class="stat-title">NDVI Min</div>
            <div class="stat-value" style="color: #EF4444;">-0.120</div>
        </div>
    """, unsafe_allow_html=True)

    fig_ring = go.Figure(go.Pie(
        values=[75, 25],
        hole=0.75,
        showlegend=False,
        hoverinfo="none",
        textinfo="none",
        marker=dict(colors=["#FF4D4D", "#1E293B"])
    ))
    fig_ring.add_annotation(
        text="<b>75 %</b>",
        x=0.5, y=0.5,
        font=dict(size=15, color="#FFFFFF"),
        showarrow=False
    )
    fig_ring.update_layout(
        height=120,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    st.plotly_chart(fig_ring, use_container_width=True, config={'displayModeBar': False})
    st.markdown("<p style='text-align: center; color: #94A3B8; font-size: 0.75rem; margin-top: -12px;'>Độ phủ thực vật</p>", unsafe_allow_html=True)

    st.markdown("""
        <div class="legend-panel">
            <div style="font-weight: bold; font-size: 0.75rem; margin-bottom: 6px; color: #38BDF8;">Chú giải chỉ số NDVI</div>
            <div class="legend-item">
                <span class="color-box" style="background: #d7191c;"></span>
                -1.0 - 0.0 (Nước / Đất)
            </div>
            <div class="legend-item">
                <span class="color-box" style="background: #ffffbf;"></span>
                0.0 - 0.3 (Thực vật thưa)
            </div>
            <div class="legend-item">
                <span class="color-box" style="background: #1a9641;"></span>
                0.3 - 1.0 (Thảm thực vật dày)
            </div>
        </div>
    """, unsafe_allow_html=True)

# =============================================================================
# 6. PHẦN DƯỚI: BIỂU ĐỒ CHUỖI THỜI GIAN & KẾT QUẢ TÓM TẮT
# =============================================================================
st.markdown("---")
st.markdown("<p style='font-weight: bold; font-size: 0.9rem;'>📈 DIỄN BIẾN CHUỖI THỜI GIAN & DỰ BÁO AI (2017 - 2027)</p>", unsafe_allow_html=True)

np.random.seed(42)
dates = pd.date_range(start="2017-01-01", end="2026-09-01", freq="MS")
actual_ndvi = 0.5 + 0.2 * np.sin(np.linspace(0, 20, len(dates))) + np.random.normal(0, 0.03, len(dates))

future_dates = pd.date_range(start="2026-09-01", end="2027-06-01", freq="MS")
predicted_ndvi = 0.5 + 0.2 * np.sin(np.linspace(20, 22, len(future_dates)))

fig_chart = go.Figure()
fig_chart.add_trace(go.Scatter(x=dates, y=actual_ndvi, mode="lines+markers", name="NDVI Thực tế", line=dict(color="#38BDF8", width=1.5)))
fig_chart.add_trace(go.Scatter(x=future_dates, y=predicted_ndvi, mode="lines+markers", name="AI Dự báo tương lai", line=dict(color="#F59E0B", width=1.5, dash="dash")))

fig_chart.update_layout(
    template="plotly_dark",
    paper_bgcolor="#151D2A",
    plot_bgcolor="#151D2A",
    height=240,
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(showgrid=True, gridcolor="#26334D"),
    yaxis=dict(showgrid=True, gridcolor="#26334D", range=[-0.2, 1.0]),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
st.plotly_chart(fig_chart, use_container_width=True)

# Báo cáo tóm tắt
c1, c2, c3, c4 = st.columns(4)
with c1: st.info(f"**Vùng:** {selected_district}")
with c2: st.info(f"**Tỉnh/TP:** {selected_province}")
with c3: st.info("**Đánh giá:** Sức khỏe TỐT 🟢")
with c4: st.info(f"**Mốc:** {selected_time.strftime('%m/%Y')}")
