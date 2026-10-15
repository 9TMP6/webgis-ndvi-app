# utils/tiff_export.py
# Xuất NDVI dạng GeoTIFF (float32, có toạ độ WGS84) để mở trực tiếp trong QGIS/ArcGIS.
# Chỉ cần thư viện tifffile (nhỏ, không cần GDAL/rasterio).
import io
import numpy as np
import pandas as pd

NODATA = -9999.0


def generate_ndvi_geotiff(df: pd.DataFrame, max_side: int = 1000):
    """-> bytes của file .tif, hoặc None nếu không đủ dữ liệu / lỗi."""
    import tifffile
    from utils.map_utils import _export_boundaries, _split_main_and_far, _export_interpolate

    if df is None or df.empty:
        return None
    d = df.dropna(subset=["longitude", "latitude", "ndvi_mean"])
    if d.empty:
        return None
    lons = d["longitude"].to_numpy(float)
    lats = d["latitude"].to_numpy(float)
    vals = d["ndvi_mean"].to_numpy(float)

    _, geom = _export_boundaries()
    m_main, _ = _split_main_and_far(lons, lats)          # giống ảnh PNG: lấy phần đất liền
    res = _export_interpolate(lons[m_main], lats[m_main], vals[m_main], geom, max_side)
    if res is None:
        return None
    grid, (lon_min, lon_max, lat_min, lat_max) = res

    arr = np.ma.filled(grid.astype("float32"), NODATA)   # ngoài ranh giới = NODATA
    arr = np.flipud(arr)                                  # GeoTIFF: hàng 0 là phía Bắc
    rows, cols = arr.shape
    dx, dy = (lon_max - lon_min) / cols, (lat_max - lat_min) / rows

    extratags = [
        (33550, 12, 3, (dx, dy, 0.0), True),                                   # ModelPixelScale
        (33922, 12, 6, (0.0, 0.0, 0.0, lon_min, lat_max, 0.0), True),          # ModelTiepoint (góc trên-trái)
        (34735, 3, 16, (1, 1, 0, 3,                                            # GeoKeyDirectory
                        1024, 0, 1, 2,        # GTModelType = Geographic
                        1025, 0, 1, 1,        # GTRasterType = PixelIsArea
                        2048, 0, 1, 4326), True),  # EPSG:4326
        (42113, 2, 0, str(int(NODATA)), True),                                 # GDAL_NODATA
    ]
    buf = io.BytesIO()
    tifffile.imwrite(buf, arr, photometric="minisblack", compression="deflate", extratags=extratags)
    return buf.getvalue()
