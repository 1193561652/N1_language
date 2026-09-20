from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "output" / "AI易读Markdown归档"
MAIN_DIR = ARCHIVE / "真题Markdown"
LISTENING_DIR = ARCHIVE / "听力原文Markdown"
QUALITY_DIR = ARCHIVE / "质量与处理记录"
KB = ROOT / "output" / "N1考试知识库"

PERIOD_RE = re.compile(r"(20\d{2})年(0?[7]|0?12)月")
PAGE_SPLIT_RE = re.compile(r"(?m)^## PDF Page\s+(\d{3})\s*$")
HEADING_RE = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")
PROBLEM_RE = re.compile(r"(?:###\s*)?(問題|问题)\s*([0-9０-９]+)")
QUESTION_NUMBER_RE = re.compile(r"(?m)^(?:\*\*)?\s*(?:[0-9０-９]+|[一二三四五六七八九十]+)\s*(?:番|[.．、])")
QUALITY_RE = re.compile(r"<!--\s*page_quality:\s*([^;]+);\s*reason:\s*(.*?)\s*-->")
LINE_QUALITY_RE = re.compile(r"(?m)^-\s*Page quality:\s*([^\s-]+)\s*-\s*(.*?)\s*$")


def md5_text(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def period_from_path(path: Path) -> str:
    m = PERIOD_RE.search(path.name)
    if not m:
        return path.stem
    return f"{m.group(1)}年{int(m.group(2)):02d}月"


def corpus_from_path(path: Path) -> str:
    return "listening" if "听力原文Markdown" in str(path) else "exam"


def corpus_label(corpus: str) -> str:
    return "听力原文" if corpus == "listening" else "真题"


def extract_metadata(text: str) -> dict:
    meta = {}
    for key in ["Source PDF", "源PDF", "Source PDF MD5", "源PDF_MD5", "Overall quality", "Extraction method"]:
        m = re.search(rf"(?m)^-\s*{re.escape(key)}\s*[:：]\s*`?(.+?)`?\s*$", text)
        if m:
            meta[key] = m.group(1).strip()
    return meta


def split_pages(text: str) -> list[dict]:
    matches = list(PAGE_SPLIT_RE.finditer(text))
    pages = []
    for idx, match in enumerate(matches):
        page = match.group(1)
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        chunk = text[start:end].strip()
        pages.append({"page": page, "text": chunk})
    return pages


def headings(text: str) -> list[str]:
    result = []
    for m in HEADING_RE.finditer(text):
        title = m.group(2).strip()
        if title.startswith("PDF Page"):
            continue
        result.append(title)
    return result


def problem_labels(text: str) -> list[str]:
    labels = []
    for m in PROBLEM_RE.finditer(text):
        num = m.group(2).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        try:
            value = int(num)
        except ValueError:
            continue
        if 1 <= value <= 20:
            labels.append(f"問題{value}")
    return sorted(set(labels), key=lambda x: int(re.search(r"\d+", x).group(0)))


def page_quality(text: str) -> tuple[str, str]:
    m = QUALITY_RE.search(text)
    if not m:
        m = LINE_QUALITY_RE.search(text)
    if not m:
        return "未标记", ""
    return m.group(1).strip(), m.group(2).strip()


def classify_page(corpus: str, page_text: str, page_problems: list[str], title_hints: list[str]) -> list[str]:
    tags = []
    if corpus == "listening":
        tags.append("listening_script")
        if "听力译文" in page_text:
            tags.append("listening_translation")
        if "正解" in page_text or "答案" in page_text:
            tags.append("answer_available")
        return tags

    if not page_problems:
        return ["exam_page"]

    joined = "\n".join(title_hints) + "\n" + page_text[:400]
    if any(p in page_problems for p in ["問題1", "問題2", "問題3", "問題4"]):
        tags.append("vocabulary")
    if any(p in page_problems for p in ["問題5", "問題6", "問題7", "問題8"]):
        tags.append("grammar")
    if any(p in page_problems for p in ["問題9", "問題10", "問題11", "問題12", "問題13", "問題14"]):
        tags.append("reading")
    if "読解" in joined or "阅读" in joined:
        tags.append("reading")
    if "文法" in joined or "文法" in page_text:
        tags.append("grammar")
    if "語彙" in joined or "言葉" in joined or "読み方" in joined:
        tags.append("vocabulary")
    return sorted(set(tags)) or ["exam_page"]


def first_line(text: str, limit: int = 120) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("<!--"):
            return line[:limit]
    return ""


def collect_documents() -> list[Path]:
    files = list(MAIN_DIR.rglob("*.md")) + list(LISTENING_DIR.rglob("*.md"))
    return sorted(files, key=lambda p: (period_from_path(p), corpus_from_path(p), str(p)))


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def build() -> None:
    KB.mkdir(parents=True, exist_ok=True)
    for sub in ["indexes", "chunks", "analysis"]:
        (KB / sub).mkdir(parents=True, exist_ok=True)

    docs = []
    page_chunks = []
    problem_index: dict[str, list[dict]] = defaultdict(list)
    period_index: dict[str, dict] = defaultdict(lambda: {"exam": None, "listening": None, "chunks": []})
    tag_index: dict[str, list[dict]] = defaultdict(list)
    heading_counter = Counter()
    problem_counter = Counter()
    quality_counter = Counter()

    for path in collect_documents():
        text = read_text(path)
        period = period_from_path(path)
        corpus = corpus_from_path(path)
        metadata = extract_metadata(text)
        pages = split_pages(text)
        doc_id = f"{period}_{corpus}"
        doc = {
            "doc_id": doc_id,
            "period": period,
            "corpus": corpus,
            "corpus_label": corpus_label(corpus),
            "path": rel(path),
            "title": first_line(text).lstrip("# ").strip(),
            "md5": md5_text(text),
            "page_count": len(pages),
            "metadata": metadata,
        }
        docs.append(doc)
        period_index[period][corpus] = doc

        for page in pages:
            page_no = page["page"]
            page_text = page["text"]
            hds = headings(page_text)
            probs = problem_labels(page_text)
            q, q_reason = page_quality(page_text)
            tags = classify_page(corpus, page_text, probs, hds)
            for h in hds:
                if h.startswith("問題") or h.startswith("问题"):
                    heading_counter[h] += 1
            for p in probs:
                problem_counter[(corpus, p)] += 1
            quality_counter[(corpus, q)] += 1
            chunk_id = f"{doc_id}_p{page_no}"
            chunk = {
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "period": period,
                "corpus": corpus,
                "corpus_label": corpus_label(corpus),
                "pdf_page": page_no,
                "source_markdown": rel(path),
                "locator": f"{period} {corpus_label(corpus)} PDF Page {page_no}",
                "problems": probs,
                "headings": hds,
                "tags": tags,
                "quality": q,
                "quality_reason": q_reason,
                "char_count": len(page_text),
                "question_marker_count": len(QUESTION_NUMBER_RE.findall(page_text)),
                "text": page_text,
            }
            page_chunks.append(chunk)
            period_index[period]["chunks"].append(
                {
                    "chunk_id": chunk_id,
                    "corpus": corpus,
                    "pdf_page": page_no,
                    "problems": probs,
                    "tags": tags,
                    "quality": q,
                }
            )
            for p in probs:
                problem_index[p].append(
                    {
                        "period": period,
                        "corpus": corpus,
                        "pdf_page": page_no,
                        "chunk_id": chunk_id,
                        "source": rel(path),
                    }
                )
            for tag in tags:
                tag_index[tag].append(
                    {
                        "period": period,
                        "corpus": corpus,
                        "pdf_page": page_no,
                        "chunk_id": chunk_id,
                    }
                )

    write_jsonl(KB / "indexes" / "documents.jsonl", docs)
    write_jsonl(KB / "chunks" / "page_chunks.jsonl", page_chunks)
    for tag_name in ["vocabulary", "grammar", "reading", "listening_script", "listening_translation"]:
        write_jsonl(KB / "chunks" / f"{tag_name}.jsonl", [c for c in page_chunks if tag_name in c["tags"]])
    write_jsonl(KB / "indexes" / "periods.jsonl", [{"period": k, **v} for k, v in sorted(period_index.items())])
    write_jsonl(KB / "indexes" / "problem_index.jsonl", [{"problem": k, "locations": v} for k, v in sorted(problem_index.items(), key=lambda x: int(re.search(r"\d+", x[0]).group(0)))])
    write_jsonl(KB / "indexes" / "tag_index.jsonl", [{"tag": k, "locations": v} for k, v in sorted(tag_index.items())])

    write_readme(docs, page_chunks, problem_counter, quality_counter)
    write_period_index(period_index)
    write_problem_index(problem_index)
    write_structure_analysis(docs, page_chunks, heading_counter, problem_counter, quality_counter)
    write_quality_notes(docs, page_chunks)
    write_field_guide()


def write_readme(docs: list[dict], chunks: list[dict], problem_counter: Counter, quality_counter: Counter) -> None:
    periods = sorted({d["period"] for d in docs})
    exam_docs = sum(1 for d in docs if d["corpus"] == "exam")
    listening_docs = sum(1 for d in docs if d["corpus"] == "listening")
    lines = [
        "# JLPT N1 考试知识库",
        "",
        f"- 构建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 覆盖期次: {len(periods)}",
        f"- 真题文档: {exam_docs}",
        f"- 听力原文文档: {listening_docs}",
        f"- 页级检索块: {len(chunks)}",
        "",
        "## 推荐读取顺序",
        "",
        "- **文字・词汇逐题分类**：[分类知识库](文字词汇分类/README.md)，按商定的問題1—4分类法标注全部775道题；标签严格限定在各题所属问题内。",
        '- **语法逐题分类**：[语法分类知识库](语法分类/README.md)，按商定分类标注最近10期（2021.07—2025.12）190道题；标签严格限定在各题所属的問題5—7。',
        "",
        "1. `analysis/考试结构与语料分析.md`: 先了解语料覆盖、题型结构和质量情况。",
        "2. `indexes/period_index.md`: 按考试期次定位真题和听力。",
        "3. `indexes/problem_index.md`: 按 問題1、問題2 等题组跨年份检索。",
        "4. `chunks/page_chunks.jsonl`: 机器检索入口，每行一个 PDF 页级 chunk，含原文、页码、题组、标签和质量。",
        "",
        "## 机器可读文件",
        "",
        "- `indexes/documents.jsonl`: 每份源 Markdown 的元数据。",
        "- `indexes/periods.jsonl`: 每一期的真题、听力、页级 chunk 汇总。",
        "- `indexes/problem_index.jsonl`: 题组到页面 chunk 的倒排索引。",
        "- `indexes/tag_index.jsonl`: vocabulary / grammar / reading / listening_script 等标签索引。",
        "- `chunks/page_chunks.jsonl`: 主语料。字段 `text` 保留原始 Markdown 页面文本；`locator` 可反查期次、语料类型和 PDF 页码。",
        "- `chunks/vocabulary.jsonl`、`grammar.jsonl`、`reading.jsonl`、`listening_script.jsonl`: 按标签拆出的子语料，便于单独建索引。",
        "",
        "## 检索建议",
        "",
        "- 查某一期完整资料: 先用 `periods.jsonl` 或 `period_index.md` 找期次。",
        "- 查某类题型: 用 `problem_index.jsonl` 找 `問題N`，再读取对应 `chunk_id`。",
        "- 查听力脚本: 用 `tag_index.jsonl` 的 `listening_script`，或直接筛选 `page_chunks.jsonl` 中 `corpus == listening`。",
        "- 需要原文定位时: 使用 `locator`、`source_markdown`、`pdf_page` 三个字段。",
        "",
    ]
    (KB / "README.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_period_index(period_index: dict[str, dict]) -> None:
    lines = [
        "# 期次索引",
        "",
        "| 期次 | 真题 | 真题页块 | 听力原文 | 听力页块 | 备注 |",
        "|---|---|---:|---|---:|---|",
    ]
    for period, info in sorted(period_index.items()):
        exam = info.get("exam")
        listening = info.get("listening")
        exam_chunks = [c for c in info["chunks"] if c["corpus"] == "exam"]
        listening_chunks = [c for c in info["chunks"] if c["corpus"] == "listening"]
        note = "OK"
        if not listening:
            note = "缺听力原文"
        lines.append(
            f"| {period} | `{exam['path'] if exam else ''}` | {len(exam_chunks)} | `{listening['path'] if listening else ''}` | {len(listening_chunks)} | {note} |"
        )
    (KB / "indexes" / "period_index.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_problem_index(problem_index: dict[str, list[dict]]) -> None:
    lines = ["# 题组索引", "", "按题组列出所有出现位置。`chunk_id` 可在 `chunks/page_chunks.jsonl` 中直接定位。", ""]
    def pkey(item: tuple[str, list[dict]]) -> int:
        return int(re.search(r"\d+", item[0]).group(0))
    for problem, locs in sorted(problem_index.items(), key=pkey):
        lines.append(f"## {problem}")
        lines.append("")
        lines.append("| 期次 | 语料 | PDF页 | chunk_id | 源Markdown |")
        lines.append("|---|---|---|---|---|")
        for loc in sorted(locs, key=lambda x: (x["period"], x["corpus"], x["pdf_page"])):
            lines.append(f"| {loc['period']} | {corpus_label(loc['corpus'])} | {loc['pdf_page']} | `{loc['chunk_id']}` | `{loc['source']}` |")
        lines.append("")
    (KB / "indexes" / "problem_index.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_structure_analysis(
    docs: list[dict],
    chunks: list[dict],
    heading_counter: Counter,
    problem_counter: Counter,
    quality_counter: Counter,
) -> None:
    periods = sorted({d["period"] for d in docs})
    by_corpus = Counter(d["corpus"] for d in docs)
    tag_counts = Counter(tag for c in chunks for tag in c["tags"])
    lines = [
        "# 考试结构与语料分析",
        "",
        "## 语料范围",
        "",
        f"- 覆盖期次: {len(periods)}，从 {periods[0]} 到 {periods[-1]}。",
        f"- 真题 Markdown: {by_corpus['exam']} 份。",
        f"- 听力原文 Markdown: {by_corpus['listening']} 份。",
        f"- 页级 chunk: {len(chunks)} 个。",
        "",
        "## 知识库建模方式",
        "",
        "- 基本定位单位是 PDF 页。每个 chunk 保留完整 `## PDF Page xxx` 页面文本，避免破坏原文。",
        "- 每个 chunk 附带 `period`、`corpus`、`pdf_page`、`problems`、`tags`、`quality`、`source_markdown`。",
        "- 真题和听力分开建库，但用相同的期次字段连接，便于把同一期的阅读、语言知识和听力脚本合并检索。",
        "",
        "## 题型理解",
        "",
        "- `問題1` 到 `問題4` 多数属于文字、词汇、用法类题目，可作为 vocabulary 入口。",
        "- `問題5` 到 `問題8` 多数属于文法、句子组织、文章内语法类题目，可作为 grammar 入口。",
        "- `問題9` 之后多数进入读解，可作为 reading 入口。",
        "- 听力原文按 `listening_script` 建标签，若页面含中文译文则追加 `listening_translation`。",
        "- 上述分类是为了检索便利的启发式标签，原文仍以页面 Markdown 为准。",
        "",
        "## 标签分布",
        "",
        "| 标签 | 页级chunk数 |",
        "|---|---:|",
    ]
    for tag, count in sorted(tag_counts.items()):
        lines.append(f"| {tag} | {count} |")

    lines.extend(["", "## 题组页分布", "", "| 语料 | 题组 | 页数 |", "|---|---|---:|"])
    for (corpus, problem), count in sorted(problem_counter.items(), key=lambda x: (x[0][0], int(re.search(r"\d+", x[0][1]).group(0)))):
        lines.append(f"| {corpus_label(corpus)} | {problem} | {count} |")

    lines.extend(["", "## 页面质量分布", "", "| 语料 | 质量 | 页数 |", "|---|---|---:|"])
    for (corpus, quality), count in sorted(quality_counter.items()):
        lines.append(f"| {corpus_label(corpus)} | {quality} | {count} |")

    lines.extend(["", "## 高频题组标题样本", "", "| 标题 | 出现次数 |", "|---|---:|"])
    for heading, count in heading_counter.most_common(30):
        lines.append(f"| {heading.replace('|', '/')} | {count} |")

    lines.extend(
        [
            "",
            "## 使用建议",
            "",
            "- 做 RAG 或本地搜索时，优先索引 `chunks/page_chunks.jsonl` 的 `text`，并把 `locator` 作为引用显示。",
            "- 如果要训练题型识别，可用 `problems` 和 `tags` 作为弱标签。",
            "- 如果要构建错题或知识点库，建议从 `vocabulary`、`grammar`、`reading`、`listening_script` 四类标签分别抽取。",
            "- 页面质量为 `中`、`中高` 或 `未标记` 时，回答高精度问题前应回看源 Markdown 或源 PDF。",
        ]
    )
    (KB / "analysis" / "考试结构与语料分析.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_quality_notes(docs: list[dict], chunks: list[dict]) -> None:
    quality_docs = sorted(QUALITY_DIR.glob("*.md"))
    lines = [
        "# 质量与校对索引",
        "",
        "## 原始质量记录",
        "",
    ]
    for path in quality_docs:
        lines.append(f"- `{rel(path)}`")
    lines.extend(["", "## 页面质量非高的 chunk", "", "| 期次 | 语料 | PDF页 | 质量 | 原因 | chunk_id |", "|---|---|---|---|---|---|"])
    for c in chunks:
        if c["quality"] not in {"高", ""}:
            reason = c["quality_reason"].replace("|", "/")
            lines.append(f"| {c['period']} | {c['corpus_label']} | {c['pdf_page']} | {c['quality']} | {reason} | `{c['chunk_id']}` |")
    (KB / "analysis" / "质量与校对索引.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_field_guide() -> None:
    lines = [
        "# 知识库字段说明",
        "",
        "## `chunks/page_chunks.jsonl`",
        "",
        "| 字段 | 含义 |",
        "|---|---|",
        "| `chunk_id` | 稳定页级编号，格式为 `期次_语料_p页码`。 |",
        "| `doc_id` | 文档编号，格式为 `期次_exam` 或 `期次_listening`。 |",
        "| `period` | 考试期次，例如 `2024年12月`。 |",
        "| `corpus` | `exam` 表示真题，`listening` 表示听力原文。 |",
        "| `pdf_page` | 源 PDF 页码，三位字符串。 |",
        "| `source_markdown` | 来源 Markdown 路径。 |",
        "| `locator` | 推荐展示给 AI/用户的定位字符串。 |",
        "| `problems` | 页面中识别出的题组，例如 `問題1`。 |",
        "| `headings` | 页面内 Markdown 标题。 |",
        "| `tags` | 检索标签，如 `vocabulary`、`grammar`、`reading`、`listening_script`。 |",
        "| `quality` / `quality_reason` | 页面级质量标记与原因。 |",
        "| `question_marker_count` | 页面内疑似题号/番数标记数量，仅作粗略统计。 |",
        "| `text` | 完整页面 Markdown 原文。 |",
        "",
        "## 设计原则",
        "",
        "- 不对原文做摘要替换，所有可检索内容都保留原始页面文本。",
        "- 索引字段只做辅助理解；严格引用时以 `text` 和源 Markdown 为准。",
        "- 如果要接入向量库，建议以 `text` 为正文，以其他字段作为 metadata。",
    ]
    (KB / "analysis" / "知识库字段说明.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    build()
