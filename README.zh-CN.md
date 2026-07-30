> **语言**: [English](README.md) | 简体中文

# MiniLucene

[![CI](https://github.com/system-in-miniature/mini-lucene/actions/workflows/ci.yml/badge.svg)](https://github.com/system-in-miniature/mini-lucene/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) ![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)

MiniLucene 是一个直接呈现机制的 Python 参考实现，用于说明词法搜索
（lexical search）的工作原理。它在一个小型系统中串联了字段模式
（field schema）、文本分析（analysis）、位置倒排索引（positional inverted
index）、BM25、有界 Top-K 收集、不可变磁盘段、时点读取器
（point-in-time reader）、近实时刷新（near-real-time refresh）、删除、更新与合并。

本项目有意不做 Apache Lucene 的克隆。它不承诺兼容 Lucene API 或文件格式，
也不提供生产级性能、网络服务、分布式协调或向量检索。

## 快速开始

```python
from pathlib import Path

from minilucene import Index, KeywordField, Schema, TextField

schema = Schema(
    id=KeywordField(stored=True),
    title=TextField(stored=True, boost=2.0),
    body=TextField(stored=True),
)

index = Index.create(Path("./example-index"), schema)
with index.writer() as writer:
    writer.add_document(
        id="doc-1",
        title="Understanding Kafka Replication",
        body="Kafka uses partition leaders and follower replicas.",
    )
    writer.commit()

with index.open_reader() as reader:
    results = reader.search_text(
        'title:kafka OR body:"follower replicas"',
        default_field="body",
        top_k=10,
        highlight_fields=("title", "body"),
    )
    for hit in results.hits:
        print(hit.score, dict(hit.stored_fields), dict(hit.highlights))

index.close()
```

同一组公共边界也通过一个轻量的本地命令行界面（CLI）提供：

```text
minilucene create INDEX --schema SCHEMA_JSON
minilucene add INDEX DOCUMENT_JSON...
minilucene search INDEX QUERY --default-field body --top-k 10
minilucene delete INDEX FIELD TERM
minilucene merge INDEX SEGMENT...
```

## 心智模型

```text
Document + Schema
        ↓
field Analyzer → tokens + positions + offsets
        ↓
RAM inverted index
        ↓ flush
immutable Segment
        ↓ refresh
new point-in-time Reader
        ↓ commit
atomically published restart root

query text → lexer → parser → Query AST → prefix rewrite
                                          ↓
                          matching → global BM25
                                          ↓
                         stored fields + highlighting
                           for every matching document
                                          ↓
                                      Top-K heap
```

`TextField` 会被分词并保留位置信息。`KeywordField` 将完整值作为一个精确词项
（exact term）建立索引。`StoredField` 会随命中结果返回，但不可搜索。存储
（stored）与索引（indexed）是相互独立的属性。

标准分析器（standard analyzer）将词元转换为小写，并保留源文本偏移量与位置间隔。
因此，短语查询能够区分相邻词项和原文中被其他位置分隔的词项。高亮会重新分析已存储的
`TextField` 值、使用这些偏移量，并对全部原始文本进行 HTML 转义。

BM25 统计量对单个读取器快照（reader snapshot）全局计算，且只包含存活文档。
Top-K 收集器只保留 K 个命中对象，同时仍报告完整命中总数。这只是内存占用边界，
并不代表搜索管线是 O(K)：当前搜索器会在收集之前为每一个匹配项读取存储字段并计算高亮。

## Flush、refresh 与 commit

- `flush` 将写入器的 RAM 缓冲区转化为一个不可变段。它此时还不是持久化索引根。
- `refresh` 返回一个能看到写入器已 flush 状态的新读取器。旧读取器保持不变。
- `commit` 原子替换清单（manifest）。进程退出后重新打开时，只能看到这个已提交的根。

段（segment）是不可变的。删除操作会发布存活文档掩码（live-document mask）。
更新操作先验证替换文档，再删除所有精确词项匹配，最后添加一个替换文档。
合并操作显式合并所选段、跳过已删除文档、重新映射局部文档 ID，并原子更新写入器的段集合。
系统不会自动调度合并。

读取器和写入器会登记段所有权。只有当一个完整的过期段不在已提交清单中，
并且所有进程内所有者都已释放它时，垃圾回收才会将其删除。

## 范围

V1 支持：

- 带字段的 Unicode 文档与存储字段检索；
- 标准分析和关键词分析；
- 词项、布尔、短语、前缀和匹配全部查询；
- 全局 BM25、字段提升（field boost）和确定性的有界 Top-K；
- 带校验和的确定性教学段文件；
- 原子提交、重启恢复、NRT 刷新、删除、更新与合并；
- 查询解析、安全高亮、相关性指标、夹具（fixtures）与本地 CLI。

V1 明确排除：

- TCP、HTTP、RESP 或远程客户端兼容性；
- 复制、心跳、选举、集群与分片；
- Apache Lucene 编解码器、FST/BlockTree、WAND、SIMD 或生产调优；
- 文档一次迭代器（doc-at-a-time iterator，包括 `PostingsEnum`、合取/析取
  评分器和两阶段迭代）；匹配与评分会物化完整集合或映射；
- 数值/日期字段、文档值（doc values）、范围查询、字段排序、聚合与分面；
- 向量字段、HNSW、混合检索与自动合并调度；
- 课程章节或教学内容。

## 与 Apache Lucene 的重要差异

有些边界不仅仅是缺少优化：

- **有意简化（Intentionally simplified）：** 搜索采用完整集合代数，而不是
  文档一次迭代。`PostingsEnum`、`ConjunctionScorer` 以及相关的游标/跳跃机制均不存在。
- **语义相反（Semantics reversed）：** 在 Top-K 收集之前，会为每个匹配项生成
  存储字段和高亮。Lucene 通常先收集文档 ID/分数，再只提取胜出命中的内容。
- **语义相反（Semantics reversed）：** 短语匹配的得分是其各词项 BM25 分数之和，
  而不是由短语频率计算。
- **语义相反（Semantics reversed）：** BM25 统计量会立即排除已删除文档。
  Lucene 的段统计量在合并前仍包含这些文档，因此 MiniLucene 无法演示生产环境中
  合并可能改变分数的现象。
- **语义相反（Semantics reversed）：** 提升值固定在模式中。Lucene 7.0 移除了
  索引时字段提升，只保留查询时提升，因此两者支持的方向相反。
- **有意简化（Intentionally simplified）：** 不存在数值字段、文档值或范围查询。
- **有意简化（Intentionally simplified）：** 崩溃的进程可能永久遗留
  `.writer.lock`；不存在陈旧锁恢复或强制解锁 API。
- **有意简化（Intentionally simplified）：** 高亮会重新分析已存储文本，
  因此无法高亮已索引但未存储的字段。

请参阅 [MiniLucene → Apache Lucene 映射](docs/zh/lucene-mapping.md)，其中提供了
逐模块的 **等价（Equivalent）/ 有意简化（Intentionally simplified）/
语义相反（Semantics reversed）** 对照表。

课程将在本参考项目通过验收后另行设计。

## 开发

```bash
uv sync --dev
uv run ruff check src tests tools
uv run pytest -q
uv run python -m compileall -q src tests tools
git diff --check
```

架构与证据：

- [冻结设计](docs/superpowers/specs/2026-07-27-minilucene-reference-project-design.md)
- [实现计划](docs/superpowers/plans/2026-07-27-minilucene-reference-project.md)
- [段格式](docs/zh/segment-format.md)
- [MiniLucene → Apache Lucene 映射](docs/zh/lucene-mapping.md)
- [阶段 1：检索内核](docs/phase1-retrieval-kernel.md)
- [阶段 2：存储与提交](docs/phase2-storage-commit.md)
- [阶段 3：NRT 变更与合并](docs/phase3-nrt-mutation.md)
- [可执行行为矩阵](docs/behavior-matrix.md)

## 商标声明

MiniLucene 是独立的教学项目，与 the Apache Software Foundation 无隶属、背书或赞助关系。"Apache Lucene" 商标归其所有者所有。
