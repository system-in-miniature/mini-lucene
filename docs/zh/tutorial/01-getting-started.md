# 第 1 章：认识 MiniLucene

MiniLucene 是一份可执行的词法检索机制说明书。它不是 Apache Lucene 的
Python 绑定，也不复制 Lucene 的公开 API 或磁盘格式；它保留的是理解搜索引擎
所需的主链：Schema 定义字段语义，分析器把文本变成带位置的 token，倒排索引把
term 映射到文档，BM25 给匹配项排序，不可变段承载持久化，manifest 定义可恢复
的索引根。

这种范围适合学习。直接阅读生产级 Lucene，会同时遇到数十年的兼容约束、
专用 codec、迭代器层次、并发与性能工程。MiniLucene 让我们先跟完一条完整路径，
再与真实系统对照。代价也必须说清：这里的成功只证明教学内核自身的契约，不证明
Lucene 兼容性或生产就绪。

## 学习目标

完成本章后，你能够：

1. 说明 MiniLucene 为什么是参考实现而不是 Lucene 克隆；
2. 用本地 CLI 根据 Schema 创建磁盘索引；
3. 写入 JSON 文档并执行字段查询与短语查询；
4. 划分分析、建索引、持久化和搜索的职责；
5. 区分 indexed、stored、tokenized 与 positional 四种字段性质。

## 机制讲解：从 JSON 到排序后的命中

磁盘索引的公开边界在 `src/minilucene/index/directory.py`。
`Index.create` 写入不可变 Schema 并创建初始 manifest；`Index.open` 同时读取
两者，并在返回索引前校验指纹。调用方并不是随便打开某个段目录，而是打开一个
经过校验的发布根。

Schema 不只是字段名列表。`src/minilucene/schema.py` 中的 `TextField`、
`KeywordField` 和 `StoredField` 构造不同的 `FieldType`：

```python
def TextField(*, stored: bool = False, boost: float = 1.0) -> FieldType:
    return FieldType(
        indexed=True, tokenized=True, stored=stored,
        store_positions=True, boost=boost, analyzer_name="standard",
    )
```

indexed 决定字段能否参与检索，stored 决定原值能否随命中返回，二者相互独立。
`TextField` 会被分析并保存位置；`KeywordField` 把完整字符串当作一个精确 term；
`StoredField` 可返回但不可搜索。`Schema.__init__` 对字段排序、规范序列化并计算
SHA-256 指纹。`Index.open` 用它拒绝不匹配的 Schema，而不是猜测旧字节的含义。

CLI 很薄。`src/minilucene/cli.py` 的 `_create` 调用 `Index.create`；`_add`
打开 `IndexWriter`，逐个调用 `IndexWriter.add_document` 后 commit；`_search`
打开 `IndexReader` 并调用 `IndexReader.search_text`。CLI 没有另一套搜索语义。

写路径继续进入 `src/minilucene/writer.py`。`IndexWriter.add_document` 先让
`RamIndexBuilder.prepare_document` 校验并分析文档，再放入 RAM buffer。
`src/minilucene/index/memory.py` 的 `prepare_document` 分离 stored 值与分析
结果；`add_prepared` 按 term 汇总位置，生成含局部文档 ID、词频和位置的 posting。
`IndexWriter.commit` flush buffer、重新校验所有段，再原子发布 manifest。

查询路径从字符串开始，但不会停留在字符串。`src/minilucene/reader.py` 的
`IndexReader.search_text` 委托给
`src/minilucene/search/searcher.py` 的 `IndexSearcher.search_text`。
lexer/parser 生成封闭的 Query AST，匹配和计分都面向 AST。CLI 输出把完整
`total_hits` 与有界命中列表分开，并给出 score、段代际、段内文档 ID、stored
字段和可选高亮。

```text
schema + JSON document
        │
        ▼
校验 → 分析 → RAM postings → 不可变段 → manifest
                                         │
query text → Query AST → 匹配 → BM25 → Top-K ◀─┘
```

每条箭头都是可检查、可测试的边界。CLI 背后没有隐藏服务器：MiniLucene 是
direct-first、local-only 的。

### 如何阅读后续章节

第 2–4 章沿写路径向下：token 属性与短语正确性、RAM postings 与 norms、严格
磁盘帧。第 5–7 章研究时间边界：NRT 可见性、删除代际、reader snapshot 与
manifest 崩溃原子发布。第 8–9 章回到读路径，讨论 BM25、Top-K 与查询语言；
第 10 章用显式 merge 收束，并给出通往真实 Lucene 的路线。

阅读时始终分开三个问题：逻辑事实是什么、谁此刻可见、证据是什么。posting 表示
某 term 出现在某段的局部文档字段中；writer buffer、refresh reader 与 manifest
reader 可以有意看到不同状态；源码函数解释机制，聚焦测试或复现实验才证明行为。
熟悉的类名或图本身都不是运行证据。

CLI 适合端到端实验，后文则常用 direct Python API，以便直接观察 snapshot、
posting 和 generation。两条入口共用同一实现。API 拼写与 Lucene 不同时，应比较
职责：谁拥有 Schema 校验、段发布、reader 生命周期和查询执行。

## 对照真实 Apache Lucene

真实 Lucene 用 `IndexWriter`、`IndexWriterConfig`、`Directory`、`Analyzer`、
`IndexSearcher`、`QueryParser`、`Document` 和字段类型表达相近职责，但 codec、
段元数据、查询执行、合并调度与兼容承诺复杂得多。

MiniLucene 的 JSON CLI 只是本地适配器；Schema 在建库时冻结；文件格式仅供教学；
没有 TCP/HTTP 服务，也没有数值字段、doc values、范围查询、分面、向量检索、
自动 merge 调度或 Lucene 的 DAAT 迭代器栈。请查阅仓内
[MiniLucene → Lucene 映射](../../lucene-mapping.md)与
[可执行行为矩阵](../../behavior-matrix.md)。这些是明确的边界，不是项目名暗示
已经支持的能力。

## 动手实验：建立第一个索引

在仓库根目录执行：

```bash
export UV_CACHE_DIR=/tmp/minilucene-uv-cache
LAB=$(mktemp -d /tmp/minilucene-tutorial-ch1.XXXXXX)
printf '%s\n' '{"fields":{"id":{"indexed":true,"tokenized":false,"stored":true,"store_positions":false,"boost":1.0,"analyzer_name":"keyword"},"title":{"indexed":true,"tokenized":true,"stored":true,"store_positions":true,"boost":2.0,"analyzer_name":"standard"},"body":{"indexed":true,"tokenized":true,"stored":true,"store_positions":true,"boost":1.0,"analyzer_name":"standard"}}}' > "$LAB/schema.json"
printf '%s\n' '{"id":"doc-1","title":"Search systems","body":"An inverted index makes search fast"}' > "$LAB/doc1.json"
printf '%s\n' '{"id":"doc-2","title":"Storage systems","body":"A commit publishes durable state"}' > "$LAB/doc2.json"
uv run --offline minilucene create "$LAB/index" --schema "$LAB/schema.json"
uv run --offline minilucene add "$LAB/index" "$LAB/doc1.json" "$LAB/doc2.json"
uv run --offline minilucene search "$LAB/index" \
  'title:search OR body:"durable state"' --default-field body --top-k 10
```

实测输出（首行路径的随机后缀以你的实际值为准）：

```text
{"index":"/tmp/minilucene-tutorial-ch1.<suffix>/index","status":"created"}
{"added":2,"commit_generation":1}
{"hits":[{"highlights":{},"local_doc_id":1,"score":1.4398422119785987,"segment_generation":1,"stored_fields":{"body":"A commit publishes durable state","id":"doc-2","title":"Storage systems"}},{"highlights":{},"local_doc_id":0,"score":1.3862943611198906,"segment_generation":1,"stored_fields":{"body":"An inverted index makes search fast","id":"doc-1","title":"Search systems"}}],"total_hits":2}
```

两个文档分别命中 OR 的不同分支。title boost 与短语贡献让第二个文档略高。分数
对这份语料与当前实现是确定的，但不是跨引擎兼容承诺。本章没有 TCP 实验：
MiniLucene 根本不暴露 socket 服务，因此既不伪称已测，也没有待运行时验证项。

## 练习

1. **理解题：** 为什么 `stored=True` 不足以让字段可搜索？

    ??? note "参考答案"
        stored 只控制原值能否返回；indexed 独立控制能否检索，tokenized 与位置
        又决定可用的查询类型。

2. **理解题：** 新段目录和 `manifest.json`，哪个是重启恢复根？

    ??? note "参考答案"
        `manifest.json`。flush 但未被 manifest 命名的段，reopen 不可见。

3. **动手题：** 增加第三个 body 含 `durable state` 的文档并重跑查询。验收：
   add 输出 `added:1`、commit generation 为 2、`total_hits` 为 3。

    ??? note "参考答案"
        在 `$LAB` 新建 JSON，执行同一 add/search 命令。排序取决于新文档长度和
        命中字段，但三个验收计数必须成立；无需修改 `src/`。

4. **动手题：** 仅把新 Schema 中 id 的 stored 改为 false，建新索引。验收：
   `id:doc-1` 仍可命中，但 `stored_fields` 不含 id。

    ??? note "参考答案"
        keyword 字段仍 indexed，所以可搜索；关闭 stored 只影响结果呈现。

## 小结

MiniLucene 把 Schema 和文档变成经校验、已 commit 的搜索 snapshot，再把查询文本
变成排序命中。它的价值在于机制链清晰，不在于名称兼容。下一章聚焦第一步转换：
文本如何成为 term、position 和 offset，同时不破坏短语语义。
