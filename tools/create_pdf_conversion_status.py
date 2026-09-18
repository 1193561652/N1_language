import hashlib
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "n1_ocr_text"
REPORT = OUT_DIR / "OCR提取报告.txt"


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    report_text = REPORT.read_text(encoding="utf-8")
    pattern = re.compile(r"- (.+?\.pdf): (\d+) 页, OCR (\d+) 页, 输出 (.+?\.txt)")

    rows = []
    for match in pattern.finditer(report_text):
        pdf_name, total_pages, ocr_pages, txt_name = match.groups()
        pdf_path = ROOT / pdf_name
        txt_path = OUT_DIR / txt_name
        total_pages_int = int(total_pages)
        ocr_pages_int = int(ocr_pages)
        stat = txt_path.stat() if txt_path.exists() else None
        rows.append(
            {
                "PDF文件": pdf_name,
                "源PDF_MD5": md5_file(pdf_path) if pdf_path.exists() else "",
                "转换状态": "已完成" if txt_path.exists() else "输出缺失",
                "总页数": total_pages_int,
                "OCR页数": ocr_pages_int,
                "PDF文字层页数": total_pages_int - ocr_pages_int,
                "输出文本文件": txt_name,
                "输出文本大小(bytes)": stat.st_size if stat else "",
                "输出更新时间": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                if stat
                else "",
            }
        )

    md_path = OUT_DIR / "pdf转换状态.md"
    with md_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# PDF 转换状态\n\n")
        f.write("| PDF文件 | 源PDF_MD5 | 转换状态 | 总页数 | OCR页数 | PDF文字层页数 | 输出文本文件 |\n")
        f.write("|---|---|---|---:|---:|---:|---|\n")
        for row in rows:
            f.write(
                f"| {row['PDF文件']} | {row['源PDF_MD5']} | {row['转换状态']} | {row['总页数']} | "
                f"{row['OCR页数']} | {row['PDF文字层页数']} | {row['输出文本文件']} |\n"
            )

    print(md_path)
    print(f"rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
