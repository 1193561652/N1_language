import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pdfplumber

from convert_library2_after_2021 import POPPLER, ROOT, md5_file, normalize_text


SOURCE = ROOT / "library2" / "2022年12月" / "32022年12月N1_真题.pdf"
OUT_DIR = ROOT / "output" / "library2_refined"
OUT_MD = OUT_DIR / "2022年12月N1真题_AI易读Markdown.md"
STATUS = OUT_DIR / "2022年12月N1真题_AI易读Markdown_质量报告.md"
TMP_DIR = ROOT / "tmp" / "2022_12_ai_markdown_line_ocr"
PS_OCR_LINES = ROOT / "tools" / "windows_ocr_folder_lines.ps1"

CID_RE = re.compile(r"\(cid:\d+\)")
PROBLEM_LINE_RE = re.compile(r"^問題\s*([0-9０-９]+|[一ー−])\b")
BAD_RE = re.compile(r"(てす|問 題|問題 ー|NI|日 浯|人 れ|フロセス|ステッフ|竸争)")


def pdf_text_is_good(raw: str, clean: str) -> bool:
    if raw.count("(cid:") > 15:
        return False
    if len(clean.strip()) < 40:
        return False
    return True


def render_page(page_num: int) -> None:
    prefix = TMP_DIR / f"page_{page_num:04d}"
    subprocess.run(
        [
            str(POPPLER),
            "-f",
            str(page_num),
            "-l",
            str(page_num),
            "-r",
            "180",
            "-png",
            str(SOURCE),
            str(prefix),
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def run_line_ocr() -> None:
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PS_OCR_LINES),
            "-ImageDir",
            str(TMP_DIR),
            "-Language",
            "ja",
        ],
        cwd=ROOT,
        check=True,
    )


def normalize_problem_label(label: str) -> str:
    label = label.replace(" ", "")
    label = label.replace("問題ー", "問題1").replace("問題−", "問題1").replace("問題一", "問題1")
    return label


def cleanup_ocr(text: str) -> str:
    text = normalize_text(text)
    replacements = {
        "問 題": "問題",
        "問題 ー": "問題1",
        "問題ー": "問題1",
        "問題 一": "問題1",
        "問題一": "問題1",
        "N I": "N1",
        "NI": "N1",
        "てす": "です",
        "て す": "です",
        "で す": "です",
        "ま す": "ます",
        "し よ う": "しょう",
        "じ よ": "じょ",
        "ち よ": "ちょ",
        "に よ": "にょ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    jp = r"\u3040-\u30ff\u3400-\u9fff々〆〤ー"
    lines = []
    for line in text.splitlines():
        line = line.strip()
        for _ in range(4):
            line = re.sub(fr"([{jp}])\s+([{jp}])", r"\1\2", line)
        line = re.sub(r"([「『（])\s+", r"\1", line)
        line = re.sub(r"\s+([。、，．？！）」』])", r"\1", line)
        line = re.sub(r"[ \t]{2,}", " ", line)
        if line:
            lines.append(line)
    return "\n".join(lines)


def cleanup_pdf_text(text: str) -> str:
    text = normalize_text(CID_RE.sub("", text))
    text = text.replace("問題1２", "問題12")
    return text


def detected_problem_labels(text: str) -> list[str]:
    labels = []
    for line in text.splitlines():
        match = PROBLEM_LINE_RE.search(line.strip())
        if match:
            raw = "問題" + match.group(1)
            label = normalize_problem_label(raw)
            if label not in labels:
                labels.append(label)
    return labels


def page_quality(page: dict) -> tuple[str, str]:
    text = page["text"]
    if not text.strip():
        return "低", "空白页或未能识别"
    bad = len(BAD_RE.findall(text))
    if page["method"].startswith("OCR") and bad >= 3:
        return "中", f"OCR页，疑似错误 {bad} 处"
    if page["method"].startswith("OCR"):
        return "中", "OCR页，建议抽样校对"
    if bad:
        return "中", f"文字层疑似错误 {bad} 处"
    return "高", "文字层清晰"


def anchor(label: str) -> str:
    return re.sub(r"\s+", "-", label)


def extract_pages() -> list[dict]:
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    pages = []
    with pdfplumber.open(str(SOURCE)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            raw = page.extract_text() or ""
            clean = cleanup_pdf_text(raw)
            needs_ocr = not pdf_text_is_good(raw, clean)
            pages.append(
                {
                    "page": i,
                    "text": clean,
                    "method": "PDF text layer",
                    "needs_ocr": needs_ocr,
                }
            )
            if needs_ocr:
                render_page(i)

    if any(page["needs_ocr"] for page in pages):
        run_line_ocr()

    for page in pages:
        if not page["needs_ocr"]:
            continue
        files = sorted(TMP_DIR.glob(f"page_{page['page']:04d}-*.txt"))
        if files:
            page["text"] = cleanup_ocr(files[-1].read_text(encoding="utf-8"))
        else:
            page["text"] = "[不确定: OCR 未生成文本]"
        page["method"] = "OCR-ja line mode + cleanup"
    return pages


def write_markdown(pages: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    problem_index = []
    for page in pages:
        for label in detected_problem_labels(page["text"]):
            problem_index.append((label, page["page"]))

    with OUT_MD.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# 2022年12月 JLPT N1 真题\n\n")
        f.write("## Metadata\n\n")
        f.write(f"- Source PDF: `{SOURCE.relative_to(ROOT)}`\n")
        f.write(f"- Source PDF MD5: `{md5_file(SOURCE)}`\n")
        f.write(f"- PDF page count: {len(pages)}\n")
        f.write(f"- Extracted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("- Fidelity policy: 原文优先；PDF 文字层损坏的页面使用本地 OCR；不确定处以 `[不确定: 原因]` 标记。\n")
        f.write("- Locator rule: 每页均保留 `PDF Page xxx`，题组索引链接到对应 PDF 页。\n\n")

        f.write("## Problem Locator Index\n\n")
        if problem_index:
            for label, page_num in problem_index:
                f.write(f"- [{label} - PDF page {page_num}](#pdf-page-{page_num:03d}-{anchor(label)})\n")
        else:
            f.write("- [不确定: 未自动识别到题组]\n")
        f.write("\n## Extracted Content\n\n")

        for page in pages:
            q, note = page_quality(page)
            labels = detected_problem_labels(page["text"])
            f.write(f'<a id="pdf-page-{page["page"]:03d}"></a>\n\n')
            f.write(f'## PDF Page {page["page"]:03d}\n\n')
            f.write(f'- Source locator: PDF page {page["page"]}\n')
            f.write(f'- Extraction method: {page["method"]}\n')
            f.write(f'- Page quality: {q} - {note}\n')
            if labels:
                f.write(f'- Detected problem groups: {", ".join(labels)}\n')
            f.write("\n")
            for label in labels:
                f.write(f'<a id="pdf-page-{page["page"]:03d}-{anchor(label)}"></a>\n')
                f.write(f'### {label} (PDF page {page["page"]})\n\n')
            f.write("```text\n")
            f.write(page["text"].strip() or "[不确定: 空白页或 OCR 未识别]")
            f.write("\n```\n\n")


def write_quality_report(pages: list[dict]) -> None:
    quality_rows = []
    for page in pages:
        q, note = page_quality(page)
        quality_rows.append((page["page"], page["method"], q, note, ", ".join(detected_problem_labels(page["text"]))))

    high = sum(1 for row in quality_rows if row[2] == "高")
    mid = sum(1 for row in quality_rows if row[2] == "中")
    low = sum(1 for row in quality_rows if row[2] == "低")
    ocr = sum(1 for row in quality_rows if row[1].startswith("OCR"))
    problems = sum(1 for page in pages for _ in detected_problem_labels(page["text"]))

    with STATUS.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# 2022年12月N1 真题转换质量报告\n\n")
        f.write(f"- Markdown: `{OUT_MD.name}`\n")
        f.write(f"- Source PDF: `{SOURCE.relative_to(ROOT)}`\n")
        f.write(f"- Source PDF MD5: `{md5_file(SOURCE)}`\n")
        f.write(f"- Total pages: {len(pages)}\n")
        f.write(f"- OCR pages: {ocr}\n")
        f.write(f"- Detected problem groups: {problems}\n")
        f.write(f"- Page quality: 高 {high}, 中 {mid}, 低 {low}\n\n")
        f.write("## Page Details\n\n")
        f.write("| PDF页 | 提取方式 | 质量 | 说明 | 题组 |\n")
        f.write("|---:|---|---|---|---|\n")
        for row in quality_rows:
            f.write(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} |\n")
        f.write("\n## Follow-up\n\n")
        if low:
            f.write("- 存在低质量页面，建议人工或视觉模型校对这些页。\n")
        if ocr:
            f.write("- OCR 页已尽量保留原文结构，但仍建议抽查题干、选项和题组编号。\n")


def main() -> int:
    pages = extract_pages()
    write_markdown(pages)
    write_quality_report(pages)
    print(OUT_MD)
    print(STATUS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
