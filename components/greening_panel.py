# components/greening_panel.py
"""
Khối "Ước tính lợi ích trồng thêm cây xanh" đặt dưới bản đồ.
Lấy NDVI đang hiển thị -> tính quỹ đất còn thiếu thực vật (NDVI < 0,3) của phạm vi đã chọn (toàn TP hoặc 1 phường/xã)
-> chọn kịch bản trồng cây -> ra số cây và các lợi ích (CO2, O2, sinh khối, bóng mát, nước mưa, giá trị quy đổi).
Chạy trong fragment: đổi kịch bản/hệ số chỉ vẽ lại khối này, không chạy lại cả trang.
"""
import numpy as np
import pandas as pd
import streamlit as st

from utils.greening import (
    SCENARIOS, DEFAULTS, VEG_THRESHOLD, CELL_AREA_KM2,
    compute_benefits, scenario_trees, fmt_int, fmt_dec, fmt_money, fmt_area, fmt_mass,
)

CITY = "Toàn TP. Hồ Chí Minh"
_fragment = getattr(st, "fragment", None) or getattr(st, "experimental_fragment", None) or (lambda f: f)

_CSS = """
<style>
.gr-text { font-size: 0.98rem; line-height: 1.75; color: var(--text); margin: 6px 0 4px 0; }
.gr-text .hl { background: var(--g-100); color: var(--g-900); font-weight: 700; padding: 1px 7px; border-radius: 7px; white-space: nowrap; }
.gr-note { font-size: 0.78rem; color: var(--muted); margin-top: 10px; line-height: 1.5; }
.gr-card-sub { color: var(--muted); font-size: 0.72rem; margin-top: 1px; }
</style>
"""


def _hl(s) -> str:
    return f"<span class='hl'>{s}</span>"


def _scope_data(df: pd.DataFrame):
    """-> (danh sách phạm vi {tên: dict(area_km2, veg_pct, n_cells)}). Luôn có 'Toàn TP'; thêm từng phường/xã nếu có ranh giới."""
    d = df.dropna(subset=["ndvi_mean"])
    n_all = len(d)
    veg_city = float((d["ndvi_mean"] >= VEG_THRESHOLD).mean() * 100.0) if n_all else 0.0
    area_city = n_all * CELL_AREA_KM2
    scopes = {}
    try:
        from utils.ward_info import get_ward_stats, ward_label
        stats, _city_mean, gdf = get_ward_stats(df)
    except Exception as e:
        print(f"[GREENING] không lấy được thống kê phường/xã: {e}")
        stats, gdf = None, None

    if gdf is not None and "dtich_km2" in getattr(gdf, "columns", []):
        total = pd.to_numeric(gdf["dtich_km2"], errors="coerce").sum()
        if total and np.isfinite(total) and total > 0:
            area_city = float(total)
    scopes[CITY] = dict(area_km2=area_city, veg_pct=veg_city, n_cells=n_all)

    if stats is not None and gdf is not None and "dtich_km2" in gdf.columns:
        rows = []
        for _, r in gdf.iterrows():
            key = str(r.get("ma_xa", "")).strip()
            if key in stats.index:
                a = pd.to_numeric(r.get("dtich_km2"), errors="coerce")
                if pd.notna(a) and a > 0:
                    rows.append((ward_label(r), dict(area_km2=float(a), veg_pct=float(stats.loc[key, "veg_pct"]),
                                                     n_cells=int(stats.loc[key, "n_cells"]))))
        for label, info in sorted(rows, key=lambda t: t[0]):
            scopes.setdefault(label, info)       # trùng tên thì giữ mục đầu
    return scopes


@_fragment
def render_greening_panel(df: pd.DataFrame):
    """Vẽ khối ước tính lợi ích trồng cây. Không vẽ gì nếu chưa có dữ liệu NDVI."""
    if df is None or df.empty:
        return
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        "<section class='section-head'><div><h2>🌳 Ước tính lợi ích trồng thêm cây xanh</h2>"
        "<p class='sub'>Dựa trên NDVI đang hiển thị: phần diện tích chưa đạt ngưỡng thực vật (NDVI &lt; 0,3) "
        "là quỹ đất để trồng thêm. Chọn phạm vi và kịch bản để xem kết quả.</p></div></section>",
        unsafe_allow_html=True,
    )

    scopes = _scope_data(df)
    c1, c2, c3 = st.columns([1.4, 1.3, 0.8])
    with c1:
        scope_name = st.selectbox("Phạm vi tính", list(scopes.keys()), key="gr_scope",
                                  help="Toàn TP hoặc một phường/xã (gõ để tìm).")
    with c2:
        scen_name = st.selectbox("Kịch bản trồng cây", list(SCENARIOS.keys()), key="gr_scen")
    with c3:
        years = st.number_input("Số năm (T)", min_value=1, max_value=50, value=10, step=1, key="gr_years")

    pct, dens = SCENARIOS[scen_name]
    if pct is None:   # Tùy chỉnh
        cc1, cc2 = st.columns(2)
        with cc1:
            pct = st.slider("Tỉ lệ quỹ đất NDVI thấp được trồng (%)", 0.0, 50.0, 5.0, 0.5, key="gr_pct")
        with cc2:
            dens = st.slider("Mật độ trồng (cây/ha)", 100, 2500, 600, 50, key="gr_dens")
    else:
        st.caption(f"Kịch bản này giả định trồng trên {fmt_dec(pct, 0)}% quỹ đất NDVI thấp, mật độ {fmt_int(dens)} cây/ha "
                   "(giá trị mẫu, chọn «Tùy chỉnh» để đổi).")

    with st.expander("⚙️ Công thức và hệ số tính (có thể chỉnh)", expanded=False):
        st.markdown(
            "| Chỉ tiêu | Công thức |\n|---|---|\n"
            "| CO₂ hấp thụ (tấn) | N × C × T / 1000 |\n"
            "| O₂ tạo ra (tấn) | CO₂ × 0,727 |\n"
            "| Sinh khối tăng thêm (kg) | N × B × T |\n"
            "| Diện tích bóng mát (m²) | N × S × f |\n"
            "| Nước mưa giữ lại (m³) | N × R × T / 1000 |\n"
            "| Giá trị quy đổi (đồng) | G₁ + G₂ + G₃ − chi phí, với G₁ = CO₂ × P₁, G₂ = sinh khối × P₂, G₃ = nước × P₃ |\n\n"
            "N: số cây, T: số năm. Hệ số dưới đây là giá trị mẫu để minh họa."
        )
        a, b, c = st.columns(3)
        with a:
            C = st.number_input("C – CO₂ hấp thụ (kg/cây/năm)", 0.0, 500.0, DEFAULTS["C"], 1.0, key="gr_C")
            B = st.number_input("B – Sinh khối tăng (kg/cây/năm)", 0.0, 500.0, DEFAULTS["B"], 1.0, key="gr_B")
            P1 = st.number_input("P₁ – Giá carbon (đ/tấn CO₂)", 0.0, 10_000_000.0, DEFAULTS["P1"], 10_000.0, key="gr_P1")
        with b:
            S = st.number_input("S – Diện tích tán (m²/cây)", 0.0, 500.0, DEFAULTS["S"], 1.0, key="gr_S")
            f = st.number_input("f – Hệ số tán không chồng lấn (0–1)", 0.0, 1.0, DEFAULTS["f"], 0.05, key="gr_f")
            P2 = st.number_input("P₂ – Giá sinh khối (đ/kg)", 0.0, 1_000_000.0, DEFAULTS["P2"], 100.0, key="gr_P2")
        with c:
            R = st.number_input("R – Nước mưa giữ lại (lít/cây/năm)", 0.0, 10_000.0, DEFAULTS["R"], 10.0, key="gr_R")
            P3 = st.number_input("P₃ – Giá trị nước (đ/m³)", 0.0, 1_000_000.0, DEFAULTS["P3"], 500.0, key="gr_P3")
            ci = st.number_input("Chi phí đầu tư (đ/cây)", 0.0, 10_000_000.0, DEFAULTS["c_invest"], 10_000.0, key="gr_ci")
            cm = st.number_input("Chi phí bảo dưỡng (đ/cây/năm)", 0.0, 10_000_000.0, DEFAULTS["c_maint"], 5_000.0, key="gr_cm")

    sc = scopes[scope_name]
    low_ha, planted_ha, n_trees, veg_after = scenario_trees(sc["area_km2"], sc["veg_pct"], pct, dens)
    r = compute_benefits(n_trees, years, C=C, B=B, S=S, R=R, f=f, P1=P1, P2=P2, P3=P3, c_invest=ci, c_maint=cm)

    if n_trees <= 0:
        st.info("Với phạm vi và kịch bản này, quỹ đất có thể trồng thêm bằng 0 nên chưa có lợi ích để tính.")
        return

    cost_txt = "" if r["cost"] > 0 else " (chưa trừ chi phí đầu tư và bảo dưỡng)"
    text = (
        f"Ở phạm vi <b>{scope_name}</b>, độ phủ thực vật hiện tại (NDVI ≥ 0,3) khoảng {_hl(fmt_dec(sc['veg_pct'], 1) + '%')}, "
        f"còn khoảng {_hl(fmt_area(low_ha * 1e4))} đất chưa đạt ngưỡng. Theo kịch bản <b>{scen_name.lower()}</b>, "
        f"nếu trồng thêm khoảng {_hl(fmt_int(n_trees) + ' cây')} trên {_hl(fmt_area(planted_ha * 1e4))}, "
        f"sau {_hl(str(int(years)) + ' năm')} ước tính hấp thụ khoảng {_hl(fmt_dec(r['co2_t'], 1) + ' tấn CO₂')} "
        f"và tạo ra khoảng {_hl(fmt_dec(r['o2_t'], 1) + ' tấn O₂')}, "
        f"sinh khối tăng thêm khoảng {_hl(fmt_mass(r['biomass_kg']))}, "
        f"diện tích bóng mát khoảng {_hl(fmt_area(r['shade_m2']))} "
        f"và giữ lại khoảng {_hl(fmt_dec(r['water_m3'], 0) + ' m³')} nước mưa. "
        f"Quy đổi thành tiền, tổng lợi ích khoảng {_hl(fmt_money(r['total']))}{cost_txt}. "
        f"Độ phủ thực vật có thể tăng từ {_hl(fmt_dec(sc['veg_pct'], 1) + '%')} lên khoảng "
        f"{_hl(fmt_dec(veg_after, 1) + '%')}."
    )
    st.markdown(f"<div class='gr-text'>{text}</div>", unsafe_allow_html=True)

    cards = [
        ("Số cây trồng thêm", fmt_int(n_trees) + " cây", f"{fmt_int(dens)} cây/ha"),
        ("CO₂ hấp thụ", fmt_dec(r["co2_t"], 1) + " tấn", f"trong {int(years)} năm"),
        ("O₂ tạo ra", fmt_dec(r["o2_t"], 1) + " tấn", "CO₂ × 0,727"),
        ("Sinh khối tăng thêm", fmt_mass(r["biomass_kg"]), ""),
        ("Diện tích bóng mát", fmt_area(r["shade_m2"]), ""),
        ("Nước mưa giữ lại", fmt_dec(r["water_m3"], 0) + " m³", ""),
        ("Giá trị quy đổi", fmt_money(r["total"]), "G₁ + G₂ + G₃ − chi phí"),
        ("Độ phủ thực vật sau trồng", fmt_dec(veg_after, 1) + "%", f"hiện tại {fmt_dec(sc['veg_pct'], 1)}%"),
    ]
    html = "".join(
        f"<div class='info-card'><div class='lbl'>{lbl}</div><div class='val'>{val}</div>"
        f"{f'<div class=gr-card-sub>{sub}</div>' if sub else ''}</div>"
        for lbl, val, sub in cards
    )
    st.markdown(f"<div class='info-grid'>{html}</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='gr-note'>*Số liệu chỉ mang tính ước lượng theo công thức và hệ số mẫu, "
        "không phải kết quả đo đạc và có thể khác thực tế (loài cây, điều kiện đất, chăm sóc, tỉ lệ cây sống). "
        "Cần khảo sát thực địa trước khi áp dụng.</div>",
        unsafe_allow_html=True,
    )
