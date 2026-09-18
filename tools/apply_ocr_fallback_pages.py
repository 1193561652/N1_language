from __future__ import annotations

import re
from pathlib import Path


REPAIR_DIR = Path(__file__).resolve().parents[1] / r"tmp\gemini_pdf_to_markdown_batch\repair_2023_12"
CACHE_DIR = Path(__file__).resolve().parents[1] / r"tmp\gemini_pdf_to_markdown_batch\pages\12023年12月N1_真题"


def main() -> None:
    for txt_path in sorted(REPAIR_DIR.glob("page_*.txt")):
        match = re.search(r"page_(\d{3})-", txt_path.name)
        if not match:
            continue
        page_num = int(match.group(1))
        text = txt_path.read_text(encoding="utf-8").strip()
        out = CACHE_DIR / f"page_{page_num:03d}.md"
        markdown = (
            f"## PDF Page {page_num:03d}\n\n"
            "<!-- extraction_method: Windows local OCR fallback; reason: Gemini finishReason=RECITATION or empty response -->\n\n"
            f"{text}\n\n"
            "<!-- page_quality: 中; reason: Gemini无法逐字输出，本页使用本地OCR兜底，需人工校对题号、选项和长文换行 -->\n"
        )
        out.write_text(markdown, encoding="utf-8")
        print(out)


if __name__ == "__main__":
    main()

