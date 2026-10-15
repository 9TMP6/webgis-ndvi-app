# utils/db_writer.py
# Ghi kết quả dự đoán của AI vào bảng public.ndvi_predictions (mỗi mô hình một cột).
import datetime
import pandas as pd
from sqlalchemy import text
from utils.data_loader import get_db_engine

# Tên cột KHÔNG thể truyền bằng tham số SQL, nên chỉ cho phép các cột nằm trong danh sách này
MODEL_COLUMNS = {"LSTM": "ndvi_lstm", "GRU": "ndvi_gru", "CNNLSTM": "ndvi_cnnlstm"}

# Chỉ ghi khi kết quả phủ ít nhất 90% số ô lưới (tránh ghi dở dang chỉ ~25% ô mẫu)
MIN_COVERAGE = 0.9


def _result(status: str, message: str, rows: int = 0) -> dict:
    return {"status": status, "message": message, "rows": rows}


def save_predictions(df: pd.DataFrame, model_name: str, year: int, month: int,
                     report: dict = None, overwrite: bool = False) -> dict:
    """
    Ghi cột ndvi_<model> của bảng ndvi_predictions cho tháng (year, month).

    - overwrite=False (tự động): nếu CSDL đã có dữ liệu của đúng mô hình + tháng này thì BỎ QUA;
      nếu chưa đủ thì chỉ điền vào những ô còn trống (NULL), không đè giá trị cũ.
    - overwrite=True (nút quản trị): ghi đè tất cả.
    - Chỉ ghi khi kết quả THẬT SỰ do mô hình ONNX tạo ra (report["backend"] == "onnx").
      Nếu app đã tự chuyển sang Ridge/persistence thì không ghi, tránh lưu nhầm vào cột của mô hình.

    Trả về dict: {"status": "saved" | "skipped_exists" | "skipped_partial" | "skipped_not_model" | "error",
                  "message": str, "rows": int}
    """
    col = MODEL_COLUMNS.get(model_name)
    if col is None:
        return _result("error", f"Mô hình '{model_name}' không có cột tương ứng trong CSDL.")

    if report is not None and report.get("backend") != "onnx":
        return _result("skipped_not_model",
                       f"Không lưu: kết quả lần này do '{report.get('backend')}' tạo ra, không phải mô hình {model_name}.")

    if df is None or df.empty or "grid_id" not in df.columns:
        return _result("error", "Không có dữ liệu dự đoán để lưu.")

    try:
        d = df[["grid_id", "ndvi_mean"]].dropna().drop_duplicates("grid_id").copy()
        d["grid_id"] = d["grid_id"].astype(int)
        d["ndvi_mean"] = d["ndvi_mean"].astype(float)

        engine = get_db_engine()
        with engine.connect() as conn:
            n_grid = int(conn.execute(text("SELECT COUNT(*) FROM public.grid_cells")).scalar())
            n_exist = int(conn.execute(
                text(f"SELECT COUNT(*) FROM public.ndvi_predictions "
                     f"WHERE date = make_date(:y, :m, 1) AND {col} IS NOT NULL"),
                {"y": int(year), "m": int(month)},
            ).scalar())

        if len(d) < MIN_COVERAGE * n_grid:
            return _result("skipped_partial",
                           f"Không lưu: kết quả chỉ có {len(d):,}/{n_grid:,} ô (chưa phủ đủ toàn bản đồ).")
        if not overwrite and n_exist >= MIN_COVERAGE * n_grid:
            return _result("skipped_exists",
                           f"CSDL đã có dự đoán {model_name} cho tháng {month}/{year} ({n_exist:,} ô), không ghi lại.")

        date_val = datetime.date(int(year), int(month), 1)
        rows = [(date_val, int(g), float(v)) for g, v in zip(d["grid_id"], d["ndvi_mean"])]

        if overwrite:
            set_clause = f"{col} = EXCLUDED.{col}"                       # ghi đè
        else:
            set_clause = f"{col} = COALESCE(p.{col}, EXCLUDED.{col})"   # chỉ điền ô còn trống

        sql = (f"INSERT INTO public.ndvi_predictions AS p (date, grid_id, {col}) VALUES %s "
               f"ON CONFLICT (date, grid_id) DO UPDATE SET {set_clause}")

        from psycopg2.extras import execute_values
        raw = engine.raw_connection()
        try:
            cur = raw.cursor()
            execute_values(cur, sql, rows, page_size=5000)
            raw.commit()
        except Exception:
            raw.rollback()
            raise
        finally:
            raw.close()

        verb = "Đã ghi đè" if overwrite else "Đã lưu"
        return _result("saved", f"{verb} {len(rows):,} ô dự đoán {model_name} (tháng {month}/{year}) vào CSDL.", len(rows))

    except Exception as e:
        return _result("error", f"Lỗi khi lưu vào CSDL: {e}")
