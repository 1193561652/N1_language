from __future__ import annotations

import importlib.util
import re
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "output" / "library2_2010_2021_markdown"
STATUS = SOURCE_DIR / "转换状态.md"
OUT = ROOT / "output" / "library2_2010_2021_google_repair"
WORK = ROOT / "tmp" / "library2_2010_2021_google_repair"
SUMMARY = OUT / "Google视觉返工质量报告.md"
ALL_PAGES = OUT / "Google视觉返工页汇总.md"
REQUEST_LOG = OUT / "Google视觉返工请求记录.jsonl"
MODEL = "gemini-3.5-flash"


def load_gemini_module():
    script = ROOT / "gemini_pdf_to_markdown.py"
    spec = importlib.util.spec_from_file_location("gemini_pdf_to_markdown", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 Gemini 转换脚本。")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_status_rows() -> list[dict]:
    rows = []
    for line in STATUS.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| 20"):
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if len(cells) < 13:
            continue
        manual_pages = []
        if cells[11] != "无":
            manual_pages = [int(part.strip()) for part in cells[11].split(",") if part.strip()]
        rows.append(
            {
                "period": cells[0],
                "pdf": ROOT / cells[1],
                "quality": cells[4],
                "manual_pages": manual_pages,
                "markdown": SOURCE_DIR / cells[12],
            }
        )
    return rows


def extract_original_page(markdown_path: Path, page_num: int) -> str:
    text = markdown_path.read_text(encoding="utf-8")
    pattern = rf"^## PDF Page {page_num:03d}\s*$"
    match = re.search(pattern, text, re.M)
    if not match:
        return ""
    next_match = re.search(r"^## PDF Page \d{3}\s*$", text[match.end() :], re.M)
    block = text[match.start() :] if not next_match else text[match.start() : match.end() + next_match.start()]
    lines = []
    for line in block.splitlines():
        if line.startswith("- Source locator:"):
            continue
        if line.startswith("- Extraction method:"):
            continue
        if line.startswith("- Page quality:"):
            continue
        if line.startswith("- Detected problem groups:"):
            continue
        if line.startswith("<a id="):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def clean_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def read_quality(markdown: str) -> tuple[str, str]:
    match = re.search(r"<!--\s*page_quality:\s*(高|中|低)\s*;\s*reason:\s*(.*?)\s*-->", markdown)
    if match:
        return match.group(1), match.group(2).strip()
    return "未标记", "Google未按要求输出质量标记"


def repair_prompt(period: str, page_num: int, total_pages: int) -> str:
    return f"""请读取这张 JLPT N1 真题 PDF 页面图像，并转换为 AI 易读 Markdown。

背景：这是 {period} 的真题 PDF Page {page_num:03d}/{total_pages}，正在返工本地 OCR 质量较低的页面。

硬性要求：
1. 忠实提取原文，不要改写题干、选项、文章、听力说明、答案或封面文字。
2. 页面标题必须写为：## PDF Page {page_num:03d}
3. 如果页面中有 問題1、問題2、問題3 等题组，请用三级标题标出，例如：### 問題1
4. 每道题尽量保留题号、题干、选项结构。选项编号不要丢失。
5. 如果是封面、注意事项、答案页，也要完整保留能看清的原文。
6. 如果原文是分栏排版，请按正常阅读顺序整理，不要把左右栏混在一起。
7. 对不确定或看不清的文字，用 [不确定: 原因] 标记，不要猜。
8. 不要添加原文没有的解释、翻译或答案。
9. 不要使用 HTML ruby 标签。
10. 页面末尾必须添加一行 HTML 注释，格式严格为：
<!-- page_quality: 高/中/低; reason: 简短中文原因 -->

只输出该页 Markdown 正文。"""


def recommendation(original: str, generated: str, quality: str) -> str:
    old_len = clean_len(original)
    new_len = clean_len(generated)
    if quality == "高" and new_len >= max(20, old_len):
        return "建议替换"
    if quality in {"高", "中"} and new_len >= old_len * 1.5 and new_len >= 40:
        return "建议替换"
    if quality == "中" and new_len >= old_len:
        return "可替换，建议抽查"
    if old_len < 30 and new_len < 30:
        return "无明显改善，可能为空白/答案短页"
    return "暂不替换"


def page_cache(period: str, page_num: int) -> Path:
    safe_period = period.replace("/", "_").replace("\\", "_")
    return OUT / "pages" / safe_period / f"PDF_Page_{page_num:03d}.md"


def main() -> int:
    gemini = load_gemini_module()
    api_key = gemini.resolve_api_key()
    if not api_key:
        raise SystemExit("Gemini API Key 未配置。")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pages").mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)

    rows = []
    page_outputs = []
    targets = [(row, page) for row in parse_status_rows() for page in row["manual_pages"]]

    for index, (row, page_num) in enumerate(targets, start=1):
        pdf = row["pdf"]
        total_pages = gemini.pdf_page_count(pdf)
        cache_file = page_cache(row["period"], page_num)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        print(f"[{index}/{len(targets)}] {row['period']} PDF Page {page_num:03d}", flush=True)

        if cache_file.exists():
            markdown = cache_file.read_text(encoding="utf-8")
            status = "cached"
        else:
            image_dir = WORK / "images" / row["period"]
            rendered = gemini.render_page(pdf, page_num, image_dir, 300)
            jpg = gemini.compress_image(rendered, 2600, 92)
            markdown = gemini.call_gemini(
                api_key=api_key,
                model=MODEL,
                prompt=repair_prompt(row["period"], page_num, total_pages),
                image_b64=gemini.image_base64(jpg),
                max_output_tokens=8192,
                temperature=0.0,
                retries=5,
                page_num=page_num,
                request_log=REQUEST_LOG,
            )
            cache_file.write_text(markdown.strip() + "\n", encoding="utf-8")
            status = "completed"
            time.sleep(1.0)

        original = extract_original_page(row["markdown"], page_num)
        quality, reason = read_quality(markdown)
        rec = recommendation(original, markdown, quality)
        result = {
            "period": row["period"],
            "page": page_num,
            "status": status,
            "quality": quality,
            "reason": reason.replace("|", "/"),
            "old_len": clean_len(original),
            "new_len": clean_len(markdown),
            "recommendation": rec,
            "cache": cache_file,
        }
        rows.append(result)
        page_outputs.append((row["period"], page_num, markdown.strip()))
        write_reports(rows, page_outputs)

    write_reports(rows, page_outputs)
    return 0


def write_reports(rows: list[dict], page_outputs: list[tuple[str, int, str]]) -> None:
    improve_count = sum(1 for row in rows if "替换" in row["recommendation"] and not row["recommendation"].startswith("暂不"))
    high_count = sum(1 for row in rows if row["quality"] == "高")
    mid_count = sum(1 for row in rows if row["quality"] == "中")
    low_count = sum(1 for row in rows if row["quality"] == "低")
    no_mark_count = sum(1 for row in rows if row["quality"] == "未标记")

    lines = [
        "# 2010年-2021年7月 人工校对页 Google视觉返工质量报告",
        "",
        f"- 已处理页数: {len(rows)}",
        f"- Google质量统计: 高 {high_count}；中 {mid_count}；低 {low_count}；未标记 {no_mark_count}",
        f"- 建议替换/可替换页数: {improve_count}",
        "",
        "| 期次 | PDF Page | 状态 | Google质量 | 原稿有效字符 | Google有效字符 | 建议 | 说明 | 输出文件 |",
        "|---|---:|---|---|---:|---:|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['period']} | {row['page']:03d} | {row['status']} | {row['quality']} | "
            f"{row['old_len']} | {row['new_len']} | {row['recommendation']} | {row['reason']} | "
            f"`{row['cache'].relative_to(ROOT)}` |"
        )
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")

    body = ["# Google视觉返工页汇总", ""]
    for period, page_num, markdown in page_outputs:
        body.append(f"<!-- source_period: {period}; pdf_page: {page_num:03d} -->")
        body.append(markdown)
        body.append("")
    ALL_PAGES.write_text("\n".join(body), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
