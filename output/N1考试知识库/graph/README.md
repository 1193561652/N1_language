# 知识点图谱索引说明

- 构建时间: 2026-07-19 11:42:58
- 节点数: 10724
- 出现记录: 19929
- 关系边: 117279

## 节点类型

| 类型 | 说明 | 节点数 | 出现记录数 |
|---|---|---:|---:|
| term | 词语、表达、选项词、阅读/听力中的关键词 | 10690 | 13788 |
| grammar | 语法形式、功能表达、句子组织线索 | 9 | 1285 |
| topic | 话题领域和场景 | 8 | 3330 |
| skill | N1 题型能力点 | 17 | 1526 |

## 文件

- `knowledge_nodes.jsonl`: 所有知识点节点。
- `knowledge_occurrences.jsonl`: 知识点出现位置，含期次、PDF 页、chunk_id、上下文。
- `knowledge_edges.jsonl`: 节点之间的关联关系，含共现证据。
- `term_nodes.jsonl` / `grammar_nodes.jsonl` / `topic_nodes.jsonl` / `skill_nodes.jsonl`: 按类型拆分的节点。

## 查询方式

1. 用户给出词语、语法或话题。
2. 在 `knowledge_nodes.jsonl` 中用 `label` 或 `aliases` 匹配节点。
3. 用 `knowledge_occurrences.jsonl` 找历年出现位置。
4. 用 `knowledge_edges.jsonl` 扩展相关节点，再回查相关题目。
5. 返回时引用 `locator`、`chunk_id`、`source_markdown` 和 `pdf_page`。

## 注意

- 这是第一版规则图谱，适合检索召回；精确到单题、正确选项、深层语义辨析时，还需要进一步模型精标或人工校正。
- 原文不在图谱文件中重复存全文，完整文本仍在 `chunks/page_chunks.jsonl`。
