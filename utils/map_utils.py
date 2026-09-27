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
    Nội suy các điểm khuyết và tạo ảnh Overlay màu Cam -> Xanh
    """
    # Lọc dữ liệu hợp lệ
    df_clean = df.dropna(subset=['longitude', 'latitude', 'ndvi_mean'])
    
    lons = df_clean['longitude'].values
    lats = df_clean['latitude'].values
    ndvis = df_clean['ndvi_mean'].values

    # 1. Tạo Lưới tọa độ đều (Meshgrid)
    lon_min, lon_max = lons.min(), lons.max()
    lat_min, lat_max = lats.min(), lats.max()

    grid_lon = np.linspace(lon_min, lon_max, grid_resolution)
    grid_lat = np.linspace(lat_min, lat_max, grid_resolution)
    grid_lon_mesh, grid_lat_mesh = np.meshgrid(grid_lon, grid_lat)

    # 2. Nội suy điểm khuyết (Tuyến tính + Điểm gần nhất)
    grid_ndvi = griddata((lons, lats), ndvis, (grid_lon_mesh, grid_lat_mesh), method='linear')
    
    # Lấp các ô khuyết ở viền bằng nearest
    nan_mask = np.isnan(grid_ndvi)
    if np.any(nan_mask):
        grid_ndvi_nearest = griddata((lons, lats), ndvis, (grid_lon_mesh, grid_lat_mesh), method='nearest')
        grid_ndvi[nan_mask] = grid_ndvi_nearest[nan_mask]

    # 3. Tạo Dải màu: Cam/Đỏ (Phi thực vật < 0.2) -> Vàng -> Xanh (Thực vật > 0.5)
    colors = ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#a6d96a", "#1a9850", "#006837"]
    cmap = mcolors.LinearSegmentedColormap.from_list("ndvi_cmap", colors)
    
    # Chuẩn hóa dải giá trị NDVI từ -0.1 đến 0.7
    norm = mcolors.Normalize(vmin=-0.1, vmax=0.7)
    rgba_img = cmap(norm(grid_ndvi))

    # Đảo trục Y vì ảnh Folium render từ gốc trên bên trái
    rgba_img = np.flipud(rgba_img)
    
    # Chuyển thành định dạng PNG Bytes
    img_uint8 = (rgba_img * 255).astype(np.uint8)
    img = Image.fromarray(img_uint8)
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    # Tọa độ khung ranh giới cho Folium [[lat_min, lon_min], [lat_max, lon_max]]
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
