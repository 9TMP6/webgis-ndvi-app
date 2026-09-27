import io
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from scipy.interpolate import griddata
from PIL import Image
import folium
from folium.raster_layers import ImageOverlay

def generate_ndvi_raster(df: pd.DataFrame, grid_resolution: int = 300):
    """
    Nội suy toàn bộ các ô GRID trong CSDL thành dải ảnh NDVI (Cam -> Vàng -> Xanh)
    """
    # Lọc bỏ dòng khuyết tọa độ hoặc giá trị NDVI
    df_clean = df.dropna(subset=['longitude', 'latitude', 'ndvi_mean'])
    
    if df_clean.empty:
        return None, None

    lons = df_clean['longitude'].values
    lats = df_clean['latitude'].values
    ndvis = df_clean['ndvi_mean'].values

    # 1. Tạo ma trận lưới đều
    lon_min, lon_max = lons.min(), lons.max()
    lat_min, lat_max = lats.min(), lats.max()

    grid_lon = np.linspace(lon_min, lon_max, grid_resolution)
    grid_lat = np.linspace(lat_min, lat_max, grid_resolution)
    grid_lon_mesh, grid_lat_mesh = np.meshgrid(grid_lon, grid_lat)

    # 2. Nội suy điểm khuyết (Linear + Nearest cho vùng viền)
    grid_ndvi = griddata((lons, lats), ndvis, (grid_lon_mesh, grid_lat_mesh), method='linear')
    nan_mask = np.isnan(grid_ndvi)
    if np.any(nan_mask):
        grid_ndvi_nearest = griddata((lons, lats), ndvis, (grid_lon_mesh, grid_lat_mesh), method='nearest')
        grid_ndvi[nan_mask] = grid_ndvi_nearest[nan_mask]

    # 3. Dải màu NDVI chuẩn: Đỏ/Cam (Phi thực vật) -> Vàng -> Xanh lá (Thực vật xanh)
    colors = ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#a6d96a", "#1a9850", "#006837"]
    cmap = mcolors.LinearSegmentedColormap.from_list("ndvi_cmap", colors)
    
    # Chuẩn hóa NDVI trong khoảng -0.1 đến 0.7
    norm = mcolors.Normalize(vmin=-0.1, vmax=0.7)
    rgba_img = cmap(norm(grid_ndvi))

    # Đảo trục Y cho đúng chiều tọa độ bản đồ Folium
    rgba_img = np.flipud(rgba_img)
    
    # Chuyển ma trận màu thành Byte PNG
    img_uint8 = (rgba_img * 255).astype(np.uint8)
    img = Image.fromarray(img_uint8)
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    bounds = [[lat_min, lon_min], [lat_max, lon_max]]
    return buffer, bounds

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
