import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
from folium.plugins import Fullscreen


# ============================================================
# 1. PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="GEO NDVI",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# 2. GLOBAL STYLE
# ============================================================

st.markdown("""
<style>

html, body, [class*="css"] {
    font-family: "Inter", "Segoe UI", sans-serif;
}

.stApp {
    background: #ffffff;
    color: #1f2937;
}


/* Remove Streamlit default top space */

.block-container {
    padding-top: 0.8rem;
    padding-bottom: 0.5rem;
}


/* Sidebar */

section[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #e5e7eb;
}


/* Sidebar title */

.sidebar-title {
    font-size: 20px;
    font-weight: 700;
    color: #111827;
    letter-spacing: -0.3px;
}

.sidebar-subtitle {
    font-size: 12px;
    color: #6b7280;
    margin-top: -5px;
    margin-bottom: 22px;
}


/* Top navigation */

.topbar {
    height: 58px;

    display: flex;
    align-items: center;
    justify-content: space-between;

    border-bottom: 1px solid #e5e7eb;

    margin-bottom: 10px;
}

.brand {
    font-size: 18px;
    font-weight: 700;
    color: #111827;
}

.brand span {
    color: #15803d;
}

.map-title {
    font-size: 13px;
    color: #6b7280;
}


/* Section */

.section-title {
    font-size: 11px;
    font-weight: 700;
    color: #6b7280;
    letter-spacing: 0.8px;
    text-transform: uppercase;

    margin-top: 18px;
    margin-bottom: 8px;
}


/* Information panel */

.info-panel {
    background: #ffffff;

    border: 1px solid #e5e7eb;

    border-radius: 8px;

    padding: 16px;

    margin-bottom: 10px;
}

.info-label {
    font-size: 11px;
    color: #6b7280;
    margin-bottom: 3px;
}

.info-value {
    font-size: 23px;
    font-weight: 700;
    color: #111827;
}

.info-unit {
    font-size: 11px;
    color: #9ca3af;
}


/* NDVI status */

.ndvi-status {
    display: inline-block;

    background: #ecfdf5;

    color: #15803d;

    border: 1px solid #bbf7d0;

    padding: 5px 9px;

    border-radius: 5px;

    font-size: 11px;

    font-weight: 600;
}


/* Map legend */

.ndvi-legend {

    position: fixed;

    bottom: 28px;

    left: 28px;

    background: rgba(255,255,255,0.96);

    border: 1px solid #d1d5db;

    border-radius: 6px;

    padding: 10px 12px;

    width: 155px;

    font-size: 11px;

    color: #374151;

    box-shadow: 0 2px 8px rgba(0,0,0,0.08);

    z-index: 9999;
}

.legend-title {
    font-weight: 700;
    margin-bottom: 7px;
}

.legend-row {
    display: flex;
    align-items: center;
    margin: 4px 0;
}

.legend-color {
    width: 13px;
    height: 13px;
    margin-right: 7px;
    border-radius: 2px;
}


/* Hide Streamlit menu */

#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

header {
    visibility: hidden;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# 3. LOCATION DATA
# ============================================================

LOCATION_DATA = {

    "An Giang": {

        "Toàn tỉnh": [
            10.5361,
            105.1325,
            9
        ],

        "Huyện Chợ Mới": [
            10.5000,
            105.5500,
            12
        ],

        "TP. Long Xuyên": [
            10.3800,
            105.4300,
            12
        ]
    },

    "TP. Hồ Chí Minh": {

        "Toàn thành phố": [
            10.7769,
            106.7009,
            10
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
    }
}


# ============================================================
# 4. SIDEBAR
# ============================================================

st.sidebar.markdown(
    """
    <div class="sidebar-title">
        🌍 GEO <span>NDVI</span>
    </div>

    <div class="sidebar-subtitle">
        WebGIS Monitoring & Prediction
    </div>
    """,
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# LOCATION
# ------------------------------------------------------------

st.sidebar.markdown(
    '<div class="section-title">Khu vực</div>',
    unsafe_allow_html=True
)

selected_province = st.sidebar.selectbox(
    "Tỉnh / Thành phố",
    list(LOCATION_DATA.keys()),
    label_visibility="collapsed"
)


district_options = list(
    LOCATION_DATA[selected_province].keys()
)


selected_district = st.sidebar.selectbox(
    "Khu vực",
    district_options,
    label_visibility="collapsed"
)


# ------------------------------------------------------------
# TIME
# ------------------------------------------------------------

st.sidebar.markdown(
    '<div class="section-title">Thời gian</div>',
    unsafe_allow_html=True
)


selected_year = st.sidebar.selectbox(
    "Năm",
    [2026, 2027],
    index=0
)


selected_month = st.sidebar.selectbox(
    "Tháng",
    range(1, 13),
    index=8,
    format_func=lambda x: f"Tháng {x:02d}"
)


# ------------------------------------------------------------
# LAYERS
# ------------------------------------------------------------

st.sidebar.markdown(
    '<div class="section-title">Lớp dữ liệu</div>',
    unsafe_allow_html=True
)


show_boundary = st.sidebar.checkbox(
    "Ranh giới hành chính",
    value=True
)


show_grid = st.sidebar.checkbox(
    "Lưới 500 × 500 m",
    value=False
)


show_ndvi = st.sidebar.checkbox(
    "Lớp NDVI",
    value=False
)


# ------------------------------------------------------------
# BASEMAP
# ------------------------------------------------------------

st.sidebar.markdown(
    '<div class="section-title">Bản đồ nền</div>',
    unsafe_allow_html=True
)


basemap_choice = st.sidebar.radio(
    "Basemap",
    [
        "Satellite",
        "Street Map"
    ],
    label_visibility="collapsed"
)


# ============================================================
# 5. LOCATION
# ============================================================

lat, lng, zoom = LOCATION_DATA[
    selected_province
][
    selected_district
]


# ============================================================
# 6. TOP BAR
# ============================================================

st.markdown(
    f"""
    <div class="topbar">

        <div class="brand">
            GEO <span>NDVI</span>
        </div>

        <div class="map-title">
            {selected_district} ·
            {selected_province} ·
            {selected_month:02d}/{selected_year}
        </div>

    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# 7. MAIN GIS AREA
# ============================================================

map_col, info_col = st.columns(
    [4.8, 1.2],
    gap="small"
)


# ============================================================
# 8. MAP
# ============================================================

with map_col:

    if basemap_choice == "Satellite":

        tile = "Esri WorldImagery"

    else:

        tile = "OpenStreetMap"


    m = folium.Map(

        location=[
            lat,
            lng
        ],

        zoom_start=zoom,

        tiles=tile,

        control_scale=True,

        zoom_control=True
    )


    # --------------------------------------------------------
    # FULLSCREEN
    # --------------------------------------------------------

    Fullscreen(
        position="topright",
        title="Toàn màn hình",
        title_cancel="Thoát toàn màn hình"
    ).add_to(m)


    # --------------------------------------------------------
    # LOCATION MARKER
    # --------------------------------------------------------

    folium.Marker(

        [
            lat,
            lng
        ],

        tooltip=selected_district,

        popup=f"""
        <b>{selected_district}</b><br>
        {selected_province}
        """

    ).add_to(m)


    # --------------------------------------------------------
    # NDVI LEGEND
    # --------------------------------------------------------

    if show_ndvi:

        legend_html = """

        <div class="ndvi-legend">

            <div class="legend-title">
                NDVI
            </div>

            <div class="legend-row">
                <span
                    class="legend-color"
                    style="background:#d73027;">
                </span>
                -1.0 – 0.0
            </div>

            <div class="legend-row">
                <span
                    class="legend-color"
                    style="background:#fee08b;">
                </span>
                0.0 – 0.3
            </div>

            <div class="legend-row">
                <span
                    class="legend-color"
                    style="background:#66bd63;">
                </span>
                0.3 – 0.6
            </div>

            <div class="legend-row">
                <span
                    class="legend-color"
                    style="background:#1a9850;">
                </span>
                0.6 – 1.0
            </div>

        </div>

        """

        m.get_root().html.add_child(
            folium.Element(
                legend_html
            )
        )


    # --------------------------------------------------------
    # MAP
    # --------------------------------------------------------

    map_data = st_folium(

        m,

        width="100%",

        height=650,

        returned_objects=[
            "last_clicked"
        ]
    )


# ============================================================
# 9. RIGHT INFORMATION PANEL
# ============================================================

with info_col:

    st.markdown(
        "### Thông tin"
    )


    st.caption(
        f"{selected_district}"
    )


    # --------------------------------------------------------
    # NDVI MEAN
    # --------------------------------------------------------

    st.markdown(
        """
        <div class="info-panel">

            <div class="info-label">
                NDVI TRUNG BÌNH
            </div>

            <div class="info-value">
                0.642
            </div>

            <div class="info-unit">
                Giá trị trung bình khu vực
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )


    # --------------------------------------------------------
    # MAX
    # --------------------------------------------------------

    st.markdown(
        """
        <div class="info-panel">

            <div class="info-label">
                NDVI CAO NHẤT
            </div>

            <div class="info-value">
                0.891
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )


    # --------------------------------------------------------
    # MIN
    # --------------------------------------------------------

    st.markdown(
        """
        <div class="info-panel">

            <div class="info-label">
                NDVI THẤP NHẤT
            </div>

            <div class="info-value">
                -0.120
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )


    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    st.markdown(
        """
        <div style="margin-top:14px;">

            <div class="info-label">
                TRẠNG THÁI THẢM THỰC VẬT
            </div>

            <br>

            <span class="ndvi-status">
                ● PHÁT TRIỂN TỐT
            </span>

        </div>
        """,
        unsafe_allow_html=True
    )


    # --------------------------------------------------------
    # CLICKED POINT
    # --------------------------------------------------------

    if map_data and map_data.get("last_clicked"):

        point = map_data["last_clicked"]

        st.markdown(
            "<br><div class='section-title'>Điểm được chọn</div>",
            unsafe_allow_html=True
        )

        st.caption(
            f"Latitude: {point['lat']:.6f}"
        )

        st.caption(
            f"Longitude: {point['lng']:.6f}"
        )


# ============================================================
# 10. TIME SERIES
# ============================================================

st.markdown("<br>", unsafe_allow_html=True)

st.markdown(
    '<div class="section-title">Diễn biến NDVI</div>',
    unsafe_allow_html=True
)


dates = pd.date_range(
    start="2017-01-01",
    end="2026-09-01",
    freq="MS"
)


actual_ndvi = (
    0.5
    + 0.2 *
    pd.Series(
        range(len(dates))
    ).apply(
        lambda x: __import__("math").sin(x / 8)
    )
)


future_dates = pd.date_range(
    start="2026-10-01",
    end="2027-06-01",
    freq="MS"
)


predicted_ndvi = (
    0.5
    + 0.2 *
    pd.Series(
        range(len(future_dates))
    ).apply(
        lambda x: __import__("math").sin(
            (len(dates) + x) / 8
        )
    )
)


fig = go.Figure()


fig.add_trace(
    go.Scatter(

        x=dates,

        y=actual_ndvi,

        mode="lines",

        name="NDVI thực tế",

        line=dict(
            color="#2563eb",
            width=2
        )
    )
)


fig.add_trace(
    go.Scatter(

        x=future_dates,

        y=predicted_ndvi,

        mode="lines",

        name="Dự báo AI",

        line=dict(
            color="#16a34a",
            width=2,
            dash="dash"
        )
    )
)


fig.update_layout(

    height=270,

    margin=dict(
        l=20,
        r=20,
        t=10,
        b=20
    ),

    paper_bgcolor="#ffffff",

    plot_bgcolor="#ffffff",

    font=dict(
        color="#374151"
    ),

    xaxis=dict(
        showgrid=True,
        gridcolor="#f1f5f9"
    ),

    yaxis=dict(
        showgrid=True,
        gridcolor="#f1f5f9",
        range=[-0.2, 1]
    ),

    legend=dict(
        orientation="h",
        y=1.08,
        x=1,
        xanchor="right"
    )
)


st.plotly_chart(
    fig,
    use_container_width=True
)
