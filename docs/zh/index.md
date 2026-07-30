# MiniLucene 教程

[English](../index.md)

MiniLucene 是一个紧凑的 Python 词法搜索参考实现，用来串联字段模式、分析器、
位置倒排索引、BM25、不可变段、时点读取器和近实时变更。它是可检查的教学系统，
不是 Apache Lucene API 或文件格式的兼容实现。

## 安装

需要 Python 3.12+ 和 [uv](https://docs.astral.sh/uv/)。

```bash
git clone https://github.com/system-in-miniature/MiniLucene.git
cd MiniLucene
uv sync --dev
```

## 第一个实验

运行第 4 章的 CLI 实验：

```bash
uv run minilucene create demo-index --schema schema.json
uv run minilucene add demo-index doc-1.json doc-2.json
uv run minilucene search demo-index '"follower replicas"' \
  --default-field body --top-k 10 --highlight body
```

结果应包含一个命中：文档 `1`，并将 `<em>follower replicas</em>` 标为高亮。
第 4 章给出完整 JSON 文件，并说明观察重点。

## 阅读顺序

先把检索、持久化、NRT 三个验收章节当作架构导览，再通过映射与行为矩阵区分
这个微型实现和生产 Lucene 的语义边界。

完整功能范围、心智模型和公共 API 示例见
[中文 README](https://github.com/system-in-miniature/MiniLucene/blob/main/README.zh-CN.md)。
[设计历史存档](../superpowers/README.md)记录建设期计划；现行文档与可执行测试
才是当前事实来源。
