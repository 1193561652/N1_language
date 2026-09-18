from pathlib import Path
import re

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "01 Lessons" / "Lesson001 Business Japanese - Meeting.md"
OUT_DIR = ROOT / "output" / "docx"
OUTPUT = OUT_DIR / "Lesson001 Business Japanese - Meeting.docx"


COLORS = {
    "blue": RGBColor(0x2E, 0x74, 0xB5),
    "dark_blue": RGBColor(0x1F, 0x4D, 0x78),
    "muted": RGBColor(0x66, 0x66, 0x66),
    "header_fill": "E8EEF5",
    "callout_fill": "F4F6F9",
}


RUBY = {
    "日本語能力試験": "にほんごのうりょくしけん",
    "販売計画": "はんばいけいかく",
    "意見交換": "いけんこうかん",
    "関係部署": "かんけいぶしょ",
    "調査結果": "ちょうさけっか",
    "関係者": "かんけいしゃ",
    "参加者": "さんかしゃ",
    "担当者": "たんとうしゃ",
    "参考資料": "さんこうしりょう",
    "会議資料": "かいぎしりょう",
    "今日中": "きょうじゅう",
    "本日中": "ほんじつじゅう",
    "午後三時": "ごごさんじ",
    "新企画": "しんきかく",
    "進め方": "すすめかた",
    "会議": "かいぎ",
    "確認": "かくにん",
    "資料": "しりょう",
    "日程": "にってい",
    "調整": "ちょうせい",
    "議題": "ぎだい",
    "共有": "きょうゆう",
    "予定": "よてい",
    "内容": "ないよう",
    "連絡": "れんらく",
    "報告": "ほうこく",
    "説明": "せつめい",
    "提案": "ていあん",
    "相談": "そうだん",
    "参加": "さんか",
    "出席": "しゅっせき",
    "欠席": "けっせき",
    "変更": "へんこう",
    "決定": "けってい",
    "案内": "あんない",
    "メール": "メール",
    "作成": "さくせい",
    "配布": "はいふ",
    "目": "め",
    "通": "とお",
    "進捗": "しんちょく",
    "情報": "じょうほう",
    "方針": "ほうしん",
    "質問": "しつもん",
    "整理": "せいり",
    "新": "あたら",
    "計画": "けいかく",
    "意見": "いけん",
    "事前": "じぜん",
    "承知": "しょうち",
    "添付": "てんぷ",
    "皆様": "みなさま",
    "場合": "ばあい",
    "明日": "あした",
    "今日": "きょう",
    "本日": "ほんじつ",
    "今後": "こんご",
    "来月": "らいげつ",
    "中": "ちゅう",
    "前": "まえ",
    "後": "あと",
    "少": "すこ",
    "伺": "うかが",
    "思": "おも",
    "助": "たす",
    "願": "ねが",
    "疲": "つか",
    "行": "おこな",
    "聞": "き",
    "開": "ひら",
    "入": "はい",
    "移": "うつ",
    "見": "み",
    "読": "よ",
    "送": "おく",
    "改": "あらた",
    "修正": "しゅうせい",
    "時間": "じかん",
    "都合": "つごう",
    "合": "あ",
    "結論": "けつろん",
    "出": "だ",
    "関": "かん",
    "基": "もと",
    "基づいて": "もとづいて",
    "名詞": "めいし",
    "動詞": "どうし",
}

RUBY_KEYS = sorted(RUBY, key=len, reverse=True)


def has_japanese_signal(text):
    return bool(re.search(r"[\u3040-\u30ff]", text))


def set_run_font(run, size=None, bold=None, color=None):
    run.font.name = "Microsoft YaHei"
    run._element.rPr.rFonts.set(qn("w:ascii"), "Microsoft YaHei")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Microsoft YaHei")
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color:
        run.font.color.rgb = color


def set_paragraph_font(paragraph, size=11, color=None):
    for run in paragraph.runs:
        set_run_font(run, size=size, color=color)


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_margins(cell, top=80, start=120, bottom=80, end=120):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for m, v in {"top": top, "start": start, "bottom": bottom, "end": end}.items():
        node = tc_mar.find(qn(f"w:{m}"))
        if node is None:
            node = OxmlElement(f"w:{m}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(v))
        node.set(qn("w:type"), "dxa")


def append_plain_run(paragraph, text, size=11, bold=False, color=None, code=False):
    run = paragraph.add_run(text)
    set_run_font(run, size=size, bold=bold, color=color)
    if code:
        run.font.name = "Consolas"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Yu Gothic")
    return run


def append_ruby(paragraph, base, ruby_text, size=11, bold=False, color=None):
    # Word/WPS compatibility first: keep both kanji and kana as normal visible text.
    append_plain_run(paragraph, f"{base}（{ruby_text}）", size=size, bold=bold, color=color)


def add_text_with_optional_ruby(paragraph, text, size=11, bold=False, color=None, force_ruby=False):
    if not force_ruby:
        append_plain_run(paragraph, text, size=size, bold=bold, color=color)
        return

    i = 0
    while i < len(text):
        match_key = None
        for key in RUBY_KEYS:
            if text.startswith(key, i):
                match_key = key
                break
        if match_key:
            # If the source already has an explicit reading, keep the original
            # instead of adding a duplicate superscript.
            explicit = f"（{RUBY[match_key]}）"
            if text.startswith(explicit, i + len(match_key)):
                append_plain_run(paragraph, match_key, size=size, bold=bold, color=color)
            else:
                append_ruby(paragraph, match_key, RUBY[match_key], size=size, bold=bold, color=color)
            i += len(match_key)
        else:
            append_plain_run(paragraph, text[i], size=size, bold=bold, color=color)
            i += 1


def set_table_width(table, widths):
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    tbl_w = tbl_pr.first_child_found_in("w:tblW")
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths)))
    tbl_w.set(qn("w:type"), "dxa")

    tbl_ind = tbl_pr.first_child_found_in("w:tblInd")
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), "120")
    tbl_ind.set(qn("w:type"), "dxa")

    grid = tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)

    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            width = widths[idx]
            cell.width = Inches(width / 1440)
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.first_child_found_in("w:tcW")
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc_pr.append(tc_w)
            tc_w.set(qn("w:w"), str(width))
            tc_w.set(qn("w:type"), "dxa")
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)


def style_doc(doc):
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)

    normal = doc.styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Microsoft YaHei")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Microsoft YaHei")
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.25

    for name, size, color, before, after in [
        ("Heading 1", 16, COLORS["blue"], 18, 10),
        ("Heading 2", 13, COLORS["blue"], 14, 7),
        ("Heading 3", 12, COLORS["dark_blue"], 10, 5),
    ]:
        style = doc.styles[name]
        style.font.name = "Microsoft YaHei"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Microsoft YaHei")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Microsoft YaHei")
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.font.size = Pt(size)
        style.font.color.rgb = color
        style.font.bold = True
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.line_spacing = 1.25


def add_rich_paragraph(doc, text, style=None, force_ruby=False):
    p = doc.add_paragraph(style=style)
    # Light inline code handling.
    parts = re.split(r"(`[^`]+`)", text)
    for part in parts:
        if not part:
            continue
        if part.startswith("`") and part.endswith("`"):
            append_plain_run(p, part[1:-1], size=10, code=True)
        else:
            add_text_with_optional_ruby(p, part, force_ruby=force_ruby)
    return p


def add_callout(doc, lines):
    table = doc.add_table(rows=1, cols=1)
    set_table_width(table, [9360])
    cell = table.cell(0, 0)
    set_cell_shading(cell, COLORS["callout_fill"])
    cell.text = ""
    for i, line in enumerate(lines):
        p = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
        p.paragraph_format.space_after = Pt(3)
        add_text_with_optional_ruby(p, line, size=10.5, force_ruby=has_japanese_signal(line))


def parse_table(lines):
    rows = []
    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c or "") for c in cells):
            continue
        rows.append(cells)
    return rows


def add_table(doc, rows):
    if not rows:
        return
    cols = len(rows[0])
    table = doc.add_table(rows=len(rows), cols=cols)
    table.style = "Table Grid"
    if cols == 2:
        widths = [2700, 6660]
    elif cols == 3:
        widths = [2160, 3600, 3600]
    elif cols == 4:
        widths = [1900, 2500, 2500, 2460]
    else:
        base = 9360 // cols
        widths = [base] * cols
        widths[-1] += 9360 - sum(widths)
    set_table_width(table, widths)
    for r_idx, row in enumerate(rows):
        for c_idx, value in enumerate(row):
            cell = table.cell(r_idx, c_idx)
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            add_text_with_optional_ruby(
                p,
                value,
                size=10,
                bold=(r_idx == 0),
                force_ruby=has_japanese_signal(value) or bool(re.search(r"[\u4e00-\u9fff]", value) and value in RUBY),
            )
            if r_idx == 0:
                set_cell_shading(cell, COLORS["header_fill"])


def build_doc():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    markdown = SOURCE.read_text(encoding="utf-8").splitlines()

    doc = Document()
    style_doc(doc)

    title = doc.add_paragraph()
    title.paragraph_format.space_after = Pt(3)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = title.add_run("Lesson001 Business Japanese - Meeting")
    set_run_font(run, size=24, bold=True, color=RGBColor(0x0B, 0x25, 0x45))

    subtitle = doc.add_paragraph()
    subtitle.paragraph_format.space_after = Pt(10)
    run = subtitle.add_run("N1 Language System / Business Japanese / Meeting")
    set_run_font(run, size=11, color=COLORS["muted"])

    doc.add_paragraph(
        "Scene -> Expression -> Vocabulary -> Grammar -> Listening / Reading -> JLPT",
        style=None,
    )

    in_code = False
    code_lines = []
    table_lines = []
    pending_callout = []
    skip_first_title = True

    def flush_table():
        nonlocal table_lines
        if table_lines:
            add_table(doc, parse_table(table_lines))
            table_lines = []

    def flush_code():
        nonlocal code_lines
        if code_lines:
            add_callout(doc, code_lines)
            code_lines = []

    for raw in markdown:
        line = raw.rstrip()

        if skip_first_title and line.startswith("# "):
            skip_first_title = False
            continue

        if line.startswith("```"):
            if in_code:
                in_code = False
                flush_code()
            else:
                flush_table()
                in_code = True
                code_lines = []
            continue

        if in_code:
            code_lines.append(line)
            continue

        if line.strip().startswith("|"):
            table_lines.append(line)
            continue
        flush_table()

        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("## "):
            doc.add_paragraph(stripped[3:], style="Heading 1")
        elif stripped.startswith("### "):
            doc.add_paragraph(stripped[4:], style="Heading 2")
        elif stripped.startswith("#### "):
            doc.add_paragraph(stripped[5:], style="Heading 3")
        elif stripped.startswith("- "):
            body = stripped[2:]
            p = add_rich_paragraph(doc, body, style="List Bullet", force_ruby=has_japanese_signal(body))
            p.paragraph_format.left_indent = Inches(0.375)
            p.paragraph_format.first_line_indent = Inches(-0.188)
            p.paragraph_format.space_after = Pt(4)
        elif re.match(r"^\d+\.\s+", stripped):
            text = re.sub(r"^\d+\.\s+", "", stripped)
            p = add_rich_paragraph(doc, text, style="List Number", force_ruby=has_japanese_signal(text))
            p.paragraph_format.left_indent = Inches(0.375)
            p.paragraph_format.first_line_indent = Inches(-0.188)
            p.paragraph_format.space_after = Pt(4)
        elif stripped in {"Answer:", "Answers:", "Model answers:", "Model:", "Examples:", "Practice:", "Question:", "Questions:", "Script:", "Key expressions:", "Thinking:", "Function:", "Source:", "Source status:", "Vocabulary:", "Collocations:", "Grammar:", "Scene tags:"}:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(3)
            run = p.add_run(stripped)
            set_run_font(run, size=11, bold=True, color=COLORS["dark_blue"])
        else:
            p = add_rich_paragraph(doc, stripped, force_ruby=has_japanese_signal(stripped))
            p.paragraph_format.space_after = Pt(6)

    flush_table()
    flush_code()

    footer = doc.sections[0].footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = footer.add_run("N1 Language System - Lesson001")
    set_run_font(run, size=9, color=COLORS["muted"])

    doc.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print(build_doc())
