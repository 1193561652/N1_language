from __future__ import annotations

import hashlib
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "library2"
ARCHIVE = ROOT / "output" / "AI易读Markdown归档"
OUT = ARCHIVE / "听力原文Markdown"
REPORT_DIR = ARCHIVE / "质量与处理记录"
STATUS = REPORT_DIR / "听力原文提取质量报告.md"

PERIODS = [
    "2010年07月",
    "2010年12月",
    "2011年07月",
    "2011年12月",
    "2012年07月",
    "2012年12月",
    "2013年07月",
    "2013年12月",
    "2014年07月",
    "2014年12月",
    "2015年07月",
    "2015年12月",
    "2016年07月",
    "2016年12月",
    "2017年07月",
    "2017年12月",
    "2018年07月",
    "2018年12月",
    "2019年07月",
    "2019年12月",
    "2020年12月",
    "2021年07月",
    "2021年12月",
    "2022年07月",
    "2022年12月",
    "2023年07月",
    "2023年12月",
    "2024年07月",
    "2024年12月",
    "2025年07月",
    "2025年12月",
]

CID_RE = re.compile(r"\(cid:\d+\)")
SPACE_RE = re.compile(r"[ \t\u3000]+")
PROBLEM_RE = re.compile(r"(問題\s*[0-9０-９]+|[0-9０-９]+番)")


def period_folder(period: str) -> Path:
    year = int(period[:4])
    month = int(period[5:7])
    folder_name = f"{year}年{month}月"
    if year <= 2020:
        return LIB / "2010年-2020年" / folder_name
    return LIB / folder_name


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize(raw: str) -> str:
    text = unicodedata.normalize("NFKC", raw or "")
    text = CID_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines = [SPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def cjk_count(text: str) -> int:
    return sum(1 for ch in text if "\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff")


def score_candidate(path: Path) -> int:
    name = path.name
    score = 0
    if "N1" in name:
        score += 1000
    if "听力原文" in name or "聴解原文" in name:
        score += 900
    if "答案解析+听力原文+译文" in name:
        score += 800
    elif "答案解析+听力原文" in name:
        score += 700
    if "真题+听力原文" in name:
        score += 650
    if "听力译文" in name or "阅读译文" in name:
        score -= 900
    if "N2" in name:
        score -= 2000
    # Prefer compact transcript/answer files over huge scanned bundles when labels tie.
    score -= min(path.stat().st_size // 2_000_000, 20)
    return score


def select_source(period: str) -> Path | None:
    folder = period_folder(period)
    if not folder.exists():
        return None
    candidates = []
    for path in folder.glob("*.pdf"):
        name = path.name
        if "N2" in name:
            continue
        if "听力原文" in name or "真题+听力原文" in name or "答案解析+听力原文" in name:
            if "译文" in name or "原文" in name:
                candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=score_candidate)


def page_quality(raw: str, clean: str) -> tuple[str, str]:
    cid = raw.count("(cid:")
    if cid > 20:
        return "低", f"CID乱码较多({cid})"
    if len(clean) < 80:
        return "中", "页面文字较少，可能为空白/封面/答案页"
    if cjk_count(clean) < 40:
        return "中", "有效日文较少，建议抽查"
    return "高", "PDF文字层清晰"


def extract_pdf(period: str, pdf: Path) -> dict:
    pages = []
    with pdfplumber.open(str(pdf)) as doc:
        for idx, page in enumerate(doc.pages, start=1):
            raw = page.extract_text() or ""
            clean = normalize(raw)
            quality, reason = page_quality(raw, clean)
            pages.append(
                {
                    "page": idx,
                    "text": clean,
                    "quality": quality,
                    "reason": reason,
                    "problems": sorted(set(m.group(1) for m in PROBLEM_RE.finditer(clean))),
                }
            )

    year = period[:4]
    out_dir = OUT / year
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{period}N1听力原文.md"
    quality = overall_quality(pages)
    write_markdown(period, pdf, pages, out_path, quality)
    return {
        "period": period,
        "pdf": pdf,
        "md5": md5_file(pdf),
        "out": out_path,
        "pages": len(pages),
        "quality": quality[0],
        "reason": quality[1],
        "low_pages": [p["page"] for p in pages if p["quality"] == "低"],
        "mid_pages": [p["page"] for p in pages if p["quality"] == "中"],
    }


def overall_quality(pages: list[dict]) -> tuple[str, str]:
    if not pages:
        return "低", "未提取到页面"
    low = [p for p in pages if p["quality"] == "低"]
    mid = [p for p in pages if p["quality"] == "中"]
    chars = sum(len(p["text"]) for p in pages)
    if chars < 300:
        return "低", "总文字量过少"
    if low:
        return "低", f"{len(low)}页低质量"
    if len(mid) > max(2, len(pages) // 2):
        return "中", f"中等质量页较多({len(mid)}/{len(pages)})"
    if mid:
        return "中高", f"少量页面需抽查({len(mid)}/{len(pages)})"
    return "高", "PDF文字层清晰"


def write_markdown(period: str, pdf: Path, pages: list[dict], out_path: Path, quality: tuple[str, str]) -> None:
    lines = [
        f"# {period} JLPT N1 听力原文",
        "",
        "## Metadata",
        "",
        f"- Source PDF: `{pdf.relative_to(ROOT)}`",
        f"- Source PDF MD5: `{md5_file(pdf)}`",
        f"- PDF page count: {len(pages)}",
        "- Content type: 听力原文 / 听解脚本相关资料",
        "- Locator rule: 每页用 `## PDF Page xxx` 保留 PDF 页码定位。",
        f"- Overall quality: {quality[0]}",
        f"- Quality note: {quality[1]}",
        f"- Extracted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Extracted Content",
        "",
    ]
    for page in pages:
        lines.extend(
            [
                f'<a id="pdf-page-{page["page"]:03d}"></a>',
                "",
                f'## PDF Page {page["page"]:03d}',
                "",
                f'- Source locator: PDF page {page["page"]}',
                "- Extraction method: PDF text layer",
                f'- Page quality: {page["quality"]} - {page["reason"]}',
            ]
        )
        if page["problems"]:
            lines.append("- Detected groups: " + ", ".join(page["problems"]))
        lines.append("")
        lines.append(page["text"] if page["text"] else "[不确定: 该页未提取到文字，可能为空白页或扫描页]")
        lines.append("")
    out_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8", newline="\n")


def page_list(pages: list[int]) -> str:
    return "无" if not pages else ", ".join(f"{p:03d}" for p in pages)


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for period in PERIODS:
        pdf = select_source(period)
        print(f"{period}: {pdf.relative_to(ROOT) if pdf else 'MISSING'}", flush=True)
        if pdf is None:
            rows.append({"period": period, "status": "缺失", "quality": "缺失", "reason": "未找到听力原文PDF"})
            continue
        try:
            result = extract_pdf(period, pdf)
            result["status"] = "完成"
            rows.append(result)
        except Exception as exc:
            rows.append({"period": period, "status": "失败", "quality": "低", "reason": str(exc), "pdf": pdf})
    write_report(rows)
    return 0


def write_report(rows: list[dict]) -> None:
    done = [r for r in rows if r["status"] == "完成"]
    missing = [r for r in rows if r["status"] != "完成"]
    quality_counts: dict[str, int] = {}
    for r in rows:
        quality_counts[r["quality"]] = quality_counts.get(r["quality"], 0) + 1
    lines = [
        "# 听力原文提取质量报告",
        "",
        f"- 覆盖期次: {len(rows)}",
        f"- 完成提取: {len(done)}",
        f"- 缺失/失败: {len(missing)}",
        "- 质量分布: " + "；".join(f"{k}: {v}" for k, v in sorted(quality_counts.items())),
        "- 说明: 优先选用文件名含“听力原文”的 PDF；“听力译文”仅为中文译文，不作为听力原文主来源。",
        "",
        "## 明细",
        "",
        "| 期次 | 状态 | 质量 | 源PDF | 源PDF_MD5 | 页数 | 中质量页 | 低质量页 | 输出Markdown | 说明 |",
        "|---|---|---|---|---|---:|---|---|---|---|",
    ]
    for r in rows:
        if r["status"] == "完成":
            lines.append(
                f"| {r['period']} | {r['status']} | {r['quality']} | `{r['pdf'].relative_to(ROOT)}` | `{r['md5']}` | "
                f"{r['pages']} | {page_list(r['mid_pages'])} | {page_list(r['low_pages'])} | "
                f"`{r['out'].relative_to(ROOT)}` | {r['reason']} |"
            )
        else:
            pdf = r.get("pdf")
            pdf_text = f"`{pdf.relative_to(ROOT)}`" if isinstance(pdf, Path) else ""
            lines.append(f"| {r['period']} | {r['status']} | {r['quality']} | {pdf_text} |  | 0 | 无 | 无 |  | {r['reason']} |")
    lines.extend(
        [
            "",
            "## 需要后续处理",
            "",
        ]
    )
    needs = [r for r in rows if r["status"] != "完成" or r["quality"] in {"低", "缺失"}]
    if not needs:
        lines.append("- 无必须处理项。")
    else:
        for r in needs:
            lines.append(f"- {r['period']}: {r['reason']}")
    STATUS.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
