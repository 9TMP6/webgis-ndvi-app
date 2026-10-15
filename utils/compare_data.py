# utils/compare_data.py
# Lấy dữ liệu từ CSDL để so sánh NDVI quan trắc với 3 mô hình (KHÔNG chạy dự đoán).
import re
import pandas as pd
import streamlit as st
from sqlalchemy import text
from utils.data_loader import get_db_engine

START_DATE = pd.Timestamp("2018-01-01")
SERIES = ["Quan trắc (CSDL)", "LSTM", "GRU", "CNNLSTM"]

# Một tháng chỉ được vẽ khi có ĐỦ ô lưới; thiếu nhiều -> để trống (đứt khúc) thay vì vẽ số sai lệch
MIN_PRED_RATIO = 0.9      # dự đoán: >= 90% số ô lưới (giống db_writer.MIN_COVERAGE)
MIN_OBS_CELLS = 20000     # quan trắc: >= 20.000 ô (giống ngưỡng lọc mây trong data_loader)


@st.cache_data(ttl=300, show_spinner=False)
def get_last_month():
    """Tháng cuối cùng có trong CSDL (quan trắc hoặc dự đoán)."""
    with get_db_engine().connect() as conn:
        v = conn.execute(text(
            "SELECT GREATEST((SELECT MAX(date) FROM public.ndvi_observed),"
            "                (SELECT MAX(date) FROM public.ndvi_predictions))"
        )).scalar()
    return pd.Timestamp(v) if v is not None else None


@st.cache_data(ttl=300, show_spinner=False)
def load_monthly_comparison(start: str, end: str) -> pd.DataFrame:
    """
    Mỗi tháng = trung bình NDVI của tất cả ô lưới có dữ liệu trong tháng đó.
    Trả về cột: date, 'Quan trắc (CSDL)', LSTM, GRU, CNNLSTM. Tháng thiếu/không đủ ô = NaN.
    """
    p = {"s": pd.Timestamp(start).date(), "e": pd.Timestamp(end).date()}
    engine = get_db_engine()
    with engine.connect() as conn:
        n_grid = int(conn.execute(text("SELECT COUNT(*) FROM public.grid_cells")).scalar())
    obs = pd.read_sql(text("""
        SELECT date, AVG(ndvi_mean)::float8 AS v, COUNT(ndvi_mean) AS n
        FROM public.ndvi_observed WHERE date BETWEEN :s AND :e GROUP BY date
    """), engine, params=p)
    pred = pd.read_sql(text("""
        SELECT date,
               AVG(ndvi_lstm)::float8 AS lstm,       COUNT(ndvi_lstm) AS n_lstm,
               AVG(ndvi_gru)::float8 AS gru,         COUNT(ndvi_gru) AS n_gru,
               AVG(ndvi_cnnlstm)::float8 AS cnnlstm, COUNT(ndvi_cnnlstm) AS n_cnnlstm
        FROM public.ndvi_predictions WHERE date BETWEEN :s AND :e GROUP BY date
    """), engine, params=p)

    months = pd.date_range(p["s"], p["e"], freq="MS")
    out = pd.DataFrame(index=months)

    obs["date"] = pd.to_datetime(obs["date"])
    o = obs.set_index("date")
    min_obs = min(MIN_OBS_CELLS, MIN_PRED_RATIO * n_grid)
    out["Quan trắc (CSDL)"] = o["v"].where(o["n"] >= min_obs)

    pred["date"] = pd.to_datetime(pred["date"])
    pr = pred.set_index("date")
    for name, col in (("LSTM", "lstm"), ("GRU", "gru"), ("CNNLSTM", "cnnlstm")):
        out[name] = pr[col].where(pr[f"n_{col}"] >= MIN_PRED_RATIO * n_grid) if not pr.empty else float("nan")

    out.index.name = "date"
    return out.reset_index()


@st.cache_data(ttl=300, show_spinner=False)
def load_model_metrics(start: str, end: str) -> pd.DataFrame:
    """Đọc nguyên bảng model_metrics (đã tính sẵn), chỉ lọc theo khoảng thời gian."""
    df = pd.read_sql(text("""
        SELECT model, date, mae::float8 AS mae, rmse::float8 AS rmse, r2::float8 AS r2, n_cells
        FROM public.model_metrics WHERE date BETWEEN :s AND :e ORDER BY date, model
    """), get_db_engine(), params={"s": pd.Timestamp(start).date(), "e": pd.Timestamp(end).date()})
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        # "CNN-LSTM", "cnn_lstm", "cnnlstm" -> "CNNLSTM"
        df["model"] = df["model"].map(lambda s: re.sub(r"[^A-Za-z0-9]", "", str(s)).upper())
    return df
