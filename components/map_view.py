import warnings
import folium
import streamlit as st
from streamlit_folium import st_folium
from folium.raster_layers import ImageOverlay
from shapely.geometry import Point
from utils.data_loader import load_local_shapefile
from utils.map_utils import generate_ndvi_raster

NAME_COLS = ['NAME_1', 'NAME_2', 'TEN_TINH', 'TEN_HUYEN', 'name']


def _pick_name_col(gdf):
    cols = [c for c in NAME_COLS if c in gdf.columns]
    if cols:
        return cols[0]
    return next((c for c in gdf.columns if c != "geometry"), None)


def _find_feature(gdf, lat, lng, max_dist_deg=0.05):
    """Tìm đa giác chứa điểm (lat, lng). Không có thì lấy đa giác gần nhất (trong ~5 km)."""
    pt = Point(lng, lat)
    hit = gdf[gdf.geometry.contains(pt)]
    if hit.empty:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            d = gdf.geometry.distance(pt)
        if d.min() > max_dist_deg:
            return None
        return gdf.loc[[d.idxmin()]]
    # Nếu file có nhiều cấp chồng nhau, lấy đa giác nhỏ nhất (cấp phường)
    return hit.loc[[hit.geometry.area.idxmin()]]


def render_map(lat, lng, zoom, basemap_choice, show_boundaries, df=None,
               selected_time="", selected_district=None):
    m = folium.Map(location=[lat, lng], zoom_start=zoom, tiles=None)

    # 1. Basemap
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

    # 2. Lớp NDVI
    if df is not None and not df.empty:
        try:
            img_base64, bounds = generate_ndvi_raster(df)
            if img_base64 and bounds:
                date_str = selected_time.strftime("%m/%Y") if hasattr(selected_time, 'strftime') else str(selected_time)
                ImageOverlay(
                    image=img_base64, bounds=bounds, opacity=0.9,
                    name=f"Lớp phủ NDVI ({date_str})", interactive=True
                ).add_to(m)
        except Exception as e:
            st.error(f"⚠️ Lỗi khi vẽ lớp NDVI Raster lên bản đồ: {e}")

    # 3. Ranh giới + tô sáng khu vực đang chọn
    gdf_boundary = load_local_shapefile() if (show_boundaries or selected_district) else None
    name_col = _pick_name_col(gdf_boundary) if gdf_boundary is not None else None

    if show_boundaries and gdf_boundary is not None:
        folium.GeoJson(
            gdf_boundary,
            name="Ranh giới HCM-34",
            style_function=lambda f: {'fillColor': 'transparent', 'color': '#FFFFFF',
                                      'weight': 2.0, 'dashArray': '4, 4', 'fillOpacity': 0},
            tooltip=folium.GeoJsonTooltip(fields=[name_col], aliases=['Thông tin:']) if name_col else None,
        ).add_to(m)

    if gdf_boundary is not None and selected_district and selected_district != "Toàn tỉnh/TP":
        target = _find_feature(gdf_boundary, lat, lng)
        if target is not None:
            # Lớp "phát sáng" bên ngoài
            folium.GeoJson(
                target, name="Glow",
                style_function=lambda f: {'fillOpacity': 0, 'color': '#D946EF', 'weight': 9, 'opacity': 0.25},
            ).add_to(m)
            # Viền sáng + tô nhẹ bên trong
            folium.GeoJson(
                target, name="Khu vực đang chọn",
                style_function=lambda f: {'fillColor': '#D946EF', 'fillOpacity': 0.12,
                                          'color': '#D946EF', 'weight': 3, 'opacity': 1},
                tooltip=folium.GeoJsonTooltip(fields=[name_col], aliases=['Khu vực:']) if name_col else None,
            ).add_to(m)
            # Tự zoom vừa khít đa giác (thay cho tọa độ/zoom nhập tay)
            minx, miny, maxx, maxy = target.total_bounds
            m.fit_bounds([[miny, minx], [maxy, maxx]], padding=(30, 30), max_zoom=16)

    folium.LayerControl().add_to(m)
    st_folium(m, width="100%", height=500, key="map_view_component")

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
#                     'color': '#FFFFFF',
#                     'weight': 2.0,
#                     'dashArray': '4, 4',
#                     'fillOpacity': 0,
#                 },
#                 tooltip=folium.GeoJsonTooltip(fields=tooltip_field, aliases=['Thông tin:'])
#             ).add_to(m)

#     # 5. Thêm bảng quản lý Layer & Hiển thị lên Streamlit
#     folium.LayerControl().add_to(m)
#     st_folium(m, width="100%", height=500, key="map_view_component")
