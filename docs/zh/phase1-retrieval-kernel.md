# 阶段 1：检索内核验收

> **语言**: [English](../phase1-retrieval-kernel.md) | 简体中文

## 已验收的公共闭环

内存参考路径为：

```text
Schema
→ validated Unicode document
→ field analyzer
→ immutable positional RAM segment
→ closed Query AST
→ live reader statistics
→ BM25 scorer
→ bounded Top-K collector
→ stored fields
```

主要的直接调用 API 是 `MemoryIndex.add_document()` 和
`MemoryIndex.search(query, top_k=...)`。语义测试不经过任何传输适配器。

## 固定行为

- `TextField`、`KeywordField` 和 `StoredField` 使存储、索引、分词、位置和
  加权行为彼此独立。
- 模式指纹（schema fingerprints）使用规范化排序 JSON 和 SHA-256。
- 验证与分析在 RAM 构建器发生变更前完成。
- 标准分析（Standard analysis）将词项转为小写，同时保留原始偏移量和停用词位置间隙。
- 倒排列表（posting lists）对每个字段/词项/文档只包含一条倒排记录，并按稠密的
  本地文档 ID 排序。
- 短语查询携带规范化查询位置，因此被移除的停用词不会使间隙消失。
- 布尔查询实现固定的 MUST/SHOULD/MUST_NOT 规则；只有否定条件的查询不匹配任何内容。
- 前缀查询读取词典，并在超过配置的展开上限时失败。
- BM25 默认值为 `k1=1.2` 和 `b=0.75`；字段加权会乘到单个词项的贡献上。
- 一个 `CorpusStats` 值覆盖读取器视图中的所有活跃文档。
- `TopKCollector` 在统计每个匹配项的同时，最多保留 K 个命中。
- 分数相同时，先按分段世代排序，再按本地文档 ID 排序。

## 可执行证据

阶段验收：

```text
tests/acceptance/test_phase1_retrieval_kernel.py
```

聚焦的约定测试位于：

```text
tests/contract/test_schema.py
tests/unit/analysis/test_pipeline.py
tests/contract/test_memory_index.py
tests/contract/test_query_matching.py
tests/unit/search/test_corpus_stats.py
tests/unit/search/test_bm25.py
tests/contract/test_ranking.py
tests/unit/search/test_topk.py
tests/contract/test_memory_search.py
```

2026-07-27 验收的命令：

```text
uv run pytest tests/acceptance/test_phase1_retrieval_kernel.py -q
1 passed

uv run ruff check src tests tools
All checks passed

uv run pytest -q
54 passed

uv run python -m compileall -q src tests tools
exit 0

git diff --check
exit 0
```

## 按阶段边界推迟的内容

阶段 1 有意不包含磁盘分段编解码器、清单、重启恢复、刷新、提交、删除、更新、合并、
查询字符串解析器、高亮、CLI、网络适配器、分布式协调或向量检索。
