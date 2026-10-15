# utils/app_settings.py
# Cài đặt dùng chung cho mọi người dùng (lưu trong CSDL, không phải session riêng của từng người).
# Hiện có: mô hình AI mặc định do admin chọn.
import streamlit as st
from sqlalchemy import text
from utils.data_loader import get_db_engine

MODELS = ["LSTM", "GRU", "CNNLSTM"]
DEFAULT_MODEL = "LSTM"
_KEY_MODEL = "default_model"


@st.cache_resource
def _ensure_table():
    """Tạo bảng app_settings nếu chưa có (chạy 1 lần mỗi lần khởi động app)."""
    try:
        with get_db_engine().begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS public.app_settings (
                    key   text PRIMARY KEY,
                    value text NOT NULL
                )
            """))
            # Giống các bảng khác: bật RLS để API công khai của Supabase không ghi được vào bảng này
            conn.execute(text("ALTER TABLE public.app_settings ENABLE ROW LEVEL SECURITY"))
        return True
    except Exception as e:
        print(f"[APP_SETTINGS] Không tạo được bảng app_settings: {e}")
        return False


@st.cache_data(ttl=15, show_spinner=False)
def get_default_model() -> str:
    """Mô hình mặc định hiện tại (ai vào cũng thấy cùng 1 mô hình). Lỗi -> dùng LSTM."""
    if not _ensure_table():
        return DEFAULT_MODEL
    try:
        with get_db_engine().connect() as conn:
            val = conn.execute(text("SELECT value FROM public.app_settings WHERE key = :k"),
                               {"k": _KEY_MODEL}).scalar()
        return val if val in MODELS else DEFAULT_MODEL
    except Exception as e:
        print(f"[APP_SETTINGS] Không đọc được mô hình mặc định: {e}")
        return DEFAULT_MODEL


def set_default_model(model: str) -> bool:
    if model not in MODELS or not _ensure_table():
        return False
    try:
        with get_db_engine().begin() as conn:
            conn.execute(text("""
                INSERT INTO public.app_settings (key, value) VALUES (:k, :v)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """), {"k": _KEY_MODEL, "v": model})
        get_default_model.clear()
        return True
    except Exception as e:
        print(f"[APP_SETTINGS] Không lưu được mô hình mặc định: {e}")
        return False
