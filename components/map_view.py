import folium
from streamlit_folium import st_folium
from utils.data_loader import load_local_shapefile

def render_map(lat, lng, zoom, basemap_choice, show_boundaries):
    m = folium.Map(location=[lat, lng], zoom_start=zoom, tiles=None)
    
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

    folium.LayerControl().add_to(m)
    st_folium(m, width="100%", height=500)
