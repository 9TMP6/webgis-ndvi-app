# dark_theme.py  (đặt cùng thư mục với app.py)
"""
CSS BỔ SUNG cho chế độ tối, viết khớp với utils/styles.py hiện tại.
Không thay thế CUSTOM_CSS, chỉ ghi đè các chỗ đang ép màu sáng khi người dùng đang dùng theme Dark.
"""
import streamlit as st


def is_dark_theme() -> bool:
    """True nếu người dùng đang ở theme Dark (chọn Dark, hoặc 'System' mà máy đang dùng chế độ tối)."""
    try:
        t = st.context.theme
        return (getattr(t, "type", None) or getattr(t, "base", None)) == "dark"
    except Exception:       # bản Streamlit cũ chưa có st.context.theme -> coi như theme sáng
        return False


DARK_CSS = """
<style>
:root {
    --g-900: #BBF7D0; --g-700: #4ADE80; --g-600: #22C55E; --g-500: #22C55E;
    --g-100: #14532D; --g-50: #0F2A1B;
    --card: #16271D; --line: #2A4335; --text: #E3F1E8; --muted: #9DB8A6;
    --shadow-sm: none; --shadow-md: 0 6px 16px rgba(0, 0, 0, 0.45);
}

.stApp {
    background: linear-gradient(180deg, #0B1510 0%, #0E1A13 45%, #0B1510 100%) !important;
    color: var(--text);
}
[data-testid="stHeader"] { background: rgba(14, 26, 19, 0.85) !important; }

/* Tiêu đề từng khu vực + gợi ý "Bắt đầu" */
.section-head { border-bottom-color: #2A4335 !important; }
.empty-hint { background: var(--card) !important; border-color: #2F5A40 !important; color: var(--text) !important; }
.tag-idle { background: #1B2D22 !important; color: var(--muted) !important; border-color: var(--line) !important; }

/* Sidebar + khung "Bộ lọc dự báo", "Cấu hình bản đồ"... */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F1D16 0%, #0C1711 100%) !important;
    border-right: 1px solid var(--line);
}
div[data-testid="stExpander"] { background: var(--card) !important; border: 1px solid var(--line) !important; }
div[data-testid="stExpander"] summary,
div[data-testid="stExpander"] summary p,
div[data-testid="stExpander"] label,
div[data-testid="stExpander"] p { color: var(--text) !important; }

/* Nút tải xuống */
[data-testid="stDownloadButton"] button {
    background: var(--card) !important; color: var(--g-700) !important; border: 1px solid var(--line) !important;
}
[data-testid="stDownloadButton"] button:hover { background: var(--g-50) !important; border-color: var(--g-600) !important; }

/* Chú giải NDVI (màu chữ đang viết thẳng trong metrics_view.py) */
.legend-panel div, .legend-panel span { color: #B7CFBE !important; }

/* Thẻ thông tin dưới biểu đồ: nền sáng + chữ sáng sẽ mất chữ khi hover, nên đổi sang nền tối */
.info-card { background: #12261A !important; border-color: #25402F !important; }
.info-card:hover { background: #1A3324 !important; }
.info-card .lbl { color: var(--muted) !important; }
.info-card .val { color: var(--g-900) !important; }

/* Hộp thông báo st.info / st.success... */
div[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) {
    background: #12261A !important; color: var(--text) !important; border: 1px solid #25402F !important;
}
</style>
"""
