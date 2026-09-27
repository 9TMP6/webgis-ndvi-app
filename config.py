# Cấu hình vị trí
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

# CSS Tùy chỉnh
CUSTOM_CSS = """
    <style>
    html, body, [class*="css"] { font-size: 13px !important; }
    .stApp { background-color: #0B0F17; color: #E2E8F0; }
    .top-header {
        background: linear-gradient(90deg, #0F172A 0%, #1E293B 100%);
        padding: 8px 16px; border-radius: 8px; border: 1px solid #1E293B;
        display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;
    }
    .brand-title {
        font-size: 1.1rem !important; font-weight: 800;
        background: linear-gradient(135deg, #38BDF8 0%, #10B981 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .status-badge {
        background-color: rgba(16, 185, 129, 0.15); color: #10B981;
        padding: 2px 8px; border-radius: 12px; font-size: 0.75rem !important;
        border: 1px solid rgba(16, 185, 129, 0.3); font-weight: 600;
    }
    .block-container { padding-top: 3.8rem !important; padding-bottom: 0.8rem !important; padding-left: 1rem !important; padding-right: 0.3rem !important; }
    section[data-testid="stSidebar"] { background-color: #0F172A; border-right: 1px solid #1E293B; }
    div[data-testid="stSidebarUserContent"] { padding-top: 3.8rem !important; }
    .stat-box { background: #151D2A; border: 1px solid #26334D; border-radius: 6px; padding: 8px; text-align: center; margin-bottom: 8px; }
    .stat-title { color: #94A3B8; font-size: 0.7rem !important; font-weight: 600; text-transform: uppercase; margin-bottom: 2px; }
    .stat-value { font-size: 1.1rem !important; font-weight: 700; }
    .legend-panel { background: #151D2A; border: 1px solid #26334D; border-radius: 6px; padding: 10px; margin-top: 10px; }
    .legend-item { display: flex; align-items: center; font-size: 0.75rem !important; margin-bottom: 4px; color: #CBD5E1; }
    .color-box { width: 12px; height: 12px; border-radius: 2px; margin-right: 6px; display: inline-block; }
    </style>
"""
