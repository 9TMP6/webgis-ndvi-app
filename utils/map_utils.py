import io
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from scipy.interpolate import griddata
from PIL import Image
import folium
from folium.raster_layers import ImageOverlay
import base64

def generate_ndvi_raster(df: pd.DataFrame, target_res_meters: int = 10, method: str = 'nearest'):
    """
    Tạo bản đồ NDVI sắc nét từng pixel 10m (Sentinel-2)
    
    :param df: DataFrame chứa longitude, latitude, ndvi_mean
    :param target_res_meters: Độ phân giải mong muốn (mặc định 10m x 10m)
    :param method: 'nearest' (sắc nét từng pixel vuông 10m) hoặc 'linear' (làm mịn dải màu)
    """
    df_clean = df.dropna(subset=['longitude', 'latitude', 'ndvi_mean'])
    
    if df_clean.empty:
        return None, None

    lons = df_clean['longitude'].values
    lats = df_clean['latitude'].values
    ndvis = df_clean['ndvi_mean'].values

    lon_min, lon_max = lons.min(), lons.max()
    lat_min, lat_max = lats.min(), lats.max()

    # 1. Tính toán số lượng Pixel chính xác cho độ phân giải target_res_meters (10m)
    # 1 độ vĩ độ ~ 111,000 mét
    lat_center = (lat_min + lat_max) / 2.0
    meters_per_deg_lat = 111000.0
    meters_per_deg_lon = 111000.0 * np.cos(np.radians(lat_center))

    width_meters = (lon_max - lon_min) * meters_per_deg_lon
    height_meters = (lat_max - lat_min) * meters_per_deg_lat

    # Số lượng ô lưới (pixels)
    grid_cols = int(max(width_meters / target_res_meters, 50))
    grid_rows = int(max(height_meters / target_res_meters, 50))

    # Giới hạn tối đa 2000px để tránh tràn bộ nhớ trình duyệt WebGIS
    grid_cols = min(grid_cols, 2000)
    grid_rows = min(grid_rows, 2000)

    grid_lon = np.linspace(lon_min, lon_max, grid_cols)
    grid_lat = np.linspace(lat_min, lat_max, grid_rows)
    grid_lon_mesh, grid_lat_mesh = np.meshgrid(grid_lon, grid_lat)

    # 2. Nội suy 'nearest' để giữ nguyên góc cạnh vuông vức của Pixel 10m
    grid_ndvi = griddata((lons, lats), ndvis, (grid_lon_mesh, grid_lat_mesh), method=method)

    # 3. Bảng màu NDVI rực rỡ (Đỏ -> Cam -> Vàng -> Xanh lá tươi)
    colors = ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#a6d96a", "#1a9850", "#006837"]
    cmap = mcolors.LinearSegmentedColormap.from_list("ndvi_cmap", colors)
    
    vmin = max(-0.2, float(ndvis.min()))
    vmax = min(0.9, float(ndvis.max()))
    if vmin >= vmax:
        vmin, vmax = -0.1, 0.7

    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    rgba_img = cmap(norm(grid_ndvi))

    # Đảo trục Y cho đúng hệ tọa độ GIS
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
    Dựng bản đồ Folium tích hợp lớp phủ ImageOverlay
    """
    # Mặc định tâm bản đồ TP.HCM
    m = folium.Map(
        location=[10.7769, 106.7009], 
        zoom_start=11, 
        tiles="OpenStreetMap"
    )

    if not df.empty:
        # Tạo Raster Overlay từ dữ liệu NDVI
        img_buffer, bounds = generate_ndvi_raster(df)

        # Thêm ImageOverlay vào bản đồ
        ImageOverlay(
            image=img_buffer,
            bounds=bounds,
            opacity=0.65,
            name=f"Lớp phủ NDVI ({selected_date})",
            interactive=True
        ).add_to(m)

        folium.LayerControl().add_to(m)

    return m
