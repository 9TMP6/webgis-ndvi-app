# utils/report_pdf.py
"""
Xuất BÁO CÁO NDVI dạng PDF - cùng nội dung với bản Word (utils/report_export.py).

- Dùng reportlab (thuần Python): KHÔNG cần LibreOffice/Word trên máy chủ nên chạy được trên Streamlit Cloud.
- Font DejaVu Sans lấy từ gói matplotlib (đã có trong requirements) -> đủ dấu tiếng Việt, không cần cài font hệ thống.
- Dùng lại _summary/_conclusions/SOURCE_TEXT/... của report_export để hai bản báo cáo luôn khớp số liệu.

Cần thư viện: reportlab (thêm vào requirements.txt).
"""
import io
import os
from xml.sax.saxutils import escape as _esc

import pandas as pd

from utils.report_export import (
    GREEN, SOURCE_TEXT, _conclusions, _fmt, _int, _now_vn, _summary,
)

_FONTS_READY = False

_LIMITS = [
    "NDVI là chỉ số gián tiếp, chịu ảnh hưởng của mùa vụ, thời tiết, mây và độ phân giải ô lưới (500 m); "
    "một ô có thể gồm nhiều loại bề mặt khác nhau.",
    "Giá trị trung bình theo phường/xã che đi sự khác biệt bên trong đơn vị đó.",
    "Kết quả dự báo hoặc mô phỏng không thay thế dữ liệu quan trắc và khảo sát thực địa.",
]


def _register_fonts():
    """Đăng ký họ font 'VN' (DejaVu Sans) từ thư mục font của matplotlib."""
    global _FONTS_READY
    if _FONTS_READY:
        return
    import matplotlib
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    base = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
    files = (("VN", "DejaVuSans.ttf"), ("VN-B", "DejaVuSans-Bold.ttf"),
             ("VN-I", "DejaVuSans-Oblique.ttf"), ("VN-BI", "DejaVuSans-BoldOblique.ttf"))
    for name, fn in files:
        pdfmetrics.registerFont(TTFont(name, os.path.join(base, fn)))
    pdfmetrics.registerFontFamily("VN", normal="VN", bold="VN-B", italic="VN-I", boldItalic="VN-BI")
    _FONTS_READY = True


def generate_ndvi_report_pdf(df: pd.DataFrame, ranking: pd.DataFrame = None, map_png: bytes = None,
                             period_label: str = "", source_kind: str = "ai", model_name: str = "",
                             area_label: str = "toàn TP. Hồ Chí Minh"):
    """-> bytes của file .pdf, hoặc None nếu không có dữ liệu.
    Tham số giống hệt generate_ndvi_report_docx (có thể gọi hai hàm với cùng một bộ tham số)."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)

    if df is None or df.empty:
        return None
    s = _summary(df)
    if not s:
        return None
    _register_fonts()

    src_name, src_desc = SOURCE_TEXT.get(source_kind, SOURCE_TEXT["ai"])
    src_desc = src_desc.format(model=model_name or "AI")
    when = f"ngày {period_label}" if source_kind == "daily_sim" else f"tháng {period_label}"
    green, dark = colors.HexColor("#" + GREEN), colors.HexColor("#14532D")

    # ---------- kiểu chữ ----------
    def sty(name, size=10, **kw):
        kw.setdefault("fontName", "VN")
        kw.setdefault("leading", size * 1.4)
        return ParagraphStyle(name, fontSize=size, **kw)

    st_body = sty("body", 10, alignment=TA_JUSTIFY, spaceAfter=5, firstLineIndent=18)
    st_bul = sty("bul", 10, leftIndent=16, firstLineIndent=-10, spaceAfter=3)
    st_h1 = sty("h1", 13, fontName="VN-B", textColor=dark, spaceBefore=10, spaceAfter=5, keepWithNext=1)
    st_h2 = sty("h2", 11, fontName="VN-B", spaceBefore=6, spaceAfter=4, keepWithNext=1)
    st_note = sty("note", 8.5, fontName="VN-I", spaceAfter=4)
    st_cap = sty("cap", 8.5, fontName="VN-I", alignment=TA_CENTER, spaceAfter=6)
    st_top = sty("top", 9, fontName="VN-B", alignment=TA_CENTER, textColor=colors.HexColor("#5B7A66"), spaceAfter=2)
    st_title = sty("title", 18, fontName="VN-B", alignment=TA_CENTER, textColor=dark, spaceAfter=2, leading=24)
    st_sub = sty("sub", 12, fontName="VN-B", alignment=TA_CENTER, spaceAfter=10)

    def P(text, style):
        return Paragraph(_esc(str(text)), style)

    def table(header, rows, widths_cm, right=(), size=8.5, zebra=True):
        data = [list(header)] + [[str(c) for c in r] for r in rows]
        t = Table(data, colWidths=[w * cm for w in widths_cm], repeatRows=1)
        ts = [("FONT", (0, 0), (-1, -1), "VN", size), ("FONT", (0, 0), (-1, 0), "VN-B", size),
              ("BACKGROUND", (0, 0), (-1, 0), green), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
              ("ALIGN", (0, 0), (-1, 0), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9CA3AF")),
              ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
        if zebra and len(data) > 2:
            ts.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4FAF5")]))
        for c in right:
            ts.append(("ALIGN", (c, 1), (c, -1), "RIGHT"))
        t.setStyle(TableStyle(ts))
        return t

    # ---------- bảng xếp hạng theo phường/xã ----------
    have = None
    if ranking is not None and not ranking.empty and {"NDVI TB", "Đơn vị"} <= set(ranking.columns):
        have = (ranking.dropna(subset=["NDVI TB"])
                .sort_values(["NDVI TB", "Đơn vị"], ascending=[False, True]).reset_index(drop=True))
        if have.empty:
            have = None
    top = have.iloc[0] if have is not None else None
    low = have.iloc[-1] if have is not None else None

    # ---------- nội dung ----------
    story = [
        P("HỆ THỐNG GEO-NDVI", st_top),
        P("BÁO CÁO CHỈ SỐ THỰC VẬT NDVI", st_title),
        P(f"Thành phố Hồ Chí Minh – {when}", st_sub),
    ]
    info = [
        ("Thời điểm", period_label),
        ("Phạm vi", area_label),
        ("Nguồn dữ liệu", src_name + (f" – mô hình {model_name}" if source_kind != "observed" and model_name else "")),
        ("Số ô lưới", f"{_int(s['n'])} ô (lưới 500 m)"),
        ("Ngày lập báo cáo", _now_vn().strftime("%d/%m/%Y %H:%M")),
    ]
    story.append(table(["Thông tin", "Nội dung"], info, [4.0, 12.5], size=9.5, zebra=False))

    story += [P("1. Mục đích và phạm vi", st_h1),
              P(f"Báo cáo tóm tắt chỉ số thực vật NDVI của {area_label} vào {when}, gồm thống kê chung, bản đồ phân bố "
                "và bảng NDVI theo phường/xã, nhằm hỗ trợ theo dõi hiện trạng thực vật ở mức tham khảo.", st_body)]

    story += [P("2. Nguồn dữ liệu và phương pháp", st_h1), P(src_desc, st_body),
              P("NDVI (Normalized Difference Vegetation Index) được tính từ băng cận hồng ngoại (B8) và băng đỏ (B4) của "
                "Sentinel-2, nhận giá trị từ −1 đến 1; giá trị càng cao thường tương ứng mật độ thực vật xanh càng lớn. "
                "NDVI của từng phường/xã là trung bình của các ô lưới nằm trong ranh giới đơn vị đó.", st_body)]

    story += [P("3. Kết quả tổng quan", st_h1), P("3.1. Thống kê chung", st_h2)]
    story.append(table(["Chỉ tiêu", "Giá trị"], [
        ("NDVI trung bình", _fmt(s["mean"])), ("NDVI trung vị", _fmt(s["median"])),
        ("Độ lệch chuẩn", _fmt(s["std"])), ("NDVI thấp nhất", _fmt(s["min"])), ("NDVI cao nhất", _fmt(s["max"])),
        ("Tỷ lệ ô có NDVI ≥ 0,3", f"{_fmt(s['veg_pct'], 1)}%"),
    ], [9.0, 6.0], right=(1,), size=9.5))

    story.append(P("3.2. Phân bố ô lưới theo mức NDVI", st_h2))
    story.append(table(["Mức NDVI", "Số ô", "Tỷ lệ"],
                       [(n, _int(c), f"{_fmt(c / s['n'] * 100, 1)}%") for n, c in s["classes"]],
                       [8.5, 3.5, 3.5], right=(1, 2), size=9.5))
    story.append(Spacer(1, 4))
    story.append(P("Ghi chú: cách chia mức chỉ dùng để tóm tắt trong báo cáo này, không phải chuẩn phân loại chính thức.",
                   st_note))

    h_map = P("3.3. Bản đồ phân bố NDVI", st_h2)
    if map_png:
        try:
            from PIL import Image as PILImage
            w_px, h_px = PILImage.open(io.BytesIO(map_png)).size
            w_cm = 16.0
            h_cm = min(w_cm * h_px / w_px, 22.0)           # không cao quá 1 trang
            w_cm = h_cm * w_px / h_px
            story.append(KeepTogether([   # tiêu đề + ảnh + chú thích luôn nằm cùng một trang
                h_map,
                Image(io.BytesIO(map_png), width=w_cm * cm, height=h_cm * cm),
                P(f"Hình 1. Bản đồ phân bố NDVI {when} ({src_name}).", st_cap),
            ]))
        except Exception:
            story += [h_map, P("(Không chèn được ảnh bản đồ.)", st_note)]
    else:
        story += [h_map, P("(Chưa có ảnh bản đồ.)", st_note)]

    num = 4
    if have is not None:
        n = min(10, len(have))
        story += [P(f"{num}. NDVI theo phường/xã", st_h1),
                  P(f"Dữ liệu có {len(have)} phường/xã (theo ranh giới hành chính HCM-34). Dưới đây là 10 đơn vị có NDVI "
                    "trung bình cao nhất và thấp nhất; bảng đầy đủ ở Phụ lục A.", st_body)]

        def rank_rows(part, start):
            has_veg = "Độ phủ TV (%)" in part.columns
            return [(k, r["Đơn vị"], _fmt(r["NDVI TB"]), _fmt(r["Độ phủ TV (%)"], 0) if has_veg else "–")
                    for k, (_, r) in enumerate(part.iterrows(), start=start)]

        head, w = ["Hạng", "Đơn vị", "NDVI TB", "Độ phủ TV (%)"], [1.8, 7.7, 3.0, 4.0]
        story.append(P(f"{num}.1. {n} đơn vị có NDVI trung bình cao nhất", st_h2))
        story.append(table(head, rank_rows(have.head(n), 1), w, right=(0, 2, 3)))
        story.append(P(f"{num}.2. {n} đơn vị có NDVI trung bình thấp nhất", st_h2))
        story.append(table(head, rank_rows(have.tail(n), len(have) - n + 1), w, right=(0, 2, 3)))
        story.append(Spacer(1, 4))
        story.append(P("Ghi chú: Độ phủ TV (%) là tỷ lệ ô lưới trong đơn vị có NDVI từ 0,3 trở lên.", st_note))
        num += 1

    story.append(P(f"{num}. Nhận xét và kết luận", st_h1))
    for line in _conclusions(s, top, low, period_label, source_kind, model_name):
        story.append(P("• " + line, st_bul))
    num += 1

    story.append(P(f"{num}. Hạn chế và lưu ý", st_h1))
    for line in _LIMITS:
        story.append(P("• " + line, st_bul))

    # ---------- phụ lục: bảng đầy đủ ----------
    if have is not None and ranking is not None:
        story += [PageBreak(), P("Phụ lục A. Bảng NDVI đầy đủ theo phường/xã", st_h1)]
        cols = [c for c in ["Hạng", "Đơn vị", "NDVI TB", "Đánh giá", "Độ phủ TV (%)", "Số ô lưới"] if c in ranking.columns]
        widths = {"Hạng": 1.4, "Đơn vị": 6.3, "NDVI TB": 2.1, "Đánh giá": 3.0, "Độ phủ TV (%)": 2.3, "Số ô lưới": 1.8}
        full = ranking.sort_values(["NDVI TB", "Đơn vị"], ascending=[False, True], na_position="last")
        rows = []
        for k, (_, r) in enumerate(full.iterrows(), start=1):
            row = []
            for c in cols:
                val = r[c]
                if c == "Hạng":
                    row.append(str(int(val)) if pd.notna(val) else str(k))
                elif c == "NDVI TB":
                    row.append(_fmt(val))
                elif c == "Độ phủ TV (%)":
                    row.append(_fmt(val, 0))
                elif c == "Số ô lưới":
                    row.append(_int(val))
                else:
                    row.append("" if pd.isna(val) else str(val))
            rows.append(row)
        right = tuple(i for i, c in enumerate(cols) if c in ("Hạng", "NDVI TB", "Độ phủ TV (%)", "Số ô lưới"))
        story.append(table(cols, rows, [widths[c] for c in cols], right=right, size=8))

    # ---------- chân trang + xuất ----------
    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("VN", 8)
        canvas.setFillColor(colors.HexColor("#5B7A66"))
        canvas.drawCentredString(A4[0] / 2, 1.0 * cm, f"GEO-NDVI – Báo cáo tự động từ hệ thống | Trang {doc_.page}")
        canvas.restoreState()

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=2.5 * cm, rightMargin=2.0 * cm, topMargin=2.0 * cm,
                      bottomMargin=2.0 * cm, title=f"Báo cáo NDVI {period_label}", author="GEO-NDVI"
                      ).build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
