import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from folium.plugins import Fullscreen


# ============================================================
# 1. CẤU HÌNH TRANG
# ============================================================

st.set_page_config(
    layout="wide",
    page_title="GEO NDVI WebGIS",
    page_icon="🌐",
    initial_sidebar_state="expanded"
)


# ============================================================
# 2. CSS
# ============================================================

st.markdown("""
<style>

.stApp {
    background-color: #121824;
    color: #E2E8F0;
}

/* SIDEBAR */

section[data-testid="stSidebar"] {
    background-color: #1A2332;
    border-right: 1px solid #2D3748;
}

section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #F8FAFC;
}


/* HEADER */

.app-header {
    padding: 5px 0 15px 0;
}

.app-title {
    font-size: 25px;
    font-weight: 700;
    color: #F8FAFC;
}

.app-subtitle {
    color: #94A3B8;
    font-size: 13px;
    margin-top: 3px;
}

.system-status {
    text-align: right;
    padding-top: 10px;
    color: #94A3B8;
    font-size: 12px;
}

.status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    background-color: #10B981;
    border-radius: 50%;
    margin-right: 5px;
}


/* MAP HEADER */

.map-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    background-color: #1A2332;

    border: 1px solid #2D3748;
    border-bottom: none;

    padding: 10px 14px;

    border-radius: 8px 8px 0 0;

    font-size: 13px;
    font-weight: 600;
}

.map-location {
    color: #38BDF8;
    font-size: 12px;
}


/* RIGHT INFORMATION PANEL */

.gis-stat {
    background-color: #1A2332;

    border: 1px solid #2D3748;

    border-radius: 7px;

    padding: 12px;

    margin-bottom: 10px;
}

.stat-label {
    color: #94A3B8;
    font-size: 11px;
}

.stat-value {
    color: #38BDF8;
    font-size: 25px;
    font-weight: 700;
    margin-top: 3px;
}

.stat-value.green {
    color: #10B981;
}

.stat-value.red {
    color: #EF4444;
}


/* LEGEND */

.ndvi-legend {
    position: fixed;

    bottom: 35px;
    left: 35px;

    width: 175px;

    background-color: rgba(18, 24, 36, 0.92);

    color: white;

    padding: 10px;

    border-radius: 7px;

    border: 1px solid #2D3748;

    font-size: 11px;

    z-index: 9999;
}

.legend-color {
    display: inline-block;

    width: 11px;
    height: 11px;

    margin-right: 5px;
}

.legend-color.low {
    background-color: #d7191c;
}

.legend-color.medium {
    background-color: #ffffbf;
}

.legend-color.high {
    background-color: #1a9641;


/* METRIC */

div[data-testid="stMetricValue"] {
    color: #38BDF8 !important;
}


/* REMOVE EXTRA SPACE */

.block-container {
    padding-top: 1.2rem;
    padding-bottom: 1rem;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# 3. DỮ LIỆU VỊ TRÍ
# ============================================================

LOCATION_DATA = {

    "TP. Hồ Chí Minh": {

        "Toàn thành phố": [
            10.7769,
            106.7009,
            10
        ],

        "Phường Long Nguyên": [
            11.1230,
            106.6540,
            13
        ],

        "Quận 1": [
            10.7756,
            106.7004,
            14
        ],

        "Thành phố Thủ Đức": [
            10.8494,
            106.7537,
            12
        ]
    },


    "An Giang": {

        "Toàn tỉnh": [
            10.5361,
            105.1325,
            10
        ],

        "Huyện Chợ Mới": [
            10.5000,
            105.5500,
            12
        ],

        "TP. Long Xuyên": [
            10.3800,
            105.4300,
            13
        ]
    }
}


# ============================================================
# 4. SIDEBAR
# ============================================================

st.sidebar.markdown(
    """
    <div style="
        font-size:22px;
        font-weight:700;
        color:#F8FAFC;
        margin-bottom:3px;
    ">
        🌐 GEO NDVI
    </div>

    <div style="
        font-size:12px;
        color:#94A3B8;
        margin-bottom:18px;
    ">
        WebGIS Monitoring Platform
    </div>
    """,
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# KHU VỰC DỰ BÁO
# ------------------------------------------------------------

with st.sidebar.expander(
    "🔮 DỰ BÁO NDVI",
    expanded=True
):

    selected_province = st.selectbox(
        "Tỉnh / Thành phố",
        list(LOCATION_DATA.keys())
    )


    district_options = list(
        LOCATION_DATA[selected_province].keys()
    )


    selected_district = st.selectbox(
        "Khu vực",
        district_options
    )


    selected_year = st.selectbox(
        "Năm dự báo",
        [2026, 2027]
    )


    selected_month = st.selectbox(
        "Tháng dự báo",
        range(1, 13),
        format_func=lambda x: f"Tháng {x:02d}"
    )


    st.markdown("---")


    btn_predict = st.button(
        "🚀 CHẠY DỰ BÁO AI",
        use_container_width=True,
        type="primary"
    )


    btn_export = st.button(
        "📥 XUẤT DỮ LIỆU",
        use_container_width=True
    )


# ------------------------------------------------------------
# CẤU HÌNH BẢN ĐỒ
# ------------------------------------------------------------

with st.sidebar.expander(
    "🗺️ CẤU HÌNH BẢN ĐỒ",
    expanded=True
):

    basemap_choice = st.radio(
        "Bản đồ nền",
        [
            "Esri Satellite",
            "OpenStreetMap"
        ]
    )


    show_boundary = st.checkbox(
        "Hiển thị ranh giới",
        value=True
    )


    show_grid = st.checkbox(
        "Hiển thị lưới NDVI",
        value=False
    )


# ------------------------------------------------------------
# THÔNG TIN DỮ LIỆU
# ------------------------------------------------------------

with st.sidebar.expander(
    "📡 NGUỒN DỮ LIỆU",
    expanded=False
):

    st.write("🛰️ Sentinel-2")

    st.write("📐 Độ phân giải: 10 m")

    st.write("🗓️ Chu kỳ: Theo tháng")

    st.write("🧠 Mô hình: GRU")


# ============================================================
# 5. LẤY TỌA ĐỘ
# ============================================================

lat, lng, zoom = LOCATION_DATA[
    selected_province
][
    selected_district
]


# ============================================================
# 6. HEADER
# ============================================================

header_left, header_right = st.columns(
    [4, 1]
)


with header_left:

    st.markdown(
        """
        <div class="app-header">

            <div class="app-title">
                🌐 GEO NDVI WEBGIS
            </div>

            <div class="app-subtitle">
                Hệ thống giám sát và dự báo chỉ số NDVI
                bằng dữ liệu viễn thám
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )


with header_right:

    st.markdown(
        """
        <div class="system-status">

            <span class="status-dot"></span>

            SYSTEM ONLINE

        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# 7. KHU VỰC WEBGIS CHÍNH
# ============================================================

map_col, info_col = st.columns(
    [4.7, 1.3]
)


# ============================================================
# 8. BẢN ĐỒ
# ============================================================

with map_col:

    st.markdown(
        f"""
        <div class="map-header">

            <span>
                🗺️ BẢN ĐỒ GIÁM SÁT NDVI
            </span>

            <span class="map-location">
                {selected_district} · {selected_province}
            </span>

        </div>
        """,
        unsafe_allow_html=True
    )


    # -----------------------------------------
    # BASEMAP
    # -----------------------------------------

    if basemap_choice == "Esri Satellite":

        tile_provider = "Esri WorldImagery"

    else:

        tile_provider = "OpenStreetMap"


    # -----------------------------------------
    # CREATE MAP
    # -----------------------------------------

    m = folium.Map(
        location=[
            lat,
            lng
        ],

        zoom_start=zoom,

        tiles=tile_provider,

        control_scale=True
    )


    # -----------------------------------------
    # FULLSCREEN
    # -----------------------------------------

    Fullscreen(
        position="topright",

        title="Toàn màn hình",

        title_cancel="Thoát toàn màn hình",

        force_separate_button=True
    ).add_to(m)


    # -----------------------------------------
    # LOCATION MARKER
    # -----------------------------------------

    folium.Marker(

        [lat, lng],

        tooltip=selected_district,

        popup=f"""
        <b>{selected_district}</b><br>
        {selected_province}<br>
        NDVI Mean: 0.642
        """

    ).add_to(m)


    # -----------------------------------------
    # NDVI LEGEND
    # -----------------------------------------

    legend_html = """
    <div class="ndvi-legend">

        <b>CHÚ GIẢI NDVI</b>

        <br><br>

        <span class="legend-color low"></span>
        -1.0 → 0.0

        <br>

        <span class="legend-color medium"></span>
        0.0 → 0.3

        <br>

        <span class="legend-color high"></span>
        0.3 → 1.0

    </div>
    """


    m.get_root().html.add_child(
        folium.Element(
            legend_html
        )
    )


    # -----------------------------------------
    # RENDER MAP
    # -----------------------------------------

    st_folium(

        m,

        width="100%",

        height=620,

        returned_objects=[]
    )


# ============================================================
# 9. INFORMATION PANEL
# ============================================================

with info_col:

    st.markdown(
        "### 📊 THÔNG TIN"
    )


    st.caption(
        f"{selected_district}"
    )


    # -----------------------------------------
    # NDVI MEAN
    # -----------------------------------------

    st.markdown(
        """
        <div class="gis-stat">

            <div class="stat-label">
                NDVI MEAN
            </div>

            <div class="stat-value">
                0.642
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )


    # -----------------------------------------
    # NDVI MAX
    # -----------------------------------------

    st.markdown(
        """
        <div class="gis-stat">

            <div class="stat-label">
                NDVI MAX
            </div>

            <div class="stat-value green">
                0.891
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )


    # -----------------------------------------
    # NDVI MIN
    # -----------------------------------------

    st.markdown(
        """
        <div class="gis-stat">

            <div class="stat-label">
                NDVI MIN
            </div>

            <div class="stat-value red">
                -0.120
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )


    st.markdown("---")


    # -----------------------------------------
    # VEGETATION HEALTH
    # -----------------------------------------

    st.markdown(
        "#### 🌱 SỨC KHỎE"
    )


    fig_gauge = go.Figure(
        go.Indicator(

            mode="gauge+number",

            value=78,

            number={
                "suffix": "%",
                "font": {
                    "size": 24,
                    "color": "#10B981"
                }
            },

            gauge={

                "axis": {
                    "range": [0, 100]
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

        height=180,

        margin=dict(
            l=5,
            r=5,
            t=10,
            b=10
        ),

        paper_bgcolor="rgba(0,0,0,0)"
    )


    st.plotly_chart(
        fig_gauge,
        use_container_width=True
    )


    st.success(
        "🟢 Thảm thực vật phát triển tốt"
    )


# ============================================================
# 10. TIME SERIES
# ============================================================

st.markdown("---")


st.markdown(
    "### 📈 DIỄN BIẾN NDVI THEO THỜI GIAN"
)


# -----------------------------------------
# DATA SAMPLE
# -----------------------------------------

dates = pd.date_range(
    start="2017-01-01",
    end="2026-09-01",
    freq="MS"
)


np.random.seed(42)


actual_ndvi = (
    0.5
    + 0.2 * np.sin(
        np.linspace(
            0,
            20,
            len(dates)
        )
    )
    + np.random.normal(
        0,
        0.03,
        len(dates)
    )
)


future_dates = pd.date_range(
    start="2026-10-01",
    end="2027-06-01",
    freq="MS"
)


predicted_ndvi = (
    0.5
    + 0.2 * np.sin(
        np.linspace(
            20,
            22,
            len(future_dates)
        )
    )
)


# -----------------------------------------
# CHART
# -----------------------------------------

fig_chart = go.Figure()


fig_chart.add_trace(
    go.Scatter(

        x=dates,

        y=actual_ndvi,

        mode="lines",

        name="NDVI thực tế",

        line=dict(
            color="#38BDF8",
            width=2
        )
    )
)


fig_chart.add_trace(
    go.Scatter(

        x=future_dates,

        y=predicted_ndvi,

        mode="lines",

        name="AI dự báo",

        line=dict(
            color="#F59E0B",
            width=2,
            dash="dash"
        )
    )
)


fig_chart.update_layout(

    template="plotly_dark",

    height=300,

    paper_bgcolor="#1A2332",

    plot_bgcolor="#1A2332",

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
        range=[
            -0.2,
            1
        ],

        showgrid=True,

        gridcolor="#2D3748"
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


# ============================================================
# 11. SUMMARY
# ============================================================

st.markdown(
    "### 📋 TÓM TẮT KHU VỰC"
)


c1, c2, c3, c4 = st.columns(4)


with c1:

    st.metric(
        "Vùng theo dõi",
        selected_district
    )


with c2:

    st.metric(
        "NDVI hiện tại",
        "0.642"
    )


with c3:

    st.metric(
        "Dự báo",
        "0.671",
        "+0.029"
    )


with c4:

    st.metric(
        "Thời gian",
        f"{selected_month:02d}/{selected_year}"
    )


# ============================================================
# 12. BUTTON ACTION
# ============================================================

if btn_predict:

    st.toast(
        "🚀 Đã kích hoạt mô phỏng dự báo AI!",
        icon="🧠"
    )


if btn_export:

    st.toast(
        "📥 Chức năng xuất dữ liệu đang được chuẩn bị.",
        icon="📊"
    )
