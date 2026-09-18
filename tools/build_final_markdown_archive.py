from __future__ import annotations

import hashlib
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
ARCHIVE = OUT / "AI易读Markdown归档"
EXAM_DIR = ARCHIVE / "真题Markdown"
REPORT_DIR = ARCHIVE / "质量与处理记录"


CANONICAL = [
    ("2010年07月", OUT / "library2_2010_2021_markdown" / "2010年7月N1真题_主底稿.md"),
    ("2010年12月", OUT / "library2_2010_2021_markdown" / "2010年12月N1真题_主底稿.md"),
    ("2011年07月", OUT / "library2_2010_2021_markdown" / "2011年7月N1真题_主底稿.md"),
    ("2011年12月", OUT / "library2_2010_2021_markdown" / "2011年12月N1真题_主底稿.md"),
    ("2012年07月", OUT / "library2_2010_2021_markdown" / "2012年7月N1真题_主底稿.md"),
    ("2012年12月", OUT / "library2_2010_2021_markdown" / "2012年12月N1真题_主底稿.md"),
    ("2013年07月", OUT / "library2_2010_2021_markdown" / "2013年7月N1真题_主底稿.md"),
    ("2013年12月", OUT / "library2_2010_2021_markdown" / "2013年12月N1真题_主底稿.md"),
    ("2014年07月", OUT / "library2_2010_2021_markdown" / "2014年7月N1真题_主底稿.md"),
    ("2014年12月", OUT / "library2_2010_2021_markdown" / "2014年12月N1真题_主底稿.md"),
    ("2015年07月", OUT / "library2_2010_2021_markdown" / "2015年7月N1真题_主底稿.md"),
    ("2015年12月", OUT / "library2_2010_2021_markdown" / "2015年12月N1真题_主底稿.md"),
    ("2016年07月", OUT / "library2_2010_2021_markdown" / "2016年7月N1真题_主底稿.md"),
    ("2016年12月", OUT / "library2_2010_2021_markdown" / "2016年12月N1真题_主底稿.md"),
    ("2017年07月", OUT / "library2_2010_2021_markdown" / "2017年7月N1真题_主底稿.md"),
    ("2017年12月", OUT / "library2_2010_2021_markdown" / "2017年12月N1真题_主底稿.md"),
    ("2018年07月", OUT / "library2_2010_2021_markdown" / "2018年7月N1真题_主底稿.md"),
    ("2018年12月", OUT / "library2_2010_2021_markdown" / "2018年12月N1真题_主底稿.md"),
    ("2019年07月", OUT / "library2_2010_2021_markdown" / "2019年7月N1真题_主底稿.md"),
    ("2019年12月", OUT / "library2_2010_2021_markdown" / "2019年12月N1真题_主底稿.md"),
    ("2020年12月", OUT / "library2_2010_2021_markdown" / "2020年12月N1真题_主底稿.md"),
    ("2021年07月", OUT / "library2_2010_2021_markdown" / "2021年7月N1真题_主底稿.md"),
    ("2021年12月", OUT / "library2_after_2021_markdown" / "2021年12月__【2】2021年12月N1真题+听力原文.md"),
    ("2022年07月", OUT / "library2_after_2021_markdown" / "2022年7月__【2】2022年07月N1 真题.md"),
    ("2022年12月", OUT / "library2_aistudio" / "2022年12月N1真题_AIStudio主底稿.md"),
    ("2023年07月", OUT / "library2_after_2021_markdown" / "2023年7月__【3】2023年07月N1 真题.md"),
    ("2023年12月", OUT / "library2_gemini_batch" / "2023年12月N1真题_Gemini视觉主底稿.md"),
    ("2024年07月", OUT / "library2_after_2021_markdown" / "2024年7月__【2】2024年07月N1 真题+听力原文.md"),
    ("2024年12月", OUT / "library2_gemini_batch" / "2024年12月N1真题_Gemini视觉主底稿.md"),
    ("2025年07月", OUT / "library2_gemini_batch" / "2025年7月N1真题_Gemini视觉主底稿.md"),
    ("2025年12月", OUT / "library2_gemini_batch" / "2025年12月N1真题_Gemini视觉主底稿.md"),
]


PROCESS_REPORTS = [
    OUT / "整体质量报告.md",
    OUT / "library2_2010_2021_markdown" / "质量报告.md",
    OUT / "library2_2010_2021_markdown" / "转换状态.md",
    OUT / "library2_aistudio" / "2022年12月N1真题_AIStudio主底稿_质量记录.md",
    OUT / "library2_aistudio" / "2022年12月人工提取综合校正记录.md",
    OUT / "library2_gemini_batch" / "转换结果统计.md",
    OUT / "library2_gemini_batch" / "2023年12月人工校对记录.md",
]


def md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_markdown(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    # Normalize a few common OCR spacing artifacts only when the whole line is clearly spaced-out Japanese.
    lines = []
    for line in text.splitlines():
        if is_spaced_japanese_line(line):
            lines.append(re.sub(r"(?<=[\u3040-\u30ff\u4e00-\u9fffA-Za-z0-9]) (?=[\u3040-\u30ff\u4e00-\u9fffA-Za-z0-9])", "", line))
        else:
            lines.append(line.rstrip())
    return "\n".join(lines).strip() + "\n"


def is_spaced_japanese_line(line: str) -> bool:
    if len(line) < 16:
        return False
    spaces = line.count(" ")
    cjk = sum(1 for ch in line if "\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff")
    # Conservative: only collapse if spaces are frequent and the line is mostly Japanese text.
    return cjk >= 8 and spaces >= 5 and spaces / max(len(line), 1) > 0.18


def page_count(text: str) -> int:
    return len(re.findall(r"^## PDF Page \d{3}\s*$", text, re.M))


def source_pdf(text: str) -> str:
    patterns = [
        r"- Source PDF:\s*`([^`]+)`",
        r"- 源PDF[：:]\s*`([^`]+)`",
        r"- 源PDF[：:]\s*([^`\n]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return ""


def source_md5(text: str) -> str:
    patterns = [
        r"- Source PDF MD5:\s*`([^`]+)`",
        r"- 源PDF_MD5[：:]\s*`([^`]+)`",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return ""


def audit_text(period: str, text: str) -> list[str]:
    issues = []
    if page_count(text) == 0:
        issues.append("未检测到 PDF Page 标题")
    if "[不确定:" in text:
        issues.append("仍含 [不确定] 标记")
    if "page_quality: 低" in text or "Page quality: 低" in text:
        issues.append("仍含低质量页标记")
    if "需人工校对" in text:
        issues.append("仍含需人工校对字样")
    if re.search(r"[ぁ-んァ-ン一-龯] [ぁ-んァ-ン一-龯] [ぁ-んァ-ン一-龯] [ぁ-んァ-ン一-龯]", text):
        issues.append("疑似仍有 OCR 字间空格")
    if "<ruby>" in text:
        issues.append("含 ruby HTML，保留原样未自动改写")
    return issues


def main() -> int:
    if ARCHIVE.exists():
        shutil.rmtree(ARCHIVE)
    EXAM_DIR.mkdir(parents=True)
    REPORT_DIR.mkdir(parents=True)

    rows = []
    for period, src in CANONICAL:
        if not src.exists():
            rows.append({"period": period, "status": "missing", "source": str(src), "issues": ["源文件不存在"]})
            continue
        raw = src.read_text(encoding="utf-8")
        normalized = normalize_markdown(raw)
        year = period[:4]
        dst_dir = EXAM_DIR / year
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / f"{period}N1真题.md"
        dst.write_text(normalized, encoding="utf-8", newline="\n")
        issues = audit_text(period, normalized)
        rows.append(
            {
                "period": period,
                "status": "archived",
                "source": str(src.relative_to(ROOT)),
                "dest": str(dst.relative_to(ROOT)),
                "pages": page_count(normalized),
                "source_pdf": source_pdf(normalized),
                "source_md5": source_md5(normalized),
                "md5": md5(dst),
                "issues": issues,
            }
        )

    for report in PROCESS_REPORTS:
        if report.exists():
            shutil.copy2(report, REPORT_DIR / report.name)

    write_index(rows)
    write_audit(rows)
    return 0


def write_index(rows: list[dict]) -> None:
    lines = [
        "# JLPT N1 AI易读Markdown最终归档",
        "",
        f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 用途: 存放每期一份最终可用真题 Markdown，便于 AI 直接读取。",
        "- 说明: 原始输出和中间过程文件没有移动；本目录为精选归档副本。",
        "- 内容规范: 每份文件保留 PDF Page 定位；保留源 PDF 与 MD5；按期次归入年份目录。",
        "",
        "## 文件索引",
        "",
        "| 期次 | 页数 | 源PDF | 源PDF_MD5 | 归档Markdown | 归档MD5 | 备注 |",
        "|---|---:|---|---|---|---|---|",
    ]
    for row in rows:
        if row["status"] != "archived":
            lines.append(f"| {row['period']} | 0 |  |  |  |  | 源文件缺失: `{row['source']}` |")
            continue
        note = "OK" if not row["issues"] else "；".join(row["issues"])
        lines.append(
            f"| {row['period']} | {row['pages']} | `{row['source_pdf']}` | `{row['source_md5']}` | "
            f"`{row['dest']}` | `{row['md5']}` | {note} |"
        )
    (ARCHIVE / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_audit(rows: list[dict]) -> None:
    lines = [
        "# 最终归档体检报告",
        "",
        f"- 归档文件数: {sum(1 for r in rows if r['status'] == 'archived')}",
        f"- 缺失文件数: {sum(1 for r in rows if r['status'] != 'archived')}",
        f"- 需注意文件数: {sum(1 for r in rows if r.get('issues'))}",
        "",
        "## 明细",
        "",
        "| 期次 | 状态 | 页数 | 体检结果 |",
        "|---|---|---:|---|",
    ]
    for row in rows:
        result = "OK" if not row.get("issues") else "；".join(row["issues"])
        lines.append(f"| {row['period']} | {row['status']} | {row.get('pages', 0)} | {result} |")
    lines.extend(
        [
            "",
            "## 自动整理说明",
            "",
            "- 已对归档副本做 Unicode NFKC 标准化，减少兼容汉字/假名宽度差异对 AI 检索的影响。",
            "- 对明显 OCR 字间空格的行做了保守合并；仅在一行中日文字符密集且空格比例明显异常时处理。",
            "- 未自动重写 ruby HTML、题文内容或选项内容；这些属于可能影响原文忠实度的改动。",
            "- 逻辑修正仅限高把握的格式/OCR 空格整理，没有根据答案或语义擅自改写题文。",
        ]
    )
    (ARCHIVE / "归档体检报告.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
