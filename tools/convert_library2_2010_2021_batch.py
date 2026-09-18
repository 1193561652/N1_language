from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "library2"
OUT = ROOT / "output" / "library2_2010_2021_markdown"
TMP = ROOT / "tmp" / "library2_2010_2021_ocr_pages"
STATUS = OUT / "转换状态.md"
QUALITY_REPORT = OUT / "质量报告.md"
POPPLER = Path(
    r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe"
)
OCR_SCRIPT = ROOT / "tools" / "windows_ocr_folder_lines.ps1"

CID_RE = re.compile(r"\(cid:\d+\)")
SPACE_RE = re.compile(r"[ \t\u3000]+")
BLANK_RE = re.compile(r"\n{3,}")
PROBLEM_RE = re.compile(r"(問題\s*[0-9０-９]+|问题\s*[0-9０-９]+)")

PERIODS = [
    "2010年7月",
    "2010年12月",
    "2011年7月",
    "2011年12月",
    "2012年7月",
    "2012年12月",
    "2013年7月",
    "2013年12月",
    "2014年7月",
    "2014年12月",
    "2015年7月",
    "2015年12月",
    "2016年7月",
    "2016年12月",
    "2017年7月",
    "2017年12月",
    "2018年7月",
    "2018年12月",
    "2019年7月",
    "2019年12月",
    "2020年12月",
    "2021年7月",
]


def normalize(raw: str) -> str:
    text = CID_RE.sub("", raw or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = "\n".join(SPACE_RE.sub(" ", line).strip() for line in text.splitlines())
    return BLANK_RE.sub("\n\n", text).strip()


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cjk_count(text: str) -> int:
    return sum(1 for ch in text if "\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff")


def is_good_text(raw: str, clean: str) -> bool:
    if raw.count("(cid:") > 10:
        return False
    if len(clean) >= 120 and cjk_count(clean) >= 50:
        return True
    if "問題" in clean and len(clean) >= 60:
        return True
    return False


def period_sort_key(period: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{4})年(\d{1,2})月", period)
    if not match:
        return (9999, 99)
    return (int(match.group(1)), int(match.group(2)))


def candidate_paths(period: str) -> list[Path]:
    if period == "2021年7月":
        folder = LIB / "2021年7月"
    else:
        folder = LIB / "2010年-2020年" / period
    return sorted(folder.glob("*N1_真题.pdf"))


def score_pdf(path: Path) -> tuple[int, int, int, int]:
    good_pages = 0
    problems = 0
    chars = 0
    cid = 0
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            raw = page.extract_text() or ""
            clean = normalize(raw)
            chars += len(clean)
            cid += raw.count("(cid:")
            problems += len(PROBLEM_RE.findall(clean))
            if is_good_text(raw, clean):
                good_pages += 1
    score = good_pages * 100 + problems * 20 + min(chars // 1000, 50) - cid
    return score, good_pages, problems, chars


def selected_pdfs() -> list[tuple[str, Path]]:
    selected = []
    for period in PERIODS:
        paths = candidate_paths(period)
        if not paths:
            continue
        best = max(paths, key=lambda path: score_pdf(path)[0])
        selected.append((period, best))
    return selected


def render_page(pdf: Path, page_num: int, image_dir: Path) -> None:
    prefix = image_dir / f"page_{page_num:04d}"
    subprocess.run(
        [
            str(POPPLER),
            "-f",
            str(page_num),
            "-l",
            str(page_num),
            "-r",
            "260",
            "-png",
            str(pdf),
            str(prefix),
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def run_ocr(image_dir: Path) -> None:
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(OCR_SCRIPT),
            "-ImageDir",
            str(image_dir),
            "-Language",
            "ja",
        ],
        cwd=ROOT,
        check=True,
    )


def detected_problems(text: str) -> list[str]:
    seen = []
    for match in PROBLEM_RE.finditer(text):
        label = re.sub(r"\s+", "", match.group(1))
        if label not in seen:
            seen.append(label)
    return seen


def page_quality(page: dict) -> tuple[str, str, bool]:
    text = page["text"].strip()
    if page["method"].startswith("OCR"):
        if len(text) >= 80 and cjk_count(text) >= 40:
            return "中", "使用本地OCR补足，需抽查文字间距和个别识别错误", True
        if len(text) < 15:
            return "低", "OCR后仍几乎无可用文字，可能为空白页/封面页或识别失败", True
        return "低", "OCR后文字较少，建议人工校对", True
    if len(text) < 15:
        return "中", "该页文字很少，可能是封面、空白页或说明页", False
    if cjk_count(text) < 20 and len(text) < 80:
        return "中", "该页有效日文较少，建议抽查", True
    return "高", "PDF文字层清晰", False


def overall_quality(page_rows: list[dict], problem_count: int) -> tuple[str, str]:
    manual_pages = [p for p in page_rows if p["manual_check"]]
    low_pages = [p for p in page_rows if p["quality"] == "低"]
    ocr_pages = [p for p in page_rows if p["method"].startswith("OCR")]
    reasons = []
    if low_pages:
        reasons.append(f"{len(low_pages)}页低质量")
    if ocr_pages:
        reasons.append(f"{len(ocr_pages)}页使用OCR")
    if problem_count < 16:
        reasons.append(f"题组识别偏少({problem_count})")
    if not reasons:
        return "高", "PDF文字层整体清晰"
    if low_pages or problem_count < 18 or len(manual_pages) >= 5:
        return "中", "；".join(reasons)
    return "中高", "；".join(reasons)


def anchor(text: str) -> str:
    return re.sub(r"\s+", "-", text.strip())


def output_name(period: str) -> str:
    return f"{period}N1真题_主底稿.md"


def convert_one(period: str, pdf: Path) -> dict:
    work = TMP / period
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    pages = []
    with pdfplumber.open(str(pdf)) as doc:
        for index, page in enumerate(doc.pages, start=1):
            raw = page.extract_text() or ""
            clean = normalize(raw)
            needs_ocr = not is_good_text(raw, clean)
            row = {
                "page": index,
                "text": clean,
                "method": "PDF text layer",
                "needs_ocr": needs_ocr,
            }
            pages.append(row)
            if needs_ocr:
                render_page(pdf, index, work)

    if any(page["needs_ocr"] for page in pages):
        run_ocr(work)

    for page in pages:
        if not page["needs_ocr"]:
            continue
        txt_files = sorted(work.glob(f"page_{page['page']:04d}-*.txt"))
        if txt_files:
            page["text"] = normalize(txt_files[-1].read_text(encoding="utf-8"))
        page["method"] = "OCR-ja from rendered PDF page"

    problem_index = []
    for page in pages:
        page["problems"] = detected_problems(page["text"])
        quality, reason, manual = page_quality(page)
        page["quality"] = quality
        page["quality_reason"] = reason
        page["manual_check"] = manual
        for problem in page["problems"]:
            problem_index.append((problem, page["page"]))

    unique_problem_count = len({(problem, page) for problem, page in problem_index})
    quality, reason = overall_quality(pages, unique_problem_count)
    out_path = OUT / output_name(period)
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"# {period} JLPT N1 真题\n\n")
        f.write("## Metadata\n\n")
        f.write(f"- Source PDF: `{pdf.relative_to(ROOT)}`\n")
        f.write(f"- Source PDF MD5: `{md5_file(pdf)}`\n")
        f.write(f"- PDF page count: {len(pages)}\n")
        f.write(f"- Extracted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- Overall quality: {quality}\n")
        f.write(f"- Quality note: {reason}\n")
        f.write("- Locator rule: each page starts with `## PDF Page xxx`; detected problem groups are listed below and inside page metadata.\n")
        f.write("- Fidelity rule: PDF text layer is used when readable; OCR is used only where the text layer is missing or broken.\n\n")

        f.write("## Problem Locator Index\n\n")
        if problem_index:
            for problem, page_num in problem_index:
                f.write(f"- [{problem} - PDF Page {page_num:03d}](#pdf-page-{page_num:03d}-{anchor(problem)})\n")
        else:
            f.write("- No problem groups detected.\n")
        f.write("\n## Extracted Content\n\n")

        for page in pages:
            page_num = page["page"]
            for problem in page["problems"]:
                f.write(f'<a id="pdf-page-{page_num:03d}-{anchor(problem)}"></a>\n')
            f.write(f'<a id="pdf-page-{page_num:03d}"></a>\n\n')
            f.write(f"## PDF Page {page_num:03d}\n\n")
            f.write(f"- Source locator: PDF page {page_num}\n")
            f.write(f"- Extraction method: {page['method']}\n")
            f.write(f"- Page quality: {page['quality']} - {page['quality_reason']}\n")
            if page["problems"]:
                f.write(f"- Detected problem groups: {', '.join(page['problems'])}\n")
            f.write("\n")
            if page["text"].strip():
                f.write(page["text"].strip() + "\n\n")
            else:
                f.write("[不确定: 该页未提取到可用文字，可能为空白页或图片页]\n\n")

    manual_pages = [page["page"] for page in pages if page["manual_check"]]
    ocr_pages = [page["page"] for page in pages if page["method"].startswith("OCR")]
    low_pages = [page["page"] for page in pages if page["quality"] == "低"]
    return {
        "period": period,
        "pdf": str(pdf.relative_to(ROOT)),
        "md5": md5_file(pdf),
        "status": "完成",
        "quality": quality,
        "reason": reason,
        "pages": len(pages),
        "text_pages": len(pages) - len(ocr_pages),
        "ocr_pages": ocr_pages,
        "problem_count": unique_problem_count,
        "manual_pages": manual_pages,
        "low_pages": low_pages,
        "markdown": out_path.name,
    }


def page_list(pages: list[int]) -> str:
    return "无" if not pages else ", ".join(f"{page:03d}" for page in pages)


def write_reports(rows: list[dict]) -> None:
    with STATUS.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# 2010年-2021年7月 转换状态\n\n")
        f.write("| 期次 | PDF文件 | 源PDF_MD5 | 状态 | 质量 | 质量说明 | 总页数 | PDF文字层页数 | OCR页数 | 题组数 | 需人工校对页数 | 需人工校对页 | AI Markdown文件 |\n")
        f.write("|---|---|---|---|---|---|---:|---:|---:|---:|---:|---|---|\n")
        for row in rows:
            f.write(
                f"| {row['period']} | `{row['pdf']}` | `{row['md5']}` | {row['status']} | {row['quality']} | {row['reason']} | "
                f"{row['pages']} | {row['text_pages']} | {len(row['ocr_pages'])} | {row['problem_count']} | "
                f"{len(row['manual_pages'])} | {page_list(row['manual_pages'])} | `{row['markdown']}` |\n"
            )

    total_pages = sum(row["pages"] for row in rows)
    total_manual = sum(len(row["manual_pages"]) for row in rows)
    total_ocr = sum(len(row["ocr_pages"]) for row in rows)
    quality_counts = {}
    for row in rows:
        quality_counts[row["quality"]] = quality_counts.get(row["quality"], 0) + 1

    with QUALITY_REPORT.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# 2010年-2021年7月 质量报告\n\n")
        f.write("## 总览\n\n")
        f.write(f"- 覆盖期次: {len(rows)}\n")
        f.write(f"- 覆盖PDF页数: {total_pages}\n")
        f.write(f"- 使用OCR页数: {total_ocr}\n")
        f.write(f"- 需要人工校对页数: {total_manual}\n")
        f.write("- 质量分布: " + "；".join(f"{key}: {value}" for key, value in sorted(quality_counts.items())) + "\n")
        f.write("- 说明: 需人工校对页主要来自本地OCR补足页、低文字量页或题组识别偏少的异常期次。\n\n")

        f.write("## 每期明细\n\n")
        f.write("| 期次 | 质量 | 总页数 | OCR页 | 需人工校对页数 | 需人工校对页 | 质量说明 |\n")
        f.write("|---|---|---:|---|---:|---|---|\n")
        for row in rows:
            f.write(
                f"| {row['period']} | {row['quality']} | {row['pages']} | {page_list(row['ocr_pages'])} | "
                f"{len(row['manual_pages'])} | {page_list(row['manual_pages'])} | {row['reason']} |\n"
            )

        needs = [row for row in rows if row["manual_pages"]]
        f.write("\n## 需要人工校对\n\n")
        if not needs:
            f.write("- 无。\n")
        else:
            for row in needs:
                f.write(f"- {row['period']}: {len(row['manual_pages'])}页，PDF Page {page_list(row['manual_pages'])}。\n")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    rows = []
    targets = selected_pdfs()
    for index, (period, pdf) in enumerate(targets, start=1):
        print(f"[{index}/{len(targets)}] {period}: {pdf.relative_to(ROOT)}", flush=True)
        row = convert_one(period, pdf)
        rows.append(row)
        write_reports(rows)
    print(STATUS, flush=True)
    print(QUALITY_REPORT, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
