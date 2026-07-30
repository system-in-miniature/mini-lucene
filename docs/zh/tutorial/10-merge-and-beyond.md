# 合并与方法论

## 学习目标

完成本章后，你将能够：

1. 解释为什么 merge 要重写选中的不可变段，而不是拼接文件；
2. 追踪存活文档过滤、稠密文档 ID 重映射和 writer 段集合替换；
3. 区分成功 merge 发布、持久 commit 与垃圾回收；
4. 解释为什么 MiniLucene 没有自动 merge policy、后台 scheduler 或 DAAT 搜索；以及
5. 把项目缺口转化成进入 Apache Lucene 的具体阅读路线。

## 1. 为什么需要 merge

Flush 会创建不可变段。频繁 flush 因而产生许多小段，删除则在旧段中留下失效 postings 和 stored values。搜索快照可以通过查询所有段并用 live-doc 掩码过滤来维持逻辑正确性，但物理工作量和文件数会增长。

Merge 创建一个新的不可变段，只包含选中段集合中的存活文档。它可以减少段 reader 数量、丢弃已删除物理内容，并重新稠密编号本地 ID。它不会修改输入段。

MiniLucene 让 merge 显式发生：

```python
writer.merge((generation_a, generation_b))
```

这是教学选择，不是生产自动化。调用者选择 writer 已持有的至少两个互不重复代际。`src/minilucene/writer.py` 的 `IndexWriter.merge()` 会在变更前拒绝数量不足、重复或未知代际。

## 2. 捕获不可变输入

`IndexWriter.merge()` 构造 `ordered_selected` 时保留 writer 当前段顺序。它通过带校验的 `SegmentStore` 打开每个选中段，并把每个镜像与 writer 当前
live-doc `frozenset` 配对。

这一对才是逻辑输入：

```text
不可变 SegmentImage + 时间点 live-doc 掩码
```

只使用段镜像会复活已删除文档。稍后再读掩码则可能混合代际。先捕获 tuple，可以给 `src/minilucene/merge.py` 的
`merge_segment_images()` 一份稳定视图。

writer 分配新段代际，并跳过任何已经存在的代际，包括之前失败发布留下的完整孤儿。不会覆盖输入目录。

## 3. 稠密重映射存活文档

`merge_segment_images()` 为每个输入段创建一份
`旧本地 ID → 新本地 ID` 映射。它访问 `sorted(live_docs)`，分配下一个稠密
ID，复制 stored document，并复制每个字段长度。已删除 ID 不会得到映射。

随后，它遍历输入镜像中的每个字段、词项和 posting。只有旧本地 ID 存在于映射中时，才复制 posting。新 posting 保留原词频和 position tuple，但改用新的稠密 ID。

这种直接复制 postings 很重要。只从 stored fields 重建索引会丢失“已索引但未 stored”的文本。如果 analyzer 行为发生变化，重新分析 stored text 也可能改变结果。MiniLucene 把已验证段镜像视为索引结构的来源。

假设选中段包含：

```text
段 2：存活 ID {0, 2}
段 5：存活 ID {1}
```

合并映射分别为 `{0: 0, 2: 1}` 与 `{1: 2}`。输出
`max_doc == 3`，没有删除掩码，本地 ID 为 `0, 1, 2`。

## 4. 先发布输出，再交换 writer 状态

构造 `SegmentImage` 后，`IndexWriter.merge()` 调用
`SegmentStore.publish()`。只有发布成功后，它才构造并赋值下一份 writer 段列表、live-doc 字典、元数据字典、dirty 集合和代际计数器。

替代段插入最早被选中位置。未选中段保持相对顺序。即使选中输入不相邻，这也能保持确定性的全局文档顺序。

状态交换前失败会保持旧 writer 集合为权威状态。该发布边界由
`tests/acceptance/test_failure_matrix.py` 的
`test_merge_publish_failure_preserves_writer_set()` 测试。

成功 `merge()` 仍不是持久 commit。它改变 writer 状态并发布新不可变段目录，但在 `IndexWriter.commit()` 成功前，`manifest.json` 仍引用旧提交。
NRT `refresh()` 能在 commit 前看到 writer 状态；进程 reopen 看不到。

## 5. 旧 reader 与旧文件按需存活

writer merge 并提交输出后，旧 reader 仍可能引用输入段。因为
`ReaderSnapshot` 已冻结，它的结果保持不变。不能只因为新 reader 能使用压实段，就让旧 reader 失效。

`IndexWriter.merge()` 通过 `src/minilucene/storage/registry.py` 的
`SegmentRegistry.replace()` 更新 writer owner。commit 从 manifest 移除旧代际后，只有当没有 reader owner 保留它们时，旧段才可被
`Index.collect_garbage()` 回收。`SegmentRegistry.collect_garbage()` 强制检查 manifest、writer 与 reader 所有权并集。

Merge 还会清除新段的 live-doc 元数据，因为它只复制存活文档。输出从全存活状态开始。旧掩码文件仍位于旧段目录中，等安全回收这些目录时一起消失。

MiniLucene 的仅活文档 BM25 统计意味着 merge 前后同一逻辑查询得到相同分数。这与 Apache Lucene 不同：Lucene 的删除文档可能在 merge 前仍留在段统计中，物理删除它们可能改变分数。

## 6. 与 Apache Lucene merge 机制对照

真实 Lucene 使用 `MergePolicy` 选择工作，用 `MergeScheduler` 执行。
`TieredMergePolicy` 会考虑段大小、删除回收、允许段数和优化成本，而不是要求应用为每次 merge 列出代际。Merge 可以与索引并发运行，生产代码还处理 warmer/cache 行为、I/O 节流、compound files、故障记账以及 commit/deletion policy 交互。

MiniLucene 没有这些调度机制。它的显式同步方法让四条不变量清晰可见：

1. 捕获不可变镜像和精确 live 掩码；
2. 构造新的稠密不可变镜像；
3. 在交换 writer 状态前发布输出；以及
4. 延迟删除输入，直到根和 owner 都释放它们。

虽然运维系统大幅简化，但这些不变量可以迁移。行为矩阵中的
[显式 merge](../behavior-matrix.md)、merge 发布失败、段所有权和“无自动 merge scheduler”条目定义已实现边界。
[MiniLucene 到 Lucene 映射](../lucene-mapping.md)则给出 `MergePolicy` 与
`MergeScheduler` 这些生产对应物。

## 7. 下一个主要缺口：document-at-a-time 执行

Merge 只是一个前进方向。MiniLucene 当前查询引擎会物化完整匹配集合和分数字典。Apache Lucene 按文档顺序推进 postings 迭代器，组合 scorer，并把有竞争力的命中流式送进 collector。这种 document-at-a-time（DAAT）设计支持 postings skip、专用 conjunction/disjunction 执行、two-phase matching 和竞争分数剪枝。

超越本仓库的一条合理进阶路线是：

```text
当前 ReaderView.postings() tuple
  → 类 PostingsEnum 的 next_doc()/advance() cursor
  → conjunction 与 disjunction 迭代器
  → scorer 迭代进入轻量 collector
  → 只为胜者 fetch stored fields
  → block-max 元数据与竞争性跳过
```

不要从 WAND 开始。首先用精确 cursor 生命周期替换完整集合所有权，同时保持查询语义；然后测量。当前有界 `TopKCollector` 可以启发 collector 接口，但第 8 章已经说明，它本身并不会创造 DAAT 执行。

## 8. 进入真实 Lucene 的实用路线

把 MiniLucene 模块当成带去 Lucene 的问题，而不是文件格式或 API 兼容层：

- 从 `storage/manifest.py` 出发，阅读 `SegmentInfos`、`segments_N`、commit points 和 `IndexDeletionPolicy`。
- 从 `storage/live_docs.py` 出发，查看 `LiveDocsFormat`、`.liv` 文件和 leaf reader live bits。
- 从 `writer.py` 与 `merge.py` 出发，学习 `IndexWriter`、flush control、
  `TieredMergePolicy` 和 `ConcurrentMergeScheduler`。
- 从 `search/scorer.py` 出发，学习 `Weight`、`Scorer`、
  `DocIdSetIterator`、conjunction/disjunction scorer 和 two-phase iteration。
- 从 `search/collector.py` 出发，学习 `Collector`、`LeafCollector` 和
  `TopScoreDocCollector`。
- 从 `query_parser/` 与 `search/rewrite.py` 出发，学习 Lucene query parser 与 `MultiTermQuery` rewrite 方法。

仓库还明确声明重要非目标：不兼容 Lucene codec、没有网络 adapter、没有分布式协调、没有向量检索、没有 numeric/range 字段、doc values、sorting、faceting 或自动 merge scheduler。参见
[行为矩阵](../behavior-matrix.md)与[映射](../lucene-mapping.md)。诚实路线图必须从这些当前边界出发。

## 9. 动手实验：合并存活文档

在仓库根目录运行：

```bash
UV_CACHE_DIR=/tmp/minilucene-uv-cache uv run python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory

from minilucene import Index, KeywordField, Schema, TextField
from minilucene.query import TermQuery

schema = Schema(
    id=KeywordField(stored=True),
    body=TextField(stored=True),
)

with TemporaryDirectory() as directory:
    index = Index.create(Path(directory), schema)
    with index.writer() as writer:
        writer.add_document(id="1", body="common first")
        writer.flush()
        writer.add_document(id="2", body="common deleted")
        writer.flush()
        writer.add_document(id="3", body="common third")
        writer.commit()

    with index.writer() as writer:
        writer.delete_by_term("id", "2")
        before = writer.segment_generations
        merged = writer.merge(before)
        after = writer.segment_generations
        writer.commit()

    reader = index.open_reader()
    results = reader.search(TermQuery("body", "common"), top_k=10)
    print(f"before={before}")
    print(f"after={after}")
    print(f"merged_generation={merged.generation}")
    print(f"total_hits={results.total_hits}")
    print(
        "ids="
        f"{[hit.stored_fields['id'] for hit in results.hits]}"
    )
    reader.close()
    index.close()
PY
```

实测输出：

```text
before=(1, 2, 3)
after=(4,)
merged_generation=4
total_hits=2
ids=['1', '3']
```

已删除文档不会被复制，三个输入段变成一个全存活输出段。

运行聚焦可执行证据：

```bash
UV_CACHE_DIR=/tmp/minilucene-uv-cache uv run pytest tests/nrt/test_segment_merge.py -q
```

实测输出：

```text
6 passed in 1.26s
```

## 10. 练习

### 练习 1——数据流

为什么 merge 必须直接复制 postings，而不能只根据 stored fields 重建？

??? note "参考答案"

    已索引字段不一定 stored。根据 stored fields 重建会丢失这类可搜索内容；如果 analysis 已改变，还可能改变 positions 或 terms。复制经过验证的 postings、positions、norms 和 stored values 才能保留索引快照。

### 练习 2——生命周期

Merge 并 commit 后，为什么 `collect_garbage()` 仍可能保留输入段？

??? note "参考答案"

    旧 reader 可能仍持有它们。只有当代际不在 manifest、writer owner 和任何 reader owner 中时才能删除。Commit 改变持久根，但不会让现有时间点 reader 失效。

### 练习 3——动手策略设计

不要修改 `src/`。在临时目录编写一个使用段字节大小和删除比例的
`select_merge(segments)` 策略。它应返回至少两个代际组成的有序 tuple，或者不返回工作。

验收方式：为“过多小段”“一个大段加一个小段”和“高删除回收”提供确定性测试。声明最大 merge width，并证明函数绝不返回未知或重复代际。

??? note "参考答案"

    一种可接受的教学策略按 `(size, generation)` 排序候选；当小段数量超过阈值时选择不超过固定 width 的候选，并单独优先选择删除比例超过阈值的段。它按当前 writer 顺序返回代际。测试应断言 width、唯一性、成员关系、确定性选择，以及健康布局不产生工作。这不是
    `TieredMergePolicy`，而是让输入和不变量显式化的有界练习。

### 练习 4——路线图

在 DAAT 执行与自动 merge 调度中选择一个下一子系统。写一页设计，包含一条不变量、最小 API、故障边界和可执行验收测试。

??? note "参考答案"

    DAAT 设计应从生命周期明确的 cursor 开始，包含 `doc_id`、
    `next_doc()` 与 `advance(target)`，然后把命中和分数与当前完整集合 oracle 对比。Merge scheduler 设计应分离确定性选择与执行，保留 writer 单 owner，并注入发布失败，证明旧 writer 集合仍是权威状态。

## 小结

显式 merge 捕获不可变段及其精确 live 掩码，只稠密重映射存活文档，发布新段，并且仅在成功后交换 writer 状态。Commit 与 owner-aware 垃圾回收是之后不同的边界。MiniLucene 止步于自动 `TieredMergePolicy` 调度和 DAAT 查询执行之前；它们不是模糊遗漏，而是具体下一接口。完成本教程后，你应能带着更尖锐的问题阅读真实 Lucene，同时不会把这个教学 codec 误认为真实 Lucene。
