import re
from pathlib import Path

from convert_library2_after_2021 import (
    OUT_DIR,
    ROOT,
    STATUS_PATH,
    assess_quality,
    detected_problems,
    md5_file,
    selected_pdfs,
    safe_output_name,
)


METHOD_RE = re.compile(r"^- Extraction method: (.+)$", re.MULTILINE)
BLOCK_RE = re.compile(r"```text\n(.*?)\n```", re.DOTALL)
PAGE_RE = re.compile(r"^## PDF Page", re.MULTILINE)


def read_pages(md_path: Path) -> list[dict]:
    text = md_path.read_text(encoding="utf-8")
    methods = METHOD_RE.findall(text)
    blocks = BLOCK_RE.findall(text)
    count = max(len(methods), len(blocks), len(PAGE_RE.findall(text)))
    pages = []
    for i in range(count):
        pages.append(
            {
                "page": i + 1,
                "method": methods[i] if i < len(methods) else "Unknown",
                "text": blocks[i] if i < len(blocks) else "",
            }
        )
    return pages


def main() -> int:
    rows = []
    for pdf_path in selected_pdfs():
        md_name = safe_output_name(pdf_path)
        md_path = OUT_DIR / md_name
        if not md_path.exists():
            rows.append(
                {
                    "pdf": str(pdf_path.relative_to(ROOT)),
                    "md5": md5_file(pdf_path),
                    "status": "Pending",
                    "pages": "",
                    "ocr_pages": "",
                    "text_pages": "",
                    "quality": "未处理",
                    "reason": "Markdown文件不存在",
                    "problem_count": "",
                    "markdown": "",
                }
            )
            continue
        pages = read_pages(md_path)
        quality, reason = assess_quality(pdf_path, pages)
        ocr_pages = sum(1 for page in pages if page["method"].startswith("OCR"))
        problem_count = len({(problem, page["page"]) for page in pages for problem in detected_problems(page["text"])})
        rows.append(
            {
                "pdf": str(pdf_path.relative_to(ROOT)),
                "md5": md5_file(pdf_path),
                "status": "AI Markdown completed",
                "pages": len(pages),
                "ocr_pages": ocr_pages,
                "text_pages": len(pages) - ocr_pages,
                "quality": quality,
                "reason": reason,
                "problem_count": problem_count,
                "markdown": md_name,
            }
        )

    with STATUS_PATH.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# library2 2021年7月之后转换状态\n\n")
        f.write("| PDF文件 | 源PDF_MD5 | 转换状态 | 质量 | 质量说明 | 总页数 | OCR页数 | PDF文字层页数 | 题组数 | AI Markdown文件 |\n")
        f.write("|---|---|---|---|---|---:|---:|---:|---:|---|\n")
        for row in rows:
            f.write(
                f"| {row['pdf']} | {row['md5']} | {row['status']} | {row['quality']} | {row['reason']} | "
                f"{row['pages']} | {row['ocr_pages']} | {row['text_pages']} | {row['problem_count']} | {row['markdown']} |\n"
            )
    print(STATUS_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
