# utils/model_metrics.py
# Tự tính & lưu chỉ số chính xác (R², MAE, RMSE) của từng mô hình theo từng THÁNG vào bảng model_metrics.
# 1 dòng = 1 mô hình + 1 tháng. Chỉ số tính trên TẤT CẢ ô lưới của tháng đó (dự đoán so với quan trắc).
import re
import pandas as pd
from sqlalchemy import text, bindparam
from utils.data_loader import get_db_engine
from utils.db_writer import MODEL_COLUMNS
from utils.compare_data import MIN_PRED_RATIO, load_model_metrics

# Số ô có CẢ quan trắc lẫn dự đoán tối thiểu để chỉ số đáng tin (tháng nhiều mây sẽ bị bỏ qua)
MIN_MATCHED_CELLS = 500


def _norm(name) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(name)).upper()


def ensure_metrics(start, end, force: bool = False) -> dict:
    """
    Với mỗi (mô hình, tháng) trong [start, end]:
      - đã có dòng trong model_metrics  -> giữ nguyên (trừ khi force=True thì xoá tính lại)
      - chưa có, và ndvi_predictions đã đủ ô (>= 90% lưới) và có quan trắc để so -> TÍNH rồi lưu
      - ngược lại -> bỏ qua (tháng đó sẽ không hiện lên bảng)
    Trả về {"computed": int, "skipped_no_obs": int, "error": str|None}
    """
    s, e = pd.Timestamp(start).date(), pd.Timestamp(end).date()
    out = {"computed": 0, "skipped_no_obs": 0, "error": None}
    try:
        with get_db_engine().begin() as conn:
            n_grid = int(conn.execute(text("SELECT COUNT(*) FROM public.grid_cells")).scalar())
            p = {"s": s, "e": e}
            if force:
                conn.execute(text("DELETE FROM public.model_metrics WHERE date BETWEEN :s AND :e"), p)
            have = {(_norm(m), d) for m, d in conn.execute(
                text("SELECT model, date FROM public.model_metrics WHERE date BETWEEN :s AND :e"), p)}

            for model, col in MODEL_COLUMNS.items():        # tên cột lấy từ danh sách cố định -> an toàn
                cov = conn.execute(text(
                    f"SELECT date, COUNT({col}) FROM public.ndvi_predictions "
                    f"WHERE date BETWEEN :s AND :e GROUP BY date"), p).all()
                todo = [d for d, n in cov if n >= MIN_PRED_RATIO * n_grid and (model, d) not in have]
                if not todo:
                    continue
                q = text(f"""
                    WITH j AS (
                        SELECT p.date AS d, o.ndvi_mean::float8 AS o, p.{col}::float8 AS p
                        FROM public.ndvi_predictions p
                        JOIN public.ndvi_observed o ON o.grid_id = p.grid_id AND o.date = p.date
                        WHERE p.date IN :dates AND p.{col} IS NOT NULL AND o.ndvi_mean IS NOT NULL
                    ), m AS (SELECT d, AVG(o) AS mo FROM j GROUP BY d)
                    SELECT j.d AS date, COUNT(*) AS n,
                           AVG(ABS(j.p - j.o)) AS mae,
                           SQRT(AVG((j.p - j.o) ^ 2)) AS rmse,
                           1 - SUM((j.p - j.o) ^ 2) / NULLIF(SUM((j.o - m.mo) ^ 2), 0) AS r2
                    FROM j JOIN m ON m.d = j.d GROUP BY j.d
                """).bindparams(bindparam("dates", expanding=True))
                rows = conn.execute(q, {"dates": todo}).mappings().all()

                good = [{"model": model, "date": r["date"], "mae": r["mae"], "rmse": r["rmse"],
                         "r2": r["r2"], "n": int(r["n"])}
                        for r in rows if int(r["n"]) >= MIN_MATCHED_CELLS]
                out["skipped_no_obs"] += len(todo) - len(good)
                if good:
                    conn.execute(text("""
                        INSERT INTO public.model_metrics (model, date, mae, rmse, r2, n_cells)
                        VALUES (:model, :date, :mae, :rmse, :r2, :n)
                        ON CONFLICT (model, date) DO UPDATE
                        SET mae = EXCLUDED.mae, rmse = EXCLUDED.rmse, r2 = EXCLUDED.r2, n_cells = EXCLUDED.n_cells
                    """), good)
                    out["computed"] += len(good)
        if out["computed"] or force:
            load_model_metrics.clear()
    except Exception as ex:
        out["error"] = str(ex)
    return out
