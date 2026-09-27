st.markdown("""
<style>

.stApp {
    background: #121824;
    color: #E2E8F0;
}

/* HEADER */

.app-header {
    padding: 8px 0 18px 0;
}

.app-title {
    font-size: 24px;
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
    padding-top: 12px;
    color: #94A3B8;
    font-size: 12px;
}

.status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    background: #10B981;
    border-radius: 50%;
    margin-right: 5px;
}

/* MAP */

.map-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #1A2332;
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

/* RIGHT GIS PANEL */

.gis-stat {
    background: #1A2332;
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

/* NDVI LEGEND */

.ndvi-legend {
    position: fixed;
    bottom: 35px;
    left: 35px;
    width: 170px;
    background: rgba(18, 24, 36, 0.92);
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
    background: #d7191c;
}

.legend-color.medium {
    background: #ffffbf;
}

.legend-color.high {
    background: #1a9641;

}

</style>
""", unsafe_allow_html=True)
