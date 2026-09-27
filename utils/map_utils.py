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

def generate_ndvi_raster(df: pd.DataFrame, grid_resolution: int = 300):
    """
    Nội suy toàn bộ các ô GRID trong CSDL thành dải ảnh NDVI (Đỏ/Cam -> Vàng -> Xanh)
    Trả về chuỗi Base64 Data URI để Folium Overlay hiển thị chuẩn xác 100%.
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

    # 3. Dải màu NDVI chuẩn rực rỡ: Đỏ/Cam (Đất/Đô thị) -> Vàng -> Xanh Lá Tươi (Thảm thực vật)
    colors = ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#a6d96a", "#1a9850", "#006837"]
    cmap = mcolors.LinearSegmentedColormap.from_list("ndvi_cmap", colors)
    
    # Chuẩn hóa linh hoạt dựa trên khoảng giá trị NDVI thực tế
    vmin = max(-0.2, float(ndvis.min()))
    vmax = min(0.9, float(ndvis.max()))
    if vmin >= vmax:
        vmin, vmax = -0.1, 0.7

    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    rgba_img = cmap(norm(grid_ndvi))

    # Đảo trục Y cho đúng chiều tọa độ bản đồ Folium
    rgba_img = np.flipud(rgba_img)
    
    # Chuyển ma trận màu thành PNG và mã hóa sang Base64 Data URI
    img_uint8 = (rgba_img * 255).astype(np.uint8)
    img = Image.fromarray(img_uint8)
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    # 🟢 MÃ HÓA BASE64 DẠNG DATA URI CHUẨN CHO WEBGIS
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
