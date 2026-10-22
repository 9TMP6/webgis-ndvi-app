# utils/gee_loader.py
# Tự động lấy NDVI tháng mới từ Google Earth Engine -> nạp vào bảng ndvi_observed.
# Quy trình BẤT ĐỒNG BỘ (GEE chạy 10-15 phút/tháng nên không bắt người dùng chờ):
#   Bước 1  Bấm "Bắt đầu"      -> app gửi nhiệm vụ lên GEE rồi thôi (lưu mã nhiệm vụ vào CSDL).
#   Bước 2  Bấm "Kiểm tra"      -> khi GEE báo xong, app tải kết quả, ghép grid_id, ghi CSDL.
# Nhiệm vụ chạy trên máy chủ GEE, đóng trình duyệt hay tắt app vẫn không mất.
import datetime
import io
import json
import pandas as pd
import streamlit as st
from sqlalchemy import text
from utils.data_loader import get_db_engine

# ====================== CẤU HÌNH (giữ ĐÚNG như notebook Colab cũ) ======================
SHP_PATH = "data/hcm_post_merger.shp"     # shapefile gốc dùng để tạo lưới (xem hướng dẫn)
ASSET_FOLDER = "ndvi_tmp"                 # thư mục tạm trên GEE, kết quả được xoá sau khi nạp
S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
MAX_CLOUD_PERCENT = 30                    # CLOUDY_PIXEL_PERCENTAGE < 30
SCALE = 10
CRS = "EPSG:32648"                        # UTM 48N, lưới 500 m
GRID_SIZE = 500
FIRST_MONTH = pd.Timestamp("2016-01-01")  # dùng khi ndvi_observed còn trống
# ====================== QUY TẮC AN TOÀN ======================
DELAY_DAYS = 5            # chỉ xử lý tháng M khi đã qua ngày (cuối tháng M + 5 ngày): chờ ảnh Sentinel-2 về đủ
MAX_MONTHS_PER_JOB = 6    # mỗi lần chỉ gửi tối đa 6 tháng
MIN_VALID_CELLS = 20000   # tháng có ít hơn số ô hợp lệ này thì KHÔNG ghi (giống ngưỡng của app)
_JOB_KEY = "gee_job"
_FINAL = {"INGESTED", "FAILED", "CANCELLED", "SKIPPED_LOW", "NO_IMAGES"}


# ====================== KẾT NỐI GEE ======================
@st.cache_resource
def _init_ee():
    import ee
    cfg = st.secrets["gee"]
    cred = ee.ServiceAccountCredentials(cfg["service_account"], key_data=cfg["private_key_json"])
    ee.Initialize(cred, project=cfg["project"])
    return ee


# ====================== TẠO LƯỚI + TÍNH NDVI THÁNG (copy từ notebook) ======================
def _build_boundary_and_grid(ee):
    import geopandas as gpd
    gdf = gpd.read_file(SHP_PATH).to_crs("EPSG:4326")
    if (~gdf.geometry.is_valid).sum() > 0:
        gdf["geometry"] = gdf.geometry.buffer(0)
    boundary = ee.FeatureCollection(json.loads(gdf.to_json()))
    grid_raw = boundary.geometry().coveringGrid(proj=ee.Projection(CRS), scale=GRID_SIZE)
    grid = ee.FeatureCollection(grid_raw).map(
        lambda f: f.set("grid_code", ee.String("GRID_").cat(ee.String(f.id()))))
    return boundary, grid


def _month_collection(ee, boundary, grid, year: int, month: int):
    """Trả về (FeatureCollection thống kê theo ô, số ảnh). Không có ảnh -> (None, 0)."""
    start = ee.Date.fromYMD(year, month, 1)
    end = start.advance(1, "month")

    def mask_clouds(img):
        scl = img.select("SCL")
        m = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11))
        return img.normalizedDifference(["B8", "B4"]).rename("NDVI").updateMask(m)

    col = (ee.ImageCollection(S2_COLLECTION).filterBounds(boundary).filterDate(start, end)
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUD_PERCENT)).map(mask_clouds))
    n = int(col.size().getInfo())
    if n == 0:
        return None, 0
    reducer = (ee.Reducer.mean().combine(ee.Reducer.min(), sharedInputs=True)
               .combine(ee.Reducer.max(), sharedInputs=True))
    stats = col.mean().rename("NDVI").reduceRegions(
        collection=grid, reducer=reducer, scale=SCALE, crs=CRS, tileScale=4)
    out = stats.map(lambda f: ee.Feature(None, {
        "grid_code": f.get("grid_code"), "ndvi_mean": f.get("mean"),
        "ndvi_min": f.get("min"), "ndvi_max": f.get("max")}))
    return out, n


# ====================== XÁC ĐỊNH THÁNG CẦN CẬP NHẬT ======================
def last_db_month():
    with get_db_engine().connect() as conn:
        v = conn.execute(text("SELECT MAX(date) FROM public.ndvi_observed")).scalar()
    return pd.Timestamp(v) if v is not None else None


def pending_months(today=None, last=None):
    """Các tháng từ (tháng cuối trong CSDL + 1) tới tháng ĐÃ KẾT THÚC và đủ DELAY_DAYS ngày chờ ảnh."""
    today = pd.Timestamp(today or datetime.date.today())
    last = last if last is not None else last_db_month()
    m = (last + pd.DateOffset(months=1)) if last is not None else FIRST_MONTH
    out = []
    while today >= m + pd.DateOffset(months=1) + pd.Timedelta(days=DELAY_DAYS):
        out.append(m)
        m = m + pd.DateOffset(months=1)
    return out[:MAX_MONTHS_PER_JOB]


# ====================== LƯU TRẠNG THÁI NHIỆM VỤ (bảng app_settings) ======================
def _load_job():
    with get_db_engine().connect() as conn:
        v = conn.execute(text("SELECT value FROM public.app_settings WHERE key = :k"), {"k": _JOB_KEY}).scalar()
    return json.loads(v) if v else None


def _save_job(job):
    with get_db_engine().begin() as conn:
        if job is None:
            conn.execute(text("DELETE FROM public.app_settings WHERE key = :k"), {"k": _JOB_KEY})
        else:
            conn.execute(text("""INSERT INTO public.app_settings (key, value) VALUES (:k, :v)
                                 ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"""),
                         {"k": _JOB_KEY, "v": json.dumps(job, ensure_ascii=False)})


# ====================== BƯỚC 1: GỬI NHIỆM VỤ ======================
def start_job(months):
    ee = _init_ee()
    project = st.secrets["gee"]["project"]
    folder = f"projects/{project}/assets/{ASSET_FOLDER}"
    try:
        ee.data.createAsset({"type": "FOLDER"}, folder)
    except Exception:
        pass                                        # đã có thư mục
    boundary, grid = _build_boundary_and_grid(ee)
    items = []
    for m in months:
        label = f"{m.year}-{m.month:02d}"
        fc, n_img = _month_collection(ee, boundary, grid, m.year, m.month)
        if fc is None:
            items.append({"month": label, "state": "NO_IMAGES", "msg": "Không có ảnh Sentinel-2 đạt điều kiện"})
            continue
        asset_id = f"{folder}/ndvi_{m.year}_{m.month:02d}"
        try:
            ee.data.deleteAsset(asset_id)           # xoá bản cũ còn sót (nếu có)
        except Exception:
            pass
        task = ee.batch.Export.table.toAsset(collection=fc, description=f"ndvi_{m.year}_{m.month:02d}",
                                             assetId=asset_id)
        task.start()
        items.append({"month": label, "state": "SUBMITTED", "task_id": task.id, "asset": asset_id,
                      "msg": f"{n_img} ảnh Sentinel-2"})
    _save_job({"created": datetime.datetime.now().isoformat(timespec="seconds"), "items": items})


# ====================== BƯỚC 2: KIỂM TRA + NẠP CSDL ======================
def _ingest(ee, item):
    import requests
    from psycopg2.extras import execute_values
    fc = ee.FeatureCollection(item["asset"])
    url = fc.getDownloadURL("csv", selectors=["grid_code", "ndvi_mean", "ndvi_min", "ndvi_max"])
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))

    engine = get_db_engine()
    ids = pd.read_sql(text("SELECT grid_id, grid_code FROM public.grid_cells"), engine)
    df = df.merge(ids, on="grid_code", how="inner")             # gắn grid_id của CSDL
    df = df.dropna(subset=["ndvi_mean"])                         # bỏ ô bị mây
    if len(df) < MIN_VALID_CELLS:
        return {"state": "SKIPPED_LOW", "msg": f"Chỉ có {len(df):,} ô hợp lệ (< {MIN_VALID_CELLS:,}), không ghi."}

    y, mth = map(int, item["month"].split("-"))
    date_val = datetime.date(y, mth, 1)
    d = df[["grid_id", "ndvi_mean", "ndvi_min", "ndvi_max"]].astype(object)
    d = d.where(d.notna(), None)
    rows = [(date_val, int(a), b, c, e) for a, b, c, e in d.itertuples(index=False, name=None)]

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        execute_values(cur, """INSERT INTO public.ndvi_observed (date, grid_id, ndvi_mean, ndvi_min, ndvi_max)
                               VALUES %s ON CONFLICT (date, grid_id) DO UPDATE SET
                               ndvi_mean = EXCLUDED.ndvi_mean, ndvi_min = EXCLUDED.ndvi_min,
                               ndvi_max = EXCLUDED.ndvi_max""", rows, page_size=5000)
        cur.execute("DELETE FROM public.model_metrics WHERE date = %s", (date_val,))  # quan trắc đổi -> tính lại chỉ số
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()
    try:
        ee.data.deleteAsset(item["asset"])
    except Exception:
        pass
    st.cache_data.clear()
    return {"state": "INGESTED", "msg": f"Đã ghi {len(rows):,} ô"}


def refresh_job():
    ee = _init_ee()
    job = _load_job()
    if not job:
        return
    for it in job["items"]:
        if it["state"] in _FINAL:
            continue
        try:
            if it["state"] != "COMPLETED":
                s = ee.data.getTaskStatus(it["task_id"])[0]
                it["state"] = s.get("state", it["state"])
                if it["state"] == "FAILED":
                    it["msg"] = s.get("error_message", "")
            if it["state"] == "COMPLETED":
                it.update(_ingest(ee, it))
        except Exception as e:
            it["msg"] = f"Lỗi: {e}"
    _save_job(job)


# ====================== GIAO DIỆN (gọi 1 dòng trong menu admin) ======================
def render_gee_panel():
    st.markdown("**🛰️ Cập nhật dữ liệu từ GEE**")
    if "gee" not in st.secrets:
        st.caption("Chưa cấu hình mục [gee] trong secrets.")
        return
    try:
        job = _load_job()
    except Exception as e:
        st.error(f"Không đọc được trạng thái: {e}")
        return

    if job:
        icon = {"INGESTED": "✅", "COMPLETED": "⏳", "RUNNING": "🔄", "SUBMITTED": "🕒", "READY": "🕒",
                "FAILED": "❌", "SKIPPED_LOW": "⚠️", "NO_IMAGES": "⚠️", "CANCELLED": "⚠️"}
        for it in job["items"]:
            st.caption(f"{icon.get(it['state'], '•')} {it['month']}: {it['state']} {it.get('msg', '')}")
        done = all(it["state"] in _FINAL for it in job["items"])
        if not done:
            st.caption("GEE xử lý khoảng 10–15 phút mỗi tháng. Có thể đóng trang, quay lại bấm kiểm tra sau.")
            if st.button("🔄 Kiểm tra tiến độ / nạp CSDL", use_container_width=True, key="btn_gee_refresh"):
                with st.spinner("Đang kiểm tra GEE và nạp dữ liệu..."):
                    refresh_job()
                st.rerun()
        else:
            if st.button("Đóng và làm mới", use_container_width=True, key="btn_gee_close"):
                _save_job(None)
                st.rerun()
        return

    try:
        pend = pending_months()
    except Exception as e:
        st.error(f"Không đọc được CSDL: {e}")
        return
    if not pend:
        st.caption(f"Chưa có tháng mới đủ điều kiện (tháng phải kết thúc và qua {DELAY_DAYS} ngày để ảnh về đủ).")
        return
    names = ", ".join(f"{m.month:02d}/{m.year}" for m in pend)
    st.caption(f"Tháng sẽ lấy: {names}")
    if st.button("🚀 Bắt đầu cập nhật từ GEE", use_container_width=True, key="btn_gee_start"):
        with st.spinner("Đang gửi nhiệm vụ lên GEE..."):
            try:
                start_job(pend)
            except Exception as e:
                st.error(f"Không gửi được nhiệm vụ: {e}")
                return
        st.rerun()
