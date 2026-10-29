# utils/timeline.py
# "Xem diễn biến theo thời gian": phát lần lượt NDVI QUAN TRẮC của các tháng trong khoảng người dùng chọn.
#
# Chiến lược để không "chạy trâu":
#   1. Chỉ đọc dữ liệu quan trắc có sẵn trong CSDL (không bao giờ chạy AI), 1 truy vấn cho cả khoảng.
#   2. Tháng không đủ dữ liệu (< MIN_CELLS ô) bị bỏ qua ngầm, không báo.
#   3. Phần nặng (tam giác Delaunay, vị trí pixel, mặt nạ ranh giới) chỉ tính MỘT LẦN rồi dùng lại cho mọi tháng,
#      mỗi tháng chỉ còn phép nhân trọng số bằng numpy.
#   4. Mọi khung ảnh được gửi sang trình duyệt 1 lần, việc phát/tạm dừng/kéo thanh trượt chạy bằng JavaScript
#      trong trình duyệt nên mượt, không làm Streamlit chạy lại trang.
import base64
import io
import json
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from sqlalchemy import text
from utils.data_loader import get_db_engine, load_local_shapefile
from utils.map_utils import NDVI_STOPS, NDVI_VMIN, NDVI_VMAX, get_ndvi_cmap
from components.layout import render_section_title

MIN_CELLS = 20000          # tháng có ít hơn số ô quan trắc hợp lệ này thì bỏ qua (giống ngưỡng của app)
MAX_FRAMES = 72            # an toàn bộ nhớ: tối đa số khung (lấy các tháng gần nhất)
MAX_SIDE_PX = 360          # độ phân giải lưới nội suy mỗi khung (ảnh xuất ra gấp đôi)
GAP_FILL_K = 6             # điền ô bị mây bằng IDW từ K ô hợp lệ gần nhất
VIEW_HEIGHT = 700
DEFAULT_YEARS = (2017, 2026)


# ====================================================================================================
#  1. PHẦN CỐ ĐỊNH (tính 1 lần): lưới ô, tam giác, trọng số nội suy, mặt nạ ranh giới
# ====================================================================================================
def _make_geometry(lon, lat, ids, geom_union=None, max_side=MAX_SIDE_PX):
    """lon/lat/ids: toạ độ và mã của TẤT CẢ ô lưới (ids đã sắp xếp tăng dần)."""
    from scipy.spatial import Delaunay, cKDTree

    lon_min, lon_max = float(lon.min()), float(lon.max())
    lat_min, lat_max = float(lat.min()), float(lat.max())
    k = float(np.cos(np.radians((lat_min + lat_max) / 2.0)))
    w_m, h_m = (lon_max - lon_min) * 111000.0 * k, (lat_max - lat_min) * 111000.0
    cols = int(min(max(w_m / 10.0, 80), max_side))
    rows = int(min(max(h_m / 10.0, 80), max_side))
    mlon, mlat = np.meshgrid(np.linspace(lon_min, lon_max, cols), np.linspace(lat_min, lat_max, rows))
    G = np.column_stack([mlon.ravel(), mlat.ravel()])

    P = np.column_stack([lon, lat])
    tri = Delaunay(P)
    simp = tri.find_simplex(G)
    inside = simp >= 0
    verts = np.zeros((G.shape[0], 3), dtype=np.int64)
    wts = np.zeros((G.shape[0], 3), dtype=np.float64)
    if inside.any():
        T = tri.transform[simp[inside]]
        b = np.einsum("ijk,ik->ij", T[:, :2, :], G[inside] - T[:, 2, :])
        w = np.column_stack([b, 1.0 - b.sum(axis=1)])
        verts[inside] = tri.simplices[simp[inside]]
        wts[inside] = w
        bad = ~np.isfinite(w).all(axis=1)            # tam giác suy biến -> dùng ô gần nhất
        if bad.any():
            idx = np.where(inside)[0][bad]
            inside[idx] = False
    nearest = None
    if (~inside).any():
        nearest = cKDTree(P).query(G[~inside])[1]

    mask = np.ones(G.shape[0], dtype=bool)           # True = nằm trong ranh giới TP.HCM
    if geom_union is not None:
        try:
            try:
                from shapely import contains_xy
                mask = np.asarray(contains_xy(geom_union, G[:, 0], G[:, 1]), dtype=bool)
            except ImportError:
                from shapely.vectorized import contains
                mask = np.asarray(contains(geom_union, G[:, 0], G[:, 1]), dtype=bool)
        except Exception as e:
            print(f"⚠️ Không cắt được theo ranh giới: {e}")

    return {
        "ids": ids, "n_cells": len(ids), "rows": rows, "cols": cols,
        "bounds": [[lat_min, lon_min], [lat_max, lon_max]],
        "inside": inside, "verts": verts, "wts": wts, "nearest": nearest, "mask": mask,
        "xy_scaled": np.column_stack([lon * k, lat]),
    }


@st.cache_resource(show_spinner=False)
def _geometry():
    cells = pd.read_sql(text("SELECT grid_id, longitude::float8 AS lon, latitude::float8 AS lat "
                             "FROM public.grid_cells ORDER BY grid_id"), get_db_engine())
    cells = cells.dropna()
    geom_union = None
    try:
        gdf = load_local_shapefile()
        if gdf is not None and not gdf.empty:
            try:
                geom_union = gdf.geometry.union_all()
            except AttributeError:
                geom_union = gdf.unary_union
    except Exception as e:
        print(f"⚠️ Không đọc được ranh giới: {e}")
    return _make_geometry(cells["lon"].to_numpy(), cells["lat"].to_numpy(),
                          cells["grid_id"].to_numpy(), geom_union)


# ====================================================================================================
#  2. DỮ LIỆU: 1 truy vấn cho cả khoảng thời gian
# ====================================================================================================
@st.cache_data(ttl=600, show_spinner=False)
def get_year_bounds():
    try:
        with get_db_engine().connect() as conn:
            lo, hi = conn.execute(text("SELECT MIN(date), MAX(date) FROM public.ndvi_observed")).one()
        if lo is not None and hi is not None:
            return int(lo.year), int(hi.year), int(hi.month)
    except Exception as e:
        print(f"[TIMELINE] Không đọc được khoảng năm: {e}")
    return DEFAULT_YEARS[0], DEFAULT_YEARS[1], 12


def _load_observed(start, end) -> pd.DataFrame:
    """Chỉ lấy các tháng đủ MIN_CELLS ô; cột: date, grid_id, v."""
    q = text("""
        SELECT o.date, o.grid_id, o.ndvi_mean::float4 AS v
        FROM public.ndvi_observed o
        WHERE o.ndvi_mean IS NOT NULL AND o.date BETWEEN :s AND :e
          AND o.date IN (SELECT date FROM public.ndvi_observed
                         WHERE ndvi_mean IS NOT NULL AND date BETWEEN :s AND :e
                         GROUP BY date HAVING COUNT(ndvi_mean) >= :minc)
        ORDER BY o.date
    """)
    return pd.read_sql(q, get_db_engine(),
                       params={"s": pd.Timestamp(start).date(), "e": pd.Timestamp(end).date(), "minc": MIN_CELLS})


# ====================================================================================================
#  3. TẠO KHUNG ẢNH
# ====================================================================================================
def _fill_gaps(vals, xy_scaled):
    """Điền ô bị mây (NaN) bằng IDW từ các ô hợp lệ gần nhất để mặt nội suy liền mạch."""
    miss = np.isnan(vals)
    if not miss.any():
        return vals
    from scipy.spatial import cKDTree
    valid = ~miss
    d, i = cKDTree(xy_scaled[valid]).query(xy_scaled[miss], k=GAP_FILL_K)
    w = 1.0 / np.maximum(d, 1e-9) ** 2
    out = vals.copy()
    out[miss] = (w * vals[valid][i]).sum(axis=1) / w.sum(axis=1)
    return out


def _frame_image(geo, vals, cmap, norm) -> str:
    """vals: NDVI đã điền đủ cho mọi ô lưới -> ảnh WebP (data URI) có nền trong suốt ngoài ranh giới."""
    from scipy.ndimage import gaussian_filter
    from PIL import Image

    n = geo["rows"] * geo["cols"]
    grid = np.empty(n, dtype=np.float64)
    ins = geo["inside"]
    grid[ins] = (vals[geo["verts"][ins]] * geo["wts"][ins]).sum(axis=1)
    if geo["nearest"] is not None:
        grid[~ins] = vals[geo["nearest"]]
    grid = gaussian_filter(grid.reshape(geo["rows"], geo["cols"]), sigma=0.8)

    rgba = cmap(norm(grid))
    rgba[..., 3] = geo["mask"].reshape(geo["rows"], geo["cols"]).astype(float)
    rgba = np.flipud(rgba)
    img = Image.fromarray((rgba * 255).astype(np.uint8))
    img = img.resize((geo["cols"] * 2, geo["rows"] * 2), resample=Image.Resampling.BICUBIC)
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=82, method=4)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _frames_from_df(df: pd.DataFrame, geo) -> list:
    if df is None or df.empty:
        return []
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    months = sorted(df["date"].unique())[-MAX_FRAMES:]
    ids = geo["ids"]
    pos = np.searchsorted(ids, df["grid_id"].to_numpy())
    pos = np.clip(pos, 0, len(ids) - 1)
    ok = ids[pos] == df["grid_id"].to_numpy()
    df, pos = df[ok], pos[ok]
    cmap = get_ndvi_cmap().copy()
    import matplotlib.colors as mcolors
    norm = mcolors.Normalize(vmin=NDVI_VMIN, vmax=NDVI_VMAX)

    frames = []
    for m in months:
        sel = (df["date"] == m).to_numpy()
        vals = np.full(geo["n_cells"], np.nan, dtype=np.float64)
        vals[pos[sel]] = df["v"].to_numpy()[sel]
        mean = float(np.nanmean(vals))
        frames.append({"l": f"{pd.Timestamp(m):%m/%Y}", "m": round(mean, 3),
                       "s": _frame_image(geo, _fill_gaps(vals, geo["xy_scaled"]), cmap, norm)})
    return frames


@st.cache_data(ttl=3600, show_spinner=False, max_entries=3)
def build_frames(start: str, end: str) -> list:
    """Danh sách khung theo thời gian [{l: 'MM/YYYY', m: NDVI trung bình, s: ảnh WebP base64}] cho khoảng [start, end]."""
    return _frames_from_df(_load_observed(start, end), _geometry())


@st.cache_data(show_spinner=False)
def _boundary_json():
    """Ranh giới đơn giản hoá (nhẹ) để vẽ viền trắng nét đứt trên bản đồ phát."""
    try:
        gdf = load_local_shapefile()
        if gdf is None or gdf.empty:
            return None
        g = gdf[["geometry"]].copy()
        g["geometry"] = g.geometry.simplify(0.0003, preserve_topology=True)
        return g.to_json()
    except Exception as e:
        print(f"⚠️ Không dựng được ranh giới: {e}")
        return None


# ====================================================================================================
#  4. TRÌNH PHÁT (HTML + JavaScript chạy trong trình duyệt)
# ====================================================================================================
_HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
html,body{margin:0;height:100%;font-family:'Be Vietnam Pro','Segoe UI',Arial,sans-serif;background:transparent}
#wrap{position:relative;height:100%;border-radius:14px;overflow:hidden;border:1px solid #D7E8DB;box-shadow:0 6px 20px rgba(20,83,45,.12)}
#map{position:absolute;inset:0;background:#E9F5EC}
.card{position:absolute;z-index:1000;background:rgba(255,255,255,.95);border:1px solid #D7E8DB;border-radius:12px;box-shadow:0 2px 8px rgba(20,83,45,.15);color:#14301F}
#hud{top:12px;left:12px;padding:8px 14px;min-width:150px}
#hud b{display:block;font-size:20px;font-weight:800;color:#14532D;line-height:1.15}
#hud span{font-size:11.5px;color:#5B7A66}
#legend{right:12px;bottom:70px;padding:8px 10px;width:190px}
#legend .t{font-weight:700;font-size:11.5px;color:#15803D;margin-bottom:5px}
#legend .bar{height:10px;border-radius:3px;background:linear-gradient(to right,__GRAD__)}
#legend .tk{display:flex;justify-content:space-between;font-size:10px;color:#5B7A66;margin-top:2px}
#ctrl{left:50%;bottom:14px;transform:translateX(-50%);display:flex;align-items:center;gap:10px;padding:7px 12px;width:min(620px,calc(100% - 24px));box-sizing:border-box}
#play{width:34px;height:34px;border:none;border-radius:50%;cursor:pointer;color:#fff;font-size:13px;font-weight:700;background:linear-gradient(135deg,#16A34A,#65A30D);flex:none}
#play:hover{filter:brightness(1.08)}
#slider{flex:1;accent-color:#16A34A;cursor:pointer;min-width:60px}
#cnt{font-size:11.5px;color:#5B7A66;white-space:nowrap;min-width:44px;text-align:right}
#speed{border:1px solid #BFDCC6;border-radius:8px;padding:3px 4px;font-size:12px;color:#15803D;background:#fff}
.leaflet-container{font-family:inherit}
</style></head><body>
<div id="wrap">
  <div id="map"></div>
  <div id="hud" class="card"><b id="hm"></b><span id="hs"></span></div>
  <div id="legend" class="card"><div class="t">Chú giải chỉ số NDVI</div><div class="bar"></div>
    <div class="tk"><span>__T0__</span><span>__T1__</span><span>__T2__</span><span>__T3__</span><span>__T4__</span></div></div>
  <div id="ctrl" class="card">
    <button id="play" title="Phát / tạm dừng">❚❚</button>
    <input id="slider" type="range" min="0" value="0" step="1">
    <span id="cnt"></span>
    <select id="speed" title="Tốc độ"><option value="1400">0.5×</option><option value="700" selected>1×</option><option value="350">2×</option></select>
  </div>
</div>
<script>
const FRAMES = __FRAMES__;
const BOUNDS = __BOUNDS__;
const BOUNDARY = __BOUNDARY__;
const BASE = __BASE__;
const SRC = __SRC__;
const N = FRAMES.length;
const map = L.map('map', {zoomControl:false});
L.control.zoom({position:'topright'}).addTo(map);
(BASE === 'google'
  ? L.tileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {maxZoom:20, attribution:'Google'})
  : L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {maxZoom:19, attribution:'Esri'})
).addTo(map);
map.fitBounds(BOUNDS);
const OP = 0.9;
const overlays = FRAMES.map((f, i) => L.imageOverlay(f.s, BOUNDS, {opacity: i === 0 ? OP : 0, interactive:false}).addTo(map));
if (BOUNDARY) L.geoJSON(BOUNDARY, {style:{color:'#fff', weight:1.2, dashArray:'4 4', fill:false, opacity:.9}, interactive:false}).addTo(map);

const slider = document.getElementById('slider'), btn = document.getElementById('play'), speed = document.getElementById('speed');
const hm = document.getElementById('hm'), hs = document.getElementById('hs'), cnt = document.getElementById('cnt');
slider.max = Math.max(N - 1, 0);
let cur = 0, timer = null;

function show(i) {
  overlays[cur].setOpacity(0);
  cur = i;
  overlays[cur].setOpacity(OP);
  slider.value = i;
  hm.textContent = 'Tháng ' + FRAMES[i].l;
  hs.textContent = SRC + ' · NDVI TB ' + FRAMES[i].m.toFixed(3);
  cnt.textContent = (i + 1) + '/' + N;
}
function stop() { if (timer) { clearInterval(timer); timer = null; } btn.textContent = '▶'; }
function play() {
  if (N < 2) return;
  if (timer) clearInterval(timer);
  timer = setInterval(() => show((cur + 1) % N), parseInt(speed.value, 10));
  btn.textContent = '❚❚';
}
btn.addEventListener('click', () => timer ? stop() : play());
speed.addEventListener('change', () => { if (timer) play(); });
slider.addEventListener('input', () => { stop(); show(parseInt(slider.value, 10)); });
show(0);
if (N < 2) { slider.disabled = true; btn.style.display = 'none'; } else { play(); }
</script></body></html>"""


def _build_html(frames: list, basemap_choice: str, show_boundaries: bool, bounds: list) -> str:
    span = NDVI_VMAX - NDVI_VMIN
    grad = ", ".join(f"{c} {(v - NDVI_VMIN) / span * 100:.0f}%" for v, c in NDVI_STOPS)
    ticks = [f"{NDVI_VMIN + span * k / 4:g}" for k in range(5)]
    boundary = _boundary_json() if show_boundaries else None

    def js(obj):
        return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")

    html = (_HTML.replace("__GRAD__", grad)
            .replace("__FRAMES__", js(frames)).replace("__BOUNDS__", js(bounds))
            .replace("__BOUNDARY__", boundary.replace("</", "<\\/") if boundary else "null")
            .replace("__BASE__", js("google" if basemap_choice == "Google Hybrid" else "esri"))
            .replace("__SRC__", js("Quan trắc vệ tinh")))
    for k, t in enumerate(ticks):
        html = html.replace(f"__T{k}__", t)
    return html


# ====================================================================================================
#  5. GIAO DIỆN: ô điều khiển ở thanh bên + màn hình phát
# ====================================================================================================
def _open_timeline():
    s = pd.Timestamp(int(st.session_state["tl_sy"]), int(st.session_state["tl_sm"]), 1)
    e = pd.Timestamp(int(st.session_state["tl_ey"]), int(st.session_state["tl_em"]), 1)
    if s > e:
        s, e = e, s
    st.session_state["timeline_range"] = (s, e)
    st.session_state["view_mode"] = "timeline"


def render_timeline_controls():
    """Gọi trong `with st.sidebar:` của render_sidebar: 2 ô bắt đầu, 2 ô kết thúc và nút Xem."""
    y_lo, y_hi, m_hi = get_year_bounds()
    years = list(range(y_lo, y_hi + 1))
    with st.expander("🎞️ Diễn biến theo thời gian", expanded=False):
        c1, c2 = st.columns(2)
        c1.selectbox("Từ tháng:", list(range(1, 13)), index=0, key="tl_sm")
        c2.selectbox("Năm:", years, index=max(len(years) - 3, 0), key="tl_sy")
        c3, c4 = st.columns(2)
        c3.selectbox("Đến tháng:", list(range(1, 13)), index=m_hi - 1, key="tl_em")
        c4.selectbox("Năm:", years, index=len(years) - 1, key="tl_ey")
        st.button("▶️ Xem", use_container_width=True, key="btn_open_timeline", on_click=_open_timeline,
                  help="Phát lần lượt NDVI quan trắc của các tháng trong khoảng đã chọn")


def render_timeline_view(basemap_choice: str, show_boundaries: bool):
    render_section_title(
        title="🎞️ Diễn biến NDVI theo thời gian",
        subtitle="Phát lần lượt bản đồ NDVI quan trắc của các tháng trong khoảng đã chọn.",
        source="db",
    )
    if st.button("← Quay lại bản đồ", key="btn_back_from_timeline"):
        st.session_state["view_mode"] = "map"
        st.rerun()

    rng = st.session_state.get("timeline_range")
    if not rng:
        st.markdown("<div class='empty-hint'>Chọn khoảng thời gian ở mục <b>Diễn biến theo thời gian</b> "
                    "bên thanh trái rồi nhấn <b>Xem</b>.</div>", unsafe_allow_html=True)
        return
    try:
        with st.spinner("Đang chuẩn bị hoạt cảnh..."):
            frames = build_frames(str(rng[0].date()), str(rng[1].date()))
            bounds = _geometry()["bounds"]
    except Exception as e:
        st.error(f"❌ Không tạo được hoạt cảnh: {e}")
        return
    if not frames:
        st.caption("Không có dữ liệu quan trắc trong khoảng đã chọn.")
        return
    components.html(_build_html(frames, basemap_choice, show_boundaries, bounds),
                    height=VIEW_HEIGHT, scrolling=False)
