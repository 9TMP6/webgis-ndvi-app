```python
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
    page_title="GEO BIG DATA - NDVI PREDICTION PLATFORM",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =============================================================================
# 2. CẤU HÌNH MÀU SẮC
# =============================================================================

BG_COLOR = "#121824"
CARD_COLOR = "#1A2332"
BORDER_COLOR = "#2D3748"
TEXT_COLOR = "#E2E8F0"
MUTED_COLOR = "#A0AEC0"

PRIMARY_COLOR = "#38BDF8"
SUCCESS_COLOR = "#10B981"
WARNING_COLOR = "#F59E0B"
DANGER_COLOR = "#EF4444"


# =============================================================================
# 3. CSS
# =============================================================================

def load_css():

    st.markdown(
        f"""
        <style>

        /* =========================================================
           GLOBAL
        ========================================================= */

        .stApp {{
            background-color: {BG_COLOR};
            color: {TEXT_COLOR};
        }}

        [data-testid="stHeader"] {{
            background-color: transparent;
        }}

        /* =========================================================
           SIDEBAR
        ========================================================= */

        section[data-testid="stSidebar"] {{
            background-color: {CARD_COLOR};
            border-right: 1px solid {BORDER_COLOR};
        }}

        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3 {{
            color: {TEXT_COLOR};
        }}

        /* =========================================================
           TITLE
        ========================================================= */

        .main-title {{
            font-size: 2rem;
            font-weight: 700;
            color: {TEXT_COLOR};
            margin-bottom: 0.2rem;
        }}

        .main-subtitle {{
            color: {MUTED_COLOR};
            font-size: 0.95rem;
            margin-bottom: 1.5rem;
        }}

        /* =========================================================
           STAT CARD
        ========================================================= */

        .stat-card {{
            background-color: {CARD_COLOR};
            border: 1px solid {BORDER_COLOR};
            border-radius: 10px;
            padding: 15px;
            text-align: center;
            margin-bottom: 12px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.20);
        }}

        .stat-title {{
            color: {MUTED_COLOR};
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }}

        .stat-value {{
            color: {PRIMARY_COLOR};
            font-size: 1.55rem;
            font-weight: 700;
        }}

        .stat-value.success {{
            color: {SUCCESS_COLOR};
        }}

        .stat-value.danger {{
            color: {DANGER_COLOR};
        }}

        /* =========================================================
           SECTION HEADER
        ========================================================= */

        .section-header {{
            color: {TEXT_COLOR};
            font-size: 1.15rem;
            font-weight: 650;
            margin-top: 5px;
            margin-bottom: 10px;
        }}

        /* =========================================================
           INFO CARD
        ========================================================= */

        .info-card {{
            background-color: {CARD_COLOR};
            border: 1px solid {BORDER_COLOR};
            border-radius: 10px;
            padding: 16px;
            height: 100%;
        }}

        .info-label {{
            color: {MUTED_COLOR};
            font-size: 0.78rem;
            margin-bottom: 5px;
        }}

        .info-value {{
            color: {TEXT_COLOR};
            font-size: 1rem;
            font-weight: 600;
        }}

        /* =========================================================
           FOOTER
        ========================================================= */

        .footer {{
            text-align: center;
            color: {MUTED_COLOR};
            font-size: 0.75rem;
            margin-top: 25px;
            padding: 15px;
            border-top: 1px solid {BORDER_COLOR};
        }}

        </style>
        """,
        unsafe_allow_html=True
    )


# =============================================================================
# 4. DỮ LIỆU VỊ TRÍ
# =============================================================================

LOCATION_DATA = {

    "TP. Hồ Chí Minh": {

        "Toàn tỉnh/TP": {
            "lat": 10.7769,
            "lng": 106.7009,
            "zoom": 10
        },

        "Phường Long Nguyên": {
            "lat": 11.1230,
            "lng": 106.6540,
            "zoom": 13
        },

        "Quận 1": {
            "lat": 10.7756,
            "lng": 106.7004,
            "zoom": 14
        },

        "Thành phố Thủ Đức": {
            "lat": 10.8494,
            "lng": 106.7537,
            "zoom": 12
        }
    },

    "An Giang": {

        "Toàn tỉnh/TP": {
            "lat": 10.5361,
            "lng": 105.1325,
            "zoom": 10
        },

        "Huyện Chợ Mới": {
            "lat": 10.5000,
            "lng": 105.5500,
            "zoom": 12
        },

        "TP. Long Xuyên": {
            "lat": 10.3800,
            "lng": 105.4300,
            "zoom": 13
        }
    }
}


# =============================================================================
# 5. TẠO SIDEBAR
# =============================================================================

def render_sidebar():

    st.sidebar.markdown(
        """
        <h1 style="
            color:#38BDF8;
            font-size:1.5rem;
            margin-bottom:0;
        ">
            🌐 GEO PLATFORM
        </h1>
        """,
        unsafe_allow_html=True
    )

    st.sidebar.caption(
        "Hệ thống Phân tích & Dự báo Chỉ số Vệ tinh"
    )

    # -------------------------------------------------------------------------
    # DỰ BÁO NDVI
    # -------------------------------------------------------------------------

    with st.sidebar.expander(
        "🔮 DỰ BÁO CHỈ SỐ NDVI",
        expanded=True
    ):

        provinces = list(LOCATION_DATA.keys())

        selected_province = st.selectbox(
            "Tỉnh / Thành phố",
            provinces
        )

        districts = list(
            LOCATION_DATA[selected_province].keys()
        )

        selected_district = st.selectbox(
            "Quận / Huyện / Phường / Xã",
            districts
        )

        selected_time = st.date_input(
            "Thời gian hiển thị",
            value=pd.Timestamp("2026-09-01"),
            format="DD/MM/YYYY"
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

    # -------------------------------------------------------------------------
    # BẢN ĐỒ
    # -------------------------------------------------------------------------

    with st.sidebar.expander(
        "⚙️ CẤU HÌNH BẢN ĐỒ",
        expanded=False
    ):

        basemap_choice = st.radio(
            "Lớp bản đồ nền",
            [
                "Esri Satellite",
                "OpenStreetMap"
            ]
        )

        show_boundary = st.checkbox(
            "Hiển thị ranh giới Phường/Xã",
            value=True
        )

    # -------------------------------------------------------------------------
    # BÁO CÁO
    # -------------------------------------------------------------------------

    with st.sidebar.expander(
        "📊 BÁO CÁO & THỐNG KÊ",
        expanded=False
    ):

        st.write("📜 Lịch sử truy vấn dữ liệu")
        st.write("📄 Tải báo cáo PDF tổng hợp")

    return (
        selected_province,
        selected_district,
        selected_time,
        basemap_choice,
        show_boundary,
        btn_predict,
        btn_export
    )


# =============================================================================
# 6. TẠO BẢN ĐỒ
# =============================================================================

def create_map(
    lat,
    lng,
    zoom,
    basemap_choice,
    show_boundary
):

    # -------------------------------------------------------------------------
    # BASE MAP
    # -------------------------------------------------------------------------

    if basemap_choice == "Esri Satellite":

        m = folium.Map(
            location=[lat, lng],
            zoom_start=zoom,
            tiles=None,
            control_scale=True
        )

        folium.TileLayer(
            tiles=(
                "https://server.arcgisonline.com/"
                "ArcGIS/rest/services/World_Imagery/"
                "MapServer/tile/{z}/{y}/{x}"
            ),
            attr="Esri World Imagery",
            name="Esri Satellite",
            overlay=False,
            control=True
        ).add_to(m)

    else:

        m = folium.Map(
            location=[lat, lng],
            zoom_start=zoom,
            tiles="OpenStreetMap",
            control_scale=True
        )

    # -------------------------------------------------------------------------
    # LEGEND
    # -------------------------------------------------------------------------

    legend_html = f"""
    <div style="
        position: fixed;
        bottom: 30px;
        left: 30px;
        width: 205px;
        background-color: rgba(26,35,50,0.94);
        z-index: 9999;
        font-size: 12px;
        color: white;
        padding: 12px;
        border-radius: 8px;
        border: 1px solid {BORDER_COLOR};
        box-shadow: 0 3px 10px rgba(0,0,0,0.35);
    ">

        <div style="
            font-weight:bold;
            margin-bottom:8px;
            color:{PRIMARY_COLOR};
        ">
            🛰️ Chú giải NDVI
        </div>

        <div style="margin-bottom:5px;">
            <span style="
                background:#d7191c;
                width:13px;
                height:13px;
                display:inline-block;
                margin-right:6px;
            "></span>
            -1.0 → 0.0
        </div>

        <div style="margin-bottom:5px;">
            <span style="
                background:#ffffbf;
                width:13px;
                height:13px;
                display:inline-block;
                margin-right:6px;
            "></span>
            0.0 → 0.3
        </div>

        <div>
            <span style="
                background:#1a9641;
                width:13px;
                height:13px;
                display:inline-block;
                margin-right:6px;
            "></span>
            0.3 → 1.0
        </div>

    </div>
    """

    m.get_root().html.add_child(
        folium.Element(legend_html)
    )

    # -------------------------------------------------------------------------
    # RANH GIỚI
    # -------------------------------------------------------------------------

    if show_boundary:

        # Placeholder.
        # Sau này có thể thay bằng GeoJSON ranh giới thật.
        pass

    # -------------------------------------------------------------------------
    # LAYER CONTROL
    # -------------------------------------------------------------------------

    folium.LayerControl().add_to(m)

    return m


# =============================================================================
# 7. STAT CARDS
# =============================================================================

def render_stat_cards():

    st.markdown(
        f"""
        <div class="stat-card">

            <div class="stat-title">
                NDVI MEAN
            </div>

            <div class="stat-value">
                0.642
            </div>

        </div>

        <div class="stat-card">

            <div class="stat-title">
                NDVI MAX
            </div>

            <div class="stat-value success">
                0.891
            </div>

        </div>

        <div class="stat-card">

            <div class="stat-title">
                NDVI MIN
            </div>

            <div class="stat-value danger">
                -0.120
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )


# =============================================================================
# 8. GAUGE CHART
# =============================================================================

def create_gauge(value=78):

    fig = go.Figure(
        go.Indicator(

            mode="gauge+number",

            value=value,

            title={
                "text": "Độ phủ xanh",
                "font": {
                    "size": 14,
                    "color": MUTED_COLOR
                }
            },

            number={
                "suffix": "%",
                "font": {
                    "color": SUCCESS_COLOR,
                    "size": 22
                }
            },

            gauge={

                "axis": {
                    "range": [0, 100],
                    "tickwidth": 1,
                    "tickcolor": BORDER_COLOR
                },

                "bar": {
                    "color": SUCCESS_COLOR
                },

                "bgcolor": CARD_COLOR,

                "bordercolor": BORDER_COLOR
            }
        )
    )

    fig.update_layout(

        height=180,

        margin=dict(
            l=10,
            r=10,
            t=35,
            b=5
        ),

        paper_bgcolor="rgba(0,0,0,0)",

        plot_bgcolor="rgba(0,0,0,0)"
    )

    return fig


# =============================================================================
# 9. DỮ LIỆU NDVI DEMO
# =============================================================================

@st.cache_data
def generate_demo_ndvi():

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

    return (
        dates,
        actual_ndvi,
        future_dates,
        predicted_ndvi
    )


# =============================================================================
# 10. BIỂU ĐỒ CHUỖI THỜI GIAN
# =============================================================================

def create_ndvi_chart():

    (
        dates,
        actual_ndvi,
        future_dates,
        predicted_ndvi
    ) = generate_demo_ndvi()

    fig = go.Figure()

    # -------------------------------------------------------------------------
    # ACTUAL
    # -------------------------------------------------------------------------

    fig.add_trace(
        go.Scatter(

            x=dates,

            y=actual_ndvi,

            mode="lines+markers",

            name="NDVI Thực tế",

            line={
                "color": PRIMARY_COLOR,
                "width": 2
            },

            marker={
                "size": 4
            }
        )
    )

    # -------------------------------------------------------------------------
    # PREDICTION
    # -------------------------------------------------------------------------

    fig.add_trace(
        go.Scatter(

            x=future_dates,

            y=predicted_ndvi,

            mode="lines+markers",

            name="AI Dự báo",

            line={
                "color": WARNING_COLOR,
                "width": 2,
                "dash": "dash"
            },

            marker={
                "size": 4
            }
        )
    )

    # -------------------------------------------------------------------------
    # LAYOUT
    # -------------------------------------------------------------------------

    fig.update_layout(

        template="plotly_dark",

        paper_bgcolor=CARD_COLOR,

        plot_bgcolor=CARD_COLOR,

        height=350,

        margin=dict(
            l=20,
            r=20,
            t=30,
            b=20
        ),

        xaxis={
            "showgrid": True,
            "gridcolor": BORDER_COLOR,
            "title": "Thời gian"
        },

        yaxis={
            "showgrid": True,
            "gridcolor": BORDER_COLOR,
            "range": [-0.2, 1.0],
            "title": "NDVI"
        },

        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1
        },

        hovermode="x unified"
    )

    return fig


# =============================================================================
# 11. INFO CARD
# =============================================================================

def render_info_card(label, value):

    st.markdown(
        f"""
        <div class="info-card">

            <div class="info-label">
                {label}
            </div>

            <div class="info-value">
                {value}
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )


# =============================================================================
# 12. MAIN APP
# =============================================================================

def main():

    # -------------------------------------------------------------------------
    # CSS
    # -------------------------------------------------------------------------

    load_css()

    # -------------------------------------------------------------------------
    # SIDEBAR
    # -------------------------------------------------------------------------

    (
        selected_province,
        selected_district,
        selected_time,
        basemap_choice,
        show_boundary,
        btn_predict,
        btn_export
    ) = render_sidebar()

    # -------------------------------------------------------------------------
    # BUTTON ACTIONS
    # -------------------------------------------------------------------------

    if btn_predict:

        st.sidebar.success(
            f"🚀 Đang xử lý dự báo NDVI\n\n"
            f"📍 {selected_district}\n\n"
            f"📅 {selected_time.strftime('%m/%Y')}"
        )

    if btn_export:

        st.sidebar.info(
            "📥 Chức năng xuất GeoJSON / CSV "
            "sẽ được kết nối với dữ liệu thật."
        )

    # -------------------------------------------------------------------------
    # LOCATION
    # -------------------------------------------------------------------------

    location = LOCATION_DATA[
        selected_province
    ][
        selected_district
    ]

    lat = location["lat"]
    lng = location["lng"]
    zoom = location["zoom"]

    # -------------------------------------------------------------------------
    # HEADER
    # -------------------------------------------------------------------------

    st.markdown(
        """
        <div class="main-title">
            🛡️ BẢNG ĐIỀU KHIỂN GIÁM SÁT & DỰ BÁO
            THẢM THỰC VẬT (NDVI)
        </div>

        <div class="main-subtitle">
            GEO BIG DATA • Remote Sensing • AI Prediction • WebGIS
        </div>
        """,
        unsafe_allow_html=True
    )

    # -------------------------------------------------------------------------
    # MAP + METRICS
    # -------------------------------------------------------------------------

    col_map, col_metrics = st.columns(
        [3, 1],
        gap="medium"
    )

    # ========================================================================
    # MAP
    # ========================================================================

    with col_map:

        st.markdown(
            f"""
            <div class="section-header">
                📍 Bản đồ vệ tinh:
                {selected_district} ({selected_province})
            </div>
            """,
            unsafe_allow_html=True
        )

        map_object = create_map(
            lat=lat,
            lng=lng,
            zoom=zoom,
            basemap_choice=basemap_choice,
            show_boundary=show_boundary
        )

        st_folium(
            map_object,
            width="100%",
            height=500,
            returned_objects=[]
        )

    # ========================================================================
    # METRICS
    # ========================================================================

    with col_metrics:

        st.markdown(
            '<div class="section-header">📊 Thông số vùng</div>',
            unsafe_allow_html=True
        )

        render_stat_cards()

        gauge = create_gauge(
            value=78
        )

        st.plotly_chart(
            gauge,
            use_container_width=True,
            config={
                "displayModeBar": False
            }
        )

    # -------------------------------------------------------------------------
    # DIVIDER
    # -------------------------------------------------------------------------

    st.markdown("---")

    # -------------------------------------------------------------------------
    # TIME SERIES
    # -------------------------------------------------------------------------

    st.markdown(
        """
        <div class="section-header">
            📈 BIẾN ĐỘNG CHỈ SỐ NDVI THEO THỜI GIAN
            (2017 - 2026)
        </div>
        """,
        unsafe_allow_html=True
    )

    chart = create_ndvi_chart()

    st.plotly_chart(
        chart,
        use_container_width=True,
        config={
            "displayModeBar": False
        }
    )

    # -------------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------------

    st.markdown("---")

    st.markdown(
        """
        <div class="section-header">
            📋 BÁO CÁO TÓM TẮT KHU VỰC
        </div>
        """,
        unsafe_allow_html=True
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        render_info_card(
            "Vùng theo dõi",
            selected_district
        )

    with c2:
        render_info_card(
            "Tỉnh / Thành phố",
            selected_province
        )

    with c3:
        render_info_card(
            "Đánh giá sức khỏe",
            "Phát triển tốt 🟢"
        )

    with c4:
        render_info_card(
            "Mốc thời gian",
            selected_time.strftime("%m/%Y")
        )

    # -------------------------------------------------------------------------
    # FOOTER
    # -------------------------------------------------------------------------

    st.markdown(
        """
        <div class="footer">
            GEO BIG DATA - NDVI PREDICTION PLATFORM
            <br>
            Remote Sensing • GIS • Artificial Intelligence
        </div>
        """,
        unsafe_allow_html=True
    )


# =============================================================================
# 13. ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    main()
```
