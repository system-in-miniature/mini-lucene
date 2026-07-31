# 文档一次查询执行（DAAT）

## 学习目标

学完本章后，你将能够：

1. 解释为什么物化完整命中集合会随总命中数增长；
2. 跟踪 posting 游标的 `next()` 与 `advance(target)`；
3. 用拉链对齐执行合取，用最小堆执行析取；
4. 把 MUST_NOT 理解为对 required 流的过滤；
5. 区分 DAAT 收集阶段与后续 stored fields 提取阶段；以及
6. 用集合代数 scorer 作为差分测试 oracle。

## 1. 为什么完整集合无法扩展

原有 `query/match.py` 很容易阅读：叶子查询变成 `set[int]`，AND 做交集，
OR 做并集，NOT 减去 prohibited 集合。之后 `search/scorer.py` 的
`score_query()` 再建立完整的 `dict[int, float]`。

它是很有价值的语义 oracle，但所有权会随命中数增长：

```text
term A postings ──→ set A ─┐
                           ├─→ 完整交集 ─→ 完整分数字典
term B postings ──→ set B ─┘
```

两个高频词项若各自匹配数百万文档，交集被消费前两个集合都必须存在。管线后面的
Top-K 堆无法收回这部分内存。

DAAT 改变了所有权契约：每个节点只保存当前位置与按 clause 数量有界的归并状态。

```text
posting 游标 → iterator 树 → 每次一个 (doc_id, score) → Top-K
```

MiniLucene 没有删除集合版。它仍然是最容易理解的布尔语义可执行定义，也是检验
流式路径的 oracle。

## 2. 游标契约

`src/minilucene/search/iterators.py` 的 `PostingsIterator` 包装一条有序
posting list：

```text
UNPOSITIONED (-1)
      │ next() / advance(target)
      ▼
 当前 live posting ── next()/advance() ──→ 更后的 posting
      │
      └──────────────────────────────────→ NO_MORE_DOCS
```

- `doc()` 观察当前状态；
- `next()` 移到下一个 posting；
- `advance(target)` 移到首个 `doc_id >= target` 的 posting；
- 到达末尾后状态稳定，后续调用仍返回 `NO_MORE_DOCS`。

对 `[1, 4, 9, 15]` 调用 `advance(5)` 会落在 `9`。target 是下界。

MiniLucene 的教学 codec 没有 skip data，所以 `advance()` 仍是线性扫描。
接口先于优化仍然有价值：组合 iterator 可以请求“前进到目标”，而不依赖 posting
格式如何实现。真实 Lucene 的 `PostingsEnum` 会利用 skip list 与块级元数据。

## 3. AND 是拉链对齐

`ConjunctionIterator` 对应 Lucene `ConjunctionDISI`。它不建立交集，而是不断
推进落后的游标，直到所有 doc ID 相同：

```text
A:  1   3   5       9      12
B:  0   3   4       9  11  12
C:      3       8   9      12
        ▲               输出：3、9、12
```

若 A 在 5，而 B 前进到 9，那么 5 不可能再属于交集，A 可以直接朝 9 前进。
若另一个 child 又越过到 12，12 成为新 target，对齐重新开始。

```text
target = 第一个 child
重复：
    对其余每个 child：
        child.advance(target)
        若 child > target：
            第一个 child.advance(child)
            用更大的 target 重新对齐
    若全部 child == target：
        输出 target
```

任一 child 为空都会让整个合取立即结束，这正是“与空集求交”的流式版本。

## 4. OR 是最小堆归并

`DisjunctionIterator` 对应 Lucene `DisjunctionDISIApproximation`。堆中为每个
未耗尽 child 保存一个 `(doc_id, child)`：

```text
A: 1       5       9
B:   2     5   8
C:         5           10

堆顶：1 → 2 → 5 → 8 → 9 → 10
                ^
     位于 5 的三个游标一起前进，因此 5 只输出一次
```

堆状态是 `O(clause 数量)`，而不是 `O(命中数量)`。多个 child 可以停在同一个
当前文档上，让 Boolean scorer 汇总全部匹配 clause 的 BM25 贡献。下一次调用时，
所有等于刚输出 doc ID 的堆项一起前进，再选择新的最小值。

## 5. MUST_NOT 过滤 required 流

`ReqExclIterator` 对应 Lucene `ReqExclScorer` 的职责：

```text
required:    1  2     4        7  9
prohibited:  0  2  3           7     10
output:      1        4           9
```

对每个 required 候选，只把 prohibited 游标推进到这个候选。相等则拒绝；
若 prohibited 已经更大则接受，因为有序 doc ID 不会后退。

`search/scorer.py` 的编译器保持既有布尔契约：

- MUST child 构成合取；
- 没有 MUST 时，SHOULD child 构成析取；
- 存在 MUST 时，SHOULD 不决定命中，但匹配时仍贡献分数；
- MUST_NOT child 先析取，再作为 exclusion 流；
- 只有 MUST_NOT 的查询仍然不匹配任何文档。

布尔树会递归编译，所以 AND 的 child 自身也可以是 OR 或带排除的子树。

## 6. 流式 BM25 与显式回退

`iter_scored_docs()` 把 term、match-all 和 Boolean 节点编译成 scorer 游标。
term scorer 持有当前 `Posting`，因此能读取 oracle 使用的相同
`term_frequency`，并以相同 live `df`、live 文档数、field length、平均长度和
schema boost 调用既有 `BM25.term_score()`。Boolean scorer 按 clause 顺序汇总
匹配的正向 child。

并非所有查询类型都已经迁移：

| rewrite 后的查询 | 执行方式 |
|---|---|
| `TermQuery` | DAAT |
| `MatchAllQuery` | 在 reader live-doc ID 上执行 DAAT |
| term/match-all `BooleanQuery` | 递归 DAAT |
| `PrefixQuery` | 通常先 rewrite 为 term/Boolean，再执行 DAAT |
| `PhraseQuery` | 整树回退 `score_query()` |
| 直接传给 scorer、尚未 rewrite 的 `PrefixQuery` | 整树回退 |

回退单位是整棵树，而不是单个叶子。Boolean 树只要含 phrase，整树就走 oracle。
在 positional two-phase iterator 尚未实现时，这能避免混合执行改变命中或加分顺序。

## 7. 两个阶段：先 collect，再 fetch

`IndexSearcher.search()` 现在明确分为两段：

```text
阶段 1：查询执行
iterator 树 → (snapshot doc ID, score)
            → address
            → TopKCollector 最多保留 K 个轻量候选

阶段 2：结果物化
最终 K 个候选 → stored_fields()
             → highlight_document()
             → 对外 SearchHit
```

collector 会统计每个命中，但竞争候选中只存 score、snapshot doc ID、segment
generation 与 local doc ID；它不读取 stored fields，也不高亮。于是
`top_k=0` 仍遍历并统计完整流，但 stored-field fetch 次数为零。

“collector 最多保留 K 个”现在对昂贵命中物化端到端为真：只有最终胜者会变成
`SearchHit`。这并不意味着所有查询工作都是 `O(K)`：每个命中仍需打分，phrase
回退仍会物化完整集合/映射，而且系统没有 WAND 式的非竞争文档跳过。

## 8. 差分实验：DAAT 对拍 oracle

教学安全网是 `tests/unit/search/test_daat_scorer.py`。固定 seed `0xDAA7`，
生成 24 个随机小语料；每个语料生成 40 棵最多三层的嵌套 Boolean 查询树，
覆盖 AND/MUST、OR/SHOULD 与 NOT/MUST_NOT：

```text
24 个语料 × 40 个查询 = 960 个语料/查询对拍组合
```

每次对拍要求 doc ID 完全一致，浮点分数逐项近似一致：

```python
oracle = score_query(reader, query)
actual = dict(iter_scored_docs(reader, query))
assert actual.keys() == oracle.keys()
assert actual == pytest.approx(oracle)
```

运行游标与差分测试：

```bash
UV_CACHE_DIR=/tmp/minilucene-uv-cache uv run pytest \
  tests/unit/search/test_iterators.py \
  tests/unit/search/test_daat_scorer.py -q
```

实测输出：

```text
......................                                                   [100%]
22 passed in 0.19s
```

late-fetch 契约单独可执行：

```bash
UV_CACHE_DIR=/tmp/minilucene-uv-cache uv run pytest \
  tests/contract/test_collect_then_fetch.py -q
```

实测输出：

```text
..                                                                       [100%]
2 passed in 0.04s
```

测试观察到：`top_k=3` 时 `10 matched / 3 fetched`；`top_k=0` 时
`4 matched / 0 fetched`。耗时会变化，计数与零失败才是稳定证据。

## 9. 真实 Lucene 走得更远

MiniLucene 现在教授的是游标形状，而不是生产级优化栈。真实 Lucene 还包括：

- 编码后的 skip data 与块感知 `advance`；
- 每个 leaf reader 的 scorer，而不是教学用全局 doc ID 游标；
- `TwoPhaseIterator` 的 approximation 与 confirmation，这对 phrase 等昂贵匹配很重要；
- impacts 与 block maximum score；
- WAND、Block-Max WAND、MaxScore 类非竞争文档剪枝；
- 专用 bulk scorer 与 collector 协同。

合理路线是：先把 phrase 迁移到“词项合取近似 + 位置确认”，再增加可观察 advance
计数与 codec skip data，测量之后才考虑 WAND/MaxScore。所有优化仍应与集合 oracle
对拍。

## 10. 练习

### 练习 1：跟踪合取

给定 `A=[2, 5, 8, 13]`、`B=[1, 5, 9, 13]`、
`C=[5, 7, 13]`，写出拉链对齐的每次 target 变化。

??? note "参考答案"

    第一个输出是 5。A 前进到 8 后，B 越过到 9；A 再前进到 13，B 与 C 都前进到
    13，于是第二个输出是 13。之后任一 child 耗尽都会终止合取。

### 练习 2：给 ConjunctionIterator 加提前终止统计

复制一份 `ConjunctionIterator` 到临时目录，增加三项计数：`advance()` 调用次数、
target 变化次数、因 child 耗尽导致的提前终止次数。分别测试空 child、稀疏 child
和三个完全对齐 child。

验收：计数不能改变输出 doc ID；稀疏用例至少发生一次 target 变化；空 child
用例必须恰好记录一次提前终止。

??? note "参考答案"

    统计必须只观察既有转换：在状态转换旁递增，不允许反过来用计数控制执行。
    `stats()` 返回一个冻结 dataclass，可以避免暴露可写的 iterator 内部状态。

### 练习 3：设计 phrase two-phase iteration

设计一个 phrase scorer：以各 term posting 的合取作为 approximation，以 positions
检查作为 confirmation。说明从哪里读取 term BM25 贡献，以及如何保持现有 phrase
打分语义不变。

??? note "参考答案"

    approximation 只输出含全部词项的文档；confirmation 在 collect 前调用位置谓词。
    确认成功后，从各游标当前 posting 读取 tf，并按查询词项顺序求和。移除 phrase
    fallback 前，差分测试仍必须同时比较命中和分数。

## 小结

MiniLucene 现在会把受支持的 Boolean 树编译为有界状态 doc-ID 游标：拉链合取、
堆析取和 required/excluded 过滤。BM25 每次产生一个文档并直接送入 Top-K；
stored fields 与 highlights 只为最终胜者提取。原有集合与分数字典路径仍被保留，
既是未迁移查询类型的 fallback，也是让这次结构性改变可信的 oracle。
