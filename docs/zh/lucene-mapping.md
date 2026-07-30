> **语言**: [English](../lucene-mapping.md) | 简体中文

# MiniLucene → Apache Lucene 映射

MiniLucene 是一个教学实现，而不是兼容 Apache Lucene 的编解码器（codec）或
API。本指南将这些小型 Python 模块映射到它们旨在揭示的生产级概念，
并指出哪些地方若把 MiniLucene 的心智模型照搬到真实 Lucene 中将会出错。

## 如何理解这些标签

- **等价（Equivalent）**：所教授的是相同的概念性不变量。名称、API、
  并发保证和磁盘字节仍可能不同。
- **有意简化（Intentionally simplified）**：生产概念仍可辨认，
  但省略了重要机制或查询类型。
- **语义相反（Semantics reversed）**：MiniLucene 有意或无意地做出了
  与当前 Lucene 相反的选择。应将这些行视为警告，而不是同一行为的较小型实现。

## 模块与格式映射

| Level | MiniLucene module or format | Apache Lucene counterpart | What carries over, and what does not |
|---|---|---|---|
| **Equivalent** | `manifest.json` (`storage/manifest.py`) | `SegmentInfos` and the latest `segments_N` commit file | Both are the atomically published root that names the segment generations belonging to one durable commit. The JSON layout is custom and is not a Lucene file format. |
| **Equivalent** | `live_*.bin` (`storage/live_docs.py`) | `LiveDocsFormat`, `.liv` files, and `Bits` live-doc views | Postings stay immutable while a generation-stamped bitset hides deleted local doc IDs. The encoding and naming are MiniLucene-specific. |
| **Intentionally simplified** | `storage/codec.py`, `storage/segment_store.py`, `terms.bin`, `postings.bin`, `stored.bin`, `norms.bin` | `Codec` plus `PostingsFormat`, `StoredFieldsFormat`, `NormsFormat`, and related per-segment files | The split teaches format ownership, delta encoding, checksums, and strict decoding. It omits Lucene codecs such as BlockTree terms, skip data, packed blocks, compound files, and format compatibility. |
| **Equivalent** | `analysis/pipeline.py` | `Analyzer`, `TokenStream`, `Tokenizer`, and `TokenFilter` | A tokenizer produces tokens and filters transform the stream while attributes such as term, position, and offsets survive the pipeline. Python tuples replace Lucene's reusable attribute stream. |
| **Equivalent** | `analysis/standard.py` position and offset handling | `PositionIncrementAttribute` and `OffsetAttribute` | Removing a stopword does not renumber later tokens, so a phrase cannot jump across the removed source position. Tokenization and the one-word default stop set are only educational. |
| **Intentionally simplified** | `writer.py` | `IndexWriter` | It owns buffering, immutable segment publication, deletion generations, refresh, commit, and explicit merge, but has no rollback or `prepareCommit`. |
| **Intentionally simplified** | one `RamIndexBuilder` in `writer.py` | `DocumentsWriterPerThread` (DWPT), flush control, and indexing chains | MiniLucene has a single-threaded RAM buffer. There is no per-thread indexing, concurrent flush, reader pool, or Lucene-style writer concurrency model. |
| **Equivalent** | `storage/registry.py` | `IndexDeletionPolicy`, `IndexFileDeleter`, and reader/file reference counting | Obsolete segments are reclaimed only after the durable commit and all process-local owners stop referencing them. Unlike Lucene, ownership here is an in-process registry and does not protect readers in another process. |
| **Intentionally simplified** | `reader.py` (`IndexReader`) and `snapshot.py` | `DirectoryReader`, leaf readers, and point-in-time reader snapshots | A reader freezes a segment/live-doc view and remains unchanged after later refreshes. MiniLucene eagerly materializes segment images and has no shared `SegmentReader`/core cache. |
| **Intentionally simplified** | `search/reader.py` (`ReaderView`) | low-level leaf/composite reader access used by search | It translates global doc IDs, exposes postings/stored fields, and builds corpus statistics, but it is an internal query-facing view rather than a public lifecycle owner. |
| **Semantics reversed** | live-only corpus statistics in `search/reader.py` | Lucene term statistics before merge | MiniLucene excludes deleted documents from `docFreq`, document count, and average lengths immediately. Lucene's segment statistics still include deleted documents until merge, so merge can change scores in real Lucene; MiniLucene erases that phenomenon. |
| **Intentionally simplified** | `query/match.py` and `search/scorer.py` | `PostingsEnum`, `DocIdSetIterator`, `Scorer`, `ConjunctionScorer`, `DisjunctionScorer`, and two-phase iteration | MiniLucene materializes complete `set[int]` matches and `dict[int, float]` scores. It has no doc-at-a-time cursors, postings skipping, conjunction/disjunction merge, or two-phase iterator. |
| **Semantics reversed** | `search/searcher.py` plus `search/collector.py` | `IndexSearcher`, `Collector`/`LeafCollector`, `TopScoreDocCollector`, then stored-field/highlight fetch | MiniLucene loads stored fields and computes highlights for every match before offering it to the Top-K heap. Lucene normally collects doc ID/score first and fetches expensive hit content only for the winners. MiniLucene retains only O(K) hit objects, but its stored-field I/O and highlighting work remain O(total hits). |
| **Semantics reversed** | phrase branch in `search/scorer.py` | `PhraseQuery`, phrase matcher, phrase frequency, and similarity scoring | MiniLucene first verifies adjacency, then sums BM25 contributions of the component terms. Lucene scores using phrase frequency; repeated phrases and scattered term frequency therefore rank differently. |
| **Intentionally simplified** | `query/model.py`, `query_parser/`, and `search/rewrite.py` | Lucene `Query` subclasses, query parser, and multi-term query rewrite | Term, boolean, exact phrase, prefix, and match-all queries form a closed teaching AST. Phrase slop, fuzzy/wildcard/regex queries, numeric/range queries, and most rewrite strategies are absent. |
| **Semantics reversed** | `boost` on `FieldType` in `schema.py` | query-time boosts such as `BoostQuery` | MiniLucene fixes boost in the schema and applies it while scoring every query. Lucene 7.0 removed index-time field boosts and retains query-time boost, so the supported direction is the opposite. |
| **Intentionally simplified** | string-only `schema.py` and `document.py` | `FieldType`, point fields/BKD trees, doc values, stored fields, and term vectors | MiniLucene has only text/keyword/stored strings. It has no numeric or date fields, range query, doc values, field sorting, aggregation/faceting, term vectors, payloads, or multi-valued fields. |
| **Intentionally simplified** | explicit `merge()` and `merge.py` | `MergePolicy`, `MergeScheduler`, and `IndexWriter` merge execution | Live documents are copied into one immutable segment with dense local doc IDs, but there is no automatic or tiered merge policy and no background scheduling. |
| **Intentionally simplified** | `highlight.py` | Lucene highlighters using postings offsets, term vectors, or re-analysis | MiniLucene re-analyzes stored text. Consequently an indexed-but-not-stored field cannot be highlighted, even though real Lucene can be configured with offsets or term vectors for highlighting. |
| **Intentionally simplified** | `.writer.lock` in `writer.py` | Lucene `LockFactory`/`NativeFSLockFactory` and `IndexWriter` write lock | `O_EXCL` prevents two writers, but a crash leaves the file behind permanently. The PID is informational only; there is no stale-lock validation or force-unlock API. |

## 查询执行警告

最重要的差距不仅仅是缺少 WAND 或 SIMD。MiniLucene 根本不包含文档一次
（doc-at-a-time）执行路径：

```text
MiniLucene: postings → complete sets → complete score dictionary
Lucene:     postings cursors → scorer iteration → collector → top doc IDs
                                                       ↓
                                            stored fields/highlighting
```

`TopKCollector` 确实将保留的命中对象数量限制为 K，但这不会使当前搜索路径成为
O(K)：`IndexSearcher.search` 会在堆能够丢弃匹配项之前，为每个匹配文档读取
存储字段并计算高亮。

## 读者还应了解的其他边界

- 短语匹配保留分析器位置间隔，但短语得分是各词项 BM25 分数之和，
  而不是基于短语频率计算的 BM25。
- BM25 统计量只使用存活文档。真实 Lucene 会在合并前将已删除文档保留在
  段统计量中，这正是生产环境中的合并可能改变分数的原因。
- 提升值（boost）属于 MiniLucene 模式。当前 Lucene 改为支持查询时提升；
  两者方向相反。
- 数值/日期字段、文档值、范围查询、字段排序、聚合与分面均不在实现范围内。
- 进程崩溃可能遗留 `.writer.lock`；正常关闭会移除它，但项目不提供恢复或解锁 API。
- 高亮要求字段是已存储的 `TextField`，因为 MiniLucene 会重新分析存储文本，
  而不是读取索引偏移量或词项向量。
