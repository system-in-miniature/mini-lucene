# 第 3 章：倒排索引

文档集合适合按文档写入和读取；搜索问的是反方向问题：给定 term，哪些文档含有它？
倒排索引把 term 变成 key，把文档中的出现变成 posting list。MiniLucene 先在 RAM
构造结构，再冻结为不可变段。四类数据都清晰可见：词典、postings、stored fields
和字段长度 norms。

## 学习目标

完成本章后，你能够追踪分析结果如何进入 posting list，区分词频、位置、字段长度
和 stored 字段，解释文档 ID 为何是段内局部的，检查 RAM 段并关联搜索结果，以及
区分“DAAT 的 Top-K 命中物化有界”和“全部搜索工作都是 O(K)”。

## 机制讲解：构造 RAM 段

`src/minilucene/index/memory.py` 把准备与修改分开。
`RamIndexBuilder.prepare_document` 先调用 `src/minilucene/document.py`
的 `freeze_document`，按 Schema 校验字段名和字符串值，返回不可变 mapping。
校验发生在 builder 修改前，所以坏文档不会留下半条 posting。

每个 indexed 字段经 `_analyze` 处理，结果与完整 frozen document、stored-only
投影一起放入 `PreparedDocument`。其 `posting_count` 统计每字段不同 term 的数量，
而非 token 总数；writer 的 posting flush 阈值使用的就是这个单位。

`RamIndexBuilder.add_prepared` 执行真正的倒排。下一个局部 doc ID 等于当前 stored
文档数。它记录每个 indexed 字段经分析后的 token 数作为 field length，再按 term
聚合位置：

```python
positions_by_term: dict[str, list[int]] = defaultdict(list)
for token in tokens:
    positions_by_term[token.term].append(token.position)
```

每个不同的 `(field, term, document)` 追加一个 `Posting`。
`src/minilucene/index/postings.py` 的不可变 dataclass 保存 `doc_id`、
`term_frequency` 和 `positions`。词频等于位置数；TextField 保存位置，KeywordField
不支持短语，所以位置 tuple 为空。

```text
postings[field][term] = (Posting(local_doc_id, tf, positions), ...)
field_lengths[field][local_doc_id] = 分析后 token 数
stored_documents[local_doc_id] = 可返回字段映射
```

field 是 key 的一部分：title 的 `python` 与 body 的 `python` 不同，可有不同
boost、长度统计与查询 clause。

词典避免扫描全部文档；posting 给出成员关系，tf 支持 BM25 的饱和词频项，position
支持短语；norms 是分析后 token 长度，用于 BM25 长度归一化；stored fields 用于
结果呈现。indexed-but-not-stored 字段可排序但不能返回原文，stored-only 元数据
则不产生 term。

`RamIndexBuilder.freeze` 把可变集合复制为 tuple/mapping proxy，返回
`MemorySegment`。每段都有自己的 generation 和局部 ID 空间；不同段都可有 doc 0，
命中用 `(segment_generation, local_doc_id)` 消歧，merge 时也可重映射。

### 从 postings 到结果

`MemoryIndex.search` 把 builder 冻结为 generation 0，用 `ReaderView` 包装后调用
`IndexSearcher.search`。`src/minilucene/search/stats.py` 的
`CorpusStats.from_segments` 在 reader 范围内计算 live 文档数、df 与平均长度，
避免分数取决于碰巧在哪次 flush 中分段。

`src/minilucene/search/collector.py` 的 `TopKCollector.collect` 最多保留 K 个
hit，却仍累计完整命中数，因此 `total_hits` 可大于 `len(hits)`。当前 searcher
会让受支持的 term/Boolean 树流经 DAAT 游标，并执行 collect-then-fetch，所以只为
最终胜者构造 stored fields/高亮。含 phrase 的树仍回退完整匹配 map，且没有
skip data、WAND 或竞争分数剪枝。“Top-K 命中物化有界”是真，“全部查询工作都为
O(K)”是假。[第 11 章](11-daat.md)会完整展开这条边界。

RAM builder 可变，frozen segment 不可变。删除以后发布独立 live-doc mask，merge
创建替代段，而不是原地改 posting，这正是 point-in-time reader 的基础。

### 成本模型与确定性

倒排把工作从查询时移到建索引时。term query 直接词典查候选，phrase 再检查位置，
Boolean 组合有序游标。含 phrase 的查询当前回退保留的集合/map oracle；rewrite
后的 term/Boolean 树执行 DAAT。
`freeze` 排序字段和 term，文档按插入顺序，posting doc ID 递增，磁盘 codec 据此
产生规范输出并拒绝乱序。Top-K tie-break 使用 score 与文档地址，不依赖字典偶然
迭代顺序。

一个 term 重复百次只增加一个 term-document posting，却增加 tf、长度和 position
list；所以 `max_postings` 是边数近似，不是精确 RAM/字节预算。应用自己的稳定 ID
应放在 KeywordField 中，不能把段内 doc ID 当业务 ID。

## 对照真实 Apache Lucene

Lucene 同样有 term dictionary、postings、frequency、positions、norms 与 stored
fields，但使用 BlockTree、FST、packed integers、skip/impacts、doc values 和
`TermsEnum`/`PostingsEnum` 等 DAAT 迭代器。MiniLucene 没有这些压缩和优化，也无
payload、numeric point 或 per-field codec。它立即从 snapshot BM25 统计排除删除
文档，而 Lucene 段统计可能到 merge 才变化；MiniLucene phrase score 还是 term
BM25 之和。详见[Lucene 映射](../../lucene-mapping.md)与
[行为矩阵](../../behavior-matrix.md)。

## 动手实验：观察 postings 与 norms

```bash
export UV_CACHE_DIR=/tmp/minilucene-uv-cache
uv run --offline python - <<'PY'
from minilucene import MemoryIndex, Schema, TextField
from minilucene.query import TermQuery
index = MemoryIndex(Schema(body=TextField(stored=True)))
index.add_document(body="blue blue sky")
index.add_document(body="blue sea")
segment = index._builder.freeze(generation=0)
print(segment.postings["body"]["blue"])
print(segment.field_lengths["body"])
results = index.search(TermQuery("body", "blue"), top_k=1)
print(results.total_hits, len(results.hits), dict(results.hits[0].stored_fields))
PY
```

实测输出：

```text
(Posting(doc_id=0, term_frequency=2, positions=(0, 1)), Posting(doc_id=1, term_frequency=1, positions=(0,)))
(3, 2)
2 1 {'body': 'blue blue sky'}
```

两个候选中只保留一个 hit，但 `total_hits=2`；doc 0 的 tf=2，位置为 0、1，长度为 3。

```bash
uv run --offline pytest -q tests/contract/test_memory_index.py \
  tests/contract/test_memory_search.py tests/unit/search/test_topk.py
```

实测：`11 passed in 0.07s`。

## 练习

1. **理解题：** 为什么 posting 使用段内 ID？

    ??? note "参考答案"
        段独立构造，merge 会压缩/重映射。reader 内稳定地址是段身份加局部 ID。

2. **理解题：** `blue blue sky` 变成 `blue sky` 后 df、tf 如何变化？

    ??? note "参考答案"
        该文档 tf 从 2 到 1，两个文档仍含 blue，所以 df 仍为 2；长度从 3 到 2。

3. **动手题：** 增加 `red sky` 并打印 blue/sky posting。验收：blue 的 ID 为
   0、1，sky 为 0、2。

    ??? note "参考答案"
        freeze 前 add 文档，再访问对应 term；不改 `src/`。

4. **动手题：** 改成 `top_k=0`。验收：total_hits 仍为 2，hits 为空。

    ??? note "参考答案"
        collector 容量与完整匹配计数相互独立。

## 小结

倒排索引用 field+term 查找替代全文档扫描。postings 承载成员、频率与位置，norms
承载长度，stored fields 承载呈现；freeze 把可变 builder 变成局部 ID 的不可变段。
下一章把这些结构序列化，并研究损坏或歧义字节应如何 fail closed。
