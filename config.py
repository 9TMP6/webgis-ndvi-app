# config.py
import streamlit as st
DATABASE_URL = st.secrets["postgres"]["url"]
LOCATION_DATA = {
    "TP. Hồ Chí Minh": {
        # 🌐 Tổng quan Toàn Thành phố
        "Toàn tỉnh/TP": [10.7769, 106.7009, 10],

        # 🏛️ KHU VỰC TRUNG TÂM (DOWNTOWN)
        "Quận 1 - P. Bến Nghé": [10.7783, 106.7022, 15],
        "Quận 1 - P. Bến Thành": [10.7725, 106.6981, 15],
        "Quận 1 - P. Tân Định": [10.7900, 106.6903, 15],
        "Quận 3 - P. Võ Thị Sáu": [10.7850, 106.6880, 15],
        "Quận 3 - Phường 11": [10.7801, 106.6775, 15],
        "Quận 4 - Phường 13": [10.7610, 106.7060, 15],
        "Quận 5 - Phường 11 (Chợ Lớn)": [10.7532, 106.6610, 15],
        "Quận 6 - Phường 1": [10.7480, 106.6490, 15],
        "Quận 8 - Phường 5": [10.7380, 106.6660, 14],
        "Quận 10 - Phường 12": [10.7730, 106.6710, 15],
        "Quận 11 - Phường 15": [10.7660, 106.6540, 15],

        # 🏙️ THÀNH PHỐ THỦ ĐỨC (ĐÔNG TP.HCM)
        "TP. Thủ Đức ": [10.8494, 106.7537, 12],
        "TP. Thủ Đức - P. Thảo Điền": [10.8062, 106.7328, 14],
        "TP. Thủ Đức - P. An Khánh (Thủ Thiêm)": [10.7780, 106.7180, 14],
        "TP. Thủ Đức - P. Linh Trung (ĐHQG)": [10.8710, 106.7900, 14],
        "TP. Thủ Đức - P. Hiệp Phú (KCN Hiệp Phước/CNC)": [10.8450, 106.7860, 14],
        "TP. Thủ Đức - P. Long Bình": [10.8750, 106.8200, 13],
        "TP. Thủ Đức - P. Phước Long B": [10.8190, 106.7720, 14],

        # 🏬 KHU VỰC NỘI THÀNH MỞ RỘNG
        "Quận Bình Thạnh - P. 22 (Vinhomes)": [10.7930, 106.7210, 15],
        "Quận Bình Thạnh - P. 25": [10.8080, 106.7130, 15],
        "Quận Gò Vấp - Phường 10": [10.8380, 106.6680, 14],
        "Quận Phú Nhuận - Phường 7": [10.7980, 106.6870, 15],
        "Quận Tân Bình - P. 2 (Sân bay Tân Sơn Nhất)": [10.8140, 106.6620, 14],
        "Quận Tân Phú - P. Sơn Kỳ": [10.8030, 106.6190, 14],
        "Quận Bình Tân - P. An Lạc": [10.7280, 106.6080, 14],
        "Quận Bình Tân - P. Bình Hưng Hòa": [10.8000, 106.5930, 14],

        # 🌉 KHU VỰC PHÍA NAM
        "Quận 7 - P. Tân Phong (Phú Mỹ Hưng)": [10.7290, 106.7080, 14],
        "Quận 7 - P. Tân Thuận Đông": [10.7600, 106.7300, 14],
        "Quận 12 - P. Tân Chánh Hiệp": [10.8600, 106.6200, 14],
        "Quận 12 - P. Thạnh Lộc": [10.8800, 106.6800, 14],

        # 🌾 KHU VỰC NGOẠI THÀNH (VÙNG NÔNG NGHIỆP & SINH THÁI)
        "Huyện Bình Chánh - Xã Bình Hưng": [10.7180, 106.6610, 13],
        "Huyện Bình Chánh - Thị trấn Tân Túc": [10.6860, 106.5590, 13],
        "Huyện Củ Chi - Thị trấn Củ Chi": [10.9700, 106.4950, 12],
        "Huyện Củ Chi - Xã Phạm Văn Cội": [11.0800, 106.5400, 12],
        "Huyện Hóc Môn - Thị trấn Hóc Môn": [10.8870, 106.5910, 13],
        "Huyện Nhà Bè - Xã Phước Kiển": [10.7100, 106.7000, 13],
        "Huyện Nhà Bè - Xã Hiệp Phước": [10.6200, 106.7300, 12],
        "Huyện Cần Giờ - Thị trấn Cần Thạnh": [10.4080, 106.9530, 12],
        "Huyện Cần Giờ - Xã Long Hòa (Rừng Sác)": [10.4500, 106.8800, 11]
    }
    
    # "An Giang": {
    #     "Toàn tỉnh/TP": [10.5361, 105.1325, 10],
    #     "TP. Long Xuyên": [10.3800, 105.4300, 13],
    #     "TP. Châu Đốc": [10.7000, 105.1100, 13],
    #     "Thị xã Tịnh Biên": [10.6000, 104.9300, 12],
    #     "Huyện Chợ Mới": [10.5000, 105.5500, 12],
    #     "Huyện Tri Tôn": [10.4200, 105.0000, 12]
    # }
}
CUSTOM_CSS = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800&display=swap');

    :root {
        --g-900: #14532D; --g-700: #15803D; --g-600: #16A34A; --g-500: #22C55E;
        --g-100: #DCFCE7; --g-50: #F0FDF4;
        --card: #FFFFFF; --line: #D7E8DB; --text: #14301F; --muted: #5B7A66;
    }

    html, body, [class*="css"] { font-size: 13px !important; }
    .stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
    .stApp button, .stApp input, .stApp textarea {
        font-family: 'Be Vietnam Pro', 'Segoe UI', sans-serif;
    }
    .stApp {
        background: linear-gradient(180deg, #EEF8F0 0%, #F8FCF9 45%, #ECF6EF 100%);
        color: var(--text);
    }
    .stApp h1, .stApp h2, .stApp h3 { color: var(--g-900); }
    .stApp hr { border-color: #CFE3D4 !important; }

    /* ===== Header ===== */
    .top-header {
        background: linear-gradient(100deg, #15803D 0%, #16A34A 50%, #65A30D 100%);
        padding: 10px 18px; border-radius: 14px;
        display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;
        box-shadow: 0 6px 18px rgba(22, 101, 52, 0.22);
    }
    .brand-title { font-size: 1.15rem !important; font-weight: 800; color: #FFFFFF; letter-spacing: 0.3px; }
    .status-badge {
        background: rgba(255, 255, 255, 0.20); color: #FFFFFF;
        padding: 3px 10px; border-radius: 999px; font-size: 0.75rem !important;
        border: 1px solid rgba(255, 255, 255, 0.45); font-weight: 600;
    }

    .block-container { padding-top: 3.8rem !important; padding-bottom: 0.8rem !important; padding-left: 1rem !important; padding-right: 0.3rem !important; }

    /* ===== Sidebar ===== */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #E9F5EC 0%, #F4FAF5 100%);
        border-right: 1px solid var(--line);
    }
    div[data-testid="stSidebarUserContent"] { padding-top: 3.8rem !important; }
    div[data-testid="stExpander"] {
        background: #FFFFFF; border: 1px solid var(--line) !important; border-radius: 12px !important;
        box-shadow: 0 1px 3px rgba(20, 83, 45, 0.06);
    }

    /* ===== Nút bấm ===== */
    button[kind="primary"], button[data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, #16A34A 0%, #65A30D 100%) !important;
        color: #FFFFFF !important; border: none !important; font-weight: 700 !important;
        border-radius: 10px !important; box-shadow: 0 4px 12px rgba(22, 163, 74, 0.30);
        transition: transform .15s ease, filter .15s ease;
    }
    button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {
        filter: brightness(1.07); transform: translateY(-1px);
    }
    [data-testid="stDownloadButton"] button {
        background: #FFFFFF; color: var(--g-700); border: 1px solid #BFDCC6; border-radius: 10px;
    }
    [data-testid="stDownloadButton"] button:hover { background: var(--g-50); border-color: var(--g-600); color: var(--g-700); }

    /* ===== Thẻ chỉ số & chú giải ===== */
    .stat-box {
        background: var(--card); border: 1px solid var(--line); border-radius: 12px;
        padding: 10px; text-align: center; margin-bottom: 8px;
        box-shadow: 0 2px 8px rgba(20, 83, 45, 0.06);
    }
    .stat-title { color: var(--muted); font-size: 0.7rem !important; font-weight: 600; text-transform: uppercase; margin-bottom: 2px; }
    .stat-value { font-size: 1.15rem !important; font-weight: 700; }
    .legend-panel {
        background: var(--card); border: 1px solid var(--line); border-radius: 12px;
        padding: 12px; margin-top: 10px; box-shadow: 0 2px 8px rgba(20, 83, 45, 0.06);
    }
    .legend-item { display: flex; align-items: center; font-size: 0.75rem !important; margin-bottom: 4px; color: #3F5B49; }
    .color-box { width: 12px; height: 12px; border-radius: 3px; margin-right: 6px; display: inline-block; }

    /* ===== Bản đồ & thông báo ===== */
    iframe[title="streamlit_folium.st_folium"] {
        border-radius: 14px; border: 1px solid var(--line); box-shadow: 0 6px 20px rgba(20, 83, 45, 0.12);
    }
    div[data-testid="stAlert"] { border-radius: 12px; }
    div[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) {
        background: #ECF8EF; color: var(--g-900); border: 1px solid #CBE8D3;
    }

    [data-testid="stHeader"] a[href*="github"] {
        display: none !important;
    }
    </style>
"""
