# 打分与 Top-K

## 学习目标

完成本章后，你将能够：

1. 计算 MiniLucene 用于一项 BM25 词项贡献的四类输入；
2. 追踪匹配、打分、stored-field 加载和 Top-K 收集；
3. 解释确定性同分规则，以及为什么 `top_k=0` 仍会统计匹配数；
4. 找出当前 phrase 打分和 collect-then-fetch 相对 Apache Lucene 的偏差；以及
5. 验证已删除文档不会贡献 MiniLucene 的语料统计。

## 1. 匹配与打分是两个阶段

查询先决定哪些文档有资格，再给它们分数。
`src/minilucene/search/scorer.py` 的 `score_query()` 首先调用
`match_query(reader, query)`，物化完整的候选快照文档 ID
`set[int]`。这是便于理解正确性的教学边界：Boolean 和 phrase 逻辑可以与排序分开学习。

对于 `TermQuery`，`score_query()` 调用 `_term_scores()`。它为每个存活 posting 读取：

- `tf`：该文档该字段内的词频；
- `df`：该字段该词项的存活文档频率；
- `n`：reader 快照的存活文档总数；
- `dl`：该文档的分析后字段长度；以及
- `avgdl`：存活且拥有该字段的文档平均分析长度。

实现从 `src/minilucene/search/stats.py` 的 `CorpusStats` 获得
`df`、`n` 与 `avgdl`；这些值由 `src/minilucene/search/reader.py`
的 `ReaderView._build_corpus_stats()` 冻结。该函数只迭代快照中的存活段内 ID。因此，新删除的文档既不贡献匹配，也不贡献背景统计。

这是 MiniLucene 有意选择的语义。它让显式 merge 前后的打分保持稳定，因为 merge 精确复制同一份存活语料。

## 2. BM25 奖励证据，但重复收益会饱和

`src/minilucene/search/bm25.py` 的 `BM25.term_score()` 实现：

```text
idf = log(1 + (n - df + 0.5) / (df + 0.5))
normalization = 1 - b + b * dl / avgdl
tf_weight = tf * (k1 + 1) / (tf + k1 * normalization)
score = idf * tf_weight
```

默认参数为 `k1=1.2`、`b=0.75`。

IDF 让更稀有的词项信息量更高。`tf_weight` 的分数随词项重复而增长，但分子与分母都随 `tf` 增长，所以收益会饱和，而非线性增长。长度归一化削弱长文档仅仅因为容纳词项机会更多而获得的优势。当 `avgdl` 为零时，代码使用
`1.0` 作为归一化值，使空统计字段仍有定义。

`BM25.__post_init__()` 拒绝负数或非有限 `k1`，以及 `[0, 1]` 之外的
`b`。`term_score()` 拒绝非法计数和长度；当 `tf == 0`、`df == 0`
或 `n == 0` 时返回零。

随后，MiniLucene 在 `_term_scores()` 中把贡献乘以 schema 字段 boost。这适合教学，但方向与现代 Lucene 相反：当前 Lucene 使用
`BoostQuery` 等查询时 boost，并已移除索引时字段 boost。该差异明确记录在
[MiniLucene 到 Lucene 映射](../lucene-mapping.md)中。

BM25 分数既不是概率，也不是百分比。它适合在相同查询、reader 快照、similarity 参数、schema boost 和语料统计下排列文档。改变存活语料可能改变 IDF 与平均长度，因此不同快照的绝对数值不能直接校准。仓库测试在冻结输入下比较受控排序或近似分数，并未给出通用的“相关性良好”阈值。

## 3. 复合分数

`src/minilucene/search/scorer.py` 的 `score_query()` 遵循封闭查询 AST：

- term 获得一个 BM25 贡献；
- prefix 通常先被 rewrite，随后由匹配的展开词项贡献分数；
- Boolean 查询汇总非 prohibited 子查询的分数，但只保留通过 Boolean 匹配的文档；
- match-all 给每个候选文档 `0.0` 分；以及
- phrase 先要求位置匹配，再为合格文档汇总组成词项的 BM25 贡献。

phrase 分支必须诚实标注。MiniLucene 用 positions 证明相邻关系，但**不计算 phrase frequency**。某文档只包含一次短语，却散落着许多组成词项，也可能比多次包含完整短语的文档分数更高。Apache Lucene 的
`PhraseQuery` 通过 phrase matcher 和 similarity 使用短语频率。因此，两套系统可能对同一批 phrase 匹配项排出不同顺序。

prefix 打分同样汇总展开词项贡献。展开本身有界并且超限立即失败，第 9 章会详细讨论。

## 4. 堆最多保留 K 个命中

`src/minilucene/search/collector.py` 的 `TopKCollector` 把总匹配数与保留结果分开。每次调用 `collect()` 都递增 `total_hits`。当
`top_k == 0` 时，到此即止：调用者可以统计匹配而不保留命中对象。

K 为正时，collector 维护最多 K 个条目的最小堆。键为：

```python
(score, -segment_generation, -local_doc_id)
```

最小的保留键最容易被淘汰。高分胜出；同分时，较小段代际胜出；同段内，较小本地文档 ID 胜出。`top_docs()` 最后按分数降序、段代际升序、本地 ID 升序排列胜者。相同快照在不同运行中的顺序确定。

collector 为命中对象使用 `O(K)` 内存，同时 `total_hits` 仍统计完整匹配集合。`max_retained` 是可观察测试钩子，永远不超过 K。

同分规则使用段和本地 ID，而不是 stored 应用 ID。这些物理 ID 在一份 reader 快照内稳定，但 merge 后可能改变，因此应用不能把该兜底顺序当作永久外部身份。MiniLucene 通过仅活文档统计保持 merge 前后分数，但同分文档可能获得新的稠密本地 ID。需要稳定业务顺序的产品必须添加显式排序键；字段排序本身不在 V1 范围内。

## 5. 关键的 collect-then-fetch 偏差

很容易误以为 `O(K)` 堆会让整条搜索路径都变成 `O(K)`。源码并非如此。

`src/minilucene/search/searcher.py` 的 `IndexSearcher.search()` 先 rewrite 查询，再调用 `score_query()`，物化完整分数字典。随后它遍历每个有分文档。在调用 `collector.collect()` 之前，它已经解析地址、加载 stored fields，并调用
`highlight_document()`。

```text
MiniLucene
完整匹配集合 → 完整分数字典
→ 为每个匹配 fetch stored fields/highlight → Top-K 堆

典型 Lucene 方向
postings 迭代器/scorer → 收集 top 文档 ID 与分数
→ 只为胜者 fetch stored fields/highlight
```

因此，MiniLucene 只保留 K 个 `SearchHit` 对象，但匹配与打分内存仍与全部匹配数成比例，并且为所有匹配执行 stored-field/highlighting 工作。它没有 document-at-a-time 迭代器、postings skip、block-max WAND、two-phase iterator、leaf collector 或后置 fetch 阶段。

这不是一个小优化免责声明，而是当前执行架构。行为矩阵只承诺
[有界 Top-K](../behavior-matrix.md) 保留，并不承诺 `O(K)` 查询引擎。映射文档的查询执行警告明确记录了该偏差。

## 6. 与 Apache Lucene 对照

BM25 概念可以迁移：词频饱和、逆文档频率、长度归一化和 similarity 对象同样是真实 Lucene 的核心。保留竞争性命中的 collector 和确定性同分策略也一样。

若干生产细节不能直接迁移：

- Apache Lucene 在 leaf reader 上使用基于迭代器的 `Scorer`，而不是完整 Python set 与 dict。
- Lucene 可以跳过无竞争力 postings，并使用优化的 conjunction、disjunction、two-phase 和 top-score 收集机制。
- Lucene 通常在收集胜出的文档 ID 后才 fetch stored fields。
- Lucene 的已删除文档可能在 merge 前仍留在段统计中；MiniLucene 立刻排除它们。
- MiniLucene phrase 打分汇总词项分数，而不是 phrase frequency。
- MiniLucene 在 schema 中固定 boost，而不是用查询时 boost 包装查询。

在把 MiniLucene 实测分数当作 Apache Lucene 预测之前，请查阅
[行为矩阵](../behavior-matrix.md)中的 global BM25、bounded Top-K、live statistics 与 ranking 条目，以及[映射](../lucene-mapping.md)中的
“Semantics reversed” 行。

## 7. 动手实验：饱和、长度与堆

在仓库根目录运行：

```bash
UV_CACHE_DIR=/tmp/minilucene-uv-cache uv run python - <<'PY'
from minilucene import MemoryIndex, Schema, TextField
from minilucene.query import TermQuery

schema = Schema(body=TextField(stored=True))
index = MemoryIndex(schema)
index.add_document(body="kafka")
index.add_document(body="kafka kafka kafka kafka")
index.add_document(body="kafka filler filler filler filler filler")
index.add_document(body="unrelated")

results = index.search(TermQuery("body", "kafka"), top_k=2)
print(f"total_hits={results.total_hits}")
print(f"retained={len(results.hits)}")
for hit in results.hits:
    print(f"{hit.stored_fields['body']!r} score={hit.score:.6f}")

count_only = index.search(TermQuery("body", "kafka"), top_k=0)
print(
    f"count_only total={count_only.total_hits} "
    f"retained={len(count_only.hits)}"
)
PY
```

实测输出：

```text
total_hits=3
retained=2
'kafka kafka kafka kafka' score=0.570680
'kafka' score=0.490428
count_only total=3 retained=0
```

重复四次的分数高于一次，但并非四倍。只出现一次的更长文档因长度归一化而落在 Top-2 之外。`top_k=0` 仍遍历并统计三个匹配。

还可以运行可执行公式检查：

```bash
UV_CACHE_DIR=/tmp/minilucene-uv-cache uv run pytest tests/unit/search/test_bm25.py tests/unit/search/test_topk.py -q
```

实测输出：

```text
10 passed in 0.08s
```

耗时会变化；稳定证据是通过数量和零失败。

## 8. 练习

### 练习 1——计算题

若 `n=10`、`df=2`、`tf=1` 且 `dl=avgdl`，当 `tf` 变为 4 时，BM25 公式的哪些部分会变化？

??? note "参考答案"

    因为 `n` 和 `df` 不变，`idf` 不变。因为 `dl/avgdl` 不变，长度归一化不变。只有 `tf_weight` 变化，并以次线性方式趋向饱和上限。

### 练习 2——架构题

为什么 `TopKCollector.max_retained <= K` 不能证明搜索内存为 `O(K)`？

??? note "参考答案"

    `score_query()` 已经物化完整候选集合和分数字典。collector 只限制保留的
    `SearchHit` 对象，不限制匹配或打分状态。`IndexSearcher.search()` 还会在堆准入之前 fetch 并高亮每个匹配。

### 练习 3——动手题

不要修改 `src/`。把 `src/minilucene/search/searcher.py` 复制到临时目录，草拟一个两阶段“先收集地址，再 fetch 胜者”的版本。列出 collector 返回类型需要怎样改变。

验收方式：临时 diff 必须避免在 Top-K 选择前调用 `stored_fields()` 和
`highlight_document()`，保持 `total_hits`，并描述如何把胜者地址转换成最终
`SearchHit` 对象。

??? note "参考答案"

    第一阶段可以收集轻量
    `(score, segment_generation, local_doc_id, snapshot_doc_id)` 记录。
    `top_docs()` 找出胜者后，第二阶段只为这些记录解析 stored fields 与
    highlights。collector 应返回轻量 scored address，而不是当前完全物化的
    `SearchHit`；fetch 后仍可组装公开 `TopDocs`。

## 小结

MiniLucene 把匹配资格与 BM25 贡献分开，冻结仅活文档统计，并用确定性堆最多保留 K 个命中。该堆并未改变当前的全量物化架构：每个匹配都会产生分数、stored fields 与 highlight；phrase 分数汇总词项证据，而不是短语频率。下一章将前移一个阶段，研究文本如何变成 scorer 接受的封闭查询 AST。
