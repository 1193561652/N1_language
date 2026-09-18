import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pdfplumber

from convert_library2_after_2021 import (
    POPPLER,
    PS_OCR,
    ROOT,
    assess_quality,
    detected_problems,
    md5_file,
    normalize_text,
)


SOURCE = ROOT / "library2" / "2022年12月" / "32022年12月N1_真题.pdf"
OUT_DIR = ROOT / "output" / "library2_refined"
TMP_DIR = ROOT / "tmp" / "refine_2022_12_ocr"
OUT_MD = OUT_DIR / "2022年12月N1_标准真题_增强转换.md"
STATUS = OUT_DIR / "转换状态.md"

CID_RE = re.compile(r"\(cid:\d+\)")
PROBLEM_RE = re.compile(r"(問題\s*[0-9０-９]+|問題[一ー−])")


def should_ocr(raw: str, clean: str) -> bool:
    if raw.count("(cid:") > 15:
        return True
    if len(clean) < 40:
        return True
    return False


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


def run_ocr() -> None:
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PS_OCR),
            "-ImageDir",
            str(TMP_DIR),
            "-Language",
            "ja",
        ],
        cwd=ROOT,
        check=True,
    )


def clean_ocr_text(text: str) -> str:
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
        "て は": "では",
        "て す": "です",
        "て き": "でき",
        "し よ う": "しょう",
        "じ よ": "じょ",
        "ち よ": "ちょ",
        "に よ": "にょ",
        "だ っ": "だっ",
        "ま す": "ます",
        "で す": "です",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # Windows OCR inserts spaces between nearly every Japanese character.
    jp = r"\u3040-\u30ff\u3400-\u9fff々〆〤ー"
    for _ in range(4):
        text = re.sub(fr"([{jp}])\s+([{jp}])", r"\1\2", text)
    text = re.sub(r"([０-９0-9])\s+([０-９0-9])", r"\1\2", text)
    text = re.sub(r"\s+([。、，．？！）」』])", r"\1", text)
    text = re.sub(r"([「『（])\s+", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def detected_problem_labels(text: str) -> list[str]:
    labels = []
    for match in PROBLEM_RE.finditer(text):
        label = match.group(1).replace(" ", "")
        label = label.replace("問題ー", "問題1").replace("問題一", "問題1")
        if label not in labels:
            labels.append(label)
    return labels


def anchor(text: str) -> str:
    return re.sub(r"\s+", "-", text)


def build_markdown(pages: list[dict], quality: str, reason: str) -> None:
    problem_index = []
    for page in pages:
        for label in detected_problem_labels(page["text"]):
            problem_index.append((label, page["page"]))

    with OUT_MD.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# 2022年12月N1 标准真题 增强转换\n\n")
        f.write("## Metadata\n\n")
        f.write(f"- Source PDF: `{SOURCE.relative_to(ROOT)}`\n")
        f.write(f"- Source PDF MD5: `{md5_file(SOURCE)}`\n")
        f.write(f"- PDF page count: {len(pages)}\n")
        f.write(f"- Extracted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- Quality: {quality}\n")
        f.write(f"- Quality note: {reason}\n")
        f.write("- Purpose: standard usable Markdown for the 2022-12 N1 exam.\n")
        f.write("- Locator rule: every block records the original PDF page; problem headings link to page anchors.\n\n")
        f.write("## Problem Locator Index\n\n")
        for label, page_num in problem_index:
            f.write(f"- [{label} - PDF page {page_num}](#pdf-page-{page_num:03d}-{anchor(label)})\n")
        if not problem_index:
            f.write("- No problem groups detected.\n")
        f.write("\n## Extracted Content\n\n")

        for page in pages:
            f.write(f'<a id="pdf-page-{page["page"]:03d}"></a>\n\n')
            f.write(f'## PDF Page {page["page"]:03d}\n\n')
            f.write(f'- Source locator: PDF page {page["page"]}\n')
            f.write(f'- Extraction method: {page["method"]}\n')
            labels = detected_problem_labels(page["text"])
            if labels:
                f.write(f'- Detected problem groups: {", ".join(labels)}\n')
                for label in labels:
                    f.write(f'\n<a id="pdf-page-{page["page"]:03d}-{anchor(label)}"></a>\n')
                    f.write(f'### {label} (PDF page {page["page"]})\n')
            f.write("\n```text\n")
            f.write(page["text"].strip())
            f.write("\n```\n\n")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    pages = []
    with pdfplumber.open(str(SOURCE)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            raw = page.extract_text() or ""
            clean = normalize_text(CID_RE.sub("", raw))
            needs_ocr = should_ocr(raw, clean)
            pages.append({"page": i, "text": clean, "method": "PDF text layer", "needs_ocr": needs_ocr})
            if needs_ocr:
                render_page(i)

    if any(p["needs_ocr"] for p in pages):
        run_ocr()

    for page in pages:
        if page["needs_ocr"]:
            txts = sorted(TMP_DIR.glob(f"page_{page['page']:04d}-*.txt"))
            page["text"] = clean_ocr_text(txts[-1].read_text(encoding="utf-8") if txts else "")
            page["method"] = "OCR-ja + cleanup"
        else:
            page["text"] = clean_ocr_text(page["text"])

    quality, reason = assess_quality(SOURCE, pages)
    # This refined output intentionally uses OCR; make the note more precise.
    if quality == "低" and sum(p["method"].startswith("OCR") for p in pages) > 0:
        reason = reason + "；已做OCR清洗，仍需抽样校对"
    build_markdown(pages, quality, reason)

    ocr_pages = sum(p["method"].startswith("OCR") for p in pages)
    problem_count = sum(len(detected_problem_labels(p["text"])) for p in pages)
    with STATUS.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# 2022年12月返工转换状态\n\n")
        f.write("| PDF文件 | 源PDF_MD5 | 转换状态 | 质量 | 质量说明 | 总页数 | OCR页数 | PDF文字层页数 | 题组数 | AI Markdown文件 |\n")
        f.write("|---|---|---|---|---|---:|---:|---:|---:|---|\n")
        f.write(
            f"| {SOURCE.relative_to(ROOT)} | {md5_file(SOURCE)} | Refined standard completed | "
            f"{quality} | {reason} | {len(pages)} | {ocr_pages} | {len(pages)-ocr_pages} | {problem_count} | {OUT_MD.name} |\n"
        )

    print(OUT_MD)
    print(STATUS)
    print(f"pages={len(pages)} ocr_pages={ocr_pages} problem_groups={problem_count} quality={quality}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
