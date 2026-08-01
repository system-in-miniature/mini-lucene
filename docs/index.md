# MiniLucene Tutorial / MiniLucene 教程

[Chinese edition / 中文版](zh/index.md)

MiniLucene is a compact Python reference implementation for learning how
lexical search connects schemas, analyzers, positional inverted indexes, BM25,
immutable segments, point-in-time readers, and near-real-time mutation. It is
an inspectable teaching system, not an Apache Lucene API or file-format clone.

MiniLucene 是一个紧凑的 Python 词法搜索参考实现，用来串联字段模式、分析器、
位置倒排索引、BM25、不可变段、时点读取器和近实时变更。它是可检查的教学系统，
不是 Apache Lucene API 或文件格式的兼容实现。

## Learning modes / 学习模式

### Mechanism Tutorial / 机制教程

Use the existing eleven chapters for concept-first study of analysis, indexing,
storage, NRT mutation, query language, scoring, merge, and DAAT. / 希望先建立
概念与运行时心智模型时，按现有十一章学习分析、索引、存储、NRT、查询、评分、合并与 DAAT。

### Self-Guided Rebuild / 自主重建

Use the [thirty-stage Journey](journey/index.md) to understand each problem,
test contract, concept boundary, and grouped code diff in a browser. / 使用
[三十阶段重建旅程](zh/journey/index.md)，在浏览器中理解每个问题、测试契约、概念边界
与按机制分组的代码差异。

### Agent-Guided Rebuild / Agent 带教

Use the [CLI guide](agent-guide.md) when you want Codex to interactively teach,
implement, and verify one Stage. / 希望由 Codex 互动讲解、实现并验收一个 Stage 时，
参照 [CLI 使用教程](zh/agent-guide.md)。

## Install / 安装

You need Python 3.12+ and [uv](https://docs.astral.sh/uv/).

需要 Python 3.12+ 和 [uv](https://docs.astral.sh/uv/)。

```bash
git clone https://github.com/system-in-miniature/mini-lucene.git
cd MiniLucene
uv sync --dev
```

## First experiment / 第一个实验

Run the CLI experiment from Chapter 4:

运行第 4 章的 CLI 实验：

```bash
uv run minilucene create demo-index --schema schema.json
uv run minilucene add demo-index doc-1.json doc-2.json
uv run minilucene search demo-index '"follower replicas"' \
  --default-field body --top-k 10 --highlight body
```

The result should contain one hit, document `1`, with
`<em>follower replicas</em>` highlighted. Chapter 4 supplies the complete JSON
fixtures and explains what to inspect.

结果应包含一个命中：文档 `1`，并将 `<em>follower replicas</em>` 标为高亮。
第 4 章给出完整 JSON 文件，并说明观察重点。

## Reading path / 阅读顺序

Read the retrieval, persistence, and NRT acceptance chapters as an architecture
tour; then use the mapping and behavior matrix to separate this miniature's
mechanisms from production Lucene behavior.

先把检索、持久化、NRT 三个验收章节当作架构导览，再通过映射与行为矩阵区分
这个微型实现和生产 Lucene 的语义边界。

For the complete feature scope, mental model, and public API example, see the
[English README](https://github.com/system-in-miniature/mini-lucene#readme).
The [design history archive](superpowers/README.md) records construction-time
plans; current docs and executable tests remain the source of truth.

完整功能范围、心智模型和公共 API 示例见
[中文 README](https://github.com/system-in-miniature/mini-lucene/blob/main/README.zh-CN.md)。
[设计历史存档](superpowers/README.md)记录建设期计划；现行文档与可执行测试
才是当前事实来源。
