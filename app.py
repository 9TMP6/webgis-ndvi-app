import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from folium.plugins import Fullscreen


st.set_page_config(
    page_title="NDVI Intelligence Platform",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed"
)


BG = "#08111C"
SURFACE = "#0D1926"
SURFACE_2 = "#111F2E"
BORDER = "#203245"
TEXT = "#E8F0F7"
MUTED = "#8295A8"
BLUE = "#38BDF8"
GREEN = "#22C55E"
YELLOW = "#FACC15"
RED = "#F87171"


def inject_css():
    st.markdown(
        f"""
        <style>
        html, body, [class*="css"] {{
            font-family: Inter, Arial, sans-serif;
        }}

        .stApp {{
            background: {BG};
            color: {TEXT};
        }}

        .block-container {{
            max-width: 1500px;
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }}

        .top-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 18px 22px;
            margin-bottom: 16px;
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 14px;
        }}

        .brand {{
            font-size: 22px;
            font-weight: 700;
            letter-spacing: 1px;
            color: {TEXT};
        }}

        .subtitle {{
            margin-top: 4px;
            color: {MUTED};
            font-size: 12px;
            letter-spacing: 1px;
        }}

        .status {{
            padding: 8px 14px;
            border-radius: 20px;
            background: rgba(34,197,94,.12);
            border: 1px solid rgba(34,197,94,.35);
            color: {GREEN};
            font-size: 12px;
            font-weight: 600;
        }}

        .control-box {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 14px;
            padding: 12px 14px 4px;
            margin-bottom: 16px;
        }}

        .section-title {{
            font-size: 12px;
            color: {MUTED};
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }}

        .map-title {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}

        .map-title-main {{
            font-size: 15px;
            font-weight: 650;
        }}

        .map-title-sub {{
            color: {MUTED};
            font-size: 12px;
        }}

        .metric {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 12px;
            padding: 16px;
            min-height: 105px;
        }}

        .metric-label {{
            color: {MUTED};
            font-size: 12px;
            margin-bottom: 8px;
        }}

        .metric-value {{
            color: {TEXT};
            font-size: 27px;
            font-weight: 700;
        }}

        .metric-note {{
            color: {GREEN};
            font-size: 11px;
            margin-top: 4px;
        }}

        .panel {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 14px;
            padding: 18px;
            height: 100%;
        }}

        .panel-title {{
            font-size: 14px;
            font-weight: 650;
            margin-bottom: 12px;
        }}

        .info-row {{
            display: flex;
            justify-content: space-between;
            padding: 9px 0;
            border-bottom: 1px solid {BORDER};
            font-size: 12px;
        }}

        .info-label {{
            color: {MUTED};
        }}

        .info-value {{
            color: {TEXT};
            font-weight: 600;
        }}

        .footer {{
            margin-top: 25px;
            padding-top: 15px;
            border-top: 1px solid {BORDER};
            text-align: center;
            color: {MUTED};
            font-size: 11px;
        }}

        div[data-testid="stButton"] button {{
            border-radius: 8px;
            font-weight: 600;
        }}

        div[data-testid="stDownloadButton"] button {{
            border-radius: 8px;
            font-weight: 600;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )


LOCATION_DATA = {
    "An Giang": {
        "Toàn tỉnh": (10.5216, 105.1259),
        "TP. Long Xuyên": (10.3864, 105.4352),
        "Huyện Chợ Mới": (10.5452, 105.3372)
    },
    "TP. Hồ Chí Minh": {
        "Toàn thành phố": (10.8231, 106.6297),
        "Quận 1": (10.7756, 106.7004),
        "TP. Thủ Đức": (10.8505, 106.7717)
    }
}


@st.cache_data
def generate_demo_data():
    dates = pd.date_range(
        "2017-01-01",
        "2026-09-01",
        freq="MS"
    )

    rng = np.random.default_rng(42)

    base = 0.58 + 0.08 * np.sin(
        np.arange(len(dates)) / 7
    )

    noise = rng.normal(
        0,
        0.025,
        len(dates)
    )

    values = np.clip(
        base + noise,
        -1,
        1
    )

    future_dates = pd.date_range(
        "2026-10-01",
        "2027-06-01",
        freq="MS"
    )

    future_base = 0.64 + 0.025 * np.sin(
        np.arange(len(future_dates)) / 2.5
    )

    future_noise = rng.normal(
        0,
        0.012,
        len(future_dates)
    )

    future_values = np.clip(
        future_base + future_noise,
        -1,
        1
    )

    return (
        dates,
        values,
        future_dates,
        future_values
    )


def add_basemap(m, selected):
    if selected == "🛰️ Satellite":
        folium.TileLayer(
            tiles=(
                "https://server.arcgisonline.com/ArcGIS/rest/"
                "services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            ),
            attr="Esri World Imagery",
            name="Satellite",
            control=False
        ).add_to(m)

    elif selected == "🗺️ Street":
        folium.TileLayer(
            tiles="OpenStreetMap",
            name="Street",
            control=False
        ).add_to(m)

    else:
        folium.TileLayer(
            tiles="CartoDB dark_matter",
            name="Dark",
            control=False
        ).add_to(m)


def add_ndvi_legend(m):
    legend = """
    <div style="
        position: fixed;
        bottom: 30px;
        left: 30px;
        z-index: 9999;
        background: rgba(8,17,28,.94);
        border: 1px solid #203245;
        border-radius: 10px;
        padding: 12px 14px;
        color: #E8F0F7;
        font-size: 11px;
        width: 170px;
    ">
        <div style="font-weight:700;margin-bottom:8px;">
            NDVI
        </div>

        <div style="display:flex;align-items:center;margin:4px 0;">
            <span style="
                width:13px;
                height:13px;
                background:#8B0000;
                display:inline-block;
                margin-right:7px;
            "></span>
            <span>-1.0 → 0.0</span>
        </div>

        <div style="display:flex;align-items:center;margin:4px 0;">
            <span style="
                width:13px;
                height:13px;
                background:#FACC15;
                display:inline-block;
                margin-right:7px;
            "></span>
            <span>0.0 → 0.3</span>
        </div>

        <div style="display:flex;align-items:center;margin:4px 0;">
            <span style="
                width:13px;
                height:13px;
                background:#22C55E;
                display:inline-block;
                margin-right:7px;
            "></span>
            <span>0.3 → 0.6</span>
        </div>

        <div style="display:flex;align-items:center;margin:4px 0;">
            <span style="
                width:13px;
                height:13px;
                background:#166534;
                display:inline-block;
                margin-right:7px;
            "></span>
            <span>0.6 → 1.0</span>
        </div>
    </div>
    """

    m.get_root().html.add_child(
        folium.Element(legend)
    )


def build_map(lat, lng, basemap):
    m = folium.Map(
        location=[lat, lng],
        zoom_start=10,
        control_scale=True,
        zoom_control=True,
        tiles=None
    )

    add_basemap(
        m,
        basemap
    )

    folium.Marker(
        [lat, lng],
        tooltip="Selected location",
        popup=f"""
        <b>NDVI Monitoring Point</b><br>
        Latitude: {lat:.5f}<br>
        Longitude: {lng:.5f}
        """,
        icon=folium.Icon(
            color="green",
            icon="leaf",
            prefix="fa"
        )
    ).add_to(m)

    folium.Circle(
        [lat, lng],
        radius=5000,
        color="#38BDF8",
        weight=1,
        fill=False
    ).add_to(m)

    Fullscreen(
        position="topright",
        title="Full screen",
        title_cancel="Exit full screen",
        force_separate_button=True
    ).add_to(m)

    add_ndvi_legend(m)

    return m


def build_chart():
    dates, values, future_dates, future_values = (
        generate_demo_data()
    )

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=dates,
            y=values,
            mode="lines",
            name="Historical",
            line=dict(
                color=BLUE,
                width=2
            )
        )
    )

    fig.add_trace(
        go.Scatter(
            x=future_dates,
            y=future_values,
            mode="lines",
            name="GRU Forecast",
            line=dict(
                color=GREEN,
                width=2,
                dash="dash"
            )
        )
    )

    fig.update_layout(
        height=350,
        margin=dict(
            l=10,
            r=10,
            t=15,
            b=10
        ),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(
            color=TEXT,
            size=11
        ),
        legend=dict(
            orientation="h",
            y=1.08,
            x=0
        ),
        xaxis=dict(
            gridcolor=BORDER,
            zeroline=False
        ),
        yaxis=dict(
            title="NDVI",
            range=[-0.2, 1],
            gridcolor=BORDER,
            zeroline=False
        ),
        hovermode="x unified"
    )

    return fig


def metric_card(label, value, note):
    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def main():
    inject_css()

    st.markdown(
        """
        <div class="top-header">
            <div>
                <div class="brand">
                    GEO BIG DATA
                </div>
                <div class="subtitle">
                    NDVI INTELLIGENCE & REMOTE SENSING PLATFORM
                </div>
            </div>

            <div class="status">
                ● SYSTEM ONLINE
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="control-box">',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="section-title">Monitoring controls</div>',
        unsafe_allow_html=True
    )

    col1, col2, col3, col4, col5, col6 = st.columns(
        [1.2, 1.3, 1.1, 1.1, 1.0, 1.1]
    )

    with col1:
        province = st.selectbox(
            "Province",
            list(LOCATION_DATA.keys())
        )

    with col2:
        district = st.selectbox(
            "Administrative area",
            list(LOCATION_DATA[province].keys())
        )

    with col3:
        year = st.selectbox(
            "Year",
            list(range(2020, 2027)),
            index=6
        )

    with col4:
        month = st.selectbox(
            "Month",
            list(range(1, 13)),
            index=8
        )

    with col5:
        basemap = st.selectbox(
            "Basemap",
            [
                "🛰️ Satellite",
                "🗺️ Street",
                "🌑 Dark"
            ]
        )

    with col6:
        show_boundary = st.checkbox(
            "Show boundary",
            value=True
        )

    st.markdown(
        "</div>",
        unsafe_allow_html=True
    )

    lat, lng = LOCATION_DATA[province][district]

    map_col, info_col = st.columns(
        [3.6, 1]
    )

    with map_col:
        st.markdown(
            f"""
            <div class="map-title">
                <div>
                    <div class="map-title-main">
                        NDVI Spatial Monitoring
                    </div>
                    <div class="map-title-sub">
                        {district} · {province} · {month:02d}/{year}
                    </div>
                </div>

                <div class="map-title-sub">
                    Resolution: 500 × 500 m
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        m = build_map(
            lat,
            lng,
            basemap
        )

        if show_boundary:
            folium.Circle(
                [lat, lng],
                radius=15000,
                color="#38BDF8",
                weight=1,
                fill=False,
                dash_array="6 6"
            ).add_to(m)

        st_folium(
            m,
            width=None,
            height=620,
            returned_objects=[]
        )

    with info_col:
        st.markdown(
            '<div class="panel">',
            unsafe_allow_html=True
        )

        st.markdown(
            '<div class="panel-title">Spatial information</div>',
            unsafe_allow_html=True
        )

        info = [
            ("Region", province),
            ("Area", district),
            ("Latitude", f"{lat:.5f}"),
            ("Longitude", f"{lng:.5f}"),
            ("Resolution", "500 × 500 m"),
            ("Satellite", "Sentinel-2"),
            ("Index", "NDVI"),
            ("Model", "GRU"),
            ("Data year", str(year))
        ]

        for label, value in info:
            st.markdown(
                f"""
                <div class="info-row">
                    <span class="info-label">{label}</span>
                    <span class="info-value">{value}</span>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.markdown(
            "<br>",
            unsafe_allow_html=True
        )

        if st.button(
            "▶ Run AI Prediction",
            use_container_width=True,
            type="primary"
        ):
            st.success(
                "Prediction completed successfully."
            )

        st.download_button(
            "↓ Export NDVI Data",
            data="id,year,month,ndvi\n1,2026,09,0.642\n",
            file_name="ndvi_prediction.csv",
            mime="text/csv",
            use_container_width=True
        )

        st.markdown(
            "</div>",
            unsafe_allow_html=True
        )

    st.markdown(
        "<br>",
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="section-title">Current NDVI indicators</div>',
        unsafe_allow_html=True
    )

    k1, k2, k3, k4, k5 = st.columns(5)

    with k1:
        metric_card(
            "MEAN NDVI",
            "0.642",
            "Current observation"
        )

    with k2:
        metric_card(
            "MAX NDVI",
            "0.891",
            "Highest observed"
        )

    with k3:
        metric_card(
            "MIN NDVI",
            "-0.120",
            "Lowest observed"
        )

    with k4:
        metric_card(
            "GREEN COVER",
            "78%",
            "Vegetated area"
        )

    with k5:
        metric_card(
            "FORECAST",
            "0.671",
            "Next prediction"
        )

    st.markdown(
        "<br>",
        unsafe_allow_html=True
    )

    chart_col, summary_col = st.columns(
        [2.2, 1]
    )

    with chart_col:
        st.markdown(
            '<div class="panel">',
            unsafe_allow_html=True
        )

        st.markdown(
            '<div class="panel-title">NDVI historical & forecast</div>',
            unsafe_allow_html=True
        )

        st.plotly_chart(
            build_chart(),
            use_container_width=True,
            config={
                "displayModeBar": False
            }
        )

        st.markdown(
            "</div>",
            unsafe_allow_html=True
        )

    with summary_col:
        st.markdown(
            '<div class="panel">',
            unsafe_allow_html=True
        )

        st.markdown(
            '<div class="panel-title">Prediction summary</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            """
            <div class="info-row">
                <span class="info-label">Model</span>
                <span class="info-value">GRU</span>
            </div>

            <div class="info-row">
                <span class="info-label">Input sequence</span>
                <span class="info-value">10 steps</span>
            </div>

            <div class="info-row">
                <span class="info-label">Satellite</span>
                <span class="info-value">Sentinel-2</span>
            </div>

            <div class="info-row">
                <span class="info-label">Resolution</span>
                <span class="info-value">500 × 500 m</span>
            </div>

            <div class="info-row">
                <span class="info-label">Forecast horizon</span>
                <span class="info-value">9 months</span>
            </div>

            <div class="info-row">
                <span class="info-label">Output</span>
                <span class="info-value">NDVI GeoTIFF</span>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            "<br>",
            unsafe_allow_html=True
        )

        st.info(
            "The current interface uses demonstration values. "
            "The GRU output can be connected to the real prediction pipeline."
        )

        st.markdown(
            "</div>",
            unsafe_allow_html=True
        )

    st.markdown(
        """
        <div class="footer">
            NDVI Intelligence Platform · Remote Sensing · GIS · Deep Learning
        </div>
        """,
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
