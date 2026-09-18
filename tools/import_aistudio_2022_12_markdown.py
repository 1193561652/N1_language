from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = Path(
    r"C:\Users\Administrator\.codex\attachments\f3215060-d05a-4805-a1aa-0add37cfa1d9\pasted-text.txt"
)
SOURCE_PDF = ROOT / r"library2\2022年12月\32022年12月N1_真题.pdf"
OUT_DIR = ROOT / r"output\library2_aistudio"
OUT_MD = OUT_DIR / "2022年12月N1真题_AIStudio主底稿.md"
STATUS_MD = OUT_DIR / "转换状态.md"
REVIEW_MD = OUT_DIR / "2022年12月N1真题_AIStudio主底稿_质量记录.md"


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def page_anchor(page: int, problem: str | None = None) -> str:
    base = f"pdf-page-{page:03d}"
    if problem:
        return f"{base}-{problem}"
    return base


def split_pages(text: str) -> list[tuple[int, str]]:
    pattern = re.compile(r"^## PDF Page\s+(\d+)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    pages: list[tuple[int, str]] = []
    for idx, match in enumerate(matches):
        page_num = int(match.group(1))
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        pages.append((page_num, body))
    return pages


def clean_input(raw: str) -> tuple[str, str]:
    text = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = text.splitlines()
    if lines and lines[0].startswith("这是一份基于您提供的 PDF 截图"):
        lines = lines[1:]
    while lines and lines[0].strip() in {"", "---"}:
        lines = lines[1:]
    text = "\n".join(lines).strip()

    quality = ""
    if "\n### 质量报告" in text:
        text, quality_tail = text.split("\n### 质量报告", 1)
        quality = "### 质量报告" + quality_tail

    text = re.sub(r"\n*如果您需要继续读取下一部分或针对特定文章进行分析，请告知。\s*$", "", text).strip()
    quality = re.sub(r"\n*如果您需要继续读取下一部分或针对特定文章进行分析，请告知。\s*$", "", quality).strip()
    return text, quality


def clean_page_body(page_num: int, body: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    cleaned = body.strip()
    if "[縦書き文章の書き出し]" in cleaned:
        cleaned = cleaned.replace("[縦書き文章の書き出し]\n", "").replace("[縦書き文章の書き出し]", "")
        notes.append("AI Studio 输出含非原文说明“縦書き文章の書き出し”，已从正文移除；该页需对照 PDF 确认纵排阅读顺序。")
    if "（略）" in cleaned or "..." in cleaned:
        notes.append("页面含“略”或省略号，需确认是否为 PDF 原文而非模型省略。")
    if "非标准答案" in cleaned or "仅供参考" in cleaned:
        notes.append("答案页含“非标准答案/仅供参考”说明，需与答案解析 PDF 或原答案页核对。")
    if "微信公众号" in cleaned or "perfect" in cleaned or "ご容赦" in cleaned:
        notes.append("页面含资料来源/整理说明文字，需确认是否属于 PDF 可见内容。")
    return cleaned.strip(), notes


def detect_problem_index(pages: list[tuple[int, str]]) -> list[tuple[str, int]]:
    items: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for page_num, body in pages:
        if "答案" in body[:200] or "真題答案" in body[:200]:
            continue
        for match in re.finditer(r"(問題\s*[0-9０-９]+)", body):
            label = re.sub(r"\s+", "", match.group(1))
            key = (label, page_num)
            if key not in seen:
                seen.add(key)
                items.append((label, page_num))
    return items


def page_quality(page_num: int, notes: list[str]) -> tuple[str, str]:
    if page_num in {1, 15, 16, 19, 23, 44}:
        return "中", "AI Studio 主底稿可读，但该页存在需人工核对项：" + "；".join(notes or ["抽样校对"])
    return "中高", "AI Studio 视觉提取，结构清楚；建议抽样校对"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_md5 = md5_file(SOURCE_PDF)
    raw = INPUT.read_text(encoding="utf-8")
    content_text, ai_quality_report = clean_input(raw)
    pages_raw = split_pages(content_text)

    cleaned_pages: list[tuple[int, str, list[str]]] = []
    all_notes: list[tuple[int, str]] = []
    for page_num, body in pages_raw:
        cleaned_body, notes = clean_page_body(page_num, body)
        cleaned_pages.append((page_num, cleaned_body, notes))
        for note in notes:
            all_notes.append((page_num, note))

    index_items = detect_problem_index([(p, b) for p, b, _ in cleaned_pages])
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines: list[str] = [
        "# 2022年12月 JLPT N1 真题",
        "",
        "## Metadata",
        "",
        f"- Source PDF: `library2\\2022年12月\\32022年12月N1_真题.pdf`",
        f"- Source PDF MD5: `{source_md5}`",
        f"- PDF page count: {len(cleaned_pages)}",
        f"- Extracted at: {now}",
        "- Extraction method: Google AI Studio / Gemini 视觉文档理解结果，作为主底稿导入。",
        "- Fidelity policy: 保留 AI Studio 提取正文；删除对话型说明；疑似非原文内容写入质量记录，不直接改写日文原文。",
        "- Locator rule: 每页均保留 `PDF Page xxx`，题组索引链接到对应 PDF 页。",
        "",
        "## Problem Locator Index",
        "",
    ]
    for label, page_num in index_items:
        anchor = page_anchor(page_num, label)
        lines.append(f"- [{label} - PDF page {page_num}](#{anchor})")

    lines.extend(["", "## Extracted Content", ""])
    for page_num, body, notes in cleaned_pages:
        problem_labels = [label for label, p in index_items if p == page_num]
        primary_problem = problem_labels[0] if problem_labels else None
        lines.extend(
            [
                f'<a id="{page_anchor(page_num)}"></a>',
                *(f'<a id="{page_anchor(page_num, label)}"></a>' for label in problem_labels),
                "",
                f"## PDF Page {page_num:03d}",
                "",
                f"- Source locator: PDF page {page_num}",
                "- Extraction method: Google AI Studio / Gemini vision",
            ]
        )
        quality, reason = page_quality(page_num, notes)
        lines.append(f"- Page quality: {quality} - {reason}")
        lines.append("")
        lines.append(body)
        lines.append("")

    lines.extend(
        [
            "## Quality Notes",
            "",
            "- Overall quality: 中高",
            "- Status: 已作为 2022年12月 N1 真题主底稿导入；仍需重点校对 Page 1, 15, 16, 19, 23, 44。",
            "- Main risk: AI Studio 输出中存在少量整理说明、资料来源说明、答案页非标准说明，以及长文页可能存在省略标记。",
            "",
        ]
    )
    for page_num, note in all_notes:
        lines.append(f"- PDF Page {page_num:03d}: {note}")
    if ai_quality_report:
        lines.extend(["", "### AI Studio 原始质量报告", "", ai_quality_report])

    OUT_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    review_lines = [
        "# 2022年12月N1真题 AI Studio主底稿质量记录",
        "",
        f"- 源PDF：`library2\\2022年12月\\32022年12月N1_真题.pdf`",
        f"- 源PDF_MD5：`{source_md5}`",
        f"- 主底稿文件：`{OUT_MD.name}`",
        "- 质量：中高",
        "- 状态：已导入为主底稿，需重点页人工校对",
        "",
        "## 重点校对页",
        "",
        "- PDF Page 001：含资料来源/整理说明文字，需确认是否属于 PDF 可见内容。",
        "- PDF Page 015：原 AI Studio 输出含“縦書き文章の書き出し”说明，已从正文移除，需确认纵排文本顺序。",
        "- PDF Page 016, 019, 023：长文页含中略/注释，需确认是否为原文。",
        "- PDF Page 044：答案页含“非标准答案/仅供参考”说明，需与答案解析 PDF 或原答案页核对。",
        "",
        "## 导入处理",
        "",
        "- 删除开头对话型说明。",
        "- 删除末尾对话型续写提示。",
        "- 保留页码、题组、题号、题干、选项结构。",
        "- 生成与前面 OCR 转换一致的 Metadata、Problem Locator Index、Extracted Content 结构。",
    ]
    REVIEW_MD.write_text("\n".join(review_lines) + "\n", encoding="utf-8")

    status_lines = [
        "# AI Studio主底稿转换状态",
        "",
        "| PDF文件 | 源PDF_MD5 | 转换状态 | 质量 | 质量说明 | 总页数 | OCR页数 | PDF文字层页数 | 题组数 | AI Markdown文件 |",
        "|---|---|---|---|---|---:|---:|---:|---:|---|",
        (
            "| library2\\2022年12月\\32022年12月N1_真题.pdf "
            f"| {source_md5} "
            "| AI Studio主底稿已导入 "
            "| 中高 "
            "| 视觉提取结构明显优于本地OCR；仍需校对Page 1/15/16/19/23/44及答案页 "
            f"| {len(cleaned_pages)} "
            "| 0 "
            "| 0 "
            f"| {len(index_items)} "
            f"| {OUT_MD.name} |"
        ),
    ]
    STATUS_MD.write_text("\n".join(status_lines) + "\n", encoding="utf-8")

    print(f"written: {OUT_MD}")
    print(f"written: {STATUS_MD}")
    print(f"written: {REVIEW_MD}")


if __name__ == "__main__":
    main()
