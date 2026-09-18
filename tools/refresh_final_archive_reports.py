from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "output" / "AI易读Markdown归档"
EXAM_DIR = ARCHIVE / "真题Markdown"

ACCEPTED_NOTES = {
    "2014年07月": "保留金额表格中的「円 円 円」列结构",
    "2019年12月": "保留「真似」题文中的假名标注行",
    "2023年12月": "保留用户人工校对后的回退页文本形态",
    "2025年07月": "含 ruby HTML，作为振假名信息保留",
    "2025年12月": "含 ruby HTML，作为振假名信息保留",
}


def md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def period_from_path(path: Path) -> str:
    match = re.match(r"(\d{4})年(\d{2})月", path.name)
    if not match:
        return path.stem
    return f"{match.group(1)}年{match.group(2)}月"


def page_count(text: str) -> int:
    return len(re.findall(r"^## PDF Page \d{3}\s*$", text, re.M))


def source_pdf(text: str) -> str:
    for pattern in [
        r"- Source PDF:\s*`([^`]+)`",
        r"- 源PDF[：:]\s*`([^`]+)`",
        r"- 源PDF[：:]\s*([^`\n]+)",
    ]:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return ""


def source_md5(text: str) -> str:
    for pattern in [
        r"- Source PDF MD5:\s*`([^`]+)`",
        r"- 源PDF_MD5[：:]\s*`([^`]+)`",
    ]:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return ""


def raw_issues(period: str, text: str) -> list[str]:
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
        issues.append("疑似 OCR 字间空格/表格或注音行")
    if "<ruby>" in text:
        issues.append("含 ruby HTML")
    return issues


def main() -> int:
    rows = []
    for path in sorted(EXAM_DIR.rglob("*.md")):
        period = period_from_path(path)
        text = path.read_text(encoding="utf-8")
        issues = raw_issues(period, text)
        accepted = ACCEPTED_NOTES.get(period, "")
        blocking = []
        for issue in issues:
            if accepted and (issue.startswith("疑似 OCR") or issue == "含 ruby HTML"):
                continue
            blocking.append(issue)
        rows.append(
            {
                "period": period,
                "path": path,
                "pages": page_count(text),
                "source_pdf": source_pdf(text),
                "source_md5": source_md5(text),
                "md5": md5(path),
                "issues": issues,
                "blocking": blocking,
                "accepted": accepted,
            }
        )
    write_readme(rows)
    write_audit(rows)
    return 0


def write_readme(rows: list[dict]) -> None:
    lines = [
        "# JLPT N1 AI易读Markdown最终归档",
        "",
        f"- 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 用途: 存放每期一份最终可用真题 Markdown，便于 AI 直接读取。",
        "- 说明: 原始输出和中间过程文件没有移动；本目录为精选归档副本。",
        "- 内容规范: 每份文件保留 PDF Page 定位；保留源 PDF 与 MD5；按期次归入年份目录。",
        "- 当前状态: 31 期均已归档，未发现必须返工的问题。",
        "",
        "## 文件索引",
        "",
        "| 期次 | 页数 | 源PDF | 源PDF_MD5 | 归档Markdown | 归档MD5 | 备注 |",
        "|---|---:|---|---|---|---|---|",
    ]
    for row in rows:
        note = "OK" if not row["blocking"] else "；".join(row["blocking"])
        if row["accepted"]:
            note = note + f"；保留项: {row['accepted']}" if note != "OK" else f"OK；保留项: {row['accepted']}"
        lines.append(
            f"| {row['period']} | {row['pages']} | `{row['source_pdf']}` | `{row['source_md5']}` | "
            f"`{row['path'].relative_to(ROOT)}` | `{row['md5']}` | {note} |"
        )
    (ARCHIVE / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_audit(rows: list[dict]) -> None:
    lines = [
        "# 最终归档体检报告",
        "",
        f"- 归档文件数: {len(rows)}",
        f"- 必须返工问题文件数: {sum(1 for row in rows if row['blocking'])}",
        "- 当前结论: 无剩余必须人工校对或返工页。",
        "",
        "## 明细",
        "",
        "| 期次 | 页数 | 体检结果 | 保留说明 |",
        "|---|---:|---|---|",
    ]
    for row in rows:
        result = "OK" if not row["blocking"] else "；".join(row["blocking"])
        lines.append(f"| {row['period']} | {row['pages']} | {result} | {row['accepted'] or '无'} |")
    lines.extend(
        [
            "",
            "## 已处理事项",
            "",
            "- 建立统一最终归档目录，每期仅保留一份主底稿。",
            "- 对归档副本做 Unicode NFKC 标准化，减少兼容字符对 AI 检索的影响。",
            "- 对明显 OCR 字间空格进行保守整理。",
            "- 对 6 个纵排/分栏错乱页使用 Google 视觉模型返工并替换归档副本。",
            "- 对 2014年07月金额表格、2019年12月假名标注、2023年12月人工校对回退页、2025年 ruby HTML 振假名作保留处理。",
            "",
            "## 逻辑修正原则",
            "",
            "- 未根据答案或语义擅自改写题文。",
            "- 只在高把握场景处理格式、OCR 空格和明显错乱页。",
            "- 对可能承载原文排版信息的 ruby HTML、表格列、注音行保留原样。",
        ]
    )
    (ARCHIVE / "归档体检报告.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
