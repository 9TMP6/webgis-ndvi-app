import warnings
import folium
import streamlit as st
from streamlit_folium import st_folium
from folium.raster_layers import ImageOverlay
from folium.plugins import Fullscreen
from shapely.geometry import Point
from utils.data_loader import load_local_shapefile
from utils.map_utils import generate_ndvi_raster
from utils.ward_info import (
    compute_ward_stats, build_ward_popup, ward_label, has_ward_columns, POPUP_CSS,
)

NAME_COLS = ['ten_xa', 'NAME_1', 'NAME_2', 'TEN_TINH', 'TEN_HUYEN', 'name']


def _ward_style(feature):
    return {'fillColor': 'transparent', 'color': '#FFFFFF', 'weight': 2.0, 'dashArray': '4, 4', 'fillOpacity': 0}


def _ward_highlight(feature):
    return {'fillColor': '#FACC15', 'fillOpacity': 0.18, 'color': '#FACC15', 'weight': 3.5, 'dashArray': None}

def _range_style(inside, mode):
    """Kiểu vẽ khi đang lọc theo khoảng NDVI: trong khoảng = viền vàng nổi bật; ngoài khoảng = làm mờ (hoặc gần như ẩn)."""
    if inside:
        css = {'fillColor': '#FFFFFF', 'fillOpacity': 0.10, 'color': '#FACC15', 'weight': 3.5, 'dashArray': None}
    elif mode == "hide":
        css = {'fillColor': '#111827', 'fillOpacity': 0.93, 'color': '#374151', 'weight': 1, 'dashArray': None}
    else:
        css = {'fillColor': '#111827', 'fillOpacity': 0.55, 'color': '#FFFFFF', 'weight': 1, 'dashArray': '4, 4'}
    return lambda feature: css


@st.cache_data(show_spinner=False, max_entries=3)
def _cached_raster(df):
    """Vẽ ảnh NDVI một lần cho mỗi bộ dữ liệu: kéo thanh lọc NDVI không phải vẽ lại ảnh."""
    return generate_ndvi_raster(df)


MAP_HEIGHT = 660  # tăng từ 500 để bản đồ là trọng tâm


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
    return hit.loc[[hit.geometry.area.idxmin()]]


def render_map(lat, lng, zoom, basemap_choice, show_boundaries, df=None,
               selected_time="", selected_district=None, ndvi_range=None):
    # ndvi_range = (thấp, cao, "highlight" | "hide") hoặc None (không lọc)
    m = folium.Map(location=[lat, lng], zoom_start=zoom, tiles=None)

    # 1. Lớp bản đồ nền
    if basemap_choice == "Google Hybrid":
        folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
            attr="Google", name="Google Hybrid"
        ).add_to(m)
    elif basemap_choice == "OpenStreetMap":
        folium.TileLayer(tiles="OpenStreetMap", name="OpenStreetMap").add_to(m)
    else:  # "Ảnh vệ tinh Esri" (mặc định)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri", name="Ảnh vệ tinh Esri"
        ).add_to(m)

    # 2. Lớp NDVI
    if df is not None and not df.empty:
        try:
            img_base64, bounds = _cached_raster(df)
            if img_base64 and bounds:
                date_str = selected_time.strftime("%m/%Y") if hasattr(selected_time, 'strftime') else str(selected_time)
                ImageOverlay(
                    image=img_base64, bounds=bounds, opacity=0.9,
                    name=f"Lớp phủ NDVI ({date_str})", interactive=True
                ).add_to(m)
        except Exception as e:
            st.error(f"⚠️ Lỗi khi vẽ lớp NDVI lên bản đồ: {e}")

    # 3. Ranh giới + tô sáng khu vực đang chọn
    gdf_boundary = load_local_shapefile() if (show_boundaries or selected_district) else None
    name_col = _pick_name_col(gdf_boundary) if gdf_boundary is not None else None

    # Popup chi tiết khi bấm vào phường/xã (cần file ranh giới có cột ma_xa, ten_xa)
    popup_for = None
    if gdf_boundary is not None and has_ward_columns(gdf_boundary):
        data_loaded = df is not None and not df.empty
        stats, city_mean = None, None
        if data_loaded:
            try:
                stats, city_mean = compute_ward_stats(df, gdf_boundary)   # NDVI riêng của từng phường/xã
            except Exception as e:
                print(f"⚠️ Không tính được NDVI theo phường/xã: {e}")
        period_label = selected_time.strftime("%m/%Y") if hasattr(selected_time, "strftime") else str(selected_time)
        source_label = ""
        if data_loaded:
            if st.session_state.get("ndvi_is_ai"):
                source_label = f"dự báo bằng mô hình AI {st.session_state.get('ndvi_model') or ''}".strip()
            else:
                source_label = "quan trắc vệ tinh (CSDL)"
        m.get_root().header.add_child(folium.Element(POPUP_CSS))

        def popup_for(row):
            return folium.Popup(
                build_ward_popup(row, stats, city_mean, data_loaded, period_label, source_label), max_width=360)

    if show_boundaries and gdf_boundary is not None:
        built = False
        if popup_for is not None:
            try:
                group = folium.FeatureGroup(name="Ranh giới hành chính HCM-34", show=True)
                range_on = ndvi_range is not None and stats is not None

                def _style_for(row):
                    if not range_on:
                        return _ward_style
                    lo, hi, mode = ndvi_range
                    key = str(row["ma_xa"]).strip()
                    mean = float(stats.loc[key, "ndvi_mean"]) if key in stats.index else None
                    return _range_style(mean is not None and lo <= mean <= hi, mode)

                for _, r in gdf_boundary.iterrows():
                    fc = {"type": "FeatureCollection", "features": [{
                        "type": "Feature", "properties": {"label": ward_label(r)},
                        "geometry": r.geometry.__geo_interface__,
                    }]}
                    gj = folium.GeoJson(
                        fc, style_function=_style_for(r), highlight_function=_ward_highlight,
                        tooltip=folium.GeoJsonTooltip(fields=["label"], labels=False, sticky=True),
                    )
                    gj.add_child(popup_for(r))
                    gj.add_to(group)
                group.add_to(m)
                built = True
            except Exception as e:
                print(f"⚠️ Không dựng được popup theo phường/xã, dùng ranh giới đơn giản: {e}")
        if not built:   # file ranh giới khác cấu trúc hoặc lỗi -> giữ cách hiển thị cũ
            folium.GeoJson(
                gdf_boundary,
                name="Ranh giới hành chính HCM-34",
                style_function=lambda f: {'fillColor': 'transparent', 'color': '#FFFFFF',
                                          'weight': 2.0, 'dashArray': '4, 4', 'fillOpacity': 0},
                tooltip=folium.GeoJsonTooltip(fields=[name_col], aliases=['Thông tin:']) if name_col else None,
            ).add_to(m)

    if gdf_boundary is not None and selected_district and selected_district != "Toàn tỉnh/TP":
        target = _find_feature(gdf_boundary, lat, lng)
        if target is not None:
            folium.GeoJson(
                target, name="Viền sáng",
                style_function=lambda f: {'fillOpacity': 0, 'color': '#D946EF', 'weight': 9, 'opacity': 0.25},
            ).add_to(m)
            sel_layer = folium.GeoJson(
                target, name="Khu vực đang chọn",
                style_function=lambda f: {'fillColor': '#D946EF', 'fillOpacity': 0.12,
                                          'color': '#D946EF', 'weight': 3, 'opacity': 1},
                tooltip=folium.GeoJsonTooltip(fields=[name_col], aliases=['Khu vực:']) if name_col else None,
            )
            if popup_for is not None:
                sel_layer.add_child(popup_for(target.iloc[0]))
            sel_layer.add_to(m)
            minx, miny, maxx, maxy = target.total_bounds
            m.fit_bounds([[miny, minx], [maxy, maxx]], padding=(30, 30), max_zoom=16)

    # 4. Tiện ích: toàn màn hình + quản lý lớp
    Fullscreen(position="topleft", title="Xem toàn màn hình", title_cancel="Thoát toàn màn hình").add_to(m)
    folium.LayerControl().add_to(m)

    # returned_objects=[] -> kéo/zoom bản đồ không làm trang chạy lại
    st_folium(m, width="100%", height=MAP_HEIGHT, key="map_view_component", returned_objects=[])





