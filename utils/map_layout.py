# utils/map_layout.py
"""
XUẤT BẢN ĐỒ CHUẨN (PNG, khổ A4 nằm ngang) - khác với "Xuất ảnh NDVI" (map_utils) ở chỗ đây là TỜ BẢN ĐỒ:
  - Tên bản đồ + thời điểm + nguồn dữ liệu
  - Khung bản đồ có LƯỚI TỌA ĐỘ (kinh/vĩ độ dạng độ-phút) và nhãn ở mép khung
  - Chú giải (thang màu NDVI, ranh giới phường/xã, ranh giới TP)
  - Hướng Bắc, TỶ LỆ SỐ (1:N, đúng khi in khổ A4 ở 100%) và thước tỷ lệ đồ họa
  - Bảng thông tin (hệ tọa độ, nguồn, số ô lưới, ngày lập) + ghi chú giới hạn dữ liệu
Dùng lại phần nội suy, ranh giới và bảng màu của map_utils nên bản đồ khớp với bản đồ web.
"""
import io
import math
import textwrap
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

PAGE_W, PAGE_H = 11.69, 8.27          # A4 nằm ngang (inch)
DPI = 200
GREEN, GREEN_DK, MUTED, INK = "#15803D", "#14532D", "#5B7A66", "#111827"

NOTES = {
    "observed": "NDVI trung bình tháng từ ảnh Sentinel-2 đã lọc mây, tổng hợp theo ô lưới 500 m rồi nội suy để vẽ bản đồ.",
    "ai": "Giá trị do mô hình AI dự báo, chưa đối chiếu với quan trắc cùng thời điểm; chỉ mang tính tham khảo.",
    "daily_sim": "Giá trị theo ngày được MÔ PHỎNG (nội suy giữa các tháng liền kề), không phải ảnh vệ tinh theo ngày.",
}


def _names():
    try:
        from components.layout import APP_NAME, APP_FULL_NAME
        return APP_NAME, APP_FULL_NAME
    except Exception:
        return "LST-NDVI-TVDI", "Hệ thống giám sát nhiệt độ bề mặt – lớp phủ thực vật – mức độ khô hạn tại TP.HCM"


def _dms(v, pos, neg):
    """Độ thập phân -> 106°30′E (làm tròn tới phút)."""
    total_min = int(round(abs(v) * 60))
    d, m = divmod(total_min, 60)
    return f"{d}°{m:02d}′{pos if v >= 0 else neg}"


def _nice_step(span_deg, target=5):
    """Bước lưới 'tròn' theo phút cung: 1', 2', 5', 10', 15', 20', 30', 1°..."""
    raw = span_deg / target
    for s in (1/60, 2/60, 5/60, 10/60, 15/60, 20/60, 30/60, 1.0, 2.0):
        if s >= raw:
            return s
    return 2.0


def _ticks(lo, hi, step):
    first = math.ceil(lo / step - 1e-9) * step
    out, v = [], first
    while v <= hi + 1e-9:
        out.append(round(v, 8))
        v += step
    return out


def render_map_sheet(df: pd.DataFrame, when_text: str = "", source_label: str = "", source_kind: str = "ai",
                     place_label: str = "TP. Hồ Chí Minh"):
    from matplotlib.figure import Figure
    from matplotlib.collections import LineCollection
    from matplotlib.patches import Rectangle, Polygon
    from matplotlib.cm import ScalarMappable
    import matplotlib.colors as mcolors
    from utils.map_utils import (_export_boundaries, _line_segments, _split_main_and_far, _export_interpolate,
                                 get_ndvi_cmap, NDVI_VMIN, NDVI_VMAX)

    if df is None or df.empty:
        return None
    d = df.dropna(subset=["longitude", "latitude", "ndvi_mean"])
    if d.empty:
        return None
    lons, lats, vals = (d[c].to_numpy(float) for c in ("longitude", "latitude", "ndvi_mean"))
    app_short, app_full = _names()

    gdf, geom = _export_boundaries()
    inner_segs = []
    if gdf is not None:
        for g in gdf.geometry:
            inner_segs += _line_segments(g)
    outer_segs = _line_segments(geom)

    m_main, _ = _split_main_and_far(lons, lats)
    res = _export_interpolate(lons[m_main], lats[m_main], vals[m_main], geom, 900)
    if res is None:
        return None
    grid, (lon_min, lon_max, lat_min, lat_max) = res
    has_far = bool((~m_main).any())

    cmap = get_ndvi_cmap().copy()
    cmap.set_bad((0, 0, 0, 0))
    norm = mcolors.Normalize(vmin=NDVI_VMIN, vmax=NDVI_VMAX)

    # ---------- Bố cục (inch) ----------
    k = math.cos(math.radians((lat_min + lat_max) / 2.0))
    w_eff, h_deg = (lon_max - lon_min) * k, (lat_max - lat_min)
    panel_w, margin = 3.3, 0.4
    left_lbl, bot_lbl = 0.85, 0.75
    area_w = PAGE_W - margin - panel_w - 0.4 - left_lbl - 0.1
    max_h = 5.2
    s = min(area_w / w_eff, max_h / h_deg)
    map_w, map_h = w_eff * s, h_deg * s
    x0 = left_lbl + 0.1 + (area_w - map_w) / 2
    y0 = 0.45 + bot_lbl
    map_top = y0 + map_h
    px = PAGE_W - margin - panel_w

    fig = Figure(figsize=(PAGE_W, PAGE_H), dpi=DPI, facecolor="white")

    def fr(x, y, w, h):
        return [x / PAGE_W, y / PAGE_H, w / PAGE_W, h / PAGE_H]

    def rect(x, y, w, h, **kw):
        kw.setdefault("zorder", -5)
        fig.add_artist(Rectangle((x / PAGE_W, y / PAGE_H), w / PAGE_W, h / PAGE_H, transform=fig.transFigure, **kw))

    def text(x, y, s_, **kw):
        kw.setdefault("va", "center")
        fig.text(x / PAGE_W, y / PAGE_H, s_, **kw)

    # đường viền tờ bản đồ (2 nét)
    rect(0.18, 0.18, PAGE_W - 0.36, PAGE_H - 0.36, facecolor="none", edgecolor=INK, linewidth=1.6)
    rect(0.24, 0.24, PAGE_W - 0.48, PAGE_H - 0.48, facecolor="none", edgecolor=INK, linewidth=0.6)

    # ---------- Tên bản đồ ----------
    cx = PAGE_W / 2
    text(cx, PAGE_H - 0.55, app_full.upper(), fontsize=8.5, color=MUTED, ha="center", fontweight="bold")
    text(cx, PAGE_H - 0.98, "BẢN ĐỒ PHÂN BỐ CHỈ SỐ THỰC VẬT NDVI", fontsize=20, color=GREEN_DK,
         ha="center", fontweight="bold")
    sub = " · ".join(p for p in (place_label, when_text) if p)
    text(cx, PAGE_H - 1.38, sub, fontsize=11.5, color=INK, ha="center")
    rect(0.5, PAGE_H - 1.62, PAGE_W - 1.0, 0.012, facecolor=GREEN, edgecolor="none")

    # ---------- Khung bản đồ + lưới tọa độ ----------
    ax = fig.add_axes(fr(x0, y0, map_w, map_h), facecolor="#F4F8F5")
    ax.imshow(grid, cmap=cmap, norm=norm, origin="lower", extent=(lon_min, lon_max, lat_min, lat_max),
              interpolation="bilinear", aspect="auto", zorder=1)
    if inner_segs:
        ax.add_collection(LineCollection(inner_segs, colors="#374151", linewidths=0.25, alpha=0.55, zorder=2))
    if outer_segs:
        ax.add_collection(LineCollection(outer_segs, colors=INK, linewidths=0.9, zorder=3))
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)

    xt = _ticks(lon_min, lon_max, _nice_step(lon_max - lon_min))
    yt = _ticks(lat_min, lat_max, _nice_step(lat_max - lat_min, 6))
    ax.set_xticks(xt)
    ax.set_yticks(yt)
    ax.set_xticklabels([_dms(v, "E", "W") for v in xt], fontsize=7.5, color=INK)
    ax.set_yticklabels([_dms(v, "N", "S") for v in yt], fontsize=7.5, color=INK, rotation=90, va="center")
    ax.tick_params(length=4, width=0.8, pad=3, top=True, right=True, labeltop=False, labelright=False)
    ax.set_axisbelow(False)
    ax.grid(True, color=INK, alpha=0.35, linestyle=(0, (4, 3)), linewidth=0.5, zorder=4)
    for sp in ax.spines.values():
        sp.set_edgecolor(INK)
        sp.set_linewidth(1.4)

    # ---------- Cột bên phải ----------
    def box(y_top, h, title):
        rect(px, y_top - h, panel_w, h, facecolor="#F7FBF8", edgecolor="#9CA3AF", linewidth=0.8)
        rect(px, y_top - 0.34, panel_w, 0.34, facecolor=GREEN, edgecolor="none", zorder=-4)
        text(px + 0.15, y_top - 0.17, title, fontsize=9, color="white", fontweight="bold")

    # (1) Chú giải
    h1 = 1.85
    box(map_top, h1, "CHÚ GIẢI")
    cax = fig.add_axes(fr(px + 0.2, map_top - 0.9, panel_w - 0.4, 0.2))
    cb = fig.colorbar(ScalarMappable(norm=norm, cmap=get_ndvi_cmap()), cax=cax, orientation="horizontal")
    cb.set_ticks(np.round(np.arange(NDVI_VMIN, NDVI_VMAX + 1e-9, 0.2), 1))
    cb.ax.tick_params(labelsize=7.5, length=3, colors=INK)
    cb.outline.set_edgecolor(INK)
    text(px + 0.2, map_top - 0.5, "Chỉ số NDVI", fontsize=8.5, color=INK, fontweight="bold")
    text(px + 0.2, map_top - 1.2, "Thấp (đất trống, đô thị, mặt nước)", fontsize=7, color=MUTED)
    text(px + panel_w - 0.2, map_top - 1.2, "Cao (thực vật dày)", fontsize=7, color=MUTED, ha="right")
    ly = map_top - 1.5
    lax = fig.add_axes(fr(px + 0.2, ly - 0.3, panel_w - 0.4, 0.4))
    lax.set_xlim(0, 1)
    lax.set_ylim(0, 1)
    lax.axis("off")
    lax.plot([0.0, 0.1], [0.75, 0.75], color="#374151", lw=0.6, alpha=0.8)
    lax.text(0.14, 0.75, "Ranh giới phường/xã", fontsize=7.5, va="center", color=INK)
    lax.plot([0.0, 0.1], [0.2, 0.2], color=INK, lw=1.2)
    lax.text(0.14, 0.2, "Ranh giới TP. Hồ Chí Minh", fontsize=7.5, va="center", color=INK)

    # (2) Hướng Bắc + tỷ lệ
    y2 = map_top - h1 - 0.15
    h2 = 1.35
    box(y2, h2, "HƯỚNG BẮC VÀ TỶ LỆ")
    # hướng Bắc (la bàn đơn giản)
    nx = px + 0.55
    ax_n = fig.add_axes(fr(nx - 0.4, y2 - 1.28, 0.8, 0.8))
    ax_n.set_xlim(-1, 1)
    ax_n.set_ylim(-1.25, 1.25)
    ax_n.axis("off")
    ax_n.add_patch(Polygon([(0, 1.0), (-0.38, -0.55), (0, -0.25)], closed=True, facecolor=INK, edgecolor=INK, lw=0.8))
    ax_n.add_patch(Polygon([(0, 1.0), (0.38, -0.55), (0, -0.25)], closed=True, facecolor="white", edgecolor=INK, lw=0.8))
    ax_n.text(0, 1.1, "N", ha="center", va="bottom", fontsize=12, fontweight="bold", color=INK)
    # tỷ lệ số (đúng khi in A4 ở 100%) + thước đồ họa
    width_m = (lon_max - lon_min) * 111320.0 * k
    denom = width_m / (map_w * 0.0254)
    mag = 10 ** (len(str(int(denom))) - 2)
    denom_r = int(round(denom / mag) * mag)
    sx = px + 1.35
    text(sx, y2 - 0.5, f"Tỷ lệ ≈ 1 : {denom_r:,}".replace(",", "."), fontsize=9.5, color=INK, fontweight="bold")
    text(sx, y2 - 0.72, "(đúng khi in khổ A4, tỉ lệ 100%)", fontsize=6.8, color=MUTED)
    cand = [v for v in (1, 2, 5, 10, 20, 25, 50) if v * 1000 / denom_r / 0.0254 <= 1.85] or [1]
    bar_km = max(cand)
    bar_in = bar_km * 1000 / denom_r / 0.0254
    by = y2 - 1.02
    bx_ax = fig.add_axes(fr(sx, by - 0.12, bar_in, 0.12))
    bx_ax.set_xlim(0, 1)
    bx_ax.set_ylim(0, 1)
    bx_ax.axis("off")
    bx_ax.add_patch(Rectangle((0, 0), 0.5, 1, facecolor=INK, edgecolor=INK, lw=0.7))
    bx_ax.add_patch(Rectangle((0.5, 0), 0.5, 1, facecolor="white", edgecolor=INK, lw=0.7))
    for xx, lab in ((0, "0"), (bar_in / 2, f"{bar_km / 2:g}"), (bar_in, f"{bar_km:g} km")):
        text(sx + xx, by - 0.24, lab, fontsize=7.5, color=INK, ha="center")

    # (3) Thông tin bản đồ
    y3 = y2 - h2 - 0.15
    h3 = y3 - 0.62          # hộp thông tin kéo xuống sát chân trang
    box(y3, h3, "THÔNG TIN BẢN ĐỒ")
    now_vn = datetime.now(timezone(timedelta(hours=7)))
    rows = [("Thời điểm", when_text or "–"), ("Nguồn dữ liệu", source_label or "–"),
            ("Hệ tọa độ", "WGS 84 (EPSG:4326)"), ("Số ô lưới", f"{len(d):,}".replace(",", ".") + " (lưới 500 m)"),
            ("Ngày lập", f"{now_vn:%d/%m/%Y %H:%M}")]
    yy = y3 - 0.55
    for lab, val in rows:
        text(px + 0.15, yy, lab, fontsize=7.8, color=MUTED)
        text(px + panel_w - 0.15, yy, textwrap.shorten(val, 34, placeholder="…"), fontsize=7.8, color=INK,
             ha="right", fontweight="bold")
        rect(px + 0.15, yy - 0.11, panel_w - 0.3, 0.004, facecolor="#D7E8DB", edgecolor="none")
        yy -= 0.24
    note = NOTES.get(source_kind, NOTES["ai"])
    if has_far:
        note += " Các đảo xa bờ không hiển thị trong khung bản đồ."
    wrapped = textwrap.fill("Ghi chú: " + note, 58)
    text(px + 0.15, (yy + (y3 - h3)) / 2 - 0.02, wrapped, fontsize=6.5, color=MUTED, va="center", linespacing=1.35)

    # ---------- Chân trang ----------
    text(0.5, 0.42, f"{app_short} · Dữ liệu gốc Sentinel-2 (Google Earth Engine)", fontsize=7, color=MUTED, ha="left")
    text(PAGE_W - 0.5, 0.42, "Bản đồ được lập tự động từ hệ thống", fontsize=7, color=MUTED, ha="right")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, facecolor="white")
    return buf.getvalue()


def generate_ndvi_map_sheet(df: pd.DataFrame, when_text: str = "", source_label: str = "",
                            source_kind: str = "ai", place_label: str = "TP. Hồ Chí Minh"):
    """-> bytes PNG của tờ bản đồ chuẩn, hoặc None nếu lỗi (nút tải sẽ ẩn / báo không tạo được)."""
    try:
        return render_map_sheet(df, when_text, source_label, source_kind, place_label)
    except Exception:
        import traceback
        traceback.print_exc()
        return None
