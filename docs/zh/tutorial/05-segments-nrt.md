# 第 5 章：段与近实时

“文档已经写入”在搜索引擎里有多种含义：它可能仍在 RAM buffer，可能已经成为
不可变段，可能只对新建的进程内 reader 可见，也可能重启后可恢复。MiniLucene
把三条边界分得很清楚：`flush` 创建段，`refresh` 创建 point-in-time reader，
`commit` 发布重启恢复根。

## 学习目标

完成本章后，你能够说明 flush/refresh/commit 各自的可见性保证，解释旧 reader
为何不变化，追踪 snapshot 对不可变段的所有权，预测 commit 前后 reopen 的结果，
并在不混淆 durability 的前提下解释 NRT。

## 机制讲解：三条发布边界

`IndexWriter` 从当前 manifest 命名的段与新 `RamIndexBuilder` 开始。
`src/minilucene/writer.py` 的 `IndexWriter.add_document` 在改 buffer 前完成校验与
准备；`FlushPolicy` 可按文档数或不同 posting 数自动触发，显式调用更便于观察。

### Flush：RAM 变成不可变段

`IndexWriter.flush` 对空 buffer 返回 `None`。否则它先把 RAM 中仍 live 的文档
compact 到新 builder，选择未使用 generation，把 frozen memory segment 转为
`SegmentImage`，再调用 `SegmentStore.publish`。发布后，writer 把 generation
加入自己的私有段集合、安装全 live mask、清空 RAM 并更新进程内所有权。

段文件本身已经 durable，但 committed `manifest.json` 仍命名旧集合。
`src/minilucene/index/directory.py` 的 `Index.open_reader` 总从 manifest 打开，
所以 flush 后立刻创建的 manifest reader 看不到新段；此刻崩溃，reopen 也看不到。
它只是 orphan candidate，不是已发布根。

### Refresh：发布新的进程内视图

`IndexWriter.refresh` 先 flush，再打开 writer 私有集合中的所有 generation，捕获
对应 live mask，并构造 `commit_generation=None` 的 `IndexReader`。这个新 reader
能看到 flush 变更与 writer 侧删除。

refresh 不会修改某个全局 reader，而是返回新的 point-in-time 对象。
`src/minilucene/reader.py` 的 `IndexReader.__init__` 创建 `ReaderSnapshot`，其中
包含 `SegmentSnapshot` tuple、live masks、corpus stats、Schema 指纹与可选 commit
generation。旧 reader 保留原 tuple 和统计；后续 refresh/delete/merge/commit
都不改变它。排序也是 snapshot 的：新 reader 可有不同 df 与平均长度，旧 reader
继续使用捕获的统计。

### Commit：发布重启根

`IndexWriter.commit` 也先 flush，然后重新打开并校验要发布的每个段。dirty 删除
mask 写成新 live-doc generation，因为 postings 不可变；随后
`Manifest.next_from` 构造下一 commit generation，
`ManifestStore.write_atomic` 发布它。

`src/minilucene/storage/manifest.py` 的 `write_atomic` 把规范 JSON 写入临时文件并
fsync，原子 replace `manifest.json`，再 fsync 索引目录。manifest 是唯一重启
发布边界。未来 `Index.open` 校验 Schema 指纹，`Index.open_reader` 只打开其中
精确命名的 segment/live-doc generation。

commit 不会突变已打开 reader，只改变未来 reader 与新进程看到的根。commit 前的
refresh reader 即使段后来被 commit，仍保留 `commit_generation=None`，记录其
发布来源。

```text
add → writer RAM
          │ flush
          ▼
     immutable segment ── commit ──> atomic manifest ──> restart reader
          │ refresh
          ▼
     new in-process reader（旧 reader 不变）
```

### 所有权与废弃 generation

旧 reader 可能仍需要已被 merge 或新 manifest 淘汰的段。
`IndexReader.__init__` 在 `SegmentRegistry` 获取 generation 所有权，close 时
释放；writer 的私有集合变化时也替换所有权。`Index.collect_garbage` 委托
`src/minilucene/storage/registry.py` 的 `collect_garbage`：仅当段不在当前
manifest 且没有进程内 reader/writer 持有，才删除完整废弃段。这不是跨进程 lease。
writer lock 也没有 stale-lock recovery。

NRT 指无需每次 durable commit，就能 refresh 新 reader 使内容可搜索；它降低
可见性延迟，不代表同步 durability、复制、共识或硬实时。生产服务常用
SearcherManager、refresh policy 与并发安全的 reader 交接，本仓没有服务器或后台
refresh loop。

### 用时间线推理故障

writer 添加 A、flush、refresh，随后在 commit 前崩溃：进程活着时 refresh reader
能看见 A，重启后看不见，因为旧 manifest 仍是根。不能自动收养残留段，因为系统
不知道调用方是否打算发布那份 writer 状态。

若 commit 完成但旧 reader 继续服务，新 reader 看见 A、旧 reader 看不见，这是
search snapshot isolation，不是偶然缓存。应用决定何时退役旧 reader，其所有权
在此期间阻止回收。

| 状态 | writer/私有状态 | refresh reader | 新 manifest reader | 重启 |
|---|---:|---:|---:|---:|
| add 后 | 有 | 无 | 无 | 无 |
| flush 后 | 段 | 无 | 无 | 无 |
| refresh 后 | 段 | 有 | 无 | 无 |
| commit 后 | 段 | 已 refresh 才有 | 有 | 有 |

“重启无”指不属于恢复索引，即使 orphan 字节仍在；commit 也不会把变化推入已有
reader。明确观察者比只说“已保存”更可靠。

## 对照真实 Apache Lucene

Lucene 的 `IndexWriter` 同样 buffer/flush 不可变段，
`DirectoryReader.open(IndexWriter)` 与 `openIfChanged` 提供 NRT，
`SearcherManager` 和 controlled reopen thread 管理刷新，commit point 与更丰富
引用跟踪管理 durable 文件。

MiniLucene 只提供显式同步 refresh、单 writer lock、无后台线程、无
`SearcherManager`、commit user data、rollback 或自动 merge；所有权仅进程内，
崩溃还可能留下 stale `.writer.lock`。它立即从 BM25 统计排除删除文档，而 Lucene
段统计可能到 merge 才变化。详见[行为矩阵](../../behavior-matrix.md)、
[Lucene 映射](../../lucene-mapping.md)和
[NRT 说明](../../phase3-nrt-mutation.md)。

## 动手实验：观察三条边界

```bash
export UV_CACHE_DIR=/tmp/minilucene-uv-cache
uv run --offline python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from minilucene import Index, Schema, TextField
from minilucene.query import TermQuery
with TemporaryDirectory() as tmp:
    path = Path(tmp) / "index"
    index = Index.create(path, Schema(body=TextField(stored=True)))
    with index.writer() as writer:
        writer.add_document(body="alpha")
        segment = writer.flush()
        with index.open_reader() as committed:
            print("after flush", segment.generation,
                  committed.search(TermQuery("body", "alpha")).total_hits)
        fresh = writer.refresh()
        print("after refresh",
              fresh.search(TermQuery("body", "alpha")).total_hits,
              fresh.snapshot.commit_generation)
        writer.commit()
        with Index.open(path) as reopened, reopened.open_reader() as reader:
            print("after commit",
                  reader.search(TermQuery("body", "alpha")).total_hits,
                  reopened.manifest().commit_generation)
        fresh.close()
    index.close()
PY
```

实测输出：

```text
after flush 1 0
after refresh 1 None
after commit 1 1
```

generation 1 在 flush 后存在，但 manifest reader 为 0；refresh reader 命中但不
属于 commit generation；commit 后独立 reopen 命中。

```bash
uv run --offline pytest -q tests/contract/test_index_lifecycle.py \
  tests/nrt/test_refresh_visibility.py tests/nrt/test_reader_snapshot.py
```

实测：`14 passed in 0.80s`。

## 练习

1. **理解题：** 段文件已 fsync，为何 reopen 仍忽略？

    ??? note "参考答案"
        组件字节 durable 与索引根发布是两件事；reopen 只信原子 commit 的 manifest。

2. **理解题：** refresh 为什么返回新 reader？

    ??? note "参考答案"
        查询需要稳定段集合、mask 与统计；原地修改会破坏 point-in-time 一致性。

3. **动手题：** add 前打开 reader，再 refresh 并查询新旧对象。验收：旧为 0，
   新为 1，即使之后 commit 旧 reader 仍为 0。

    ??? note "参考答案"
        同时保留两个对象并分别 search，最后 close；无需改 `src/`。

4. **动手题：** 删除 `writer.commit()` 后在 writer 存活时 reopen。验收：
   refresh reader 为 1，manifest reader 为 0。

    ??? note "参考答案"
        这正是 NRT 可见但不 durable 的边界。

## 小结

flush 把 RAM 冻结成经校验的段文件，refresh 返回新的进程内 snapshot，commit
原子改变未来与重启 reader 的恢复根；旧 reader 始终稳定。第 6 章将在不可变 posting
之上，用 live-doc bitmap generation 实现删除与更新。
