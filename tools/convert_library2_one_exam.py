import hashlib
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "library2" / "2010年-2020年" / "2010年7月" / "32010年07月N1_真题.pdf"
OUT_DIR = ROOT / "output" / "library2_markdown"
TMP_DIR = ROOT / "tmp" / "library2_ocr_pages" / SOURCE.stem
STATUS_PATH = OUT_DIR / "转换状态.md"
POPPLER = Path(
    r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe"
)
PS_OCR = ROOT / "tools" / "windows_ocr_folder.ps1"

CID_RE = re.compile(r"\(cid:\d+\)")
NUL_RE = re.compile(r"\x00+")
SPACE_RE = re.compile(r"[ \t\u3000]+")
BLANK_RE = re.compile(r"\n{3,}")
PROBLEM_RE = re.compile(r"(問題\s*[0-9０-９]+)")


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


def run_ocr(image_dir: Path) -> None:
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
            "ja",
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


def build_markdown(pdf_path: Path, pages: list[dict], out_path: Path) -> None:
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
            f.write("\n")
            for problem in problems:
                f.write(f'<a id="pdf-page-{page_num:03d}-{anchor_label(problem)}"></a>\n')
                f.write(f"### {problem} (PDF page {page_num})\n\n")
            f.write("```text\n")
            f.write(page["text"].strip())
            f.write("\n```\n\n")


def write_status(pdf_path: Path, pages: list[dict], md_path: Path) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ocr_pages = sum(1 for page in pages if page["method"].startswith("OCR"))
    with STATUS_PATH.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# library2 转换状态\n\n")
        f.write("| PDF文件 | 源PDF_MD5 | 转换状态 | 总页数 | OCR页数 | PDF文字层页数 | AI Markdown文件 |\n")
        f.write("|---|---|---|---:|---:|---:|---|\n")
        f.write(
            f"| {pdf_path.relative_to(ROOT)} | {md5_file(pdf_path)} | AI Markdown completed | "
            f"{len(pages)} | {ocr_pages} | {len(pages) - ocr_pages} | {md_path.name} |\n"
        )


def convert() -> tuple[Path, list[dict]]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    pages = []
    with pdfplumber.open(str(SOURCE)) as pdf:
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
                render_page(SOURCE, index, TMP_DIR)

    if any(page["needs_ocr"] for page in pages):
        run_ocr(TMP_DIR)

    for page in pages:
        if not page["needs_ocr"]:
            continue
        txt_files = sorted(TMP_DIR.glob(f"page_{page['page']:04d}-*.txt"))
        if txt_files:
            page["text"] = normalize_text(txt_files[-1].read_text(encoding="utf-8"))
        page["method"] = "OCR-ja from rendered PDF page"

    md_path = OUT_DIR / f"{SOURCE.stem}.md"
    build_markdown(SOURCE, pages, md_path)
    write_status(SOURCE, pages, md_path)
    return md_path, pages


def main() -> int:
    md_path, pages = convert()
    ocr_pages = sum(1 for page in pages if page["method"].startswith("OCR"))
    print(f"Markdown: {md_path}")
    print(f"Pages: {len(pages)}")
    print(f"OCR pages: {ocr_pages}")
    print(f"Status: {STATUS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
