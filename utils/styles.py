# utils/styles.py
# Toàn bộ CSS giao diện GEO-NDVI. Thay cho biến CUSTOM_CSS cũ trong config.py.

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800&display=swap');

:root {
    --g-950: #0B3D20; --g-900: #14532D; --g-700: #15803D; --g-600: #16A34A; --g-500: #22C55E;
    --g-100: #DCFCE7; --g-50: #F0FDF4;
    --card: #FFFFFF; --line: #D7E8DB; --text: #14301F; --muted: #5B7A66;
    --amber: #B45309; --amber-bg: #FEF3C7;
    --shadow-sm: 0 2px 8px rgba(20, 83, 45, 0.07);
    --shadow-md: 0 8px 22px rgba(20, 83, 45, 0.14);
}

html { scroll-behavior: smooth; }
html, body, [class*="css"] { font-size: 14px !important; }
.stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp button, .stApp input, .stApp textarea, .stApp li {
    font-family: 'Be Vietnam Pro', 'Segoe UI', sans-serif;
}
.stApp {
    background: linear-gradient(180deg, #EEF8F0 0%, #F8FCF9 45%, #ECF6EF 100%);
    color: var(--text);
}
.stApp h1, .stApp h2, .stApp h3 { color: var(--g-900); }

/* Ẩn dòng "Made with Streamlit" mặc định, giữ lại thanh header để còn nút mở sidebar */
#MainMenu, footer { visibility: hidden; }
[data-testid="stHeader"] { background: rgba(245, 250, 246, 0.85); backdrop-filter: blur(8px); }
[data-testid="stHeader"] a[href*="github"] { display: none !important; }

/* Vùng nội dung: rộng hơn để bản đồ được ưu tiên */
.block-container {
    padding: 3.4rem 1.6rem 0.5rem 1.6rem !important;
    max-width: 100% !important;
}

/* iframe 0px của script hiệu ứng: không chiếm chỗ */
div[data-testid="stElementContainer"]:has(iframe[height="0"]) {
    position: absolute; height: 0; width: 0; overflow: hidden; margin: 0 !important;
}

/* ===== Header (hero) ===== */
.hero {
    position: relative; overflow: hidden;
    background: linear-gradient(110deg, #14532D 0%, #15803D 45%, #4D9A1E 100%);
    border-radius: 18px; padding: 16px 24px; margin-bottom: 14px;
    display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap;
    box-shadow: 0 8px 24px rgba(22, 101, 52, 0.25);
}
.hero::after {
    content: ""; position: absolute; right: -70px; top: -90px; width: 280px; height: 280px;
    border-radius: 50%; background: radial-gradient(circle, rgba(255,255,255,0.18), transparent 70%);
    pointer-events: none;
}
.hero-text { position: relative; z-index: 1; min-width: 280px; flex: 1 1 420px; }
.hero h1 {
    margin: 0 !important; padding: 0 !important; color: #FFFFFF !important;
    font-size: 1.5rem !important; font-weight: 800; line-height: 1.25; letter-spacing: 0.2px;
}
.hero p { margin: 4px 0 0 0; color: rgba(255,255,255,0.9); font-size: 0.88rem; line-height: 1.45; }
.hero-badges { position: relative; z-index: 1; display: flex; gap: 8px; flex-wrap: wrap; }
.badge {
    background: rgba(255,255,255,0.18); color: #FFFFFF; padding: 4px 12px; border-radius: 999px;
    font-size: 0.78rem; font-weight: 600; border: 1px solid rgba(255,255,255,0.45);
    transition: background .2s ease, transform .2s ease; white-space: nowrap;
}
.badge:hover { background: rgba(255,255,255,0.30); transform: translateY(-1px); }
.pulse-dot {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #86EFAC;
    margin-right: 6px; box-shadow: 0 0 0 0 rgba(134,239,172,0.8); animation: pulse 2s infinite;
}
@keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(134,239,172,0.7); }
    70% { box-shadow: 0 0 0 8px rgba(134,239,172,0); }
    100% { box-shadow: 0 0 0 0 rgba(134,239,172,0); }
}

/* ===== Tiêu đề từng khu vực nội dung ===== */
.section-head {
    display: flex; justify-content: space-between; align-items: flex-end; gap: 8px; flex-wrap: wrap;
    margin: 4px 0 10px 0; padding-bottom: 8px; border-bottom: 2px solid #CFE3D4;
}
.section-head h2 {
    margin: 0 !important; padding: 0 !important; font-size: 1.2rem !important; font-weight: 700;
    color: var(--g-900) !important; line-height: 1.3;
}
.section-head .sub { margin: 2px 0 0 0; color: var(--muted); font-size: 0.85rem; }
.tag {
    display: inline-block; padding: 3px 12px; border-radius: 999px; font-size: 0.78rem; font-weight: 600;
    border: 1px solid transparent;
}
.tag-db { background: var(--g-100); color: var(--g-900); border-color: #BBF7D0; }
.tag-ai { background: var(--amber-bg); color: var(--amber); border-color: #FDE68A; }
.tag-idle { background: #EEF2F0; color: var(--muted); border-color: var(--line); }

.empty-hint {
    background: #FFFFFF; border: 1px dashed #9CCFA9; border-radius: 12px; padding: 12px 16px;
    margin-bottom: 10px; color: var(--g-900); font-size: 0.9rem;
}

/* ===== Sidebar ===== */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #E9F5EC 0%, #F4FAF5 100%);
    border-right: 1px solid var(--line);
}
[data-testid="stSidebar"][aria-expanded="true"] {
    width: 280px !important; min-width: 280px !important; max-width: 280px !important;
}
div[data-testid="stSidebarUserContent"] { padding-top: 2.2rem !important; }
.side-brand { text-align: center; padding: 0 0 14px 0; border-bottom: 1px solid var(--line); margin-bottom: 14px; }
.side-brand .name { color: var(--g-700); font-size: 1.1rem; font-weight: 800; margin: 0; }
.side-brand .desc { color: var(--muted); font-size: 0.78rem; margin: 4px 0 0 0; }
div[data-testid="stExpander"] {
    background: #FFFFFF; border: 1px solid var(--line) !important; border-radius: 12px !important;
    box-shadow: var(--shadow-sm); transition: box-shadow .2s ease, border-color .2s ease;
}
div[data-testid="stExpander"]:hover { border-color: var(--g-600) !important; box-shadow: var(--shadow-md); }

/* ===== Nút bấm ===== */
button[kind="primary"], button[data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, #16A34A 0%, #65A30D 100%) !important;
    color: #FFFFFF !important; border: none !important; font-weight: 700 !important;
    border-radius: 10px !important; box-shadow: 0 4px 12px rgba(22, 163, 74, 0.30);
    transition: transform .15s ease, filter .15s ease, box-shadow .15s ease;
}
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {
    filter: brightness(1.07); transform: translateY(-2px); box-shadow: 0 8px 18px rgba(22, 163, 74, 0.38);
}
button[kind="primary"]:active, button[data-testid="stBaseButton-primary"]:active { transform: translateY(0); }
[data-testid="stDownloadButton"] button {
    background: #FFFFFF; color: var(--g-700); border: 1px solid #BFDCC6; border-radius: 10px;
    transition: transform .15s ease, background .15s ease, border-color .15s ease;
}
[data-testid="stDownloadButton"] button:hover {
    background: var(--g-50); border-color: var(--g-600); color: var(--g-700); transform: translateY(-1px);
}
button:focus-visible, a:focus-visible { outline: 3px solid rgba(22,163,74,0.45) !important; outline-offset: 2px; }

/* ===== Thẻ chỉ số & chú giải ===== */
.panel-title { font-weight: 700; font-size: 0.95rem; color: var(--g-900); margin: 0 0 8px 0; }
.stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 8px; }
.stat-box {
    background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: 10px 8px; text-align: center; box-shadow: var(--shadow-sm);
    transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease;
}
.stat-box:hover { transform: translateY(-3px); box-shadow: var(--shadow-md); border-color: var(--g-500); }
.stat-box.wide { grid-column: span 2; }
.stat-title { color: var(--muted); font-size: 0.78rem !important; font-weight: 600; margin-bottom: 2px; }
.stat-value { font-size: 1.3rem !important; font-weight: 700; }
.legend-panel {
    background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: 12px; margin-top: 8px; box-shadow: var(--shadow-sm);
    transition: box-shadow .2s ease;
}
.legend-panel:hover { box-shadow: var(--shadow-md); }
.ring-caption { text-align: center; color: var(--muted); font-size: 0.8rem; margin-top: -10px; }

/* ===== Bản đồ & biểu đồ ===== */
iframe[title="streamlit_folium.st_folium"] {
    border-radius: 14px; border: 1px solid var(--line); box-shadow: 0 6px 20px rgba(20, 83, 45, 0.12);
}
div[data-testid="stPlotlyChart"] {
    background: #FFFFFF; border: 1px solid var(--line); border-radius: 14px; padding: 6px;
    box-shadow: var(--shadow-sm);
}
div[data-testid="stAlert"] { border-radius: 12px; }

/* ===== Thẻ thông tin dưới biểu đồ ===== */
.info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; margin-top: 12px; }
.info-card {
    background: #ECF8EF; border: 1px solid #CBE8D3; border-radius: 12px; padding: 10px 14px;
    transition: transform .2s ease, box-shadow .2s ease, background .2s ease;
}
.info-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-md); background: #FFFFFF; }
.info-card .lbl { color: var(--muted); font-size: 0.78rem; font-weight: 600; }
.info-card .val { color: var(--g-900); font-size: 1rem; font-weight: 700; margin-top: 2px; }

/* ===== Chân trang ===== */
.site-footer {
    margin-top: 28px; border-radius: 18px 18px 0 0; padding: 22px 28px 14px 28px;
    background: linear-gradient(110deg, #0B3D20 0%, #14532D 55%, #2F6B1A 100%); color: #D8F0DF;
}
.footer-grid { display: grid; grid-template-columns: 1.6fr 1fr 1fr; gap: 24px; }
.site-footer h4 { color: #FFFFFF !important; font-size: 0.95rem !important; margin: 0 0 8px 0 !important; padding: 0 !important; }
.site-footer p, .site-footer li { font-size: 0.83rem; line-height: 1.6; color: #D8F0DF; margin: 0 0 4px 0; }
.site-footer ul { list-style: none; padding: 0; margin: 0; }
.site-footer li { transition: transform .15s ease, color .15s ease; }
.site-footer li:hover { transform: translateX(4px); color: #FFFFFF; }
.footer-bottom {
    margin-top: 14px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.18);
    text-align: center; font-size: 0.8rem; color: #B7DDC1;
}

/* ===== Nút cuộn lên đầu trang (được tạo bởi script trong layout.py) ===== */
#geo-scroll-top {
    position: fixed; right: 22px; bottom: 26px; width: 46px; height: 46px; border-radius: 50%;
    border: none; cursor: pointer; z-index: 999999; font-size: 20px; font-weight: 700; color: #FFFFFF;
    background: linear-gradient(135deg, #16A34A, #65A30D); box-shadow: 0 6px 16px rgba(22,101,52,0.4);
    opacity: 0; visibility: hidden; transform: translateY(12px);
    transition: opacity .25s ease, transform .25s ease, visibility .25s ease, filter .2s ease;
}
#geo-scroll-top.show { opacity: 1; visibility: visible; transform: translateY(0); }
#geo-scroll-top:hover { filter: brightness(1.1); transform: translateY(-3px); }

/* ===== Màn hình nhỏ ===== */
@media (max-width: 900px) {
    .block-container { padding: 3.2rem 0.8rem 0.5rem 0.8rem !important; }
    .hero h1 { font-size: 1.15rem !important; }
    .footer-grid { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) {
    * { transition: none !important; animation: none !important; scroll-behavior: auto !important; }
}
</style>
"""
