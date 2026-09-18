from __future__ import annotations

import json
import re
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import gemini_pdf_to_markdown as gemini  # noqa: E402


LIB = ROOT / "library2"
ARCHIVE = ROOT / "output" / "AI易读Markdown归档"
OUT = ARCHIVE / "听力原文Markdown"
CACHE = ROOT / "tmp" / "gemini_listening_transcripts"
REPORT_DIR = ARCHIVE / "质量与处理记录"
REPORT = REPORT_DIR / "听力原文视觉提取质量报告.md"

MODEL = "gemini-3.5-flash"
DPI = 150
MAX_SIDE = 1800
JPEG_QUALITY = 88
MAX_OUTPUT_TOKENS = 8192
TEMPERATURE = 0.0
RETRIES = 1
SLEEP_SECONDS = 0.3

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


QUALITY_RE = re.compile(r"<!--\s*page_quality:\s*([^;]+);\s*reason:\s*(.*?)\s*-->")
OMIT_RE = re.compile(r"<!--\s*omit_page:\s*(.*?)\s*-->")


def period_folder(period: str) -> Path:
    year = int(period[:4])
    month = int(period[5:7])
    folder = f"{year}年{month}月"
    if year <= 2020:
        return LIB / "2010年-2020年" / folder
    return LIB / folder


def score_candidate(path: Path) -> int:
    name = path.name
    score = 0
    if "N1" in name:
        score += 1000
    if "听力原文" in name:
        score += 900
    if "答案解析+听力原文+译文" in name:
        score += 700
    elif "答案解析+听力原文" in name:
        score += 650
    if "真题+听力原文" in name:
        score += 500
    if "听力译文" in name or "阅读译文" in name:
        score -= 900
    if "N2" in name:
        score -= 2000
    score -= min(path.stat().st_size // 3_000_000, 15)
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
            candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=score_candidate)


def listening_prompt(period: str, page_num: int, total_pages: int) -> str:
    return f"""请读取这张 JLPT N1 听力资料 PDF 页面图像，并转换为 AI 易读 Markdown。

本任务只整理“听力原文/听解脚本/听力选项/听力译文”等和听力内容直接相关的页面。

硬性要求：
0. 只输出该页 Markdown 正文，不要解释识别过程，不要输出代码块。
1. 忠实提取页面原文，不要改写日文原文、中文译文、题号、选项或答案。
2. 页面标题必须写为：## PDF Page {page_num:03d}
3. 如果页面是文字、语法、阅读等非听力解析页，请只输出：
## PDF Page {page_num:03d}
<!-- omit_page: 非听力原文/听力译文相关页 -->
<!-- page_quality: 高; reason: 已识别为非听力页并略过 -->
4. 如果页面包含听力原文、听力选项、听力译文、听解脚本，请完整提取，不要省略。
5. 用三级标题标出能识别出的题组，例如：### 問題1 / ### 問題2 / ### 問題3 / ### 問題4 / ### 問題5 / ### 听力译文。
6. 每道题尽量保留题号、发话人、题干、选项、答案的结构。
7. 对不确定或看不清的文字，用 [不确定: 原因] 标记，不要猜。
8. 如果原文是分栏排版，请按正常阅读顺序整理，不要把左右栏混在一起。
9. 页面末尾必须添加一行 HTML 注释，格式严格为：
<!-- page_quality: 高/中/低; reason: 简短中文原因 -->

期次：{period}
当前 PDF 页：{page_num}/{total_pages}
请只输出这一页的 Markdown。"""


def cache_path(period: str, page_num: int) -> Path:
    return CACHE / period / "pages" / f"page_{page_num:03d}.md"


def image_dir(period: str) -> Path:
    return CACHE / period / "images"


def call_page(period: str, pdf: Path, page_num: int, total_pages: int, request_log: Path) -> str:
    cached = cache_path(period, page_num)
    if cached.exists() and cached.read_text(encoding="utf-8").strip():
        return cached.read_text(encoding="utf-8")

    img = gemini.render_page(pdf, page_num, image_dir(period), DPI)
    jpg = gemini.compress_image(img, MAX_SIDE, JPEG_QUALITY)
    try:
        text = gemini.call_gemini(
            api_key=gemini.GEMINI_API_KEY or "",
            model=MODEL,
            prompt=listening_prompt(period, page_num, total_pages),
            image_b64=gemini.image_base64(jpg),
            max_output_tokens=MAX_OUTPUT_TOKENS,
            temperature=TEMPERATURE,
            retries=RETRIES,
            page_num=page_num,
            request_log=request_log,
        ).strip()
    except Exception as exc:
        text = "\n".join(
            [
                f"## PDF Page {page_num:03d}",
                f"[不确定: Gemini 视觉提取失败: {exc}]",
                "<!-- page_quality: 低; reason: Gemini 请求失败或返回空文本 -->",
            ]
        )
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(text + "\n", encoding="utf-8", newline="\n")
    time.sleep(SLEEP_SECONDS)
    return text


def parse_quality(text: str) -> tuple[str, str, bool]:
    omitted = bool(OMIT_RE.search(text))
    listening_cues = [
        "听力原文",
        "听力译文",
        "聴解",
        "問題1",
        "問題2",
        "問題3",
        "問題4",
        "問題5",
        "1番",
        "1 番",
        "2番",
        "2 番",
        "正解",
        "→M",
        "→F",
        "男：",
        "女：",
        "男の人",
        "女の人",
    ]
    non_listening_cues = [
        "問題13",
        "問題 13",
        "問題14",
        "問題 14",
        "問題10",
        "問題 10",
        "问题13",
        "问题 13",
        "问题14",
        "问题 14",
        "问题10",
        "问题 10",
    ]
    if not omitted and not any(cue in text for cue in listening_cues):
        omitted = True
    if any(cue in text for cue in non_listening_cues) and not any(cue in text for cue in ["→M", "→F", "男：", "女：", "1番", "1 番"]):
        omitted = True
    match = QUALITY_RE.search(text)
    if not match:
        return "中", "未标记页面质量", omitted
    quality = match.group(1).strip()
    reason = match.group(2).strip()
    if quality not in {"高", "中", "低"}:
        quality = "中"
    return quality, reason, omitted


def target_pages(pdf: Path, total: int) -> list[int]:
    name = pdf.name
    if "答案解析+听力原文+译文" in name:
        start = max(1, total // 2 - 2)
        return list(range(start, total + 1))
    if "答案解析+听力原文" in name and total > 25:
        start = max(1, total // 2 - 2)
        return list(range(start, total + 1))
    return list(range(1, total + 1))


def merge_period(period: str, pdf: Path, total_pages: int, processed_pages: list[int], page_texts: list[dict]) -> Path:
    out_dir = OUT / period[:4]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{period}N1听力原文.md"
    included = [p for p in page_texts if not p["omitted"]]
    quality_counts = Counter(p["quality"] for p in included)
    overall = "高"
    if quality_counts["低"]:
        overall = "低"
    elif quality_counts["中"]:
        overall = "中高"
    if not included:
        overall = "低"

    lines = [
        f"# {period} JLPT N1 听力原文",
        "",
        "## Metadata",
        "",
        f"- Source PDF: `{pdf.relative_to(ROOT)}`",
        f"- Source PDF MD5: `{gemini.md5_file(pdf)}`",
        f"- Source PDF page count: {total_pages}",
        f"- Processed PDF pages: {page_list(processed_pages)}",
        f"- Included listening pages: {', '.join(f'{p['page']:03d}' for p in included) if included else '无'}",
        "- Content type: 听力原文 / 听解脚本 / 听力译文",
        "- Locator rule: 每一页用 `## PDF Page xxx` 保留 PDF 页码定位。",
        "- Extraction method: Gemini vision from rendered PDF pages",
        f"- Overall quality: {overall}",
        f"- Extracted at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Extracted Content",
        "",
    ]
    for item in page_texts:
        if item["omitted"]:
            continue
        lines.append(item["text"].strip())
        lines.append("")
    out.write_text("\n".join(lines).strip() + "\n", encoding="utf-8", newline="\n")
    return out


def process_period(period: str, pdf: Path) -> dict:
    total = gemini.pdf_page_count(pdf)
    pages_to_process = target_pages(pdf, total)
    request_log = CACHE / period / "requests.jsonl"
    page_texts = []
    for page_num in pages_to_process:
        print(f"{period} PDF Page {page_num:03d}/{total:03d}", flush=True)
        text = call_page(period, pdf, page_num, total, request_log)
        quality, reason, omitted = parse_quality(text)
        page_texts.append(
            {
                "page": page_num,
                "text": text,
                "quality": quality,
                "reason": reason,
                "omitted": omitted,
            }
        )
    out = merge_period(period, pdf, total, pages_to_process, page_texts)
    included = [p for p in page_texts if not p["omitted"]]
    low = [p["page"] for p in included if p["quality"] == "低"]
    mid = [p["page"] for p in included if p["quality"] == "中"]
    if low:
        quality = "低"
        reason = f"{len(low)} 页低质量"
    elif mid:
        quality = "中高"
        reason = f"{len(mid)} 页需要抽查"
    elif included:
        quality = "高"
        reason = "视觉提取清楚"
    else:
        quality = "低"
        reason = "未识别出听力原文相关页"
    return {
        "period": period,
        "status": "完成",
        "quality": quality,
        "reason": reason,
        "pdf": pdf,
        "md5": gemini.md5_file(pdf),
        "pages": total,
        "processed_pages": pages_to_process,
        "included_pages": [p["page"] for p in included],
        "mid_pages": mid,
        "low_pages": low,
        "out": out,
        "request_log": request_log,
    }


def page_list(values: list[int]) -> str:
    return "无" if not values else ", ".join(f"{v:03d}" for v in values)


def write_report(rows: list[dict]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    done = [r for r in rows if r["status"] == "完成"]
    missing = [r for r in rows if r["status"] != "完成"]
    counts = Counter(r["quality"] for r in rows)
    lines = [
        "# 听力原文视觉提取质量报告",
        "",
        f"- 覆盖期次: {len(rows)}",
        f"- 完成提取: {len(done)}",
        f"- 缺失/失败: {len(missing)}",
        "- 质量分布: " + ("；".join(f"{k}: {v}" for k, v in counts.items()) if counts else "无"),
        "- 说明: 只保留听力原文、听解脚本、听力选项、听力译文相关页；非听力解析页已略过。",
        "",
        "## 明细",
        "",
        "| 期次 | 状态 | 质量 | 源PDF | 源PDF_MD5 | PDF页数 | 保留页 | 中质页 | 低质页 | 输出Markdown | 说明 |",
        "|---|---|---|---|---|---:|---|---|---|---|---|",
    ]
    for r in rows:
        pdf = f"`{r['pdf'].relative_to(ROOT)}`" if r.get("pdf") else ""
        out = f"`{r['out'].relative_to(ROOT)}`" if r.get("out") else ""
        md5 = f"`{r.get('md5', '')}`" if r.get("md5") else ""
        lines.append(
            "| {period} | {status} | {quality} | {pdf} | {md5} | {pages} | {included} | {mid} | {low} | {out} | {reason} |".format(
                period=r["period"],
                status=r["status"],
                quality=r["quality"],
                pdf=pdf,
                md5=md5,
                pages=r.get("pages", 0),
                included=page_list(r.get("included_pages", [])),
                mid=page_list(r.get("mid_pages", [])),
                low=page_list(r.get("low_pages", [])),
                out=out,
                reason=r["reason"],
            )
        )
    needs = [r for r in rows if r["quality"] in {"低", "缺失", "失败"} or r.get("mid_pages")]
    lines.extend(["", "## 需要后续处理", ""])
    if needs:
        for r in needs:
            lines.append(f"- {r['period']}: {r['reason']}；源文件: `{r.get('pdf', '')}`")
    else:
        lines.append("- 无。")
    REPORT.write_text("\n".join(lines).strip() + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for period in PERIODS:
        pdf = select_source(period)
        if pdf is None:
            print(f"{period}: MISSING", flush=True)
            rows.append(
                {
                    "period": period,
                    "status": "缺失",
                    "quality": "缺失",
                    "reason": "未在对应目录找到听力原文 PDF",
                }
            )
            write_report(rows)
            continue
        print(f"{period}: {pdf.relative_to(ROOT)}", flush=True)
        try:
            rows.append(process_period(period, pdf))
        except Exception as exc:
            rows.append(
                {
                    "period": period,
                    "status": "失败",
                    "quality": "失败",
                    "reason": str(exc),
                    "pdf": pdf,
                }
            )
        write_report(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
