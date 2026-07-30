# 删除与更新

## 学习目标

完成本章后，你将能够：

1. 解释为什么删除文档只改变 live-docs 掩码，而不重写 postings；
2. 从 `IndexWriter._derive_delete()` 追踪精确词项删除，直到提交时产生新的 live-docs 代际；
3. 解释为什么 `update_document()` 的含义是“先验证、删除所有匹配项、再添加一个替代文档”；
4. 演示旧 reader 保持时间点视图，而新 reader 能看到变更；以及
5. 区分 MiniLucene 的仅活文档统计与 Apache Lucene 合并前的统计。

## 1. 不可变段让删除成为覆盖层

`IndexWriter.flush()` 写出的段不可变。若重新打开并修改
`postings.bin`，就会破坏这条规则带来的简洁故障模型：一个段要么是完整且校验和正确的镜像，要么不可使用。因此，MiniLucene 把删除表示成第二个带版本的对象：仍然存活的段内文档 ID 集合。

`src/minilucene/storage/live_docs.py` 的 `LiveDocsCodec.encode()` 把该集合压成位图。段内文档 `d` 位于第 `d // 8` 个字节的 `d % 8` 位。
`LiveDocsCodec.decode()` 会检查记录的 `max_doc`、精确字节长度以及未使用的高位，然后才返回不可变 `frozenset`。这些检查很重要：为另一种段大小创建的掩码不能悄悄隐藏或暴露文档。

writer 在 `src/minilucene/writer.py` 的 `IndexWriter.__init__()` 中为每个段保存一份掩码。没有 live-doc 文件的段从
`frozenset(range(image.max_doc))` 开始，即每个段内文档都存活。之后掩码少掉某个 ID 时，postings、stored fields 和 norms 都保持不变。

因此必须区分两种身份：

```text
段代际 7             不可变 postings/stored fields/norms
live-doc 代际 3      段 7 的第三份已提交可见性掩码
```

`src/minilucene/storage/live_docs.py` 的 `LiveDocsStore.publish()` 把每份新掩码写到段目录中，计算 SHA-256 校验和，fsync 临时文件，rename 后再 fsync 目录。manifest 最终同时记录两个代际和校验和。已经持久化但没有被 manifest 引用的掩码文件，重启后与孤儿段一样不可见。

## 2. 精确词项删除：先推导，再交换

公开变更入口是 `src/minilucene/writer.py` 的
`IndexWriter.delete_by_term(field, term)`，关键工作由
`IndexWriter._derive_delete()` 完成。

首先，`_derive_delete()` 拒绝未知字段、未索引字段和空删除词项。随后它复制当前的逐段掩码字典。对于 writer 持有的每个段，它打开经过验证的段镜像，找出精确字段和精确词项的 postings，把这些段内 ID 与当前存活集合求交，并推导出更小的集合。它还会单独寻找 RAM buffer 中的匹配文档。

只有全部推导成功后，`delete_by_term()` 才替换
`self._live_docs`，把发生变化的段代际标成 dirty，并替换 buffer 的存活集合。因此，如果较后的某个段打开失败，删除不会只应用一半。返回值是“本次新删除的存活文档数”，所以重复执行同一个删除会返回零。

匹配的是索引分析后的精确词项。对于 `KeywordField`，删除
`id="doc-1"` 很自然。对于标准分析的 `TextField`，调用者必须提供已进入索引的词项，例如小写 `kafka`；这个 API 不解析查询字符串，也不会替你分析删除词项。

这种粒度也解释了“删除全部匹配项”。Postings 把一个词项映射到包含它的所有文档，writer 无法推断 ID 字段本应唯一；这里没有隐藏主键表。如果应用需要唯一性，就必须自行验证该不变量，或者接受一次更新可能淘汰多个文档。反过来，`delete_by_term()` 无法表达 Boolean、phrase 或 prefix 删除；这些功能需要另行定义查询匹配快照，而不能把字符串约定偷塞进精确词项 API。

搜索在 `src/minilucene/search/reader.py` 的 `ReaderView.postings()` 中排除已删除文档：只有段内 ID 出现在快照掩码里的 postings 才会被转换。
`ReaderView._build_corpus_stats()` 同样只统计存活 ID。因此，对新打开的 reader 来说，删除会立刻改变命中集合、文档频率、平均长度和 BM25 输入。

## 3. 更新就是删除全部匹配项，再添加一个已验证文档

MiniLucene 没有原地更新。`src/minilucene/writer.py` 的
`IndexWriter.update_document()` 实现倒排索引常见模型：

```text
验证并分析替代文档
        ↓
推导所有精确词项匹配项的删除
        ↓
构造下一份 RAM buffer，并追加一个替代文档
        ↓
一起交换所有 writer 变更状态
```

这里最值得学习的是顺序。首先运行
`self._buffer.prepare_document(replacement)`。若替代文档违反 schema，任何旧文档都不会被删除。随后 `_derive_delete()` 计算掩码，但不发布它们。新的
`RamIndexBuilder` 复制缓冲文档并加入已准备好的替代文档。直到此时，writer 才交换掩码、dirty 代际、buffer 和 buffer 的存活 ID。

`update_document()` 返回的整数是旧存活匹配项数量，不是替代文档 ID。如果三个文档共享一个本应唯一的 keyword，三者都会被删除，然后只添加一个替代文档。唯一性是应用层不变量，不是 MiniLucene 的 schema 功能。

该操作只对 writer 进程内状态具有原子性。它不会自动发布 reader，也不会自动成为重启可恢复状态。调用 `refresh()` 获得新的 NRT reader，或调用
`commit()` 发布新的可恢复根。

## 4. 时间点 reader 不会吸收后续变更

`src/minilucene/writer.py` 的 `IndexWriter.refresh()` 先 flush 当前 buffer，捕获不可变段镜像和 live 掩码组成的有序 tuple，然后构造
`IndexReader`。已提交 reader 则由
`src/minilucene/index/directory.py` 的 `Index.open_reader()` 根据 manifest 构造。

`src/minilucene/reader.py` 的 `IndexReader.__init__()` 把这些值包装进
`src/minilucene/snapshot.py` 定义的冻结 `ReaderSnapshot`，并取得所引用段代际的所有权。后续删除会替换 writer 掩码，而不会修改 reader 已持有的
`frozenset`。后续提交会替换 `manifest.json`，而不会编辑 reader 快照。

可观察时间线如下：

```text
reader A 打开 ───── 看到旧文档 ───── 仍看到旧文档 ── close
                         delete + commit
之后 reader B 打开 ───────────────── 看不到旧文档
```

这是时间点隔离，不是事务回滚。reader A 是有意保持的旧视图。
`IndexReader.close()` 只释放自身的 registry owner，且可重复调用。只有当旧段目录不在 manifest 中、不被 writer 持有、也不被任何 reader 持有时，才可回收；参见 `src/minilucene/storage/registry.py` 的
`SegmentRegistry.collect_garbage()`。

调试“删除没有生效”时，应先识别观察边界，再检查字节。要问：哪个 reader 执行搜索、它是否早于变更创建、writer 是否 refresh 或 commit，以及删除词项是否为精确索引词项。只查看旧 postings 会误导，因为它们本就应继续存在；只查看某个 live-doc 文件也不够，因为 manifest 未必引用该代际。正确证据是一份具体 reader 快照及其有序段与掩码 tuple。

## 5. 与 Apache Lucene 对照

可迁移的核心思想很强：Apache Lucene 同样保持段数据不可变，并通过逐段 live-doc 位记录删除。MiniLucene 的 `live_*.bin` 在概念上对应 Lucene 的
`LiveDocsFormat`、`.liv` 文件和 `Bits` 视图。Lucene 的按词项更新同样会删除匹配文档并添加新文档，而不是编辑旧 posting。

同时必须明确简化与差异：

- MiniLucene 通过一个 Python writer 和一个 RAM buffer 串行化变更；Lucene 有并发索引、缓冲删除包、序列号和更丰富的更新 API。
- MiniLucene 为每个 reader 急切物化段镜像与掩码；Lucene 使用 leaf reader、共享段 core、缓存和 reopen 逻辑。
- MiniLucene 的语料统计立刻排除已删除文档。Lucene 的逐段词项统计通常在 merge 前仍包含删除文档，因此真实 Lucene 的 merge 可能在存活内容不变时改变分数。
- MiniLucene 只有字符串字段，没有 doc values、数值 point 更新、soft deletes 或 update-by-query。

这些边界记录在仓库的
[MiniLucene 到 Lucene 映射](../lucene-mapping.md)中 live docs、reader、仅活文档统计和 writer 简化的对应行。
[精确词项删除](../behavior-matrix.md)、原子更新、reader 快照和段所有权的可执行声明，则在行为矩阵中绑定到具体 pytest 节点。

## 6. 动手实验：两个 reader，两个时间点

在仓库根目录运行。实验只使用临时目录和公开 Python API。

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
        writer.add_document(id="doc-1", body="old searchable text")
        writer.commit()

    old_reader = index.open_reader()
    with index.writer() as writer:
        deleted = writer.update_document(
            field="id",
            term="doc-1",
            id="doc-1",
            body="new searchable text",
        )
        writer.commit()

    new_reader = index.open_reader()
    old_old = old_reader.search(TermQuery("body", "old")).total_hits
    old_new = old_reader.search(TermQuery("body", "new")).total_hits
    new_old = new_reader.search(TermQuery("body", "old")).total_hits
    new_new = new_reader.search(TermQuery("body", "new")).total_hits
    repeated = 0
    with index.writer() as writer:
        repeated = writer.delete_by_term("id", "missing")

    print(f"updated_old_documents={deleted}")
    print(f"old_reader old={old_old} new={old_new}")
    print(f"new_reader old={new_old} new={new_new}")
    print(f"delete_missing={repeated}")
    old_reader.close()
    new_reader.close()
    index.close()
PY
```

实测输出：

```text
updated_old_documents=1
old_reader old=1 new=0
new_reader old=0 new=1
delete_missing=0
```

两个 reader 的结果不同是设计目标。旧 reader 持有原来的段和全存活掩码；新 reader 跟随新的 manifest 与掩码代际。

## 7. 练习

### 练习 1——理解题

为什么第一次成功删除后，再次执行
`delete_by_term("id", "doc-1")` 会返回零，即使旧 postings 中仍有
`doc-1`？

??? note "参考答案"

    `_derive_delete()` 会把 posting 匹配项与“当前存活集合”求交。
    posting 保持不可变，但相应段内文档 ID 已不再存活，所以不会再次计数或删除。

### 练习 2——理解题

某个无效替代文档遗漏必需字段。匹配的旧文档是否应当消失？

??? note "参考答案"

    不应当。`IndexWriter.update_document()` 在推导或交换删除状态之前调用
    `RamIndexBuilder.prepare_document()`。因此验证失败会保持掩码和 RAM
    buffer 不变。

### 练习 3——动手题

不要修改 `src/`。把 `src/minilucene/writer.py` 复制到临时目录，草拟一个
`delete_by_query(query)` 方法。明确标出在哪里推导完整匹配集合、在哪里交换 writer 状态。不要在 writer 内实现查询解析。

验收方式：临时 diff 必须保证在第一次给 `_live_docs`、
`_dirty_live_docs` 或 `_buffer_live_docs` 赋值之前完成验证与推导，并解释如何同时覆盖 buffer 与已 flush 文档。

??? note "参考答案"

    合理草图接收封闭的 `Query` 对象，为已 flush 段构造临时
    `ReaderView`，并单独匹配 RAM buffer，推导全部下一份掩码后才交换三个
    writer 字段。查询字符串解析仍属于 `query_parser`；匹配任何段失败都必须保持 writer 不变。

## 小结

MiniLucene 通过把删除可见性放进带版本的 live-doc 掩码，保持段不可变。删除先推导完整下一状态再交换；更新先验证，再完成“删全部、加一个”；reader 持有冻结掩码，因此保持时间点视图。下一章将研究这些段与掩码代际如何合成一个崩溃安全的持久化真相。
