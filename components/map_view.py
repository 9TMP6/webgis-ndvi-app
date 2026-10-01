import folium
import streamlit as st
from streamlit_folium import st_folium
from folium.raster_layers import ImageOverlay
from utils.data_loader import load_local_shapefile
from utils.map_utils import generate_ndvi_raster


def render_map(lat, lng, zoom, basemap_choice, show_boundaries, df=None, selected_time=""):
    """
    Component hiển thị bản đồ WebGIS tích hợp Basemap, NDVI Raster và Ranh giới Shapefile. 🗺️✨
    """
    # 1. Khởi tạo bản đồ tại vị trí chọn 📍
    m = folium.Map(location=[lat, lng], zoom_start=zoom, tiles=None)
    
    # 2. Xử lý Basemap (Nền bản đồ) 🌍
    if basemap_choice == "Esri Satellite":
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri", name="Esri Satellite", default=True
        ).add_to(m)
    elif basemap_choice == "Google Hybrid":
        folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
            attr="Google", name="Google Hybrid", default=True
        ).add_to(m)
    else:
        folium.TileLayer(tiles="OpenStreetMap", name="OpenStreetMap", default=True).add_to(m)

    # 3. 🟢 THÊM LỚP PHỦ NDVI (IMAGEOVERLAY) KHI BẤM DỰ ĐOÁN 🎨
    if df is not None and not df.empty:
        try:
            # Lọc sạch dữ liệu tọa độ & NDVI trước khi tạo Raster 🧹
            df_clean = df.dropna(subset=['latitude', 'longitude', 'ndvi_mean']).copy()
            
            if not df_clean.empty:
                img_base64, bounds = generate_ndvi_raster(df_clean)
                
                if img_base64 and bounds:
                    # 🛠️️ Đảm bảo chuỗi Base64 có tiền tố Data URI chuẩn cho Folium
                    if isinstance(img_base64, str) and not img_base64.startswith("data:image"):
                        img_base64 = f"data:image/png;base64,{img_base64}"
                    
                    # Định dạng hiển thị thời gian 📅
                    date_str = selected_time.strftime("%m/%Y") if hasattr(selected_time, 'strftime') else str(selected_time)
                    
                    # Thêm Lớp phủ ImageOverlay
                    ImageOverlay(
                        image=img_base64,
                        bounds=bounds,  # Chuẩn: [[min_lat, min_lng], [max_lat, max_lng]]
                        opacity=0.80,   # Độ rực rỡ & trong suốt của lớp màu 🎨
                        name=f"Lớp phủ NDVI ({date_str})",
                        interactive=True,
                        cross_origin=False
                    ).add_to(m)

                    # 🎯 Tự động Zoom khung nhìn bản đồ khớp chuẩn với Bounds của Raster
                    m.fit_bounds(bounds)

        except Exception as e:
            st.error(f"⚠️ Lỗi khi vẽ lớp NDVI Raster lên bản đồ: {e}")

    # 4. Thêm Ranh giới hành chính từ Shapefile 🏛️
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

    # 5. Thêm bảng quản lý Layer & Hiển thị lên Streamlit 🎛️
    folium.LayerControl(collapsed=False).add_to(m)
    
    return st_folium(m, width="100%", height=500, key="map_view_component")


# import folium
# import streamlit as st
# from streamlit_folium import st_folium
# from folium.raster_layers import ImageOverlay
# from utils.data_loader import load_local_shapefile
# from utils.map_utils import generate_ndvi_raster


# def render_map(lat, lng, zoom, basemap_choice, show_boundaries, df=None, selected_time=""):
#     """
#     Component hiển thị bản đồ WebGIS tích hợp Basemap, NDVI Raster và Ranh giới Shapefile.
#     """
#     # 1. Khởi tạo bản đồ tại vị trí chọn
#     m = folium.Map(location=[lat, lng], zoom_start=zoom, tiles=None)
    
#     # 2. Xử lý Basemap (Nền bản đồ)
#     if basemap_choice == "Esri Satellite":
#         folium.TileLayer(
#             tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
#             attr="Esri", name="Esri Satellite"
#         ).add_to(m)
#     elif basemap_choice == "Google Hybrid":
#         folium.TileLayer(
#             tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
#             attr="Google", name="Google Hybrid"
#         ).add_to(m)
#     else:
#         folium.TileLayer(tiles="OpenStreetMap", name="OpenStreetMap").add_to(m)

#     # 3. 🟢 THÊM LỚP PHỦ NDVI (IMAGEOVERLAY) KHI BẤM DỰ ĐOÁN
#     if df is not None and not df.empty:
#         try:
#             img_base64, bounds = generate_ndvi_raster(df)
#             if img_base64 and bounds:
#                 date_str = selected_time.strftime("%m/%Y") if hasattr(selected_time, 'strftime') else str(selected_time)
#                 ImageOverlay(
#                     image=img_base64, # Truyền Base64 string chuẩn
#                     bounds=bounds,
#                     opacity=0.75, # Độ rực rỡ của lớp màu
#                     name=f"Lớp phủ NDVI ({date_str})",
#                     interactive=True
#                 ).add_to(m)
#         except Exception as e:
#             st.error(f"⚠️ Lỗi khi vẽ lớp NDVI Raster lên bản đồ: {e}")

#     # 4. Thêm Ranh giới hành chính từ Shapefile
#     if show_boundaries:
#         gdf_boundary = load_local_shapefile()
#         if gdf_boundary is not None:
#             cols = [c for c in ['NAME_1', 'NAME_2', 'TEN_TINH', 'TEN_HUYEN', 'name'] if c in gdf_boundary.columns]
#             tooltip_field = cols[:1] if cols else [gdf_boundary.columns[0]]

#             folium.GeoJson(
#                 gdf_boundary,
#                 name="Ranh giới HCM-34",
#                 style_function=lambda feature: {
#                     'fillColor': 'transparent',
#                     'color': '#38BDF8',
#                     'weight': 2.0,
#                     'dashArray': '4, 4',
#                     'fillOpacity': 0,
#                 },
#                 tooltip=folium.GeoJsonTooltip(fields=tooltip_field, aliases=['Thông tin:'])
#             ).add_to(m)

#     # 5. Thêm bảng quản lý Layer & Hiển thị lên Streamlit
#     folium.LayerControl().add_to(m)
#     st_folium(m, width="100%", height=500, key="map_view_component")
