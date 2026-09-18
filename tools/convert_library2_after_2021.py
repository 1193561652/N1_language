import hashlib
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "library2"
OUT_DIR = ROOT / "output" / "library2_after_2021_markdown"
TMP_ROOT = ROOT / "tmp" / "library2_after_2021_ocr_pages"
STATUS_PATH = OUT_DIR / "转换状态.md"
POPPLER = Path(
    r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe"
)
PS_OCR = ROOT / "tools" / "windows_ocr_folder.ps1"

CID_RE = re.compile(r"\(cid:\d+\)")
NUL_RE = re.compile(r"\x00+")
SPACE_RE = re.compile(r"[ \t\u3000]+")
BLANK_RE = re.compile(r"\n{3,}")
PROBLEM_RE = re.compile(r"(問題\s*[0-9０-９]+|问题\s*[0-9０-９]+)")
BAD_PATTERNS = [
    "てす",
    "20 川",
    "日 浯",
    "問題 ー",
    "問 題",
    "人 れ",
    "人れる",
    "フロセス",
    "ステッフ",
    "体業",
    "体暇",
    "たらしない",
    "すうすう",
    "竸争",
]


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(raw: str) -> str:
    text = CID_RE.sub("", raw or "")
    text = NUL_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(SPACE_RE.sub(" ", line).strip() for line in text.splitlines())
    return BLANK_RE.sub("\n\n", text).strip()


def is_good_pdf_text(raw: str, clean: str) -> bool:
    cid_count = raw.count("(cid:")
    if cid_count > 15:
        return False
    if len(clean) >= 20 and cid_count == 0:
        return True
    if len(clean) < 80:
        return False
    cjk = sum(1 for ch in clean if "\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff")
    return cjk >= 40


def date_from_path(path: Path) -> tuple[int, int] | None:
    for part in path.parts:
        match = re.fullmatch(r"(\d{4})年(?:(\d{1,2})月)?", part)
        if match:
            return int(match.group(1)), int(match.group(2) or 0)
    return None


def selected_pdfs() -> list[Path]:
    pdfs = []
    for path in LIBRARY.rglob("*.pdf"):
        date = date_from_path(path.relative_to(LIBRARY))
        if date and date > (2021, 7):
            pdfs.append(path)
    return sorted(pdfs, key=lambda p: str(p.relative_to(LIBRARY)))


def safe_output_name(path: Path) -> str:
    rel = path.relative_to(LIBRARY)
    stem = "__".join(rel.with_suffix("").parts)
    return stem.replace("/", "__").replace("\\", "__") + ".md"


def work_dir_for(path: Path) -> Path:
    return TMP_ROOT / safe_output_name(path).removesuffix(".md")


def render_page(pdf_path: Path, page_num: int, image_dir: Path) -> None:
    prefix = image_dir / f"page_{page_num:04d}"
    subprocess.run(
        [
            str(POPPLER),
            "-f",
            str(page_num),
            "-l",
            str(page_num),
            "-r",
            "240",
            "-png",
            str(pdf_path),
            str(prefix),
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def ocr_language_for(path: Path) -> str:
    name = path.name
    if any(key in name for key in ["答案", "解析", "译文", "答题卡"]):
        return "zh-Hans-CN"
    return "ja"


def run_ocr(image_dir: Path, language: str) -> None:
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PS_OCR),
            "-ImageDir",
            str(image_dir),
            "-Language",
            language,
        ],
        cwd=ROOT,
        check=True,
    )


def anchor_label(text: str) -> str:
    return re.sub(r"\s+", "-", text.strip())


def detected_problems(text: str) -> list[str]:
    seen = []
    for match in PROBLEM_RE.finditer(text):
        label = re.sub(r"\s+", "", match.group(1))
        if label not in seen:
            seen.append(label)
    return seen


def assess_quality(pdf_path: Path, pages: list[dict]) -> tuple[str, str]:
    page_count = len(pages)
    ocr_pages = sum(1 for page in pages if page["method"].startswith("OCR"))
    text = "\n".join(page["text"] for page in pages)
    char_count = len(text)
    bad_hits = sum(text.count(pattern) for pattern in BAD_PATTERNS)
    problem_count = len({(problem, page["page"]) for page in pages for problem in detected_problems(page["text"])})
    reasons = []

    if page_count == 0 or char_count < max(200, page_count * 30):
        reasons.append("正文字符过少")
    if ocr_pages / max(page_count, 1) > 0.5:
        reasons.append("OCR页占比高")
    if bad_hits > 5:
        reasons.append(f"疑似OCR错误较多({bad_hits})")
    if "真题" in pdf_path.name and problem_count < 8:
        reasons.append(f"真题题组识别偏少({problem_count})")
    if any(page["text"].strip() == "" for page in pages):
        reasons.append("存在空白提取页")

    if reasons:
        return "低" if len(reasons) >= 2 or "正文字符过少" in reasons else "中", "；".join(reasons)
    if ocr_pages:
        return "中", f"少量页面使用OCR({ocr_pages}/{page_count})"
    return "高", "PDF文字层清晰"


def build_markdown(pdf_path: Path, pages: list[dict], out_path: Path, quality: str, reason: str) -> None:
    problem_index = []
    for page in pages:
        for problem in detected_problems(page["text"]):
            problem_index.append((problem, page["page"]))

    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"# {pdf_path.stem}\n\n")
        f.write("## Metadata\n\n")
        f.write(f"- Source PDF: `{pdf_path.relative_to(ROOT)}`\n")
        f.write(f"- Source PDF MD5: `{md5_file(pdf_path)}`\n")
        f.write(f"- PDF page count: {len(pages)}\n")
        f.write(f"- Extracted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- Quality: {quality}\n")
        f.write(f"- Quality note: {reason}\n")
        f.write("- Locator rule: every content block is tied to its original PDF page; detected problem groups link back to page anchors.\n")
        f.write("- Extraction rule: PDF text layer is used when readable; OCR is used only for pages whose text layer is missing or broken.\n\n")

        f.write("## Problem Locator Index\n\n")
        if problem_index:
            for problem, page_num in problem_index:
                f.write(f"- [{problem} - PDF page {page_num}](#pdf-page-{page_num:03d}-{anchor_label(problem)})\n")
        else:
            f.write("- No problem groups detected.\n")
        f.write("\n## Extracted Content\n\n")

        for page in pages:
            page_num = page["page"]
            problems = detected_problems(page["text"])
            f.write(f'<a id="pdf-page-{page_num:03d}"></a>\n\n')
            f.write(f"## PDF Page {page_num:03d}\n\n")
            f.write(f"- Source locator: PDF page {page_num}\n")
            f.write(f"- Extraction method: {page['method']}\n")
            if problems:
                f.write(f"- Detected problem groups: {', '.join(problems)}\n")
            f.write("\n```text\n")
            f.write(page["text"].strip())
            f.write("\n```\n\n")


def convert_pdf(pdf_path: Path) -> dict:
    out_path = OUT_DIR / safe_output_name(pdf_path)
    work_dir = work_dir_for(pdf_path)
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    pages = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            raw = page.extract_text() or ""
            clean = normalize_text(raw)
            needs_ocr = not is_good_pdf_text(raw, clean)
            pages.append(
                {
                    "page": index,
                    "text": clean,
                    "needs_ocr": needs_ocr,
                    "method": "PDF text layer",
                }
            )
            if needs_ocr:
                render_page(pdf_path, index, work_dir)

    if any(page["needs_ocr"] for page in pages):
        run_ocr(work_dir, ocr_language_for(pdf_path))

    for page in pages:
        if not page["needs_ocr"]:
            continue
        txt_files = sorted(work_dir.glob(f"page_{page['page']:04d}-*.txt"))
        if txt_files:
            page["text"] = normalize_text(txt_files[-1].read_text(encoding="utf-8"))
        page["method"] = f"OCR-{ocr_language_for(pdf_path)} from rendered PDF page"

    quality, reason = assess_quality(pdf_path, pages)
    build_markdown(pdf_path, pages, out_path, quality, reason)
    ocr_pages = sum(1 for page in pages if page["method"].startswith("OCR"))
    problem_count = len({(problem, page["page"]) for page in pages for problem in detected_problems(page["text"])})
    return {
        "pdf": str(pdf_path.relative_to(ROOT)),
        "md5": md5_file(pdf_path),
        "status": "AI Markdown completed",
        "pages": len(pages),
        "ocr_pages": ocr_pages,
        "text_pages": len(pages) - ocr_pages,
        "quality": quality,
        "reason": reason,
        "problem_count": problem_count,
        "markdown": out_path.name,
    }


def write_status(rows: list[dict]) -> None:
    with STATUS_PATH.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# library2 2021年7月之后转换状态\n\n")
        f.write("| PDF文件 | 源PDF_MD5 | 转换状态 | 质量 | 质量说明 | 总页数 | OCR页数 | PDF文字层页数 | 题组数 | AI Markdown文件 |\n")
        f.write("|---|---|---|---|---|---:|---:|---:|---:|---|\n")
        for row in rows:
            f.write(
                f"| {row['pdf']} | {row['md5']} | {row['status']} | {row['quality']} | {row['reason']} | "
                f"{row['pages']} | {row['ocr_pages']} | {row['text_pages']} | {row['problem_count']} | {row['markdown']} |\n"
            )


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    pdfs = selected_pdfs()
    print(f"PDFs selected: {len(pdfs)}", flush=True)
    rows = []
    for index, pdf_path in enumerate(pdfs, start=1):
        print(f"[{index}/{len(pdfs)}] {pdf_path.relative_to(ROOT)}", flush=True)
        rows.append(convert_pdf(pdf_path))
        write_status(rows)
    print(f"Status: {STATUS_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
