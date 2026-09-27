import io
import base64
import numpy as np
import pandas as pd
import matplotlib.colors as mcolors
from PIL import Image
import folium
from folium.raster_layers import ImageOverlay


def generate_ndvi_raster(df: pd.DataFrame, target_res_meters: int = 10, method: str = 'nearest'):
    """
    Tạo dải ảnh NDVI Base64 dạng raster độ phân giải 10m an toàn, chống sập app.
    """
    try:
        from scipy.interpolate import griddata
    except ImportError:
        print("⚠️ Thiếu thư viện scipy. Hãy chạy: pip install scipy")
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

    lon_min, lon_max = float(lons.min()), float(lats.max()) if len(lats) > 0 else (0.0, 0.0)
    lon_min, lon_max = float(lons.min()), float(lons.max())
    lat_min, lat_max = float(lats.min()), float(lats.max())

    # Nếu tọa độ không hợp lệ
    if lon_min == lon_max or lat_min == lat_max:
        return None, None

    # 1. Quy đổi độ phân giải sang pixel 10m
    lat_center = (lat_min + lat_max) / 2.0
    meters_per_deg_lat = 111000.0
    meters_per_deg_lon = 111000.0 * np.cos(np.radians(lat_center))

    width_meters = (lon_max - lon_min) * meters_per_deg_lon
    height_meters = (lat_max - lat_min) * meters_per_deg_lat

    grid_cols = int(max(width_meters / target_res_meters, 50))
    grid_rows = int(max(height_meters / target_res_meters, 50))

    # Giới hạn kích thước lưới tối đa để bảo vệ bộ nhớ RAM
    grid_cols = min(grid_cols, 1000)
    grid_rows = min(grid_rows, 1000)

    grid_lon = np.linspace(lon_min, lon_max, grid_cols)
    grid_lat = np.linspace(lat_min, lat_max, grid_rows)
    grid_lon_mesh, grid_lat_mesh = np.meshgrid(grid_lon, grid_lat)

    # 2. Nội suy điểm NDVI
    grid_ndvi = griddata((lons, lats), ndvis, (grid_lon_mesh, grid_lat_mesh), method=method)

    # Xử lý các điểm NaN nếu có
    if np.isnan(grid_ndvi).any():
        grid_ndvi_fill = griddata((lons, lats), ndvis, (grid_lon_mesh, grid_lat_mesh), method='nearest')
        grid_ndvi = np.where(np.isnan(grid_ndvi), grid_ndvi_fill, grid_ndvi)

    # 3. Dải màu NDVI rực rỡ (Đỏ/Cam -> Vàng -> Xanh lá tươi)
    colors = ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#a6d96a", "#1a9850", "#006837"]
    cmap = mcolors.LinearSegmentedColormap.from_list("ndvi_cmap", colors)

    vmin = max(-0.2, float(ndvis.min()))
    vmax = min(0.9, float(ndvis.max()))
    if vmin >= vmax:
        vmin, vmax = -0.1, 0.7

    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    rgba_img = cmap(norm(grid_ndvi))

    # Đảo ngược trục Y đúng hệ tọa độ GIS
    rgba_img = np.flipud(rgba_img)

    img_uint8 = (rgba_img * 255).astype(np.uint8)
    img = Image.fromarray(img_uint8)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    img_base64 = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode('utf-8')
    bounds = [[lat_min, lon_min], [lat_max, lon_max]]

    return img_base64, bounds


def build_folium_map(df: pd.DataFrame, selected_date: str):
    """
    Dựng bản đồ Folium tích hợp lớp phủ ImageOverlay an toàn tuyệt đối
    """
    m = folium.Map(
        location=[10.7769, 106.7009],
        zoom_start=11,
        tiles="OpenStreetMap"
    )

    if df is not None and not df.empty:
        # Tạo Raster Overlay từ dữ liệu NDVI
        img_base64, bounds = generate_ndvi_raster(df)

        # 🟢 BẮT BỘC KIỂM TRA ĐIỀU KIỆN NÀY ĐỂ TRÁNH TRUYỀN NONE VÀO IMAGEOVERLAY CAUSING CRASH
        if img_base64 and bounds:
            ImageOverlay(
                image=img_base64,
                bounds=bounds,
                opacity=0.75,
                name=f"Lớp phủ NDVI ({selected_date})",
                interactive=True
            ).add_to(m)

            folium.LayerControl().add_to(m)

    return m
