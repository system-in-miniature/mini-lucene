# 提交原子性

## 学习目标

完成本章后，你将能够：

1. 认出 `manifest.json` 是 MiniLucene 唯一的重启可见提交根；
2. 解释“写临时文件、fsync 文件、rename、fsync 目录”的发布顺序；
3. 把 manifest 替换失败前创建的段和 live-doc 文件归类为不可见孤儿；
4. 推演仓库中的提交故障矩阵；以及
5. 对照 MiniLucene 提交协议与 Apache Lucene 的 `segments_N` 和两阶段提交能力。

## 1. 文件持久化不等于已经提交

MiniLucene 的磁盘上可以存在许多完整文件，但它们不一定属于可恢复索引。重启后的权威问题不是“有哪些段目录”，而是“`manifest.json` 引用了哪些代际”。

`src/minilucene/storage/manifest.py` 的 `Manifest` 记录 schema 指纹、提交代际、有序 `SegmentCommit` 条目和下一代计数器。每个
`SegmentCommit` 引用一个段代际；存在删除时，还会引用 live-doc 代际和校验和。因此 manifest 描述一个完整时间点图：

```text
manifest.json
  ├── seg_000003/segment.json → 数据文件与校验和
  │    └── live_000002.bin → manifest 引用的删除掩码
  └── seg_000006/segment.json → 数据文件与校验和
```

`src/minilucene/index/directory.py` 的 `Index.open()` 要求 manifest 存在，加载持久化 schema，检查其指纹与 manifest 一致，并且不会扫描段目录来杜撰更新状态。`Index.open_reader()` 随后只打开 manifest 中按顺序记录的段引用及其指定的 live-doc 代际。

顺序也是快照的一部分。它决定全局文档 ID 转换和确定性的同分排序。恢复流程不能把目录排序后悄悄替换 manifest 顺序。

## 2. Commit 先准备子节点，再发布根

协调者是 `src/minilucene/writer.py` 的 `IndexWriter.commit()`。它先调用
`flush()`，把缓冲区中的存活文档变成不可变段。随后通过
`SegmentStore.open()` 重新打开 writer 持有的每个段。在新根引用字节之前，这一步会验证 schema 指纹、元数据、长度和 SHA-256 校验和。

对于 dirty 删除掩码，`commit()` 分配新的 live-doc 代际，并调用
`src/minilucene/storage/live_docs.py` 的 `LiveDocsStore.publish()`。它绝不覆盖旧 reader 或旧 commit 引用的掩码。若段中所有文档都存活，则
`SegmentCommit` 不包含 live-doc 引用。

只有所有段和掩码子节点都持久化后，`IndexWriter.commit()` 才构造
`Manifest.next_from()` 并调用 `ManifestStore.write_atomic()`。manifest 替换必须最后执行，因为它把先前不可达的文件变成可恢复索引。

这是一种重要的原子性：根被原子切换，而子文件提前以不可变形式准备好。它并不是一个巨型文件系统事务。

## 3. 为什么 fsync 出现两次

`src/minilucene/storage/manifest.py` 的
`ManifestStore.write_atomic()` 序列化规范、紧凑的 JSON，然后执行：

```text
写 manifest.tmp
fsync manifest.tmp
replace manifest.tmp → manifest.json
fsync 索引目录
```

第一次 fsync 要求操作系统在临时文件成为权威文件前，先持久化其内容。
`src/minilucene/storage/filesystem.py` 的 `FileSystemOps.replace()` 使用
`os.replace()`；在预期的同一文件系统设置下，它对应原子 rename。打开目标文件的 reader 会看到旧的完整名字或新的完整名字，而不是半份 JSON。

目录 fsync 的职责不同：它持久化目录项替换本身。只同步文件内容并不能在每种受支持文件系统上证明新名字绑定能经受掉电。

MiniLucene 在发布持久化 schema、段目录和 live-doc 文件时采用同一模式。实际保证仍取决于操作系统、文件系统和存储设备是否正确兑现这些调用。原子 rename 还要求源和目标位于同一文件系统；临时路径与目标同目录正是为了满足这一点。

## 4. 要么旧根，要么新根，不合成中间状态

假设提交代际 4 引用段 `(1, 3)`。writer 发布段 5，并尝试发布引用
`(1, 3, 5)` 的提交代际 5。

- 写段 5 时失败：不会尝试新 manifest；代际 4 仍是权威状态。
- 段 5 最终 rename 后、manifest 替换前失败：段 5 是完整孤儿；代际 4 仍是权威状态。
- 替换 `manifest.json` 时失败：在预期的原子 rename 模型下，旧完整 manifest 仍是权威状态。
- 一直成功到目录 fsync：代际 5 成为新的可恢复根。

代码不会在 `Index.open()` 时发现孤儿并“补完”失败的提交。那等于猜测 writer 的意图，可能发布缺少预期删除状态或顺序错误的段。

`src/minilucene/storage/manifest.py` 的 `ManifestStore.read()` 很严格：它拒绝无效 UTF-8/JSON、未知或多余字段、未知格式版本、不一致的代际计数器、重复段和不完整 live-doc 元数据。被引用段若损坏，
`SegmentStore.open()` 会 fail closed，而不是跳过它。

提交代际是单调身份，不是所有更早尝试都成功的证明。`Manifest.next_from()` 从当前可读 manifest 推进，而段分配可能跳过已被孤儿占据的代际。因此，代际空洞是正常诊断证据，不是扫描并挂接缺失目录的理由。唯一安全的关系是经过验证的根明确记录的关系。

同一规则也适用于残留 `manifest.tmp`：恢复读取 `manifest.json`，而不是时间戳看起来最新的 JSON。临时文件可能包含不完整字节、完整但未发布的根，或失败尝试的数据；修改时间无法区分它们。后续 commit 复用固定临时路径是安全的，因为它从不是恢复根；下一次协议会先覆盖并同步它，再尝试 rename。

## 5. 孤儿回收必须尊重所有权

孤儿不可见，但立即删除不一定安全。进程内 NRT reader 可能仍持有未提交段；旧 reader 也可能持有被新提交 merge 移除的段。

`src/minilucene/storage/registry.py` 的
`SegmentRegistry.collect_garbage()` 根据以下并集计算受保护代际：

```text
当前 manifest 代际
并集 每个 reader owner 的代际
并集 writer owner 的代际
```

它只删除集合外、可识别且完整的 `seg_NNNNNN` 目录。未知或畸形路径会保留以供诊断。该 registry 只保护当前进程中的 owner；它不是跨进程引用计数。这个限制记录在
[MiniLucene 到 Lucene 映射](../lucene-mapping.md)中。

代际分配也会避开完整孤儿：`IndexWriter.flush()`、`commit()` 和
`merge()` 会持续递增，直到目标代际不存在。因此，失败发布不会导致后续 writer 覆盖诊断证据。

## 6. 与 Apache Lucene 对照

概念上的对应关系是 `manifest.json` 对 Lucene 最新的 `segments_N` 提交点（由 `SegmentInfos` 表示）。两者都通过一个原子发布的小根，引用属于一致提交的文件；提前准备的不可变文件可以存在，却不属于该提交。

MiniLucene 有意省略重要生产机制：

- manifest 是自定义 JSON，不兼容 Lucene codec。
- `IndexWriter` 没有 `prepareCommit()`、`rollback()`，也没有协调多个资源的两阶段提交协议。
- 没有可配置 `IndexDeletionPolicy`、保留提交历史或 snapshot deletion policy；MiniLucene 只暴露一个当前根。
- writer lock 可能因进程崩溃残留；没有安全 stale-lock 验证或 force-unlock API。
- registry 位于进程内，无法保护另一个进程中的 reader。

行为矩阵的[原子提交](../behavior-matrix.md)、完整孤儿恢复、校验和损坏和段所有权条目，把这些声明绑定到可执行测试。映射文档中的 manifest、writer、registry 和 lock 行则说明与真实 Lucene 的类比在哪里结束。

## 7. 动手实验：根替换失败

下面的实验在 manifest rename 边界注入故障。它使用测试风格的文件系统子类，但不修改仓库代码。

```bash
UV_CACHE_DIR=/tmp/minilucene-uv-cache uv run python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory

from minilucene import Index, KeywordField, Schema, TextField
from minilucene.query import TermQuery
from minilucene.storage.filesystem import FileSystemOps
from minilucene.storage.manifest import ManifestStore


class FailManifestReplace(FileSystemOps):
    def replace(self, source: Path, destination: Path) -> None:
        if destination.name == "manifest.json":
            raise OSError("injected manifest replace failure")
        super().replace(source, destination)


schema = Schema(
    id=KeywordField(stored=True),
    body=TextField(stored=True),
)

with TemporaryDirectory() as directory:
    path = Path(directory)
    index = Index.create(path, schema)
    with index.writer() as writer:
        writer.add_document(id="1", body="committed")
        writer.commit()

    try:
        with index.writer() as writer:
            writer.add_document(id="2", body="orphan")
            writer._manifest_store = ManifestStore(
                path, fs=FailManifestReplace()
            )
            writer.commit()
    except OSError as error:
        print(error)

    reopened = Index.open(path)
    reader = reopened.open_reader()
    print(f"commit_generation={reopened.manifest().commit_generation}")
    print(
        "committed_hits="
        f"{reader.search(TermQuery('body', 'committed')).total_hits}"
    )
    print(
        "orphan_hits="
        f"{reader.search(TermQuery('body', 'orphan')).total_hits}"
    )
    segment_names = sorted(
        item.name for item in (path / "segments").iterdir()
    )
    print(f"segment_directories={segment_names}")
    reader.close()
    reopened.close()
    index.close()
PY
```

实测输出：

```text
injected manifest replace failure
commit_generation=1
committed_hits=1
orphan_hits=0
segment_directories=['seg_000001', 'seg_000002']
```

第二个段足够完整，所以留在磁盘上；但恢复仍跟随提交代际 1。存在不等于发布。

## 8. 练习

### 练习 1——理解题

为什么必须在 manifest 替换前同步段文件和 live-doc 文件？

??? note "参考答案"

    manifest 会让这些子节点在恢复时变得可达。先发布根可能留下一个持久 manifest，却引用缺失或不完整的子字节。先准备不可变子节点，可以把根发布前的崩溃变成无害的不可达孤儿。

### 练习 2——故障分类

对重启后的以下状态分类：(a) 临时段目录；(b) 完整但未引用的段；(c) manifest 引用但校验和错误的段。

??? note "参考答案"

    (a) 与 (b) 都不属于恢复后的 reader；完整未引用目录是孤儿。
    (c) 不会被静默忽略：权威根已经引用损坏数据，所以
    `SegmentStore.open()` 会 fail closed。

### 练习 3——动手题

不要编辑 `src/`。把 `src/minilucene/storage/manifest.py` 复制到临时目录，在 `write_atomic()` 中为四个可注入崩溃点添加注释，并写表格预测每个点之后的权威根。

验收方式：表格必须覆盖临时文件 fsync 前、临时文件 fsync 后、rename 后和目录 fsync 后；必须区分原子可见性声明与持久性声明。

??? note "参考答案"

    rename 前仍由旧根占据目标名字。rename 后、目录 fsync 前，进程通常能观察到新的完整文件，但名字的崩溃持久性尚未建立。目录 fsync 后，新根才是预期的持久结果。实际掉电后行为依赖文件系统保证，因此表格不应声称超出协议建立的性质。

## 小结

MiniLucene 先准备不可变子节点，再原子替换一个小 manifest 根来完成提交。文件 fsync 保护内容，rename 切换可见性，目录 fsync 保护名字变化。恢复不会靠猜测提升孤儿，垃圾回收还必须尊重所有存活 owner。持久快照建立后，下一章将跟随查询进入 BM25 打分与有界 Top-K 堆。
