import hashlib
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "n1_markdown"
STATUS_PATH = ROOT / "output" / "n1_ocr_text" / "pdf转换状态.md"
TMP_DIR = ROOT / "tmp" / "n1_ai_markdown_pages"
POPPLER = Path(
    r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe"
)
PS_OCR = ROOT / "tools" / "windows_ocr_folder.ps1"

CID_RE = re.compile(r"\(cid:\d+\)")
SPACE_RE = re.compile(r"[ \t\u3000]+")
BLANK_RE = re.compile(r"\n{3,}")
PROBLEM_RE = re.compile(r"(?:問題|问題|問 題)\s*([0-9０-９一二三四五六七八九十]+)")


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_text(raw: str) -> str:
    text = CID_RE.sub("", raw or "")
    text = text.replace("\x00", "")
    text = "".join(ch for ch in text if ch >= " " or ch in "\n\t")
    text = SPACE_RE.sub(" ", text)
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    return BLANK_RE.sub("\n\n", text).strip()


def useful_text(text: str) -> bool:
    if len(text) < 60:
        return False
    meaningful = sum(1 for ch in text if "\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff")
    if meaningful < 25:
        return False
    junk = sum(1 for ch in text if ch in ".．・|丨")
    return junk / max(len(text), 1) < 0.25


def sort_pdf_key(path: Path) -> tuple[int, int, str]:
    nums = [int(n) for n in re.findall(r"\d+", path.name)]
    year = nums[0] if nums else 9999
    month = nums[1] if len(nums) > 1 else 99
    return year, month, path.name


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
            "220",
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


def problem_markers(text: str) -> list[str]:
    seen = []
    for match in PROBLEM_RE.finditer(text):
        label = match.group(1)
        normalized = f"問題 {label}"
        if normalized not in seen:
            seen.append(normalized)
    return seen


def page_to_markdown(page: dict) -> str:
    page_num = page["page"]
    method = page["method"]
    text = page["text"].strip()
    markers = problem_markers(text)

    lines = [
        f'<a id="pdf-page-{page_num:03d}"></a>',
        "",
        f"## PDF Page {page_num:03d}",
        "",
        f"- Source locator: PDF page {page_num}",
        f"- Extraction method: {method}",
    ]
    if markers:
        lines.append(f"- Detected problem groups: {', '.join(markers)}")
    lines.append("")

    for marker in markers:
        safe = re.sub(r"\s+", "-", marker)
        lines.extend([f'<a id="pdf-page-{page_num:03d}-{safe}"></a>', f"### {marker} (PDF page {page_num})", ""])

    lines.extend(["```text", text, "```", ""])
    return "\n".join(lines)


def extract_pdf(pdf_path: Path) -> tuple[Path, dict]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    work_dir = TMP_DIR / pdf_path.stem
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    pages = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            pdf_text = clean_text(page.extract_text() or "")
            needs_ocr = not useful_text(pdf_text)
            pages.append(
                {
                    "page": index,
                    "text": pdf_text,
                    "needs_ocr": needs_ocr,
                    "method": "PDF text layer",
                }
            )
            if needs_ocr:
                render_page(pdf_path, index, work_dir)

    if any(page["needs_ocr"] for page in pages):
        run_ocr(work_dir)

    for page in pages:
        if not page["needs_ocr"]:
            continue
        txt_files = sorted(work_dir.glob(f"page_{page['page']:04d}-*.txt"))
        page["text"] = txt_files[-1].read_text(encoding="utf-8").strip() if txt_files else ""
        page["method"] = "OCR-ja from rendered PDF page"

    pdf_md5 = md5_file(pdf_path)
    out_path = OUT_DIR / f"{pdf_path.stem}.md"
    problem_index = []
    for page in pages:
        for marker in problem_markers(page["text"]):
            problem_index.append((marker, page["page"]))

    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"# {pdf_path.stem}\n\n")
        f.write("## Metadata\n\n")
        f.write(f"- Source PDF: `{pdf_path.name}`\n")
        f.write(f"- Source PDF MD5: `{pdf_md5}`\n")
        f.write(f"- PDF page count: {len(pages)}\n")
        f.write(f"- Extracted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("- Locator rule: each content block records its original PDF page; detected problem groups are listed with the same page number.\n")
        f.write("- Fidelity note: readable PDF text was used directly; pages with broken text encoding were OCRed from rendered page images.\n\n")
        f.write("## Problem Locator Index\n\n")
        if problem_index:
            for marker, page_num in problem_index:
                safe = re.sub(r"\s+", "-", marker)
                f.write(f"- [{marker} - PDF page {page_num}](#pdf-page-{page_num:03d}-{safe})\n")
        else:
            f.write("- No problem groups detected automatically.\n")
        f.write("\n## Extracted Content\n\n")
        for page in pages:
            f.write(page_to_markdown(page))

    info = {
        "pdf_name": pdf_path.name,
        "pdf_md5": pdf_md5,
        "page_count": len(pages),
        "ocr_pages": sum(1 for page in pages if page["needs_ocr"]),
        "markdown_name": out_path.name,
    }
    return out_path, info


def update_status(info: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    pdfs = sorted([p for p in ROOT.glob("*.pdf") if "N1" in p.name], key=sort_pdf_key)
    rows = []
    existing = {}
    if STATUS_PATH.exists():
        for line in STATUS_PATH.read_text(encoding="utf-8").splitlines():
            if not line.startswith("| ") or line.startswith("| PDF") or line.startswith("|---"):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells:
                existing[cells[0]] = cells

    for pdf in pdfs:
        md5 = md5_file(pdf)
        if pdf.name == info["pdf_name"]:
            rows.append(
                {
                    "pdf": pdf.name,
                    "md5": info["pdf_md5"],
                    "status": "AI Markdown completed",
                    "pages": info["page_count"],
                    "ocr_pages": info["ocr_pages"],
                    "text_pages": info["page_count"] - info["ocr_pages"],
                    "markdown": f"../n1_markdown/{info['markdown_name']}",
                }
            )
        else:
            old = existing.get(pdf.name, [])
            old_status = old[2] if len(old) > 2 else "Pending AI Markdown"
            old_markdown = old[6] if len(old) > 6 else ""
            if old_status != "AI Markdown completed":
                old_status = "Pending AI Markdown"
                old_markdown = ""
            rows.append(
                {
                    "pdf": pdf.name,
                    "md5": md5,
                    "status": old_status,
                    "pages": old[3] if len(old) > 3 else "",
                    "ocr_pages": old[4] if len(old) > 4 else "",
                    "text_pages": old[5] if len(old) > 5 else "",
                    "markdown": old_markdown,
                }
            )

    with STATUS_PATH.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# PDF 转换状态\n\n")
        f.write("| PDF文件 | 源PDF_MD5 | 转换状态 | 总页数 | OCR页数 | PDF文字层页数 | AI Markdown文件 |\n")
        f.write("|---|---|---|---:|---:|---:|---|\n")
        for row in rows:
            f.write(
                f"| {row['pdf']} | {row['md5']} | {row['status']} | {row['pages']} | "
                f"{row['ocr_pages']} | {row['text_pages']} | {row['markdown']} |\n"
            )


def delete_old_ocr_txt() -> int:
    out_dir = ROOT / "output" / "n1_ocr_text"
    deleted = 0
    if not out_dir.exists():
        return deleted
    for path in out_dir.glob("*.txt"):
        path.unlink()
        deleted += 1
    return deleted


def main() -> int:
    pdfs = sorted([p for p in ROOT.glob("*.pdf") if "N1" in p.name], key=sort_pdf_key)
    if not pdfs:
        raise SystemExit("No N1 PDF files found.")
    pdf_path = pdfs[0]
    print(f"Processing first PDF: {pdf_path.name}", flush=True)
    md_path, info = extract_pdf(pdf_path)
    update_status(info)
    deleted = delete_old_ocr_txt()
    print(f"Markdown: {md_path}", flush=True)
    print(f"Deleted old OCR txt files: {deleted}", flush=True)
    print(f"Status: {STATUS_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
