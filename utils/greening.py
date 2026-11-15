# utils/greening.py
"""
ƯỚC TÍNH LỢI ÍCH TRỒNG THÊM CÂY XANH (hàm thuần, không phụ thuộc Streamlit nên dễ kiểm tra).

Công thức (đơn giản, theo bảng tham khảo):
    CO2 hấp thụ     = N x C x T / 1000          (tấn CO2)
    O2 tạo ra       = CO2 x 0,727               (tấn O2)
    Sinh khối tăng  = N x B x T                 (kg)
    Diện tích bóng  = N x S x f                 (m2, f: 0-1 hệ số tán không chồng lấn)
    Nước mưa giữ    = N x R x T / 1000          (m3)
    G1 = CO2 x P1,  G2 = Sinh khối x P2,  G3 = Nước x P3
    Tổng lợi ích    = G1 + G2 + G3 - C_đầu tư - C_bảo dưỡng

Cách gắn với NDVI hiện có: phần diện tích CHƯA đạt ngưỡng thực vật (NDVI < 0,3) của phạm vi đang xét là quỹ đất
để trồng thêm; mỗi kịch bản chọn tỉ lệ quỹ đất được trồng và mật độ cây/ha -> ra số cây N.
Mọi hệ số và kịch bản dưới đây là GIÁ TRỊ MẪU/GIẢ ĐỊNH để minh họa, người dùng chỉnh được trên giao diện.
"""
VEG_THRESHOLD = 0.3          # cùng ngưỡng "độ phủ thực vật" của ward_info
CELL_AREA_KM2 = 0.25         # ô lưới 500 m x 500 m
O2_PER_CO2 = 0.727           # theo công thức tham khảo

# Kịch bản mẫu: (tên, % quỹ đất NDVI thấp được trồng, mật độ cây/ha). "Tùy chỉnh" cho người dùng tự nhập.
SCENARIOS = {
    "Cây xanh đô thị (nhẹ)": (2.0, 400),
    "Công viên và mảng xanh (vừa)": (5.0, 600),
    "Phủ xanh mạnh": (10.0, 1000),
    "Tùy chỉnh": (None, None),
}

# Hệ số mẫu (lấy theo bảng tham khảo); người dùng chỉnh được
DEFAULTS = dict(
    C=20.0,        # kg CO2 hấp thụ / cây / năm
    B=12.0,        # kg sinh khối tăng thêm / cây / năm
    S=15.0,        # m2 diện tích tán / cây
    R=300.0,       # lít nước mưa giữ lại / cây / năm
    f=1.0,         # hệ số tán không chồng lấn (0-1)
    P1=300_000.0,  # đ / tấn CO2
    P2=1_000.0,    # đ / kg sinh khối
    P3=10_000.0,   # đ / m3 nước
    c_invest=0.0,  # đ / cây (chi phí đầu tư một lần)
    c_maint=0.0,   # đ / cây / năm (chi phí bảo dưỡng)
)


def compute_benefits(n_trees: float, years: float, **k) -> dict:
    """Tính các lợi ích từ số cây N và số năm T. k ghi đè DEFAULTS. -> dict (dùng cho cả bảng lẫn đoạn văn)."""
    p = {**DEFAULTS, **k}
    N, T = max(float(n_trees), 0.0), max(float(years), 0.0)
    co2 = N * p["C"] * T / 1000.0
    o2 = co2 * O2_PER_CO2
    bio = N * p["B"] * T
    shade = N * p["S"] * min(max(p["f"], 0.0), 1.0)
    water = N * p["R"] * T / 1000.0
    g1, g2, g3 = co2 * p["P1"], bio * p["P2"], water * p["P3"]
    cost = N * p["c_invest"] + N * p["c_maint"] * T
    return dict(co2_t=co2, o2_t=o2, biomass_kg=bio, shade_m2=shade, water_m3=water,
                g1=g1, g2=g2, g3=g3, cost=cost, total=g1 + g2 + g3 - cost)


def scenario_trees(area_km2: float, veg_pct: float, pct_planted: float, density_per_ha: float):
    """Từ diện tích phạm vi + độ phủ thực vật hiện có (NDVI >= 0,3) -> (quỹ đất NDVI thấp ha, ha được trồng, số cây,
    độ phủ sau khi trồng %). Phần được trồng được coi là thành thực vật khi cây trưởng thành."""
    area_ha = max(float(area_km2), 0.0) * 100.0
    veg = min(max(float(veg_pct), 0.0), 100.0)
    low_ha = area_ha * (1.0 - veg / 100.0)
    planted_ha = low_ha * min(max(float(pct_planted), 0.0), 100.0) / 100.0
    n = int(round(planted_ha * max(float(density_per_ha), 0.0)))
    after = min(100.0, veg + (planted_ha / area_ha * 100.0 if area_ha > 0 else 0.0))
    return low_ha, planted_ha, n, after


# ---------------- Định dạng số kiểu Việt Nam ----------------
def fmt_int(x) -> str:
    return f"{int(round(float(x))):,}".replace(",", ".")


def fmt_dec(x, nd=1) -> str:
    s = f"{float(x):,.{nd}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_money(x) -> str:
    """Tự chọn đơn vị: nghìn tỷ / tỷ / triệu / đồng."""
    v = float(x)
    a = abs(v)
    if a >= 1e12:
        return f"{fmt_dec(v / 1e12, 2)} nghìn tỷ đồng"
    if a >= 1e9:
        return f"{fmt_dec(v / 1e9, 2)} tỷ đồng"
    if a >= 1e6:
        return f"{fmt_dec(v / 1e6, 1)} triệu đồng"
    return f"{fmt_int(v)} đồng"


def fmt_area(m2) -> str:
    """m2 -> ha khi lớn."""
    v = float(m2)
    return f"{fmt_dec(v / 1e4, 1)} ha" if abs(v) >= 1e5 else f"{fmt_int(v)} m²"


def fmt_mass(kg) -> str:
    v = float(kg)
    return f"{fmt_dec(v / 1000, 1)} tấn" if abs(v) >= 1e5 else f"{fmt_int(v)} kg"
