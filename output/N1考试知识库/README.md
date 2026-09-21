# JLPT N1 考试知识库

- 构建时间: 2026-07-19 11:32:39
- 覆盖期次: 31
- 真题文档: 31
- 听力原文文档: 30
- 页级检索块: 1401

## 推荐读取顺序

- **文字・词汇逐题分类**：[分类知识库](文字词汇分类/README.md)，按商定的問題1—4分类法标注全部775道题；标签严格限定在各题所属问题内。
- **语法逐题分类**：[语法分类知识库](语法分类/README.md)，按商定分类标注全部31期（2010.07—2025.12）609道题；标签严格限定在各题所属的問題5—7。

1. `analysis/考试结构与语料分析.md`: 先了解语料覆盖、题型结构和质量情况。
2. `indexes/period_index.md`: 按考试期次定位真题和听力。
3. `indexes/problem_index.md`: 按 問題1、問題2 等题组跨年份检索。
4. `chunks/page_chunks.jsonl`: 机器检索入口，每行一个 PDF 页级 chunk，含原文、页码、题组、标签和质量。

## 机器可读文件

- `indexes/documents.jsonl`: 每份源 Markdown 的元数据。
- `indexes/periods.jsonl`: 每一期的真题、听力、页级 chunk 汇总。
- `indexes/problem_index.jsonl`: 题组到页面 chunk 的倒排索引。
- `indexes/tag_index.jsonl`: vocabulary / grammar / reading / listening_script 等标签索引。
- `chunks/page_chunks.jsonl`: 主语料。字段 `text` 保留原始 Markdown 页面文本；`locator` 可反查期次、语料类型和 PDF 页码。
- `chunks/vocabulary.jsonl`、`grammar.jsonl`、`reading.jsonl`、`listening_script.jsonl`: 按标签拆出的子语料，便于单独建索引。

## 检索建议

- 查某一期完整资料: 先用 `periods.jsonl` 或 `period_index.md` 找期次。
- 查某类题型: 用 `problem_index.jsonl` 找 `問題N`，再读取对应 `chunk_id`。
- 查听力脚本: 用 `tag_index.jsonl` 的 `listening_script`，或直接筛选 `page_chunks.jsonl` 中 `corpus == listening`。
- 需要原文定位时: 使用 `locator`、`source_markdown`、`pdf_page` 三个字段。
