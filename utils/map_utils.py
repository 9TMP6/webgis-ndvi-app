import io
import base64
import numpy as np
import pandas as pd
import matplotlib.colors as mcolors
from PIL import Image
import folium
from folium.raster_layers import ImageOverlay


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

    # 3. 🪄 BÍ KÍP ARCGIS: Dùng Gaussian Filter làm mịn dải ranh giới màu (sigma = 1.2 -> 1.5)
    grid_ndvi_smooth = gaussian_filter(grid_ndvi, sigma=1.3)

    # 4. Bảng màu gradient 10 điểm mượt như dải màu RdYlGn chuyên dụng của ArcGIS
    colors = [
        "#a50026", "#d73027", "#f46d43", "#fdae61", 
        "#fee08b", "#d9ef8b", "#a6d96a", "#66bd63", 
        "#1a9850", "#006837"
    ]
    cmap = mcolors.LinearSegmentedColormap.from_list("arcgis_smooth_ndvi", colors)

    norm = mcolors.Normalize(vmin=0.08, vmax=0.75)
    rgba_img = cmap(norm(grid_ndvi_smooth))

    # Alpha Masking: Làm trong suốt hoàn toàn vùng không phải cây trồng (NDVI < 0.1)
    alpha_channel = np.ones_like(grid_ndvi_smooth)
    alpha_channel[grid_ndvi_smooth < 0.1] = 0.0
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
                opacity=0.80, # Độ rõ màu hoàn hảo
                name=f"Lớp phủ NDVI ({selected_date})",
                interactive=True
            ).add_to(m)

            folium.LayerControl().add_to(m)

    return m
