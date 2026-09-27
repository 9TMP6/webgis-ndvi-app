# config.py

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
        "TP. Thủ Đức - Toàn khu vực": [10.8494, 106.7537, 12],
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
    [data-testid="stHeader"] a[href*="github"] {
        display: none !important;
    }
    </style>
"""
