import folium
from streamlit_folium import st_folium
from folium.raster_layers import ImageOverlay
from utils.data_loader import load_local_shapefile
from utils.map_utils import generate_ndvi_raster


def render_map(lat, lng, zoom, basemap_choice, show_boundaries, df=None, selected_time=""):
    """
    Component hiển thị bản đồ WebGIS tích hợp Basemap, NDVI Raster và Ranh giới Shapefile.
    """
    # 1. Khởi tạo bản đồ tại vị trí chọn
    m = folium.Map(location=[lat, lng], zoom_start=zoom, tiles=None)
    
    # 2. Xử lý Basemap (Nền bản đồ)
    if basemap_choice == "Esri Satellite":
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri", name="Esri Satellite"
        ).add_to(m)
    elif basemap_choice == "Google Hybrid":
        folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
            attr="Google", name="Google Hybrid"
        ).add_to(m)
    else:
        folium.TileLayer(tiles="OpenStreetMap", name="OpenStreetMap").add_to(m)

    # 3. 🟢 MỚI: Thêm Lớp phủ NDVI (ImageOverlay) nếu có dữ liệu
    if df is not None and not df.empty:
        try:
            img_buffer, bounds = generate_ndvi_raster(df)
            ImageOverlay(
                image=img_buffer,
                bounds=bounds,
                opacity=0.65,
                name=f"Lớp phủ NDVI ({selected_time})",
                interactive=True
            ).add_to(m)
        except Exception as e:
            print(f"⚠️ Lỗi khi vẽ lớp NDVI Raster: {e}")

    # 4. Thêm Ranh giới hành chính từ Shapefile
    if show_boundaries:
        gdf_boundary = load_local_shapefile()
        if gdf_boundary is not None:
            cols = [c for c in ['NAME_1', 'NAME_2', 'TEN_TINH', 'TEN_HUYEN', 'name'] if c in gdf_boundary.columns]
            tooltip_field = cols[:1] if cols else [gdf_boundary.columns[0]]

            folium.GeoJson(
                gdf_boundary,
                name="Ranh giới HCM-34",
                style_function=lambda feature: {
                    'fillColor': 'transparent',
                    'color': '#38BDF8',
                    'weight': 2.0,
                    'dashArray': '4, 4',
                    'fillOpacity': 0,
                },
                tooltip=folium.GeoJsonTooltip(fields=tooltip_field, aliases=['Thông tin:'])
            ).add_to(m)

    # 5. Thêm bảng quản lý Layer & Hiển thị lên Streamlit
    folium.LayerControl().add_to(m)
    st_folium(m, width="100%", height=500, key="map_view_component")
