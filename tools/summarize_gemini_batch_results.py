from __future__ import annotations

import re
from pathlib import Path


OUT_DIR = Path(__file__).resolve().parents[1] / r"output\library2_gemini_batch"
SUMMARY = OUT_DIR / "转换结果统计.md"


def parse_status(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    rows = []
    for line in text.splitlines():
        if not line.startswith("| ") or line.startswith("| PDF") or line.startswith("|---"):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) >= 5 and cols[0].isdigit():
            rows.append(
                {
                    "page": int(cols[0]),
                    "status": cols[1],
                    "quality": cols[2],
                    "reason": cols[3],
                }
            )
    return {
        "rows": rows,
        "total": len(rows),
        "status_counts": count_by(rows, "status"),
        "quality_counts": count_by(rows, "quality"),
        "problem_pages": [
            row
            for row in rows
            if row["quality"] in {"低", "未标记", "未完成"} or row["status"] not in {"done", "cached"}
        ],
    }


def count_by(rows: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row[key]] = counts.get(row[key], 0) + 1
    return counts


def page_header_count(md_path: Path) -> int:
    if not md_path.exists():
        return 0
    text = md_path.read_text(encoding="utf-8")
    return len(re.findall(r"^## PDF Page\s+\d+", text, flags=re.MULTILINE))


def fmt_counts(counts: dict[str, int]) -> str:
    return "；".join(f"{k}:{v}" for k, v in sorted(counts.items())) if counts else "-"


def main() -> None:
    lines = [
        "# Gemini批量转换结果统计",
        "",
        "| 文档 | PDF页数 | Markdown页数 | 状态统计 | 质量统计 | 需返工页 |",
        "|---|---:|---:|---|---|---|",
    ]
    detail_lines = ["", "## 需返工/重点检查页面", ""]

    for status_path in sorted(OUT_DIR.glob("*_转换状态.md")):
        doc = status_path.name.replace("_转换状态.md", "")
        md_path = OUT_DIR / f"{doc}_Gemini视觉主底稿.md"
        if not md_path.exists():
            md_path = OUT_DIR / f"{doc.replace('N1真题', 'N1真题')}_Gemini视觉主底稿.md"
        data = parse_status(status_path)
        md_pages = page_header_count(md_path)
        problem_pages = data["problem_pages"]
        problem_page_text = ", ".join(f"{row['page']:03d}" for row in problem_pages) or "无"
        lines.append(
            f"| {doc} | {data['total']} | {md_pages} | {fmt_counts(data['status_counts'])} | {fmt_counts(data['quality_counts'])} | {problem_page_text} |"
        )
        detail_lines.append(f"### {doc}")
        detail_lines.append("")
        if problem_pages:
            for row in problem_pages:
                detail_lines.append(
                    f"- PDF Page {row['page']:03d}: 状态={row['status']}；质量={row['quality']}；说明={row['reason']}"
                )
        else:
            detail_lines.append("- 无")
        detail_lines.append("")

    SUMMARY.write_text("\n".join(lines + detail_lines).rstrip() + "\n", encoding="utf-8")
    print(SUMMARY)


if __name__ == "__main__":
    main()

