# utils/report_export.py
"""
Xuất BÁO CÁO NDVI dạng Word (.docx) từ dữ liệu đang xem trên bản đồ.

Bố cục: Tiêu đề + bảng thông tin chung | 1. Mục đích, phạm vi | 2. Nguồn dữ liệu, phương pháp |
3. Kết quả tổng quan (thống kê, phân bố theo mức, ảnh bản đồ) | 4. NDVI theo phường/xã (10 cao nhất, 10 thấp nhất) |
5. Nhận xét và kết luận | 6. Hạn chế, lưu ý | Phụ lục A: bảng đầy đủ.

Phần nhận xét chỉ MÔ TẢ con số, không suy diễn nguyên nhân và nói rõ giới hạn theo từng loại nguồn dữ liệu.
Cần thư viện: python-docx.
"""
import io
import datetime

import numpy as np
import pandas as pd

FONT = "Times New Roman"
GREEN = "15803D"
LIGHT = "E8F3EA"
VEG_THRESHOLD = 0.3          # cùng ngưỡng "Độ phủ thực vật" đang dùng trong bảng xếp hạng của app

# Cách chia mức chỉ để tóm tắt trong báo cáo (không phải chuẩn phân loại chính thức)
CLASSES = [
    ("Thấp (NDVI < 0,2)", -9.0, 0.2),
    ("Trung bình thấp (0,2 ≤ NDVI < 0,4)", 0.2, 0.4),
    ("Trung bình cao (0,4 ≤ NDVI < 0,6)", 0.4, 0.6),
    ("Cao (NDVI ≥ 0,6)", 0.6, 9.0),
]

SOURCE_TEXT = {
    "observed": ("Quan trắc vệ tinh (CSDL)",
                 "NDVI trung bình tháng tính từ ảnh Sentinel-2 (Google Earth Engine), đã lọc mây theo lớp SCL và "
                 "tổng hợp theo ô lưới 500 m. Ô bị mây che nhiều trong tháng có thể không có giá trị."),
    "ai": ("Dự báo AI",
           "NDVI do mô hình {model} dự báo từ chuỗi NDVI quan trắc theo tháng trước đó. Để giảm thời gian tính, "
           "mô hình chỉ chạy trên một tập ô lưới rải đều; giá trị ở các ô còn lại được nội suy theo khoảng cách "
           "từ các ô đã dự báo."),
    "daily_sim": ("Mô phỏng theo ngày (demo)",
                  "Giá trị theo ngày được MÔ PHỎNG, không phải ảnh vệ tinh theo ngày và không phải kết quả của mô hình "
                  "dự báo theo ngày. Cách làm: lấy bản đồ NDVI tháng (quan trắc hoặc dự báo {model}) của tháng hiện tại và "
                  "tháng liền kề, coi mỗi giá trị là NDVI vào ngày 15, nội suy mượt theo số ngày, rồi cộng một dao động "
                  "nhỏ cố định theo ngày và vị trí."),
}


# ---------------- Tiện ích định dạng Word ----------------
def _fmt(x, nd=3):
    """Số kiểu Việt Nam: dấu phẩy thập phân."""
    try:
        return f"{float(x):.{nd}f}".replace(".", ",")
    except (TypeError, ValueError):
        return "–"


def _int(x):
    try:
        return f"{int(round(float(x))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "–"


def _now_vn():
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    except Exception:
        return datetime.datetime.utcnow() + datetime.timedelta(hours=7)


def _set_run_font(run, size=None, bold=None, italic=None, color=None):
    from docx.shared import Pt, RGBColor
    from docx.oxml.ns import qn
    run.font.name = FONT
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def _shade(cell, hex_fill):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    tcPr = cell._element.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def _repeat_header(row):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def _no_split(row):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    trPr = row._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:cantSplit"))


def _para(doc, text="", size=13, bold=False, italic=False, align=None, space_after=6, color=None, first_indent=False):
    from docx.shared import Pt, Cm
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after, pf.space_before, pf.line_spacing = Pt(space_after), Pt(0), 1.3
    if first_indent:
        pf.first_line_indent = Cm(1.0)
    if align is not None:
        p.alignment = align
    if text:
        _set_run_font(p.add_run(text), size=size, bold=bold, italic=italic, color=color)
    return p


def _heading(doc, text, level=1):
    from docx.shared import Pt
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12 if level == 1 else 8)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    _set_run_font(p.add_run(text), size=14 if level == 1 else 13, bold=True, color="14532D" if level == 1 else "000000",
                  italic=(level == 3))
    return p


def _bullet(doc, text):
    from docx.shared import Pt, Cm
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.left_indent, pf.first_line_indent = Cm(1.0), Cm(-0.5)
    pf.space_after, pf.line_spacing = Pt(4), 1.3
    _set_run_font(p.add_run("•  " + text), size=13)
    return p


def _table(doc, header, rows, widths_cm, align_right_cols=(), font_size=11, zebra=True):
    """Bảng có hàng tiêu đề xanh, lặp lại đầu trang, không cắt đôi hàng."""
    from docx.shared import Cm, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.autofit = False
    for i, w in enumerate(widths_cm):          # đặt cả độ rộng cột (Word) lẫn từng ô (LibreOffice/Google Docs)
        t.columns[i].width = Cm(w)
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.width = Cm(widths_cm[i])
        _shade(c, GREEN)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        _set_run_font(p.add_run(h), size=font_size, bold=True, color="FFFFFF")
    _repeat_header(t.rows[0])
    for r_i, row in enumerate(rows):
        cells = t.add_row().cells
        _no_split(t.rows[-1])
        for i, v in enumerate(row):
            cells[i].width = Cm(widths_cm[i])
            if zebra and r_i % 2 == 1:
                _shade(cells[i], "F4FAF5")
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if i in align_right_cols else WD_ALIGN_PARAGRAPH.LEFT
            _set_run_font(p.add_run(str(v)), size=font_size)
    return t


def _add_page_number(section):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_run_font(p.add_run("GEO-NDVI – Báo cáo tự động từ hệ thống  |  Trang "), size=9, color="5B7A66")
    run = p.add_run()
    _set_run_font(run, size=9, color="5B7A66")
    for kind, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = txt
        run._r.append(el)


# ---------------- Thống kê + câu nhận xét ----------------
def _summary(df: pd.DataFrame) -> dict:
    v = pd.to_numeric(df["ndvi_mean"], errors="coerce").dropna().to_numpy(float)
    if len(v) == 0:
        return {}
    cls = [(name, int(((v >= lo) & (v < hi)).sum())) for name, lo, hi in CLASSES]
    return {
        "n": len(v), "mean": float(v.mean()), "median": float(np.median(v)), "std": float(v.std()),
        "min": float(v.min()), "max": float(v.max()),
        "veg_pct": float((v >= VEG_THRESHOLD).mean() * 100), "classes": cls,
    }


def _conclusions(s, top, low, period_label, source_kind, model_name):
    lines = [
        f"Tại thời điểm {period_label}, NDVI trung bình của {_int(s['n'])} ô lưới là {_fmt(s['mean'])} "
        f"(trung vị {_fmt(s['median'])}), dao động từ {_fmt(s['min'])} đến {_fmt(s['max'])}.",
        f"Khoảng {_fmt(s['veg_pct'], 1)}% số ô lưới có NDVI từ {_fmt(VEG_THRESHOLD, 1)} trở lên.",
    ]
    if top is not None and low is not None:
        lines.append(f"Trong các đơn vị hành chính có dữ liệu, {top['Đơn vị']} có NDVI trung bình cao nhất "
                     f"({_fmt(top['NDVI TB'])}) và {low['Đơn vị']} có NDVI trung bình thấp nhất ({_fmt(low['NDVI TB'])}).")
    if source_kind == "observed":
        lines.append("Số liệu thuộc về quan trắc vệ tinh nên phản ánh điều kiện ghi nhận được trong tháng; "
                     "tuy vậy, các ô bị mây che có thể thiếu hoặc kém đại diện.")
    elif source_kind == "ai":
        lines.append(f"Số liệu là kết quả dự báo của mô hình {model_name}, chưa được đối chiếu với quan trắc của "
                     "chính thời điểm này, nên chỉ nên dùng để tham khảo.")
    else:
        lines.append("Số liệu theo ngày là kết quả mô phỏng nhằm minh hoạ chức năng, chưa được kiểm chứng với "
                     "quan trắc thực tế và không nên dùng làm căn cứ ra quyết định.")
    lines.append("Báo cáo chỉ mô tả số liệu; chưa phân tích nguyên nhân của các khác biệt giữa các khu vực.")
    return lines


# ---------------- Hàm công khai ----------------
def generate_ndvi_report_docx(df: pd.DataFrame, ranking: pd.DataFrame = None, map_png: bytes = None,
                              period_label: str = "", source_kind: str = "ai", model_name: str = "",
                              area_label: str = "toàn TP. Hồ Chí Minh"):
    """-> bytes của file .docx, hoặc None nếu không có dữ liệu.
    source_kind: 'observed' (quan trắc) | 'ai' (dự báo tháng) | 'daily_sim' (mô phỏng theo ngày).
    ranking: bảng từ ward_info.build_ranking_table (cột 'Đơn vị', 'NDVI TB'...); None thì bỏ mục 4 và phụ lục."""
    from docx import Document
    from docx.shared import Pt, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    if df is None or df.empty:
        return None
    s = _summary(df)
    if not s:
        return None
    src_name, src_desc = SOURCE_TEXT.get(source_kind, SOURCE_TEXT["ai"])
    src_desc = src_desc.format(model=model_name or "AI")
    is_daily = source_kind == "daily_sim"
    when = f"ngày {period_label}" if is_daily else f"tháng {period_label}"

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin, sec.right_margin, sec.top_margin, sec.bottom_margin = Cm(3.0), Cm(2.0), Cm(2.0), Cm(2.0)
    st = doc.styles["Normal"]
    st.font.name, st.font.size = FONT, Pt(13)
    st.element.rPr.rFonts.set("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia", FONT)
    _add_page_number(sec)

    # ----- Tiêu đề -----
    C = WD_ALIGN_PARAGRAPH.CENTER
    _para(doc, "HỆ THỐNG GEO-NDVI", size=12, bold=True, align=C, space_after=2, color="5B7A66")
    _para(doc, "BÁO CÁO CHỈ SỐ THỰC VẬT NDVI", size=20, bold=True, align=C, space_after=2, color="14532D")
    _para(doc, f"Thành phố Hồ Chí Minh – {when}", size=14, bold=True, align=C, space_after=10)

    info = [
        ("Thời điểm", period_label),
        ("Phạm vi", area_label),
        ("Nguồn dữ liệu", src_name + (f" – mô hình {model_name}" if source_kind != "observed" and model_name else "")),
        ("Số ô lưới", f"{_int(s['n'])} ô (lưới 500 m)"),
        ("Ngày lập báo cáo", _now_vn().strftime("%d/%m/%Y %H:%M")),
    ]
    _table(doc, ["Thông tin", "Nội dung"], info, [4.0, 11.0], font_size=12, zebra=False)

    # ----- 1 -----
    _heading(doc, "1. Mục đích và phạm vi")
    _para(doc, f"Báo cáo tóm tắt chỉ số thực vật NDVI của {area_label} vào {when}, gồm thống kê chung, bản đồ phân bố "
               "và bảng NDVI theo phường/xã, nhằm hỗ trợ theo dõi hiện trạng thực vật ở mức tham khảo.",
          first_indent=True)

    # ----- 2 -----
    _heading(doc, "2. Nguồn dữ liệu và phương pháp")
    _para(doc, src_desc, first_indent=True)
    _para(doc, "NDVI (Normalized Difference Vegetation Index) được tính từ băng cận hồng ngoại (B8) và băng đỏ (B4) của "
               "Sentinel-2, nhận giá trị từ −1 đến 1; giá trị càng cao thường tương ứng mật độ thực vật xanh càng lớn. "
               "NDVI của từng phường/xã là trung bình của các ô lưới nằm trong ranh giới đơn vị đó.", first_indent=True)

    # ----- 3 -----
    _heading(doc, "3. Kết quả tổng quan")
    _heading(doc, "3.1. Thống kê chung", 2)
    _table(doc, ["Chỉ tiêu", "Giá trị"], [
        ("NDVI trung bình", _fmt(s["mean"])), ("NDVI trung vị", _fmt(s["median"])),
        ("Độ lệch chuẩn", _fmt(s["std"])), ("NDVI thấp nhất", _fmt(s["min"])), ("NDVI cao nhất", _fmt(s["max"])),
        (f"Tỷ lệ ô có NDVI ≥ {_fmt(VEG_THRESHOLD, 1)}", f"{_fmt(s['veg_pct'], 1)}%"),
    ], [9.0, 6.0], align_right_cols=(1,), font_size=12)

    _heading(doc, "3.2. Phân bố ô lưới theo mức NDVI", 2)
    _table(doc, ["Mức NDVI", "Số ô", "Tỷ lệ"],
           [(n, _int(c), f"{_fmt(c / s['n'] * 100, 1)}%") for n, c in s["classes"]],
           [8.0, 3.5, 3.5], align_right_cols=(1, 2), font_size=12)
    _para(doc, "Ghi chú: cách chia mức chỉ dùng để tóm tắt trong báo cáo này, không phải chuẩn phân loại chính thức.",
          size=11, italic=True, space_after=6)

    _heading(doc, "3.3. Bản đồ phân bố NDVI", 2)
    if map_png:
        try:
            doc.add_picture(io.BytesIO(map_png), width=Cm(15.0))
            doc.paragraphs[-1].alignment = C
            _para(doc, f"Hình 1. Bản đồ phân bố NDVI {when} ({src_name.lower()}).", size=11, italic=True, align=C)
        except Exception:
            _para(doc, "(Không chèn được ảnh bản đồ.)", size=11, italic=True)
    else:
        _para(doc, "(Chưa có ảnh bản đồ.)", size=11, italic=True)

    # ----- 4 -----
    top = low = None
    have = None
    if ranking is not None and not ranking.empty and "NDVI TB" in ranking.columns and "Đơn vị" in ranking.columns:
        have = ranking.dropna(subset=["NDVI TB"]).sort_values(["NDVI TB", "Đơn vị"], ascending=[False, True])
    if have is not None and not have.empty:
        top, low = have.iloc[0], have.iloc[-1]
        _heading(doc, "4. NDVI theo phường/xã")
        _para(doc, f"Dữ liệu có {len(have)} phường/xã (theo ranh giới hành chính HCM-34). Dưới đây là 10 đơn vị có NDVI "
                   "trung bình cao nhất và thấp nhất; bảng đầy đủ ở Phụ lục A.", first_indent=True)
        n = min(10, len(have))

        def rows_of(part):
            return [(int(i + 1), r["Đơn vị"], _fmt(r["NDVI TB"]),
                     _fmt(r["Độ phủ TV (%)"], 0) if "Độ phủ TV (%)" in part.columns else "–")
                    for i, (_, r) in zip(part["_rank"], part.iterrows())]

        have = have.assign(_rank=range(len(have)))
        head = ["Hạng", "Đơn vị", "NDVI TB", "Độ phủ TV (%)"]
        w = [1.8, 7.2, 3.0, 3.0]
        _heading(doc, f"4.1. {n} đơn vị có NDVI trung bình cao nhất", 2)
        _table(doc, head, rows_of(have.head(n)), w, align_right_cols=(0, 2, 3), font_size=11)
        _heading(doc, f"4.2. {n} đơn vị có NDVI trung bình thấp nhất", 2)
        _table(doc, head, rows_of(have.tail(n)), w, align_right_cols=(0, 2, 3), font_size=11)
        _para(doc, "Ghi chú: Độ phủ TV (%) là tỷ lệ ô lưới trong đơn vị có NDVI từ 0,3 trở lên.",
              size=11, italic=True, space_after=6)

    # ----- 5 -----
    _heading(doc, "5. Nhận xét và kết luận" if have is not None else "4. Nhận xét và kết luận")
    for line in _conclusions(s, top, low, period_label, source_kind, model_name):
        _bullet(doc, line)

    # ----- 6 -----
    _heading(doc, "6. Hạn chế và lưu ý" if have is not None else "5. Hạn chế và lưu ý")
    for line in [
        "NDVI là chỉ số gián tiếp, chịu ảnh hưởng của mùa vụ, thời tiết, mây và độ phân giải ô lưới (500 m); "
        "một ô có thể gồm nhiều loại bề mặt khác nhau.",
        "Giá trị trung bình theo phường/xã che đi sự khác biệt bên trong đơn vị đó.",
        "Kết quả dự báo hoặc mô phỏng không thay thế dữ liệu quan trắc và khảo sát thực địa.",
    ]:
        _bullet(doc, line)

    # ----- Phụ lục -----
    if have is not None and not have.empty:
        doc.add_page_break()
        _heading(doc, "Phụ lục A. Bảng NDVI đầy đủ theo phường/xã")
        cols = [c for c in ["Hạng", "Đơn vị", "NDVI TB", "Đánh giá", "Độ phủ TV (%)", "Số ô lưới"] if c in ranking.columns]
        widths = {"Hạng": 1.5, "Đơn vị": 5.6, "NDVI TB": 2.0, "Đánh giá": 2.5, "Độ phủ TV (%)": 2.0, "Số ô lưới": 1.6}
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
        _table(doc, cols, rows, [widths[c] for c in cols], align_right_cols=right, font_size=10)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
