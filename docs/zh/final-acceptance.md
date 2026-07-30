# MiniLucene V1 最终验收

> **语言**: [English](../final-acceptance.md) | 简体中文

于 2026-07-27 在以下位置通过验收：

```text
~/MiniLucene-workspace/MiniLucene
```

在这个仅添加证据的提交之前，受测实现树为：

```text
18db98104c5d3aeb3e75d453d2a4ec87ace43c1d
```

## 验证门槛

```text
uv sync --dev
Resolved 8 packages
Audited 7 packages

uv run ruff check src tests tools
All checks passed

uv run pytest -q
227 passed in 5.78s

uv run python -m compileall -q src tests tools
exit 0

git diff --check
exit 0
```

未完成标记扫描只找到了有意留空的异常/数据类、清理用 `except` 分支、一个上下文管理器
主体，以及固定实现计划中的示例。没有发现被跳过的验收或未完成的生产实现。

可执行行为矩阵验证了每一行文档都恰好解析为一个已收集的 pytest 节点。它包含受支持
行为、故障实验、生命周期收尾和明确的 V1 非目标。

实现后的完成度审计还依据聚焦提交历史、阶段报告和验收节点，核对了全部四份可执行
阶段计划。全部 196 个可操作计划步骤均已勾选；没有可操作步骤仍处于开放状态。

## 故障与恢复证据

验收覆盖：

1. RAM 发生变更前的文档验证与分析失败；
2. 最终目录重命名前的分段数据失败；
3. 清单替换前出现完整孤儿；
4. 清单成功替换，同时旧读取器保留旧文件；
5. 打开读取器时遇到校验和损坏会安全拒绝继续；
6. 通过刷新可见但未提交的状态在重新打开后消失；
7. 刷新、删除、更新与合并过程中的过时读取器；
8. 写入器集合交换前发生合并发布失败；
9. 重复关闭并聚合清理故障。

公共端到端验收会创建带字段索引、提交并重新打开索引、解析布尔短语查询、应用全局
BM25 与有界 Top-K、取回存储字段、安全高亮原始文本、刷新新状态、更新和删除文档、
保留旧读取器、显式合并、再次重新打开，并评估结果 ID。

所有者归零验收（owner-zero acceptance）结束时为：

```text
writer_owner = None
reader_owners = ()
segment_owners = {}
temporary_jobs = ()
.writer.lock absent
.tmp-* absent
```

## 已安装包冒烟测试

```text
uv build
Successfully built dist/minilucene_reference-0.1.0.tar.gz
Successfully built dist/minilucene_reference-0.1.0-py3-none-any.whl

uv pip install --python <isolated-venv>/bin/python <wheel>
Installed minilucene-reference==0.1.0

<isolated-venv>/bin/python -c \
  "import minilucene; print(minilucene.__version__)"
0.1.0

<isolated-venv>/bin/minilucene --help
exit 0
```

## 已验收范围

V1 支持通过直接 Python 调用和本地 CLI 使用：

- 模式、存储/索引/分词字段语义及分析器；
- 位置倒排索引，以及词项、布尔、短语、前缀和全匹配查询；
- 全局活跃文档 BM25、字段加权和确定性有界 Top-K；
- 不可变且带校验和的教学分段，以及原子清单；
- 时间点读取器、NRT 刷新、删除、更新、合并，以及感知所有权的垃圾回收；
- 查询解析、安全高亮、确定性评估指标和固定的相关性语料库。

V1 明确排除 TCP/HTTP 适配器、远程兼容性、分布式复制或协调、Apache Lucene
编解码器兼容性、生产级索引优化、自动合并调度、向量字段、近似最近邻（ANN）和
混合检索。

仓库中不存在 `course/` 或 `chapters/` 目录。在验收此参考项目后，课程设计仍是独立的
未来任务。
