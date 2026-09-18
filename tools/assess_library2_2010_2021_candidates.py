from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "library2"
OUT = ROOT / "output" / "library2_2010_2021_markdown"
REPORT = OUT / "候选PDF质量评估.md"

CID_RE = re.compile(r"\(cid:\d+\)")
SPACE_RE = re.compile(r"[ \t\u3000]+")
PROBLEM_RE = re.compile(r"問題\s*[0-9０-９]+")


def normalize(raw: str) -> str:
    text = CID_RE.sub("", raw or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(SPACE_RE.sub(" ", line).strip() for line in text.splitlines()).strip()


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def score_pdf(path: Path) -> dict:
    pages = []
    chars = 0
    problem_count = 0
    cid_count = 0
    good_pages = 0
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            raw = page.extract_text() or ""
            clean = normalize(raw)
            pages.append(clean)
            chars += len(clean)
            cid_count += raw.count("(cid:")
            problem_count += len(PROBLEM_RE.findall(clean))
            cjk = sum(1 for ch in clean if "\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff")
            if len(clean) >= 120 and cjk >= 50 and raw.count("(cid:") <= 5:
                good_pages += 1
    page_count = len(pages)
    quality_score = good_pages * 100 + problem_count * 20 + min(chars // 1000, 50) - cid_count
    return {
        "path": path,
        "md5": md5_file(path),
        "pages": page_count,
        "chars": chars,
        "cid": cid_count,
        "good_pages": good_pages,
        "problem_count": problem_count,
        "score": quality_score,
    }


def period_candidates() -> dict[str, list[Path]]:
    periods: dict[str, list[Path]] = {}
    for path in sorted((LIB / "2010年-2020年").rglob("*N1_真题.pdf")):
        period = path.parent.name
        periods.setdefault(period, []).append(path)
    for path in sorted((LIB / "2021年7月").glob("*N1_真题.pdf")):
        periods.setdefault("2021年7月", []).append(path)
    return periods


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 2010年-2021年7月 候选PDF质量评估",
        "",
        "| 期次 | 推荐 | PDF | 页数 | 好文字层页 | 字符数 | 题组数 | CID数 | 分数 | MD5 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for period, paths in sorted(period_candidates().items()):
        scored = [score_pdf(path) for path in paths]
        best = max(scored, key=lambda x: x["score"])
        for item in scored:
            rec = "YES" if item["path"] == best["path"] else ""
            lines.append(
                f"| {period} | {rec} | `{item['path'].relative_to(ROOT)}` | {item['pages']} | {item['good_pages']} | {item['chars']} | {item['problem_count']} | {item['cid']} | {item['score']} | `{item['md5']}` |"
            )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()

