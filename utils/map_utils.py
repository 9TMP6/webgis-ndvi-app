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

    # 3. làm mịn dải ranh giới màu (sigma = 0.8 để tránh làm biến dạng dải NDVI thực)
    grid_ndvi_smooth = gaussian_filter(grid_ndvi, sigma=0.8)

    # 4. 🎨 BẢNG MÀU CONTINUOUS DẠNG ARCGIS/QGIS CHUẨN VIỄN THÁM
    # Nước (-1.0 -> 0.0): Xanh dương
    # Đô thị (0.0 -> 0.18): Đỏ / Cam đậm
    # Đất trống/Cỏ thưa (0.18 -> 0.28): Vàng / Nâu
    # Nông nghiệp/Cây xanh trung bình (0.28 -> 0.45): Xanh lá mạ / Xanh lá nhạt
    # Rừng/Cây xanh rậm rạp (> 0.45): Xanh lá đậm
    
    cdict = {
        'red':   ((0.0, 0.17, 0.17),  # Nước (Blue)
                  (0.2, 0.84, 0.84),  # Đô thị (Red)
                  (0.35, 0.99, 0.99), # Đất trống (Orange)
                  (0.5, 0.65, 0.65),  # Thực vật nhẹ (Light Green)
                  (0.7, 0.10, 0.10),  # Thực vật đậm (Green)
                  (1.0, 0.00, 0.00)), # Rừng rậm (Dark Green)

        'green': ((0.0, 0.51, 0.51),
                  (0.2, 0.10, 0.10),
                  (0.35, 0.68, 0.68),
                  (0.5, 0.85, 0.85),
                  (0.7, 0.59, 0.59),
                  (1.0, 0.41, 0.41)),

        'blue':  ((0.0, 0.73, 0.73),
                  (0.2, 0.11, 0.11),
                  (0.35, 0.38, 0.38),
                  (0.5, 0.41, 0.41),
                  (0.7, 0.31, 0.31),
                  (1.0, 0.22, 0.22))
    }
    
    cmap = mcolors.LinearSegmentedColormap('ArcGIS_NDVI', cdict)
    norm = mcolors.Normalize(vmin=-0.1, vmax=0.65)

    rgba_img = cmap(norm(grid_ndvi_smooth))

    # Giữ nguyên độ hiển thị cho tất cả các vùng (Bao gồm Nước & Đô thị bê tông) 🏢🌊
    alpha_channel = np.ones_like(grid_ndvi_smooth) * 0.85

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
