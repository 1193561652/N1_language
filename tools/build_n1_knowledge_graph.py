from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "output" / "N1考试知识库"
CHUNKS = KB / "chunks" / "page_chunks.jsonl"
GRAPH = KB / "graph"

JP_TERM_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff々〆ヶー]{2,18}")
OPTION_LINE_RE = re.compile(r"(?m)^\s*([1-4１-４])[\s.．、]*([^\n]{1,80})")
BLANK_GRAMMAR_RE = re.compile(r"(?:^|\n)\s*\d+[^\n]*(?:\(\s*\)|＿+|__)[^\n]*")

GRAMMAR_PATTERNS = {
    "grammar.negation": ["ものか", "わけではない", "とは限らない", "ないことはない", "ずにはいられない"],
    "grammar.contrast_concession": ["にしても", "にもかかわらず", "とはいえ", "一方", "反面", "ところが", "それでも"],
    "grammar.cause_reason": ["ばかりに", "だけあって", "からして", "ことから", "おかげで", "せいで", "ために"],
    "grammar.condition": ["限り", "次第", "さえ", "ならでは", "にしては"],
    "grammar.temporal_aspect": ["に先立って", "にあたって", "に際して", "うちに", "最中", "次第"],
    "grammar.evaluation_degree": ["極まりない", "でならない", "に越したことはない", "にすぎない", "ほど"],
    "grammar.keigo_request": ["いただき", "いただけ", "いたし", "申し上げ", "願います", "願いいたします", "恐れ入"],
    "grammar.organization": ["★", "並べ替え", "順番", "文の組み立て"],
    "grammar.text_cohesion": ["文章の文法", "文中の", "空欄", "流れ", "接続"],
}

TOPIC_KEYWORDS = {
    "topic.work_business": ["会社", "会議", "上司", "部長", "社員", "仕事", "職場", "ビジネス", "プロジェクト", "商品", "開発", "営業"],
    "topic.school_research": ["大学", "学生", "先生", "授業", "研究", "論文", "発表", "講義", "レポート", "ゼミ"],
    "topic.daily_life": ["家", "部屋", "家族", "店", "買", "料理", "電話", "旅行", "生活", "食事"],
    "topic.public_society": ["地域", "社会", "政府", "制度", "市民", "町", "公共", "人口", "問題"],
    "topic.environment": ["環境", "自然", "森", "水", "エネルギー", "ごみ", "温暖化", "リサイクル", "農業"],
    "topic.tech_science": ["技術", "機械", "ロボット", "コンピューター", "データ", "研究", "開発", "科学"],
    "topic.health_medical": ["病院", "医者", "健康", "薬", "患者", "医療", "体", "症状"],
    "topic.culture_media": ["映画", "本", "小説", "音楽", "美術", "文化", "番組", "テレビ", "ラジオ", "広告"],
}

SKILL_BY_PROBLEM_EXAM = {
    "問題1": "skill.vocab_kanji_reading",
    "問題2": "skill.vocab_context_fill",
    "問題3": "skill.vocab_paraphrase",
    "問題4": "skill.vocab_usage",
    "問題5": "skill.grammar_form_choice",
    "問題6": "skill.grammar_sentence_order",
    "問題7": "skill.grammar_text_cohesion",
    "問題8": "skill.grammar_text_cohesion",
    "問題9": "skill.reading_short",
    "問題10": "skill.reading_medium",
    "問題11": "skill.reading_integrated",
    "問題12": "skill.reading_long",
    "問題13": "skill.reading_information_search",
}

SKILL_BY_PROBLEM_LISTENING = {
    "問題1": "skill.listening_task_understanding",
    "問題2": "skill.listening_point_understanding",
    "問題3": "skill.listening_summary",
    "問題4": "skill.listening_quick_response",
    "問題5": "skill.listening_integrated",
}

NODE_LABELS = {
    "skill.vocab_kanji_reading": ("skill", "汉字读音"),
    "skill.vocab_context_fill": ("skill", "语境词汇填空"),
    "skill.vocab_paraphrase": ("skill", "近义替换"),
    "skill.vocab_usage": ("skill", "词语用法"),
    "skill.grammar_form_choice": ("skill", "文法形式选择"),
    "skill.grammar_sentence_order": ("skill", "句子排列"),
    "skill.grammar_text_cohesion": ("skill", "文章内文法"),
    "skill.reading_short": ("skill", "短篇阅读"),
    "skill.reading_medium": ("skill", "中篇阅读"),
    "skill.reading_integrated": ("skill", "综合理解"),
    "skill.reading_long": ("skill", "长篇阅读"),
    "skill.reading_information_search": ("skill", "信息检索"),
    "skill.listening_task_understanding": ("skill", "课题理解"),
    "skill.listening_point_understanding": ("skill", "ポイント理解"),
    "skill.listening_summary": ("skill", "概要理解"),
    "skill.listening_quick_response": ("skill", "即时应答"),
    "skill.listening_integrated": ("skill", "综合理解听力"),
}

STOP_TERMS = {
    "PDF", "Page", "Source", "locator", "Extraction", "method", "Page", "quality",
    "問題", "问题", "正解", "答案", "選びなさい", "最もよいもの", "一つ",
    "日本語能力試験", "日本語", "能力", "試験", "言語知識", "読解", "聴解",
}

STOP_SUBSTRINGS = [
    "文字层",
    "清晰",
    "视觉提取",
    "结构清楚",
    "建议抽样",
    "Source",
    "PDF",
    "Page",
    "quality",
    "選びなさい",
    "選んでください",
    "最もよい",
    "次の文章",
    "次の文",
    "以下は",
    "問いに対する",
    "質問を聞いて",
    "話を聞いて",
    "受験番号",
    "試験が始まるまで",
    "日本語能力",
    "日语能力",
    "第一部分",
    "第二部分",
    "第三部分",
]


def node_id(kind: str, label: str) -> str:
    safe = re.sub(r"\s+", "_", label.strip())
    return f"{kind}:{safe}"


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def iter_chunks():
    with CHUNKS.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def clean_term(term: str) -> str:
    term = term.strip(" 　\t\n\r。、，,.;；:：()（）[]【】「」『』*_-—")
    return term


def is_good_term(term: str) -> bool:
    if len(term) < 2 or len(term) > 18:
        return False
    if term in STOP_TERMS:
        return False
    if any(s in term for s in STOP_SUBSTRINGS):
        return False
    if re.fullmatch(r"[0-9０-９]+", term):
        return False
    if any(stop in term for stop in ["PDF", "Page", "Source", "問題用紙", "注 意"]):
        return False
    if len(term) > 8 and not re.search(r"[\u3040-\u30ff]", term):
        return False
    return True


def extract_option_terms(text: str) -> list[str]:
    terms = []
    for m in OPTION_LINE_RE.finditer(text):
        opt = clean_term(m.group(2))
        if len(opt) > 30:
            continue
        for term in JP_TERM_RE.findall(opt):
            term = clean_term(term)
            if is_good_term(term):
                terms.append(term)
    return terms


def extract_inline_terms(text: str, limit: int = 30) -> list[str]:
    counts = Counter()
    body = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    kept_lines = []
    for line in body.splitlines():
        if line.startswith("- Source") or line.startswith("- Extraction") or line.startswith("- Page quality"):
            continue
        if line.startswith("## PDF Page"):
            continue
        kept_lines.append(line)
    body = "\n".join(kept_lines)
    for term in JP_TERM_RE.findall(body):
        term = clean_term(term)
        if is_good_term(term):
            counts[term] += 1
    return [t for t, _ in counts.most_common(limit)]


def extract_grammar_nodes(text: str) -> list[str]:
    hits = []
    for gid, patterns in GRAMMAR_PATTERNS.items():
        if any(p in text for p in patterns):
            hits.append(gid)
    return hits


def extract_topic_nodes(text: str) -> list[str]:
    hits = []
    for tid, words in TOPIC_KEYWORDS.items():
        score = sum(text.count(w) for w in words)
        if score >= 2:
            hits.append(tid)
    return hits


def extract_skill_nodes(chunk: dict) -> list[str]:
    mapping = SKILL_BY_PROBLEM_LISTENING if chunk["corpus"] == "listening" else SKILL_BY_PROBLEM_EXAM
    return [mapping[p] for p in chunk.get("problems", []) if p in mapping]


def add_node(nodes: dict, nid: str, kind: str, label: str, **extra) -> None:
    if nid not in nodes:
        nodes[nid] = {
            "node_id": nid,
            "type": kind,
            "label": label,
            "aliases": [],
            "description": "",
        }
    nodes[nid].update({k: v for k, v in extra.items() if v is not None})


def add_edge(edges: dict, source: str, target: str, relation: str, evidence: dict) -> None:
    if source == target:
        return
    key = (source, target, relation)
    if key not in edges:
        edges[key] = {
            "source_node": source,
            "target_node": target,
            "relation": relation,
            "weight": 0,
            "evidence": [],
        }
    edges[key]["weight"] += 1
    if len(edges[key]["evidence"]) < 20:
        edges[key]["evidence"].append(evidence)


def build() -> None:
    GRAPH.mkdir(parents=True, exist_ok=True)
    nodes: dict[str, dict] = {}
    occurrences = []
    edges: dict[tuple[str, str, str], dict] = {}
    node_occ_count = Counter()
    type_counter = Counter()

    for nid, (kind, label) in NODE_LABELS.items():
        add_node(nodes, nid, kind, label)
    for gid in GRAMMAR_PATTERNS:
        label = gid.split(".", 1)[1].replace("_", " ")
        add_node(nodes, gid, "grammar", label, aliases=GRAMMAR_PATTERNS[gid])
    for tid in TOPIC_KEYWORDS:
        label = tid.split(".", 1)[1].replace("_", " ")
        add_node(nodes, tid, "topic", label, aliases=TOPIC_KEYWORDS[tid])

    for chunk in iter_chunks():
        text = chunk["text"]
        evidence = {
            "chunk_id": chunk["chunk_id"],
            "period": chunk["period"],
            "corpus": chunk["corpus"],
            "pdf_page": chunk["pdf_page"],
            "locator": chunk["locator"],
            "source_markdown": chunk["source_markdown"],
            "problems": chunk.get("problems", []),
        }
        chunk_nodes = []

        skill_nodes = extract_skill_nodes(chunk)
        grammar_nodes = extract_grammar_nodes(text)
        topic_nodes = extract_topic_nodes(text)
        terms = extract_option_terms(text)
        if chunk["corpus"] == "listening" or "reading" in chunk.get("tags", []):
            terms.extend(extract_inline_terms(text, limit=8))
        else:
            terms.extend(extract_inline_terms(text, limit=6))
        terms = [t for t, _ in Counter(terms).most_common(12)]

        for sid in skill_nodes:
            kind, label = NODE_LABELS.get(sid, ("skill", sid))
            add_node(nodes, sid, kind, label)
            chunk_nodes.append((sid, "skill", label))
        for gid in grammar_nodes:
            add_node(nodes, gid, "grammar", gid.split(".", 1)[1].replace("_", " "), aliases=GRAMMAR_PATTERNS[gid])
            chunk_nodes.append((gid, "grammar", nodes[gid]["label"]))
        for tid in topic_nodes:
            add_node(nodes, tid, "topic", tid.split(".", 1)[1].replace("_", " "), aliases=TOPIC_KEYWORDS[tid])
            chunk_nodes.append((tid, "topic", nodes[tid]["label"]))
        for term in sorted(set(terms)):
            tid = node_id("term", term)
            add_node(nodes, tid, "term", term)
            chunk_nodes.append((tid, "term", term))

        seen = set()
        for nid, kind, label in chunk_nodes:
            if nid in seen:
                continue
            seen.add(nid)
            node_occ_count[nid] += 1
            type_counter[kind] += 1
            occurrences.append(
                {
                    "node_id": nid,
                    "type": kind,
                    "label": label,
                    **evidence,
                    "context": text[:500].replace("\n", " "),
                }
            )

        skill_ids = [n for n in seen if nodes[n]["type"] == "skill"]
        grammar_ids = [n for n in seen if nodes[n]["type"] == "grammar"]
        topic_ids = [n for n in seen if nodes[n]["type"] == "topic"]
        term_ids = [n for n in seen if nodes[n]["type"] == "term"][:12]

        for term in term_ids:
            for other in skill_ids:
                add_edge(edges, term, other, "term_skill_context", evidence)
            for other in grammar_ids:
                add_edge(edges, term, other, "term_grammar_context", evidence)
            for other in topic_ids:
                add_edge(edges, term, other, "term_topic_context", evidence)

        for gid in grammar_ids:
            for sid in skill_ids:
                add_edge(edges, gid, sid, "grammar_skill_context", evidence)
            for tid in topic_ids:
                add_edge(edges, gid, tid, "grammar_topic_context", evidence)

        for tid in topic_ids:
            for sid in skill_ids:
                add_edge(edges, tid, sid, "topic_skill_context", evidence)

        for i, a in enumerate(term_ids):
            for b in term_ids[i + 1 :]:
                add_edge(edges, a, b, "term_co_occurs_same_page", evidence)

    for nid, count in node_occ_count.items():
        nodes[nid]["occurrence_count"] = count

    node_rows = sorted(nodes.values(), key=lambda x: (x["type"], -x.get("occurrence_count", 0), x["label"]))
    occurrence_rows = sorted(occurrences, key=lambda x: (x["node_id"], x["period"], x["corpus"], x["pdf_page"]))
    edge_rows = sorted(edges.values(), key=lambda x: (-x["weight"], x["relation"], x["source_node"], x["target_node"]))

    write_jsonl(GRAPH / "knowledge_nodes.jsonl", node_rows)
    write_jsonl(GRAPH / "knowledge_occurrences.jsonl", occurrence_rows)
    write_jsonl(GRAPH / "knowledge_edges.jsonl", edge_rows)
    write_jsonl(GRAPH / "term_nodes.jsonl", [n for n in node_rows if n["type"] == "term"])
    write_jsonl(GRAPH / "grammar_nodes.jsonl", [n for n in node_rows if n["type"] == "grammar"])
    write_jsonl(GRAPH / "topic_nodes.jsonl", [n for n in node_rows if n["type"] == "topic"])
    write_jsonl(GRAPH / "skill_nodes.jsonl", [n for n in node_rows if n["type"] == "skill"])
    write_reports(node_rows, occurrence_rows, edge_rows, type_counter)


def write_reports(nodes: list[dict], occs: list[dict], edges: list[dict], type_counter: Counter) -> None:
    lines = [
        "# 知识点图谱索引说明",
        "",
        f"- 构建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 节点数: {len(nodes)}",
        f"- 出现记录: {len(occs)}",
        f"- 关系边: {len(edges)}",
        "",
        "## 节点类型",
        "",
        "| 类型 | 说明 | 节点数 | 出现记录数 |",
        "|---|---|---:|---:|",
    ]
    node_type_counts = Counter(n["type"] for n in nodes)
    descriptions = {
        "term": "词语、表达、选项词、阅读/听力中的关键词",
        "grammar": "语法形式、功能表达、句子组织线索",
        "topic": "话题领域和场景",
        "skill": "N1 题型能力点",
    }
    for kind in ["term", "grammar", "topic", "skill"]:
        lines.append(f"| {kind} | {descriptions[kind]} | {node_type_counts[kind]} | {type_counter[kind]} |")

    lines.extend(
        [
            "",
            "## 文件",
            "",
            "- `knowledge_nodes.jsonl`: 所有知识点节点。",
            "- `knowledge_occurrences.jsonl`: 知识点出现位置，含期次、PDF 页、chunk_id、上下文。",
            "- `knowledge_edges.jsonl`: 节点之间的关联关系，含共现证据。",
            "- `term_nodes.jsonl` / `grammar_nodes.jsonl` / `topic_nodes.jsonl` / `skill_nodes.jsonl`: 按类型拆分的节点。",
            "",
            "## 查询方式",
            "",
            "1. 用户给出词语、语法或话题。",
            "2. 在 `knowledge_nodes.jsonl` 中用 `label` 或 `aliases` 匹配节点。",
            "3. 用 `knowledge_occurrences.jsonl` 找历年出现位置。",
            "4. 用 `knowledge_edges.jsonl` 扩展相关节点，再回查相关题目。",
            "5. 返回时引用 `locator`、`chunk_id`、`source_markdown` 和 `pdf_page`。",
            "",
            "## 注意",
            "",
            "- 这是第一版规则图谱，适合检索召回；精确到单题、正确选项、深层语义辨析时，还需要进一步模型精标或人工校正。",
            "- 原文不在图谱文件中重复存全文，完整文本仍在 `chunks/page_chunks.jsonl`。",
        ]
    )
    (GRAPH / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    top_lines = ["# 高频知识点节点", "", "## 高频词语", "", "| 词语 | 出现页数 |", "|---|---:|"]
    for n in [n for n in nodes if n["type"] == "term"][:100]:
        top_lines.append(f"| {n['label'].replace('|', '/')} | {n.get('occurrence_count', 0)} |")
    top_lines.extend(["", "## 高频语法/话题/能力", "", "| 类型 | 节点 | 出现页数 |", "|---|---|---:|"])
    for n in [n for n in nodes if n["type"] != "term"][:100]:
        top_lines.append(f"| {n['type']} | {n['label'].replace('|', '/')} | {n.get('occurrence_count', 0)} |")
    (GRAPH / "高频知识点节点.md").write_text("\n".join(top_lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    build()
