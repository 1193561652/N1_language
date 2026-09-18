from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "output" / "N1考试知识库" / "graph"


def load_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def find_nodes(query: str) -> list[dict]:
    query_lower = query.lower()
    hits = []
    for node in load_jsonl(GRAPH / "knowledge_nodes.jsonl"):
        label = str(node.get("label", ""))
        aliases = [str(a) for a in node.get("aliases", [])]
        if label == query or query in aliases:
            hits.insert(0, node)
        elif query_lower in label.lower() or any(query_lower in a.lower() for a in aliases):
            hits.append(node)
    seen = set()
    deduped = []
    for node in hits:
        if node["node_id"] not in seen:
            seen.add(node["node_id"])
            deduped.append(node)
    return deduped


def occurrences_for(node_ids: set[str], limit: int) -> list[dict]:
    rows = []
    for occ in load_jsonl(GRAPH / "knowledge_occurrences.jsonl"):
        if occ["node_id"] in node_ids:
            rows.append(occ)
            if len(rows) >= limit:
                break
    return rows


def related_for(node_ids: set[str], limit: int) -> list[dict]:
    rows = []
    for edge in load_jsonl(GRAPH / "knowledge_edges.jsonl"):
        if edge["source_node"] in node_ids:
            rows.append(edge)
            if len(rows) >= limit:
                break
    return rows


def node_lookup() -> dict[str, dict]:
    return {n["node_id"]: n for n in load_jsonl(GRAPH / "knowledge_nodes.jsonl")}


def main() -> int:
    parser = argparse.ArgumentParser(description="Query local JLPT N1 knowledge graph.")
    parser.add_argument("query", help="词语、语法、话题或能力点")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    nodes = find_nodes(args.query)
    ids = {n["node_id"] for n in nodes[:10]}
    lookup = node_lookup()
    occs = occurrences_for(ids, args.limit)
    edges = related_for(ids, args.limit)

    print(f"# Query: {args.query}")
    print()
    print("## Matched Nodes")
    for node in nodes[:20]:
        print(f"- {node['node_id']} [{node['type']}] {node['label']} ({node.get('occurrence_count', 0)} pages)")
    print()
    print("## Occurrences")
    for occ in occs:
        print(f"- {occ['label']} | {occ['locator']} | {occ['chunk_id']} | {occ['source_markdown']}")
        print(f"  {occ.get('context', '')[:180]}")
    print()
    print("## Related Nodes")
    for edge in edges:
        target = lookup.get(edge["target_node"], {"label": edge["target_node"], "type": "unknown"})
        print(f"- {target['label']} [{target['type']}] via {edge['relation']} weight={edge['weight']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
