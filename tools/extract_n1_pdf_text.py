import re
import shutil
import subprocess
import sys
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "n1_ocr_text"
TMP_DIR = ROOT / "tmp" / "n1_ocr_pages"
POPPLER = Path(
    r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe"
)
PS_OCR = ROOT / "tools" / "windows_ocr_folder.ps1"

CID_RE = re.compile(r"\(cid:\d+\)")
SPACE_RE = re.compile(r"[ \t\u3000]+")
BLANK_RE = re.compile(r"\n{3,}")


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


def pdf_sort_key(path: Path):
    m = re.search(r"(\d{4})年(\d{1,2})月", path.name)
    if not m:
        return (9999, 99, path.name)
    return (int(m.group(1)), int(m.group(2)), path.name)


def render_page(pdf_path: Path, page_num: int, image_dir: Path) -> Path:
    prefix = image_dir / f"page_{page_num:04d}"
    subprocess.run(
        [
            str(POPPLER),
            "-f",
            str(page_num),
            "-l",
            str(page_num),
            "-r",
            "200",
            "-png",
            str(pdf_path),
            str(prefix),
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    matches = sorted(image_dir.glob(f"page_{page_num:04d}-*.png"))
    if not matches:
        raise RuntimeError(f"Rendered image not found for page {page_num}: {pdf_path.name}")
    return matches[-1]


def run_ocr(image_dir: Path):
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


def process_pdf(pdf_path: Path) -> tuple[Path, int, int]:
    print(f"Processing {pdf_path.name}", flush=True)
    work_dir = TMP_DIR / pdf_path.stem
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    pages: list[dict] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            raw = page.extract_text() or ""
            text = clean_text(raw)
            needs_ocr = not useful_text(text)
            pages.append({"page": index, "text": text, "needs_ocr": needs_ocr})
            if needs_ocr:
                render_page(pdf_path, index, work_dir)

    ocr_count = sum(1 for page in pages if page["needs_ocr"])
    if ocr_count:
        run_ocr(work_dir)
        for page in pages:
            if not page["needs_ocr"]:
                continue
            txt_files = sorted(work_dir.glob(f"page_{page['page']:04d}-*.txt"))
            page["text"] = txt_files[-1].read_text(encoding="utf-8").strip() if txt_files else ""

    out_path = OUT_DIR / f"{pdf_path.stem}.txt"
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"# {pdf_path.stem}\n\n")
        for page in pages:
            method = "OCR-ja" if page["needs_ocr"] else "PDF-text"
            f.write(f"## Page {page['page']:03d} [{method}]\n\n")
            f.write((page["text"] or "").strip())
            f.write("\n\n")

    return out_path, len(pages), ocr_count


def main() -> int:
    if not POPPLER.exists():
        raise SystemExit(f"Missing Poppler renderer: {POPPLER}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(ROOT.glob("*N1真题及全解析*.pdf"), key=pdf_sort_key)
    if not pdfs:
        raise SystemExit("No N1 PDF files found.")

    summary = []
    for pdf_path in pdfs:
        summary.append((pdf_path.name, *process_pdf(pdf_path)))

    combined = OUT_DIR / "N1真题OCR文本合集.txt"
    with combined.open("w", encoding="utf-8", newline="\n") as out:
        for name, txt_path, page_count, ocr_count in summary:
            out.write(f"\n\n{'=' * 80}\n{name}\npages={page_count}, ocr_pages={ocr_count}\n{'=' * 80}\n\n")
            out.write(txt_path.read_text(encoding="utf-8"))

    report = OUT_DIR / "OCR提取报告.txt"
    with report.open("w", encoding="utf-8", newline="\n") as f:
        f.write("N1 真题 OCR 提取报告\n\n")
        f.write(f"PDF 数量: {len(summary)}\n")
        f.write(f"输出目录: {OUT_DIR}\n")
        f.write(f"合并文本: {combined.name}\n\n")
        for name, txt_path, page_count, ocr_count in summary:
            f.write(f"- {name}: {page_count} 页, OCR {ocr_count} 页, 输出 {txt_path.name}\n")

    print(f"Done. Output: {OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
