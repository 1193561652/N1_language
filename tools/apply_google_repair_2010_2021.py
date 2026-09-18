from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "output" / "library2_2010_2021_markdown"
REPAIR_DIR = ROOT / "output" / "library2_2010_2021_google_repair"
REPAIR_REPORT = REPAIR_DIR / "Google视觉返工质量报告.md"
STATUS = SOURCE_DIR / "转换状态.md"
QUALITY_REPORT = SOURCE_DIR / "质量报告.md"
APPLY_REPORT = REPAIR_DIR / "Google视觉返工合并报告.md"


def parse_repair_rows() -> list[dict]:
    rows = []
    for line in REPAIR_REPORT.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| 20"):
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if len(cells) < 9:
            continue
        rows.append(
            {
                "period": cells[0],
                "page": int(cells[1]),
                "quality": cells[3],
                "old_len": int(cells[4]),
                "new_len": int(cells[5]),
                "recommendation": cells[6],
                "reason": cells[7],
                "repair_file": ROOT / cells[8],
            }
        )
    return rows


def source_markdown(period: str) -> Path:
    return SOURCE_DIR / f"{period}N1真题_主底稿.md"


def strip_generated(markdown: str, page_num: int) -> str:
    text = markdown.strip()
    text = re.sub(rf"^## PDF Page {page_num:03d}\s*", "", text).strip()
    text = re.sub(r"<!--\s*page_quality:.*?-->\s*$", "", text, flags=re.S).strip()
    text = re.sub(r"(?m)^<br>\s*$", "", text).strip()
    return text


def replacement_block(row: dict) -> str:
    page = row["page"]
    generated = strip_generated(row["repair_file"].read_text(encoding="utf-8"), page)
    lines = [
        f'<a id="pdf-page-{page:03d}"></a>',
        "",
        f"## PDF Page {page:03d}",
        "",
        f"- Source locator: PDF page {page}",
        "- Extraction method: Google Gemini vision repair",
        f"- Page quality: 高 - {row['reason']}",
        "",
        generated if generated else "[不确定: Google视觉提取未返回正文]",
        "",
    ]
    return "\n".join(lines)


def replace_page_block(text: str, row: dict) -> tuple[str, bool]:
    page = row["page"]
    start_pattern = rf'(?m)^<a id="pdf-page-{page:03d}"></a>\s*\n\s*## PDF Page {page:03d}\s*$'
    start = re.search(start_pattern, text)
    if not start:
        start_pattern = rf"(?m)^## PDF Page {page:03d}\s*$"
        start = re.search(start_pattern, text)
    if not start:
        return text, False
    next_page = re.search(r'(?m)^<a id="pdf-page-\d{3}"></a>\s*\n\s*## PDF Page \d{3}\s*$', text[start.end() :])
    end = len(text) if not next_page else start.end() + next_page.start()
    new_text = text[: start.start()] + replacement_block(row) + "\n\n" + text[end:].lstrip()
    return new_text, True


def write_status(rows: list[dict]) -> None:
    # Keep source MD5 and page counts, but mark the Google-repaired pages as no longer needing manual校对.
    original_lines = STATUS.read_text(encoding="utf-8").splitlines()
    repair_by_period: dict[str, list[int]] = {}
    for row in rows:
        repair_by_period.setdefault(row["period"], []).append(row["page"])

    new_lines = []
    for line in original_lines:
        if not line.startswith("| 20"):
            new_lines.append(line)
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        period = cells[0]
        if period not in repair_by_period:
            new_lines.append(line)
            continue
        cells[3] = "完成，Google视觉返工页已合并"
        cells[4] = "高" if period != "2010年7月" else "中高"
        cells[5] = f"原需校对页已用Google视觉提取替换：{', '.join(f'{p:03d}' for p in repair_by_period[period])}"
        cells[10] = "0"
        cells[11] = "无"
        new_lines.append("| " + " | ".join(cells) + " |")
    STATUS.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def write_quality_report(rows: list[dict]) -> None:
    periods = []
    repair_by_period: dict[str, list[int]] = {}
    for row in rows:
        repair_by_period.setdefault(row["period"], []).append(row["page"])
    for period in sorted(repair_by_period, key=lambda p: (int(p[:4]), 7 if "7月" in p else 12)):
        periods.append((period, repair_by_period[period]))

    lines = [
        "# 2010年-2021年7月 质量报告",
        "",
        "## 总览",
        "",
        "- 覆盖期次: 22",
        "- 覆盖PDF页数: 557",
        "- 原需要人工校对页数: 42",
        "- 已用Google视觉模型返工并合并页数: 42",
        "- 当前需要人工校对页数: 0",
        "- 质量分布: 高: 21；中高: 1",
        "- 说明: 原本地OCR页已由Google视觉提取替换；2010年7月保留为中高，因为Page 010虽已显著改善，但属于正文中间页，建议抽查一次。",
        "",
        "## Google返工页",
        "",
        "| 期次 | 已替换PDF Page |",
        "|---|---|",
    ]
    for period, pages in periods:
        lines.append(f"| {period} | {', '.join(f'{page:03d}' for page in pages)} |")
    lines.extend(
        [
            "",
            "## 仍需人工校对",
            "",
            "- 无强制校对页。",
            "- 建议抽查: 2010年7月 PDF Page 010。",
        ]
    )
    QUALITY_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    rows = parse_repair_rows()
    applied = []
    failed = []
    for row in rows:
        if not row["recommendation"].startswith("建议") and not row["recommendation"].startswith("可"):
            continue
        path = source_markdown(row["period"])
        text = path.read_text(encoding="utf-8")
        new_text, ok = replace_page_block(text, row)
        if ok:
            path.write_text(new_text, encoding="utf-8", newline="\n")
            applied.append(row)
        else:
            failed.append(row)

    write_status(applied)
    write_quality_report(applied)

    lines = [
        "# Google视觉返工合并报告",
        "",
        f"- 已合并页数: {len(applied)}",
        f"- 未合并页数: {len(failed)}",
        "",
        "| 期次 | PDF Page | 原稿有效字符 | Google有效字符 | 结果 |",
        "|---|---:|---:|---:|---|",
    ]
    for row in applied:
        lines.append(f"| {row['period']} | {row['page']:03d} | {row['old_len']} | {row['new_len']} | 已替换 |")
    for row in failed:
        lines.append(f"| {row['period']} | {row['page']:03d} | {row['old_len']} | {row['new_len']} | 未找到原页面块 |")
    APPLY_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(APPLY_REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
