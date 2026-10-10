# components/layout.py
import json
import datetime
import streamlit as st
import streamlit.components.v1 as components

APP_NAME = "GEO-NDVI"
APP_FULL_NAME = "Hệ thống Giám sát và Dự báo Chỉ số Thực vật NDVI"
APP_TAGLINE = "Ứng dụng viễn thám và AI theo dõi biến động thảm thực vật tại TP. Hồ Chí Minh"
TEAM = "Nhóm 3 – Lớp CNTT5"
SCHOOL = "Trường Đại học Tài nguyên và Môi trường TP. Hồ Chí Minh"

SEO_DESCRIPTION = (
    "GEO-NDVI là hệ thống giám sát và dự báo chỉ số thực vật NDVI tại TP. Hồ Chí Minh "
    "bằng viễn thám và trí tuệ nhân tạo (AI), kèm bản đồ trực quan, biểu đồ biến động 12 tháng "
    "và xuất dữ liệu CSV, PNG."
)
SEO_KEYWORDS = "NDVI, GEO-NDVI, viễn thám, chỉ số thực vật, dự báo NDVI, AI, bản đồ NDVI, TP. Hồ Chí Minh, WebGIS"


def format_period(t) -> str:
    """Trả về chuỗi 'MM/YYYY' từ datetime/Timestamp."""
    if hasattr(t, "month") and hasattr(t, "year"):
        return f"{t.month:02d}/{t.year}"
    return str(t)


def inject_ui_effects():
    """
    Chèn vào trang chính (qua iframe cùng origin):
    - Nút cuộn lên đầu trang
    - Thẻ meta mô tả/từ khóa, lang="vi"
    Lưu ý: Streamlit hiển thị bằng JavaScript nên công cụ tìm kiếm có thể không đọc được các thẻ này.
    """
    cfg = json.dumps({
        "description": SEO_DESCRIPTION,
        "keywords": SEO_KEYWORDS,
        "title": f"{APP_NAME} | {APP_FULL_NAME}",
    })
    components.html(
        f"""
        <script>
        (function() {{
            const cfg = {cfg};
            let doc;
            try {{ doc = window.parent.document; }} catch (e) {{ return; }}

            doc.documentElement.lang = "vi";
            const setMeta = (attr, key, value) => {{
                let el = doc.head.querySelector('meta[' + attr + '="' + key + '"]');
                if (!el) {{ el = doc.createElement('meta'); el.setAttribute(attr, key); doc.head.appendChild(el); }}
                el.setAttribute('content', value);
            }};
            setMeta('name', 'description', cfg.description);
            setMeta('name', 'keywords', cfg.keywords);
            setMeta('property', 'og:title', cfg.title);
            setMeta('property', 'og:description', cfg.description);
            setMeta('property', 'og:type', 'website');
            setMeta('property', 'og:locale', 'vi_VN');

            const getScroller = () =>
                doc.querySelector('[data-testid="stMain"]') ||
                doc.querySelector('section.main') ||
                doc.querySelector('.main');

            let btn = doc.getElementById('geo-scroll-top');
            if (!btn) {{
                btn = doc.createElement('button');
                btn.id = 'geo-scroll-top';
                btn.type = 'button';
                btn.title = 'Lên đầu trang';
                btn.setAttribute('aria-label', 'Lên đầu trang');
                btn.textContent = '↑';
                doc.body.appendChild(btn);
            }}
            const sc = getScroller();
            const target = sc || window.parent;
            const getTop = () => sc ? sc.scrollTop : window.parent.scrollY;
            const update = () => btn.classList.toggle('show', getTop() > 300);
            if (!btn.dataset.bound) {{
                btn.dataset.bound = '1';
                btn.addEventListener('click', () => target.scrollTo({{ top: 0, behavior: 'smooth' }}));
                target.addEventListener('scroll', update, {{ passive: true }});
            }}
            update();
        }})();
        </script>
        """,
        height=0,
    )


def render_header():
    st.markdown(
        f"""
        <header class="hero">
            <div class="hero-text">
                <h1>{APP_NAME} – {APP_FULL_NAME}</h1>
                <p>{APP_TAGLINE}</p>
            </div>
            <div class="hero-badges">
                <span class="badge"><span class="pulse-dot"></span>TP. Hồ Chí Minh</span>
                <span class="badge">🧠 Mô hình LSTM (ONNX)</span>
            </div>
        </header>
        """,
        unsafe_allow_html=True,
    )


def render_section_title(title: str, subtitle: str = "", source: str = None):
    """
    source: "db" (dữ liệu CSDL), "ai" (dự báo AI) hoặc None (chưa chạy).
    """
    if source == "ai":
        tag = '<span class="tag tag-ai">🤖 Dự báo bằng AI</span>'
    elif source == "db":
        tag = '<span class="tag tag-db">🛰️ Dữ liệu quan trắc từ CSDL</span>'
    else:
        tag = '<span class="tag tag-idle">⏳ Chưa chạy dự báo</span>'

    sub_html = f'<p class="sub">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f"""
        <section class="section-head">
            <div>
                <h2>{title}</h2>
                {sub_html}
            </div>
            {tag}
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_footer():
    year = datetime.datetime.now().year
    st.markdown(
        f"""
        <div class="site-footer">
            <div class="footer-grid">
                <div>
                    <h4>{APP_NAME}</h4>
                    <p>{APP_FULL_NAME}. Kết hợp dữ liệu viễn thám, cơ sở dữ liệu ô lưới và mô hình học sâu
                    để theo dõi và dự báo biến động thảm thực vật tại TP. Hồ Chí Minh.</p>
                </div>
                <div>
                    <h4>Chức năng chính</h4>
                    <ul>
                        <li>🗺️ Bản đồ NDVI theo tháng/năm</li>
                        <li>🤖 Dự báo NDVI bằng AI</li>
                        <li>📈 Biểu đồ biến động 12 tháng</li>
                        <li>📥 Xuất dữ liệu CSV và ảnh PNG</li>
                    </ul>
                </div>
                <div>
                    <h4>Thông tin dự án</h4>
                    <ul>
                        <li>👥 {TEAM}</li>
                        <li>🎓 {SCHOOL}</li>
                        <li>📍 Khu vực nghiên cứu: TP. Hồ Chí Minh</li>
                    </ul>
                </div>
            </div>
            <div class="footer-bottom">
                © {year} {TEAM} – {SCHOOL}. Bảo lưu mọi quyền.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
