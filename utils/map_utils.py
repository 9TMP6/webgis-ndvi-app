import io
import base64
import numpy as np
import pandas as pd
import matplotlib.colors as mcolors
from PIL import Image
import folium
from folium.raster_layers import ImageOverlay

NDVI_PALETTE_MODE = "gee"      # "gee" = thang màu chuẩn | "arcgis" = thang cũ

if NDVI_PALETTE_MODE == "gee":
    NDVI_VMIN, NDVI_VMAX = -0.2, 1.0 #0.0 0.8
    _PALETTE = ["#FF0000", "#FF7F00", "#FFFF00", "#ADFF2F", "#00FF00", "#00FFFF", "#007FFF", "#0000FF"]
    NDVI_STOPS = [(NDVI_VMIN + i * (NDVI_VMAX - NDVI_VMIN) / (len(_PALETTE) - 1), c)
                  for i, c in enumerate(_PALETTE)]
else:
    NDVI_VMIN, NDVI_VMAX = -0.10, 0.70
    NDVI_STOPS = [
        (-0.10, "#2b83ba"), (0.00, "#2b83ba"), (0.04, "#a50026"), (0.10, "#d73027"),
        (0.18, "#e8472f"), (0.24, "#ef6a38"), (0.30, "#f78e3e"), (0.37, "#fee08b"),
        (0.42, "#d9ef8b"), (0.48, "#91cf60"), (0.57, "#1a9850"), (0.70, "#006837"),
    ]

def get_ndvi_cmap():
    return mcolors.LinearSegmentedColormap.from_list(
        "NDVI_HCM", [((v - NDVI_VMIN) / (NDVI_VMAX - NDVI_VMIN), c) for v, c in NDVI_STOPS]
    )


def generate_ndvi_raster(df: pd.DataFrame, target_res_meters: int = 10):
    """
    Tạo ảnh NDVI mịn màng, dải màu chuyển tiếp mượt như ArcGIS bằng Gaussian Filter & Bicubic Resampling 🎨
    """
    try:
        from scipy.interpolate import griddata
        from scipy.ndimage import gaussian_filter
    except ImportError:
        print("⚠️ Thiếu thư viện scipy.")
        return None, None

    if df is None or df.empty:
        return None, None

    # Lọc bỏ dòng khuyết tọa độ hoặc giá trị NDVI
    df_clean = df.dropna(subset=['longitude', 'latitude', 'ndvi_mean'])
    if df_clean.empty:
        return None, None

    lons = df_clean['longitude'].values
    lats = df_clean['latitude'].values
    ndvis = df_clean['ndvi_mean'].values

    lon_min, lon_max = float(lons.min()), float(lons.max())
    lat_min, lat_max = float(lats.min()), float(lats.max())

    if lon_min == lon_max or lat_min == lat_max:
        return None, None

    # 1. Tính toán kích thước lưới Pixel
    lat_center = (lat_min + lat_max) / 2.0
    meters_per_deg_lat = 111000.0
    meters_per_deg_lon = 111000.0 * np.cos(np.radians(lat_center))

    width_meters = (lon_max - lon_min) * meters_per_deg_lon
    height_meters = (lat_max - lat_min) * meters_per_deg_lat

    grid_cols = int(max(width_meters / target_res_meters, 80))
    grid_rows = int(max(height_meters / target_res_meters, 80))

    # Giới hạn kích thước lưới an toàn RAM cho Streamlit Cloud
    grid_cols = min(grid_cols, 450)
    grid_rows = min(grid_rows, 450)

    grid_lon = np.linspace(lon_min, lon_max, grid_cols)
    grid_lat = np.linspace(lat_min, lat_max, grid_rows)
    grid_lon_mesh, grid_lat_mesh = np.meshgrid(grid_lon, grid_lat)

    # 2. Nội suy 'linear' tạo dải màu liên tục mượt mà
    grid_ndvi = griddata((lons, lats), ndvis, (grid_lon_mesh, grid_lat_mesh), method='linear')

    # Xử lý các ô biên bị NaN bằng 'nearest'
    if np.isnan(grid_ndvi).any():
        grid_ndvi_fill = griddata((lons, lats), ndvis, (grid_lon_mesh, grid_lat_mesh), method='nearest')
        grid_ndvi = np.where(np.isnan(grid_ndvi), grid_ndvi_fill, grid_ndvi)

    # 3. làm mịn dải ranh giới màu (sigma = 0.8 để tránh làm biến dạng dải NDVI thực)
    grid_ndvi_smooth = gaussian_filter(grid_ndvi, sigma=0.8)

    # 4. 🎨 BẢNG MÀU CONTINUOUS DẠNG ARCGIS/QGIS CHUẨN VIỄN THÁM
    # Nước (-1.0 -> 0.0): Xanh dương
    # Đô thị (0.0 -> 0.18): Đỏ / Cam đậm
    # Đất trống/Cỏ thưa (0.18 -> 0.28): Vàng / Nâu
    # Nông nghiệp/Cây xanh trung bình (0.28 -> 0.45): Xanh lá mạ / Xanh lá nhạt
    # Rừng/Cây xanh rậm rạp (> 0.45): Xanh lá đậm
    
    # cdict = {
    #     'red':   ((0.0, 0.17, 0.17),  # Nước (Blue)
    #               (0.2, 0.84, 0.84),  # Đô thị (Red)
    #               (0.35, 0.99, 0.99), # Đất trống (Orange)
    #               (0.5, 0.65, 0.65),  # Thực vật nhẹ (Light Green)
    #               (0.7, 0.10, 0.10),  # Thực vật đậm (Green)
    #               (1.0, 0.00, 0.00)), # Rừng rậm (Dark Green)

    #     'green': ((0.0, 0.51, 0.51),
    #               (0.2, 0.10, 0.10),
    #               (0.35, 0.68, 0.68),
    #               (0.5, 0.85, 0.85),
    #               (0.7, 0.59, 0.59),
    #               (1.0, 0.41, 0.41)),

    #     'blue':  ((0.0, 0.73, 0.73),
    #               (0.2, 0.11, 0.11),
    #               (0.35, 0.38, 0.38),
    #               (0.5, 0.41, 0.41),
    #               (0.7, 0.31, 0.31),
    #               (1.0, 0.22, 0.22))
    # }
    
    # cmap = mcolors.LinearSegmentedColormap('ArcGIS_NDVI', cdict)
    # norm = mcolors.Normalize(vmin=-0.1, vmax=0.65)

    cmap = get_ndvi_cmap()
    norm = mcolors.Normalize(vmin=NDVI_VMIN, vmax=NDVI_VMAX)

    rgba_img = cmap(norm(grid_ndvi_smooth))

    # Giữ nguyên độ hiển thị cho tất cả các vùng (Bao gồm Nước & Đô thị bê tông) 🏢🌊
    alpha_channel = np.ones_like(grid_ndvi_smooth) * 1.0 #0.85

    try:
        from utils.data_loader import load_local_shapefile
        gdf_shape = load_local_shapefile()
        if gdf_shape is not None and not gdf_shape.empty:
            if gdf_shape.crs and str(gdf_shape.crs).upper() != "EPSG:4326":
                gdf_shape = gdf_shape.to_crs(epsg=4326)
            
            geom_union = gdf_shape.unary_union

            try:
                from shapely import contains_xy
                inside_mask = contains_xy(geom_union, grid_lon_mesh.ravel(), grid_lat_mesh.ravel()).reshape(grid_lon_mesh.shape)
            except ImportError:
                from shapely.vectorized import contains
                inside_mask = contains(geom_union, grid_lon_mesh, grid_lat_mesh)

            # Chỉ làm trong suốt vùng nằm ngoài ranh giới TP.HCM 🗺️
            alpha_channel[~inside_mask] = 0.0
    except Exception as e:
        print(f"⚠️ Không thể cắt theo GeoJSON: {e}")

    rgba_img[..., 3] = alpha_channel

    # Đảo trục Y cho đúng tọa độ GIS
    rgba_img = np.flipud(rgba_img)

    # 5. Khử răng cưa hình ảnh với Bicubic Resampling (Phóng x2 kích thước mịn căng)
    img_uint8 = (rgba_img * 255).astype(np.uint8)
    img = Image.fromarray(img_uint8)
    img = img.resize((grid_cols * 2, grid_rows * 2), resample=Image.Resampling.BICUBIC)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    img_base64 = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode('utf-8')
    bounds = [[lat_min, lon_min], [lat_max, lon_max]]

    return img_base64, bounds



def build_folium_map(df: pd.DataFrame, selected_date: str):
    """
    Dựng bản đồ Folium tích hợp lớp phủ ImageOverlay an toàn
    """
    m = folium.Map(
        location=[10.7769, 106.7009],
        zoom_start=11,
        tiles="OpenStreetMap"
    )

    if df is not None and not df.empty:
        img_base64, bounds = generate_ndvi_raster(df)

        if img_base64 and bounds:
            ImageOverlay(
                image=img_base64,
                bounds=bounds,
                opacity=0.85, # Độ rõ màu hoàn hảo
                name=f"Lớp phủ NDVI ({selected_date})",
                interactive=True
            ).add_to(m)

            folium.LayerControl().add_to(m)

    return m

# ======================================================================
#  XUẤT ẢNH BẢN ĐỒ (PNG) - chỉ chạy khi người dùng bấm "Xuất ảnh NDVI (.PNG)"
#  Không dùng chung với bản đồ web (generate_ndvi_raster / build_folium_map giữ nguyên)
# ======================================================================
def _export_boundaries():
    """-> (gdf ranh giới WGS84, hình hợp nhất) hoặc (None, None) nếu không tải được."""
    try:
        from utils.data_loader import load_local_shapefile
        gdf = load_local_shapefile()
        if gdf is None or gdf.empty:
            return None, None
        if gdf.crs and str(gdf.crs).upper() != "EPSG:4326":
            gdf = gdf.to_crs(epsg=4326)
        geom = gdf.union_all() if hasattr(gdf, "union_all") else gdf.unary_union
        return gdf, geom
    except Exception as e:
        print(f"⚠️ Xuất ảnh: không đọc được ranh giới: {e}")
        return None, None


def _line_segments(geom):
    """Gom mọi đường viền của 1 hình (Polygon/MultiPolygon/Line...) thành list mảng toạ độ [n,2]."""
    out = []

    def walk(g):
        t = g.geom_type
        if t in ("LineString", "LinearRing"):
            out.append(np.asarray(g.coords)[:, :2])
        elif t == "Polygon":
            walk(g.exterior)
            for r in g.interiors:
                walk(r)
        elif hasattr(g, "geoms"):
            for s in g.geoms:
                walk(s)

    if geom is not None:
        walk(geom)
    return out


def _split_main_and_far(lons, lats, cell_deg=0.05, bridge_cells=6):
    """
    Tách các điểm thành "đất liền" (cụm lớn nhất) và "xa bờ" (các cụm tách rời, vd. Côn Đảo).
    Lý do: chỉ 1 cụm đảo ở rất xa cũng làm khung ảnh dài gấp đôi -> bản đồ bị đẩy lên góc trên.
    -> (mask_main, mask_far_largest)  (2 mảng bool theo thứ tự điểm)
    """
    from scipy.ndimage import label, binary_dilation

    ix = ((lons - lons.min()) / cell_deg).astype(int)
    iy = ((lats - lats.min()) / cell_deg).astype(int)
    occ = np.zeros((iy.max() + 1, ix.max() + 1), dtype=bool)
    occ[iy, ix] = True
    bridged = binary_dilation(occ, structure=np.ones((3, 3), bool), iterations=max(bridge_cells // 2, 1))
    lab, n = label(bridged, structure=np.ones((3, 3), int))
    pt_lab = lab[iy, ix]
    counts = np.bincount(pt_lab, minlength=n + 1)
    counts[0] = 0
    main_lab = int(counts.argmax())
    mask_main = pt_lab == main_lab
    counts[main_lab] = 0
    if counts.max() >= 5:                      # cụm xa bờ phải có >= 5 ô mới đáng vẽ khung phụ
        mask_far = pt_lab == int(counts.argmax())
    else:
        mask_far = np.zeros_like(mask_main)
    return mask_main, mask_far


def _export_interpolate(lons, lats, vals, geom, max_side):
    """
    Nội suy giống bản đồ web (linear -> nearest bù biên -> Gaussian), cắt theo ranh giới,
    rồi CẮT KHUNG sát phần có dữ liệu (không còn khoảng trắng).
    -> (masked_grid[rows, cols] hàng 0 = phía Nam, (lon_min, lon_max, lat_min, lat_max)) hoặc None
    """
    from scipy.interpolate import griddata
    from scipy.ndimage import gaussian_filter
    from scipy.spatial import cKDTree

    if len(vals) < 4:
        return None
    padx = 0.01 + 0.02 * float(np.ptp(lons))
    pady = 0.01 + 0.02 * float(np.ptp(lats))
    lon_min, lon_max = float(lons.min()) - padx, float(lons.max()) + padx
    lat_min, lat_max = float(lats.min()) - pady, float(lats.max()) + pady

    k = np.cos(np.radians((lat_min + lat_max) / 2.0))
    w_eff, h_deg = (lon_max - lon_min) * k, (lat_max - lat_min)
    if w_eff >= h_deg:
        cols, rows = max_side, max(int(round(max_side * h_deg / w_eff)), 40)
    else:
        rows, cols = max_side, max(int(round(max_side * w_eff / h_deg)), 40)
    dx, dy = (lon_max - lon_min) / cols, (lat_max - lat_min) / rows
    gx = lon_min + (np.arange(cols) + 0.5) * dx          # tâm ô ảnh
    gy = lat_min + (np.arange(rows) + 0.5) * dy
    X, Y = np.meshgrid(gx, gy)

    grid = griddata((lons, lats), vals, (X, Y), method="linear")
    if np.isnan(grid).any():
        fill = griddata((lons, lats), vals, (X, Y), method="nearest")
        grid = np.where(np.isnan(grid), fill, grid)
    grid = gaussian_filter(grid, sigma=1.2)

    inside = None
    if geom is not None:
        try:
            try:
                from shapely import contains_xy
                inside = contains_xy(geom, X.ravel(), Y.ravel()).reshape(X.shape)
            except (ImportError, AttributeError):
                from shapely.vectorized import contains
                inside = contains(geom, X, Y)
        except Exception as e:
            print(f"⚠️ Xuất ảnh: không cắt được theo ranh giới ({e}), dùng khoảng cách tới ô dữ liệu.")
            inside = None
    if inside is None or not inside.any():
        pts = np.column_stack([lons * k, lats])
        tree = cKDTree(pts)
        thr = 2.5 * float(np.median(tree.query(pts, k=2)[0][:, 1]))
        d_nn = tree.query(np.column_stack([X.ravel() * k, Y.ravel()]))[0].reshape(X.shape)
        inside = d_nn <= thr

    r_idx, c_idx = np.where(inside.any(axis=1))[0], np.where(inside.any(axis=0))[0]
    if len(r_idx) == 0 or len(c_idx) == 0:
        return None
    r0, r1, c0, c1 = r_idx[0], r_idx[-1], c_idx[0], c_idx[-1]
    grid = np.ma.masked_where(~inside, grid)[r0:r1 + 1, c0:c1 + 1]
    extent = (lon_min + c0 * dx, lon_min + (c1 + 1) * dx, lat_min + r0 * dy, lat_min + (r1 + 1) * dy)
    return grid, extent


def _render_export_map(df: pd.DataFrame, date_label: str, place_label: str):
    import traceback  # noqa: F401
    from datetime import datetime, timedelta, timezone
    from matplotlib.figure import Figure
    from matplotlib.collections import LineCollection
    from matplotlib.patches import Rectangle
    from matplotlib.cm import ScalarMappable
    from matplotlib.ticker import FuncFormatter, MaxNLocator

    if df is None or df.empty:
        return None
    d = df.dropna(subset=["longitude", "latitude", "ndvi_mean"])
    if d.empty:
        return None
    lons = d["longitude"].to_numpy(float)
    lats = d["latitude"].to_numpy(float)
    vals = d["ndvi_mean"].to_numpy(float)

    gdf, geom = _export_boundaries()
    inner_segs = []
    if gdf is not None:
        for g in gdf.geometry:
            inner_segs += _line_segments(g)
    outer_segs = _line_segments(geom)

    # ---- tách đất liền / đảo xa bờ, nội suy từng phần ----
    m_main, m_far = _split_main_and_far(lons, lats)
    main = _export_interpolate(lons[m_main], lats[m_main], vals[m_main], geom, 800)
    if main is None:
        return None
    grid, ext = main
    inset = None
    if m_far.any():
        inset = _export_interpolate(lons[m_far], lats[m_far], vals[m_far], geom, 300)

    cmap = get_ndvi_cmap().copy()                 # CÙNG bảng màu + thang với bản đồ web
    cmap.set_bad((0, 0, 0, 0))
    norm = mcolors.Normalize(vmin=NDVI_VMIN, vmax=NDVI_VMAX)

    # ---- bố cục (đơn vị inch) ----
    lon_min, lon_max, lat_min, lat_max = ext
    k = np.cos(np.radians((lat_min + lat_max) / 2.0))
    w_eff, h_deg = (lon_max - lon_min) * k, (lat_max - lat_min)
    scale = min(8.2 / w_eff, 8.0 / h_deg)
    map_w, map_h = w_eff * scale, h_deg * scale

    left, side_w, gap, right_pad = 1.0, 3.0, 0.4, 0.3
    bottom, top_h, top_gap = 0.95, 1.1, 0.2
    in_w = in_h = 0.0
    if inset is not None:
        _, iext = inset
        i_k = np.cos(np.radians((iext[2] + iext[3]) / 2.0))
        i_w_eff, i_h_deg = (iext[1] - iext[0]) * i_k, (iext[3] - iext[2])
        in_h = min(side_w * i_h_deg / i_w_eff, 2.3)
        in_w = in_h * i_w_eff / i_h_deg
    panel_h = 3.2 + (in_h + 0.35 if inset is not None else 0.0)
    body_h = max(map_h, panel_h)

    fig_w = left + map_w + gap + side_w + right_pad
    fig_h = bottom + body_h + top_h + top_gap
    fig = Figure(figsize=(fig_w, fig_h), dpi=150, facecolor="white")

    def fr(x, y, w, h):
        return [x / fig_w, y / fig_h, w / fig_w, h / fig_h]

    # ---- tiêu đề ----
    fig.add_artist(Rectangle((0, (fig_h - top_h) / fig_h), 1, top_h / fig_h,
                             transform=fig.transFigure, facecolor="#15803D", edgecolor="none"))
    fig.text(0.4 / fig_w, (fig_h - 0.42) / fig_h, "BẢN ĐỒ CHỈ SỐ THỰC VẬT NDVI",
             color="white", fontsize=18, fontweight="bold", va="center")
    sub = f"{place_label}  ·  Tháng {date_label}" if date_label else place_label
    fig.text(0.4 / fig_w, (fig_h - 0.82) / fig_h, sub, color="#DCFCE7", fontsize=11.5, va="center")
    fig.text((fig_w - 0.3) / fig_w, (fig_h - 0.42) / fig_h, "GEO-NDVI Intelligence Platform",
             color="#DCFCE7", fontsize=9, ha="right", va="center")

    # ---- bản đồ chính ----
    map_bottom = fig_h - top_h - top_gap - map_h
    ax = fig.add_axes(fr(left, map_bottom, map_w, map_h), facecolor="#F1F5F3")
    ax.imshow(grid, cmap=cmap, norm=norm, origin="lower", extent=ext,
              interpolation="bilinear", aspect="auto", zorder=1)
    if inner_segs:
        ax.add_collection(LineCollection(inner_segs, colors="white", linewidths=0.35, alpha=0.85, zorder=2))
    if outer_segs:
        ax.add_collection(LineCollection(outer_segs, colors="#111827", linewidths=0.9, zorder=3))
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.xaxis.set_major_locator(MaxNLocator(6))
    ax.yaxis.set_major_locator(MaxNLocator(7))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{abs(v):.2f}°{'E' if v >= 0 else 'W'}"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{abs(v):.2f}°{'N' if v >= 0 else 'S'}"))
    ax.tick_params(labelsize=8, colors="#374151")
    ax.set_axisbelow(False)
    ax.grid(True, color="#6B7280", alpha=0.35, linestyle=":", linewidth=0.6)
    for sp in ax.spines.values():
        sp.set_edgecolor("#374151")
        sp.set_linewidth(1.0)

    # mũi tên Bắc
    ax.annotate("", xy=(0.93, 0.95), xytext=(0.93, 0.86), xycoords="axes fraction", textcoords="axes fraction",
                arrowprops=dict(arrowstyle="-|>", color="#111827", lw=1.8), zorder=6)
    ax.text(0.93, 0.965, "N", transform=ax.transAxes, ha="center", va="bottom",
            fontsize=12, fontweight="bold", color="#111827", zorder=6)

    # thanh tỉ lệ
    width_km = (lon_max - lon_min) * 111.32 * k
    bar_km = max([v for v in (1, 2, 5, 10, 20, 25, 50, 100) if v <= 0.25 * width_km] or [1])
    bar_deg = bar_km / (111.32 * k)
    lon_span, lat_span = lon_max - lon_min, lat_max - lat_min
    x0, y0, hb = lon_min + 0.04 * lon_span, lat_min + 0.06 * lat_span, 0.010 * lat_span
    ax.add_patch(Rectangle((x0 - 0.012 * lon_span, y0 - 0.04 * lat_span), bar_deg + 0.024 * lon_span,
                           0.07 * lat_span, facecolor="white", alpha=0.8, edgecolor="none", zorder=5))
    ax.add_patch(Rectangle((x0, y0), bar_deg / 2, hb, facecolor="#111827", edgecolor="#111827", lw=0.6, zorder=6))
    ax.add_patch(Rectangle((x0 + bar_deg / 2, y0), bar_deg / 2, hb, facecolor="white", edgecolor="#111827", lw=0.6, zorder=6))
    for xx, lab in ((x0, "0"), (x0 + bar_deg / 2, f"{bar_km / 2:g}"), (x0 + bar_deg, f"{bar_km:g} km")):
        ax.text(xx, y0 - 0.008 * lat_span, lab, ha="center", va="top", fontsize=7.5, color="#111827", zorder=6)

    # ---- khung bên phải: chú giải, thống kê, khung phụ ----
    sx = left + map_w + gap
    top_y = fig_h - top_h - top_gap
    fig.text(sx / fig_w, (top_y - 0.05) / fig_h, "CHÚ GIẢI NDVI", fontsize=10, fontweight="bold",
             color="#15803D", va="top")
    cax = fig.add_axes(fr(sx, top_y - 0.72, side_w, 0.2))
    cb = fig.colorbar(ScalarMappable(norm=norm, cmap=get_ndvi_cmap()), cax=cax, orientation="horizontal")
    cb.set_ticks(np.linspace(NDVI_VMIN, NDVI_VMAX, 5))
    cb.ax.tick_params(labelsize=8, colors="#374151")
    cb.outline.set_edgecolor("#9CA3AF")
    fig.text(sx / fig_w, (top_y - 1.07) / fig_h, "Thấp (đất trống, đô thị)", fontsize=6.8, color="#3F5B49", va="top")
    fig.text((sx + side_w) / fig_w, (top_y - 1.07) / fig_h, "Cao (thực vật dày)", fontsize=6.8,
             color="#3F5B49", va="top", ha="right")

    mean_v = float(d["ndvi_mean"].mean())
    max_v = float(d["ndvi_max"].max()) if "ndvi_max" in d.columns else float(d["ndvi_mean"].max())
    min_v = float(d["ndvi_min"].min()) if "ndvi_min" in d.columns else float(d["ndvi_mean"].min())
    veg_pct = int((d["ndvi_mean"] >= 0.3).sum() / len(d) * 100)
    fig.text(sx / fig_w, (top_y - 1.5) / fig_h, "THỐNG KÊ VÙNG", fontsize=10, fontweight="bold",
             color="#15803D", va="top")
    fig.text(sx / fig_w, (top_y - 1.78) / fig_h,
             f"NDVI trung bình:  {mean_v:.3f}\nNDVI lớn nhất:  {max_v:.3f}\nNDVI nhỏ nhất:  {min_v:.3f}\n"
             f"Độ phủ thực vật:  {veg_pct} %  (NDVI ≥ 0.3)\nSố ô lưới:  {len(d):,}",
             fontsize=8.5, color="#14301F", va="top", linespacing=1.7,
             bbox=dict(boxstyle="round,pad=0.55", facecolor="#F0FDF4", edgecolor="#D7E8DB"))

    if inset is not None:
        igrid, iext = inset
        fig.text(sx / fig_w, (top_y - 3.2) / fig_h, "KHU VỰC ĐẢO XA BỜ (CÔN ĐẢO)", fontsize=8.5,
                 fontweight="bold", color="#15803D", va="top")
        iax = fig.add_axes(fr(sx, top_y - 3.45 - in_h, in_w, in_h), facecolor="#F1F5F3")
        iax.imshow(igrid, cmap=cmap, norm=norm, origin="lower", extent=iext,
                   interpolation="bilinear", aspect="auto", zorder=1)
        if inner_segs:
            iax.add_collection(LineCollection(inner_segs, colors="white", linewidths=0.35, alpha=0.85, zorder=2))
        if outer_segs:
            iax.add_collection(LineCollection(outer_segs, colors="#111827", linewidths=0.8, zorder=3))
        iax.set_xlim(iext[0], iext[1])
        iax.set_ylim(iext[2], iext[3])
        iax.set_xticks([])
        iax.set_yticks([])
        for sp in iax.spines.values():
            sp.set_edgecolor("#374151")
        iax.text(0.5, -0.04, f"{abs((iext[2] + iext[3]) / 2):.2f}°N, {abs((iext[0] + iext[1]) / 2):.2f}°E",
                 transform=iax.transAxes, ha="center", va="top", fontsize=7, color="#374151")

    # ---- chân trang ----
    now_vn = datetime.now(timezone(timedelta(hours=7)))
    fig.text(0.4 / fig_w, 0.30 / fig_h,
             "Nguồn dữ liệu: Sentinel-2 (Google Earth Engine) & mô hình dự báo AI   ·   Hệ tọa độ: WGS 84 (EPSG:4326)",
             fontsize=7.5, color="#5B7A66", va="center")
    fig.text((fig_w - 0.3) / fig_w, 0.30 / fig_h, f"Xuất ngày {now_vn:%d/%m/%Y %H:%M}",
             fontsize=7.5, color="#5B7A66", va="center", ha="right")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, facecolor="white")
    return buf.getvalue()


def generate_ndvi_raster_for_export(df: pd.DataFrame, target_res_meters: int = 10,
                                    date_label: str = "", place_label: str = "TP. Hồ Chí Minh"):
    """
    Xuất ảnh PNG dạng BẢN ĐỒ: tiêu đề, lưới toạ độ, chú giải, thống kê, mũi tên Bắc, thanh tỉ lệ.
    - Dùng đúng bảng màu / thang NDVI của bản đồ web (get_ndvi_cmap, NDVI_VMIN, NDVI_VMAX).
    - Tự bỏ khoảng trắng; đảo xa bờ (Côn Đảo) được tách ra khung phụ thay vì kéo dãn khung ảnh.
    - Trả về bytes PNG, hoặc None nếu lỗi (sidebar sẽ dùng ảnh mặc định).
    target_res_meters giữ lại cho tương thích chữ ký cũ, không còn dùng.
    """
    try:
        return _render_export_map(df, date_label, place_label)
    except Exception:
        import traceback
        traceback.print_exc()
        return None



# import io
# import base64
# import numpy as np
# import pandas as pd
# import matplotlib.colors as mcolors
# from PIL import Image
# import folium
# from folium.raster_layers import ImageOverlay

# NDVI_PALETTE_MODE = "gee"      # "gee" = thang màu chuẩn | "arcgis" = thang cũ

# if NDVI_PALETTE_MODE == "gee":
#     NDVI_VMIN, NDVI_VMAX = -0.2, 1.0 #0.0 0.8
#     _PALETTE = ["#FF0000", "#FF7F00", "#FFFF00", "#ADFF2F", "#00FF00", "#00FFFF", "#007FFF", "#0000FF"]
#     NDVI_STOPS = [(NDVI_VMIN + i * (NDVI_VMAX - NDVI_VMIN) / (len(_PALETTE) - 1), c)
#                   for i, c in enumerate(_PALETTE)]
# else:
#     NDVI_VMIN, NDVI_VMAX = -0.10, 0.70
#     NDVI_STOPS = [
#         (-0.10, "#2b83ba"), (0.00, "#2b83ba"), (0.04, "#a50026"), (0.10, "#d73027"),
#         (0.18, "#e8472f"), (0.24, "#ef6a38"), (0.30, "#f78e3e"), (0.37, "#fee08b"),
#         (0.42, "#d9ef8b"), (0.48, "#91cf60"), (0.57, "#1a9850"), (0.70, "#006837"),
#     ]

# def get_ndvi_cmap():
#     return mcolors.LinearSegmentedColormap.from_list(
#         "NDVI_HCM", [((v - NDVI_VMIN) / (NDVI_VMAX - NDVI_VMIN), c) for v, c in NDVI_STOPS]
#     )


# def generate_ndvi_raster(df: pd.DataFrame, target_res_meters: int = 10):
#     """
#     Tạo ảnh NDVI mịn màng, dải màu chuyển tiếp mượt như ArcGIS bằng Gaussian Filter & Bicubic Resampling 🎨
#     """
#     try:
#         from scipy.interpolate import griddata
#         from scipy.ndimage import gaussian_filter
#     except ImportError:
#         print("⚠️ Thiếu thư viện scipy.")
#         return None, None

#     if df is None or df.empty:
#         return None, None

#     # Lọc bỏ dòng khuyết tọa độ hoặc giá trị NDVI
#     df_clean = df.dropna(subset=['longitude', 'latitude', 'ndvi_mean'])
#     if df_clean.empty:
#         return None, None

#     lons = df_clean['longitude'].values
#     lats = df_clean['latitude'].values
#     ndvis = df_clean['ndvi_mean'].values

#     lon_min, lon_max = float(lons.min()), float(lons.max())
#     lat_min, lat_max = float(lats.min()), float(lats.max())

#     if lon_min == lon_max or lat_min == lat_max:
#         return None, None

#     # 1. Tính toán kích thước lưới Pixel
#     lat_center = (lat_min + lat_max) / 2.0
#     meters_per_deg_lat = 111000.0
#     meters_per_deg_lon = 111000.0 * np.cos(np.radians(lat_center))

#     width_meters = (lon_max - lon_min) * meters_per_deg_lon
#     height_meters = (lat_max - lat_min) * meters_per_deg_lat

#     grid_cols = int(max(width_meters / target_res_meters, 80))
#     grid_rows = int(max(height_meters / target_res_meters, 80))

#     # Giới hạn kích thước lưới an toàn RAM cho Streamlit Cloud
#     grid_cols = min(grid_cols, 450)
#     grid_rows = min(grid_rows, 450)

#     grid_lon = np.linspace(lon_min, lon_max, grid_cols)
#     grid_lat = np.linspace(lat_min, lat_max, grid_rows)
#     grid_lon_mesh, grid_lat_mesh = np.meshgrid(grid_lon, grid_lat)

#     # 2. Nội suy 'linear' tạo dải màu liên tục mượt mà
#     grid_ndvi = griddata((lons, lats), ndvis, (grid_lon_mesh, grid_lat_mesh), method='linear')

#     # Xử lý các ô biên bị NaN bằng 'nearest'
#     if np.isnan(grid_ndvi).any():
#         grid_ndvi_fill = griddata((lons, lats), ndvis, (grid_lon_mesh, grid_lat_mesh), method='nearest')
#         grid_ndvi = np.where(np.isnan(grid_ndvi), grid_ndvi_fill, grid_ndvi)

#     # 3. làm mịn dải ranh giới màu (sigma = 0.8 để tránh làm biến dạng dải NDVI thực)
#     grid_ndvi_smooth = gaussian_filter(grid_ndvi, sigma=0.8)

#     # 4. 🎨 BẢNG MÀU CONTINUOUS DẠNG ARCGIS/QGIS CHUẨN VIỄN THÁM
#     # Nước (-1.0 -> 0.0): Xanh dương
#     # Đô thị (0.0 -> 0.18): Đỏ / Cam đậm
#     # Đất trống/Cỏ thưa (0.18 -> 0.28): Vàng / Nâu
#     # Nông nghiệp/Cây xanh trung bình (0.28 -> 0.45): Xanh lá mạ / Xanh lá nhạt
#     # Rừng/Cây xanh rậm rạp (> 0.45): Xanh lá đậm
    
#     # cdict = {
#     #     'red':   ((0.0, 0.17, 0.17),  # Nước (Blue)
#     #               (0.2, 0.84, 0.84),  # Đô thị (Red)
#     #               (0.35, 0.99, 0.99), # Đất trống (Orange)
#     #               (0.5, 0.65, 0.65),  # Thực vật nhẹ (Light Green)
#     #               (0.7, 0.10, 0.10),  # Thực vật đậm (Green)
#     #               (1.0, 0.00, 0.00)), # Rừng rậm (Dark Green)

#     #     'green': ((0.0, 0.51, 0.51),
#     #               (0.2, 0.10, 0.10),
#     #               (0.35, 0.68, 0.68),
#     #               (0.5, 0.85, 0.85),
#     #               (0.7, 0.59, 0.59),
#     #               (1.0, 0.41, 0.41)),

#     #     'blue':  ((0.0, 0.73, 0.73),
#     #               (0.2, 0.11, 0.11),
#     #               (0.35, 0.38, 0.38),
#     #               (0.5, 0.41, 0.41),
#     #               (0.7, 0.31, 0.31),
#     #               (1.0, 0.22, 0.22))
#     # }
    
#     # cmap = mcolors.LinearSegmentedColormap('ArcGIS_NDVI', cdict)
#     # norm = mcolors.Normalize(vmin=-0.1, vmax=0.65)

#     cmap = get_ndvi_cmap()
#     norm = mcolors.Normalize(vmin=NDVI_VMIN, vmax=NDVI_VMAX)

#     rgba_img = cmap(norm(grid_ndvi_smooth))

#     # Giữ nguyên độ hiển thị cho tất cả các vùng (Bao gồm Nước & Đô thị bê tông) 🏢🌊
#     alpha_channel = np.ones_like(grid_ndvi_smooth) * 1.0 #0.85

#     try:
#         from utils.data_loader import load_local_shapefile
#         gdf_shape = load_local_shapefile()
#         if gdf_shape is not None and not gdf_shape.empty:
#             if gdf_shape.crs and str(gdf_shape.crs).upper() != "EPSG:4326":
#                 gdf_shape = gdf_shape.to_crs(epsg=4326)
            
#             geom_union = gdf_shape.unary_union

#             try:
#                 from shapely import contains_xy
#                 inside_mask = contains_xy(geom_union, grid_lon_mesh.ravel(), grid_lat_mesh.ravel()).reshape(grid_lon_mesh.shape)
#             except ImportError:
#                 from shapely.vectorized import contains
#                 inside_mask = contains(geom_union, grid_lon_mesh, grid_lat_mesh)

#             # Chỉ làm trong suốt vùng nằm ngoài ranh giới TP.HCM 🗺️
#             alpha_channel[~inside_mask] = 0.0
#     except Exception as e:
#         print(f"⚠️ Không thể cắt theo GeoJSON: {e}")

#     rgba_img[..., 3] = alpha_channel

#     # Đảo trục Y cho đúng tọa độ GIS
#     rgba_img = np.flipud(rgba_img)

#     # 5. Khử răng cưa hình ảnh với Bicubic Resampling (Phóng x2 kích thước mịn căng)
#     img_uint8 = (rgba_img * 255).astype(np.uint8)
#     img = Image.fromarray(img_uint8)
#     img = img.resize((grid_cols * 2, grid_rows * 2), resample=Image.Resampling.BICUBIC)

#     buffer = io.BytesIO()
#     img.save(buffer, format="PNG")
#     buffer.seek(0)

#     img_base64 = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode('utf-8')
#     bounds = [[lat_min, lon_min], [lat_max, lon_max]]

#     return img_base64, bounds



# def build_folium_map(df: pd.DataFrame, selected_date: str):
#     """
#     Dựng bản đồ Folium tích hợp lớp phủ ImageOverlay an toàn
#     """
#     m = folium.Map(
#         location=[10.7769, 106.7009],
#         zoom_start=11,
#         tiles="OpenStreetMap"
#     )

#     if df is not None and not df.empty:
#         img_base64, bounds = generate_ndvi_raster(df)

#         if img_base64 and bounds:
#             ImageOverlay(
#                 image=img_base64,
#                 bounds=bounds,
#                 opacity=0.85, # Độ rõ màu hoàn hảo
#                 name=f"Lớp phủ NDVI ({selected_date})",
#                 interactive=True
#             ).add_to(m)

#             folium.LayerControl().add_to(m)

#     return m

# def generate_ndvi_raster_for_export(df: pd.DataFrame, target_res_meters: int = 10):
#     """
#     Hàm chuyên dụng chỉ dùng khi tải ảnh về máy: Tự động chuẩn hóa khung hình ôm khít ranh giới 🖼️
#     """
#     try:
#         from scipy.interpolate import griddata
#         from scipy.ndimage import gaussian_filter
#     except ImportError:
#         return None

#     if df is None or df.empty:
#         return None

#     df_clean = df.dropna(subset=['longitude', 'latitude', 'ndvi_mean'])
#     if df_clean.empty:
#         return None

#     lons = df_clean['longitude'].values
#     lats = df_clean['latitude'].values
#     ndvis = df_clean['ndvi_mean'].values

#     lon_min, lon_max = float(lons.min()), float(lons.max())
#     lat_min, lat_max = float(lats.min()), float(lats.max())

#     if lon_min == lon_max or lat_min == lat_max:
#         return None

#     # 🌟 ĐOẠN QUYẾT ĐỊNH KHÔNG BỊ TRÀN VIẾN / TRẮNG DƯỚI: TÍNH TỶ LỆ CHUẨN
#     lon_span = lon_max - lon_min
#     lat_span = lat_max - lat_min
#     max_side = 600  # Độ nét cao cho ảnh tải về

#     if lon_span >= lat_span:
#         grid_cols = max_side
#         grid_rows = max(int(max_side * (lat_span / lon_span)), 50)
#     else:
#         grid_rows = max_side
#         grid_cols = max(int(max_side * (lon_span / lat_span)), 50)

#     grid_lon = np.linspace(lon_min, lon_max, grid_cols)
#     grid_lat = np.linspace(lat_min, lat_max, grid_rows)
#     grid_lon_mesh, grid_lat_mesh = np.meshgrid(grid_lon, grid_lat)

#     grid_ndvi = griddata((lons, lats), ndvis, (grid_lon_mesh, grid_lat_mesh), method='linear')
#     if np.isnan(grid_ndvi).any():
#         grid_ndvi_fill = griddata((lons, lats), ndvis, (grid_lon_mesh, grid_lat_mesh), method='nearest')
#         grid_ndvi = np.where(np.isnan(grid_ndvi), grid_ndvi_fill, grid_ndvi)

#     grid_ndvi_smooth = gaussian_filter(grid_ndvi, sigma=0.8)

#     # Giữ nguyên bảng màu ArcGIS chuẩn
#     cdict = {
#         'red':   ((0.0, 0.17, 0.17), (0.2, 0.84, 0.84), (0.35, 0.99, 0.99), (0.5, 0.65, 0.65), (0.7, 0.10, 0.10), (1.0, 0.00, 0.00)),
#         'green': ((0.0, 0.51, 0.51), (0.2, 0.10, 0.10), (0.35, 0.68, 0.68), (0.5, 0.85, 0.85), (0.7, 0.59, 0.59), (1.0, 0.41, 0.41)),
#         'blue':  ((0.0, 0.73, 0.73), (0.2, 0.11, 0.11), (0.35, 0.38, 0.38), (0.5, 0.41, 0.41), (0.7, 0.31, 0.31), (1.0, 0.22, 0.22))
#     }
#     cmap = mcolors.LinearSegmentedColormap('ArcGIS_NDVI', cdict)
    
#     vmin, vmax = float(ndvis.min()), float(ndvis.max())
#     if vmin == vmax: vmin, vmax = 0.0, 1.0
#     norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    
#     rgba_img = cmap(norm(grid_ndvi_smooth))
#     alpha_channel = np.ones_like(grid_ndvi_smooth) * 0.85

#     try:
#         from utils.data_loader import load_local_shapefile
#         gdf_shape = load_local_shapefile()
#         if gdf_shape is not None and not gdf_shape.empty:
#             if gdf_shape.crs and str(gdf_shape.crs).upper() != "EPSG:4326":
#                 gdf_shape = gdf_shape.to_crs(epsg=4326)
#             geom_union = gdf_shape.unary_union
#             try:
#                 from shapely import contains_xy
#                 inside_mask = contains_xy(geom_union, grid_lon_mesh.ravel(), grid_lat_mesh.ravel()).reshape(grid_lon_mesh.shape)
#             except ImportError:
#                 from shapely.vectorized import contains
#                 inside_mask = contains(geom_union, grid_lon_mesh, grid_lat_mesh)
#             if inside_mask.any():
#                 alpha_channel[~inside_mask] = 0.0
#     except Exception:
#         pass

#     rgba_img[..., 3] = alpha_channel
#     rgba_img = np.flipud(rgba_img)

#     img_uint8 = (rgba_img * 255).astype(np.uint8)
#     img = Image.fromarray(img_uint8)
#     img = img.resize((grid_cols * 2, grid_rows * 2), resample=Image.Resampling.BICUBIC)

#     buffer = io.BytesIO()
#     img.save(buffer, format="PNG")
#     buffer.seek(0)
#     return buffer.getvalue()
