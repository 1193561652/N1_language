from __future__ import annotations

import importlib.util
import re
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "output" / "AI易读Markdown归档"
WORK = ROOT / "tmp" / "final_archive_suspect_page_repair"
LOG = ARCHIVE / "质量与处理记录" / "最终归档疑似错乱页视觉返工记录.md"
MODEL = "gemini-3.5-flash"


TARGETS = [
    {
        "period": "2011年07月",
        "page": 23,
        "pdf": ROOT / r"library2\2010年-2020年\2011年7月\32011年07月N1_真题.pdf",
        "md": ARCHIVE / r"真题Markdown\2011\2011年07月N1真题.md",
        "reason": "疑似答案页/表格页出现字间空格",
    },
    {
        "period": "2019年12月",
        "page": 13,
        "pdf": ROOT / r"library2\2010年-2020年\2019年12月\32019年12月N1_真题.pdf",
        "md": ARCHIVE / r"真题Markdown\2019\2019年12月N1真题.md",
        "reason": "纵排正文被文字层按列拆散",
    },
    {
        "period": "2020年12月",
        "page": 8,
        "pdf": ROOT / r"library2\2010年-2020年\2020年12月\32020年12月N1_真题.pdf",
        "md": ARCHIVE / r"真题Markdown\2020\2020年12月N1真题.md",
        "reason": "纵排正文被文字层按列拆散",
    },
    {
        "period": "2021年07月",
        "page": 10,
        "pdf": ROOT / r"library2\2021年7月\32021年07月N1_真题.pdf",
        "md": ARCHIVE / r"真题Markdown\2021\2021年07月N1真题.md",
        "reason": "纵排正文被文字层按列拆散",
    },
    {
        "period": "2022年07月",
        "page": 13,
        "pdf": ROOT / r"library2\2022年7月\22022年07月N1_真题.pdf",
        "md": ARCHIVE / r"真题Markdown\2022\2022年07月N1真题.md",
        "reason": "纵排正文被文字层按列拆散",
    },
    {
        "period": "2024年07月",
        "page": 11,
        "pdf": ROOT / r"library2\2024年7月\22024年07月N1_真题+听力原文.pdf",
        "md": ARCHIVE / r"真题Markdown\2024\2024年07月N1真题.md",
        "reason": "纵排正文被文字层按列拆散",
    },
]


def load_gemini_module():
    script = ROOT / "gemini_pdf_to_markdown.py"
    spec = importlib.util.spec_from_file_location("gemini_pdf_to_markdown", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 Gemini 转换脚本。")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prompt(period: str, page: int, total: int, reason: str) -> str:
    return f"""请读取这张 JLPT N1 真题 PDF 页面图像，并转换为 AI 易读 Markdown。

背景：这是 {period} 的 PDF Page {page:03d}/{total}。该页在归档体检中发现问题：{reason}。

要求：
1. 忠实提取原文，不要改写题干、选项、文章或答案。
2. 页面标题必须是：## PDF Page {page:03d}
3. 如果是纵排文字，请按正常阅读顺序整理成横排文本。
4. 如果有题号、选项、表格或答案，请尽量保留结构。
5. 对不确定或看不清的文字，用 [不确定: 原因] 标记，不要猜。
6. 不要添加解释、翻译或答案，除非原页本来就是答案页。
7. 页面末尾添加质量注释：<!-- page_quality: 高/中/低; reason: 简短中文原因 -->

只输出该页 Markdown。"""


def replace_page(md_path: Path, page: int, new_block: str) -> bool:
    text = md_path.read_text(encoding="utf-8")
    pattern = rf"(?m)^## PDF Page {page:03d}\s*$"
    match = re.search(pattern, text)
    if not match:
        return False
    next_match = re.search(r"(?m)^## PDF Page \d{3}\s*$", text[match.end() :])
    start = match.start()
    end = len(text) if not next_match else match.end() + next_match.start()
    text = text[:start] + new_block.strip() + "\n\n" + text[end:].lstrip()
    md_path.write_text(text, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    gemini = load_gemini_module()
    api_key = gemini.resolve_api_key()
    if not api_key:
        raise SystemExit("Gemini API Key 未配置。")
    WORK.mkdir(parents=True, exist_ok=True)
    rows = []
    request_log = WORK / "request_log.jsonl"
    for index, target in enumerate(TARGETS, start=1):
        period = target["period"]
        page = target["page"]
        pdf = target["pdf"]
        md = target["md"]
        cache = WORK / f"{period}_page_{page:03d}.md"
        print(f"[{index}/{len(TARGETS)}] {period} PDF Page {page:03d}", flush=True)
        if cache.exists():
            markdown = cache.read_text(encoding="utf-8")
            status = "cached"
        else:
            total = gemini.pdf_page_count(pdf)
            image = gemini.render_page(pdf, page, WORK / "images" / period, 300)
            jpg = gemini.compress_image(image, 2600, 92)
            markdown = gemini.call_gemini(
                api_key=api_key,
                model=MODEL,
                prompt=prompt(period, page, total, target["reason"]),
                image_b64=gemini.image_base64(jpg),
                max_output_tokens=8192,
                temperature=0.0,
                retries=5,
                page_num=page,
                request_log=request_log,
            )
            cache.write_text(markdown.strip() + "\n", encoding="utf-8")
            status = "completed"
            time.sleep(1.0)
        ok = replace_page(md, page, markdown)
        rows.append({**target, "status": status, "applied": ok, "cache": cache})
    write_log(rows)
    return 0


def write_log(rows: list[dict]) -> None:
    lines = [
        "# 最终归档疑似错乱页视觉返工记录",
        "",
        "| 期次 | PDF Page | 源PDF | 归档Markdown | 原因 | 状态 | 结果 | 缓存 |",
        "|---|---:|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['period']} | {row['page']:03d} | `{row['pdf'].relative_to(ROOT)}` | "
            f"`{row['md'].relative_to(ROOT)}` | {row['reason']} | {row['status']} | "
            f"{'已替换归档页' if row['applied'] else '未找到页面块'} | `{row['cache'].relative_to(ROOT)}` |"
        )
    LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
