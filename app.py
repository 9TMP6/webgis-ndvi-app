import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import numpy as np
import plotly.graph_objects as go


# =============================================================================
# 1. CẤU HÌNH TRANG
# =============================================================================

st.set_page_config(
    layout="wide",
    page_title="GEO BIG DATA - NDVI PREDICTION PLATFORM",
    page_icon="🌐"
)


# =============================================================================
# 2. DARK MODE CSS
# =============================================================================

st.markdown(
    """
    <style>

    /* Background tổng */
    .stApp {
        background-color: #121824;
        color: #E2E8F0;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #1A2332;
        border-right: 1px solid #2D3748;
    }

    /* Metric */
    div[data-testid="stMetricValue"] {
        color: #10B981 !important;
        font-weight: bold;
    }

    /* Card thống kê */
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
    """,
    unsafe_allow_html=True
)


# =============================================================================
# 3. DỮ LIỆU VỊ TRÍ
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
# 4. SIDEBAR
# =============================================================================

st.sidebar.title("🌐 GEO PLATFORM")
st.sidebar.caption("Hệ thống Phân tích & Dự báo Chỉ số Vệ tinh")


with st.sidebar.expander(
    "🔮 DỰ BÁO CHỈ SỐ NDVI",
    expanded=True
):

    selected_province = st.selectbox(
        "Chọn Tỉnh / Thành phố:",
        list(LOCATION_DATA.keys())
    )

    district_options = list(
        LOCATION_DATA[selected_province].keys()
    )

    selected_district = st.selectbox(
        "Chọn Quận / Huyện / Phường / Xã:",
        district_options
    )

    selected_time = st.date_input(
        "Chọn Tháng / Năm hiển thị:",
        value=pd.to_datetime("2026-09-01")
    )

    st.markdown("---")

    btn_predict = st.button(
        "🚀 CHẠY DỰ BÁO AI",
        use_container_width=True,
        type="primary"
    )

    btn_export = st.button(
        "📥 XUẤT GEOJSON / CSV",
        use_container_width=True
    )


with st.sidebar.expander(
    "⚙️ CẤU HÌNH BẢN ĐỒ",
    expanded=False
):

    basemap_choice = st.radio(
        "Chọn Lớp Bản Đồ Nền:",
        ["Esri Satellite", "OpenStreetMap"]
    )

    show_boundary = st.checkbox(
        "Hiển thị Ranh giới Phường/Xã",
        value=True
    )


with st.sidebar.expander(
    "📊 BÁO CÁO & THỐNG KÊ",
    expanded=False
):

    st.write("• Lịch sử truy vấn dữ liệu")
    st.write("• Tải báo cáo PDF tổng hợp")


# =============================================================================
# 5. XỬ LÝ NÚT
# =============================================================================

if btn_predict:

    st.sidebar.success(
        f"Đang dự báo NDVI cho {selected_district}"
    )

if btn_export:

    st.sidebar.info(
        "Chức năng xuất dữ liệu sẽ được kết nối sau."
    )


# =============================================================================
# 6. LẤY TỌA ĐỘ KHU VỰC
# =============================================================================

lat, lng, zoom = LOCATION_DATA[
    selected_province
][
    selected_district
]


# =============================================================================
# 7. TIÊU ĐỀ
# =============================================================================

st.title(
    "🛡️ BẢNG ĐIỀU KHIỂN GIÁM SÁT & DỰ BÁO "
    "THẢM THỰC VẬT (NDVI)"
)


# =============================================================================
# 8. MAP + METRICS
# =============================================================================

col_map, col_metrics = st.columns([3, 1])


# -----------------------------------------------------------------------------
# MAP
# -----------------------------------------------------------------------------

with col_map:

    st.subheader(
        f"📍 Bản đồ Vệ tinh: "
        f"{selected_district} ({selected_province})"
    )

    if basemap_choice == "Esri Satellite":

        m = folium.Map(
            location=[lat, lng],
            zoom_start=zoom,
            tiles=None
        )

        folium.TileLayer(
            tiles=(
                "https://server.arcgisonline.com/"
                "ArcGIS/rest/services/World_Imagery/"
                "MapServer/tile/{z}/{y}/{x}"
            ),
            attr="Esri",
            name="Esri Satellite"
        ).add_to(m)

    else:

        m = folium.Map(
            location=[lat, lng],
            zoom_start=zoom,
            tiles="OpenStreetMap"
        )


    # -------------------------------------------------------------------------
    # LEGEND
    # -------------------------------------------------------------------------

    legend_html = """
    <div style="
        position: fixed;
        bottom: 30px;
        left: 30px;
        width: 190px;
        background-color: rgba(26, 35, 50, 0.90);
        z-index: 9999;
        font-size: 12px;
        color: white;
        padding: 10px;
        border-radius: 6px;
        border: 1px solid #2D3748;
    ">

        <b>Chú giải chỉ số NDVI</b><br><br>

        <i style="
            background:#d7191c;
            width:12px;
            height:12px;
            display:inline-block;
        "></i>
        -1.0 - 0.0 (Mặt nước/Đất)

        <br>

        <i style="
            background:#ffffbf;
            width:12px;
            height:12px;
            display:inline-block;
        "></i>
        0.0 - 0.3 (Thực vật thưa)

        <br>

        <i style="
            background:#1a9641;
            width:12px;
            height:12px;
            display:inline-block;
        "></i>
        0.3 - 1.0 (Thảm thực vật dày)

    </div>
    """

    m.get_root().html.add_child(
        folium.Element(legend_html)
    )


    # -------------------------------------------------------------------------
    # LAYER CONTROL
    # -------------------------------------------------------------------------

    folium.LayerControl().add_to(m)


    # -------------------------------------------------------------------------
    # HIỂN THỊ MAP
    # -------------------------------------------------------------------------

    st_folium(
        m,
        width="100%",
        height=460
    )


# -----------------------------------------------------------------------------
# METRICS
# -----------------------------------------------------------------------------

with col_metrics:

    st.subheader("📊 Thông Số Vùng")

    st.markdown(
        """
        <div class="stat-card">
            <h4>NDVI MEAN (Trung bình)</h4>
            <h2>0.642</h2>
        </div>

        <br>

        <div class="stat-card">
            <h4>NDVI MAX (Cao nhất)</h4>
            <h2 style="color:#10B981;">0.891</h2>
        </div>

        <br>

        <div class="stat-card">
            <h4>NDVI MIN (Thấp nhất)</h4>
            <h2 style="color:#EF4444;">-0.120</h2>
        </div>
        """,
        unsafe_allow_html=True
    )


    # -------------------------------------------------------------------------
    # GAUGE
    # -------------------------------------------------------------------------

    fig_gauge = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=78,

            title={
                "text": "Độ phủ xanh",
                "font": {
                    "size": 14,
                    "color": "#A0AEC0"
                }
            },

            number={
                "suffix": "%",
                "font": {
                    "color": "#10B981",
                    "size": 20
                }
            },

            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 1,
                    "tickcolor": "#1A2332"
                },

                "bar": {
                    "color": "#10B981"
                },

                "bgcolor": "#1A2332",

                "bordercolor": "#2D3748"
            }
        )
    )


    fig_gauge.update_layout(
        height=160,
        margin=dict(
            l=10,
            r=10,
            t=30,
            b=10
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )


    st.plotly_chart(
        fig_gauge,
        use_container_width=True
    )


# =============================================================================
# 9. BIỂU ĐỒ CHUỖI THỜI GIAN
# =============================================================================

st.markdown("---")

st.subheader(
    "📈 BIẾN ĐỘNG CHỈ SỐ NDVI THEO THỜI GIAN "
    "(2017 - 2026)"
)


# -----------------------------------------------------------------------------
# DỮ LIỆU GIẢ LẬP
# -----------------------------------------------------------------------------

np.random.seed(42)

dates = pd.date_range(
    start="2017-01-01",
    end="2026-09-01",
    freq="MS"
)


actual_ndvi = (
    0.5
    + 0.2 * np.sin(
        np.linspace(0, 20, len(dates))
    )
    + np.random.normal(
        0,
        0.03,
        len(dates)
    )
)


future_dates = pd.date_range(
    start="2026-09-01",
    end="2027-06-01",
    freq="MS"
)


predicted_ndvi = (
    0.5
    + 0.2 * np.sin(
        np.linspace(20, 22, len(future_dates))
    )
)


# =============================================================================
# 10. PLOTLY CHART
# =============================================================================

fig_chart = go.Figure()


# NDVI thực tế

fig_chart.add_trace(
    go.Scatter(
        x=dates,
        y=actual_ndvi,
        mode="lines+markers",
        name="NDVI Thực tế",
        line=dict(
            color="#38BDF8",
            width=2
        )
    )
)


# NDVI dự báo

fig_chart.add_trace(
    go.Scatter(
        x=future_dates,
        y=predicted_ndvi,
        mode="lines+markers",
        name="AI Dự báo tương lai",
        line=dict(
            color="#F59E0B",
            width=2,
            dash="dash"
        )
    )
)


fig_chart.update_layout(
    template="plotly_dark",

    paper_bgcolor="#1A2332",
    plot_bgcolor="#1A2332",

    height=320,

    margin=dict(
        l=20,
        r=20,
        t=20,
        b=20
    ),

    xaxis=dict(
        showgrid=True,
        gridcolor="#2D3748"
    ),

    yaxis=dict(
        showgrid=True,
        gridcolor="#2D3748",
        range=[-0.2, 1.0]
    ),

    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1
    )
)


st.plotly_chart(
    fig_chart,
    use_container_width=True
)


# =============================================================================
# 11. BÁO CÁO TÓM TẮT
# =============================================================================

st.markdown("---")

st.subheader(
    "📋 BÁO CÁO TÓM TẮT KHU VỰC"
)


c1, c2, c3, c4 = st.columns(4)


with c1:

    st.info(
        f"**Vùng theo dõi:**\n\n"
        f"{selected_district}"
    )


with c2:

    st.info(
        f"**Tỉnh / Thành phố:**\n\n"
        f"{selected_province}"
    )


with c3:

    st.info(
        "**Đánh giá sức khỏe:**\n\n"
        "Thảm thực vật phát triển TỐT 🟢"
    )


with c4:

    st.info(
        f"**Mốc thời gian:**\n\n"
        f"{selected_time.strftime('%m/%Y')}"
    )
