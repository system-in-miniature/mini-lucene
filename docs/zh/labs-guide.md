# 第 4 章：CLI 动手实验

[English](../labs-guide.md)

MiniLucene 当前没有 `labs/` 目录；独立实验套件仍在规划中。本章先使用已经支持的
CLI，走通同一条“创建 → 提交 → 重开 → 查询”路径。

## 准备输入文件

创建 `schema.json`：

```json
{"fields":{"id":{"indexed":true,"tokenized":false,"stored":true,"store_positions":false,"boost":1.0,"analyzer_name":"keyword"},"title":{"indexed":true,"tokenized":true,"stored":true,"store_positions":true,"boost":2.0,"analyzer_name":"standard"},"body":{"indexed":true,"tokenized":true,"stored":true,"store_positions":true,"boost":1.0,"analyzer_name":"standard"}}}
```

创建 `doc-1.json` 和 `doc-2.json`：

```json
{"id":"1","title":"Kafka Replication","body":"Kafka uses follower replicas."}
```

```json
{"id":"2","title":"Rabbit","body":"Rabbit queues messages."}
```

## 运行

在仓库根目录执行：

```bash
uv sync --dev
uv run minilucene create demo-index --schema schema.json
uv run minilucene add demo-index doc-1.json doc-2.json
uv run minilucene search demo-index '"follower replicas"' \
  --default-field body --top-k 10 --highlight body
```

重复实验时请换一个新的 `demo-index` 路径。

## 预期现象与看点

创建与写入命令分别报告 `created`、新增 2 个文档和提交代次 `1`。查询返回
`total_hits: 1`，命中文档的 `id` 为 `"1"`，并得到：

```html
Kafka uses <em>follower replicas</em>.
```

重点观察：字段模式如何决定分析与存储；`add` 如何通过 commit 发布不可变段；
短语查询如何使用位置，而高亮如何使用原文偏移。随后可阅读
[检索内核](phase1-retrieval-kernel.md)和[段格式](segment-format.md)。
