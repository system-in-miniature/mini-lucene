# 第 2 章：分析链

词法索引不能直接使用原始散文，它需要一套可重复规则，让文档和查询进入同一 term
空间。这就是分析链：tokenizer 发现边界与属性，按序执行的 TokenFilter 转换或
删除 token。真正容易出错的地方，是保留后续查询仍需要的信息。MiniLucene 最小而
关键的例子，就是停用词被删除后必须留下 position gap。

## 学习目标

完成本章后，你能够区分 tokenizer 与 filter，读懂 term/position/offset，解释
停用词过滤为何不能重编号，对比 standard 与 keyword 分析，并用内存索引验证短语。

## 机制讲解：属性穿过管道

`src/minilucene/analysis/model.py` 定义不可变 `Token`，并在 `__post_init__`
校验非空 term、非负位置与 offset，以及 end 不早于 start。错误的分析器输出会在
源头附近失败。

`src/minilucene/analysis/pipeline.py` 定义 `Tokenizer.tokenize` 和
`TokenFilter.apply` 协议。`Analyzer.analyze` 先运行一个 tokenizer，再按序运行
filter：

```python
def analyze(self, text: str) -> tuple[Token, ...]:
    tokens = self.tokenizer.tokenize(text)
    for token_filter in self.filters:
        tokens = token_filter.apply(tokens)
    return tokens
```

`LowercaseFilter.apply` 用 `dataclasses.replace` 只改变 term，保留位置与 offset；
`StopwordFilter.apply` 删除匹配 token，却原样返回幸存者。

`src/minilucene/analysis/standard.py` 的 `StandardTokenizer.tokenize` 使用
Unicode 感知的 `\w+`。每个 match 记录原始子串、在所有 tokenizer 输出中的序号、
起始字符下标和排他结束下标。`StandardAnalyzer` 组合 lowercase 与 stopword
filter，默认停用词只有 `"the"`，便于观察。`KeywordAnalyzer` 则把非空输入整体
变成 position 0 的一个 token，不加 filter，适合标识符而非自然语言。

### position gap 为什么关键

`fast the search` 的初始位置是 0、1、2。删除 position 1 的 `the` 后，必须保留
`fast@0` 与 `search@2`。若压缩成 0、1，索引就会谎称两词相邻，使精确短语
`"fast search"` 错误命中。

`src/minilucene/index/memory.py` 的 `RamIndexBuilder.add_prepared` 按 term
汇总这些位置并写入 `Posting.positions`，短语匹配器因此能校验真正连续的位置。
offset 解决另一个问题：它指向原 stored 字符串。`Fast` 虽被规范成 `fast`，0–4
仍指向原文，供高亮选择并转义原始字符。position 回答 token 顺序，offset 回答
源码字符位置，不能互换。

`RamIndexBuilder.prepare_document` 通过私有 `_analyze`，按 Schema 的
`analyzer_name` 选择 standard 或 keyword。文档 term 与同一字段的查询 term
必须属于同一词汇空间，但不等于“任何字段都跑同一个 tokenizer”。

### 分析器选择是索引契约的一部分

旧文档已 lowercase、而新查询保留大小写时，`FAST` 会查找从未写入的词典项；
若新版 analyzer 多删一个停用词，新旧段的短语位置规则也会不同。MiniLucene 把
完整字段定义持久化到 `schema.json`，并在 `Index.open` 校验
`Schema.fingerprint`，以减少这种漂移。

不过指纹只证明声明配置相同，不证明任意 analyzer 代码版本相同。内置名称目前在
`_analyze` 映射到固定工厂，没有插件注册或 analyzer version。生产系统中，
analyzer 身份必须包含配置和实现版本，而不只是一个名字。

真实系统的多值字段还需要在值之间插入 position gap，避免短语跨值命中。
MiniLucene 每字段只接受一个字符串，没有多值 gap 策略。不同字段也应选择不同
词汇规则：标识符、标题、正文、路径与代码不能盲目共用一个“聪明”分析器。

### 本实现没有声称什么

`\w+` 能识别 Unicode word 字符，但不是完整语言切分器。无空格语言、词干化、
词形还原、同义词、复合词拆分与领域规范化都需要额外组件。英文标点行为也遵循
Python regex，而非 Lucene StandardTokenizer。可组合边界允许扩展，不代表默认
分析器普适。

## 对照真实 Apache Lucene

Lucene 用 `Analyzer`、`Tokenizer`、`TokenStream` 和
`CharTermAttribute`、`PositionIncrementAttribute`、`OffsetAttribute` 等属性。
删除 token 后，gap 常由下一个 token 的 position increment 表示；组件可复用且
流式执行，并有丰富的语言、同义词和规范化支持。

MiniLucene 使用物化 tuple 与绝对位置，易读但一次分配全部 token。它只有简单
regex、一个默认停用词和两个内置 analyzer，不复现 Lucene 的 Unicode Text
Segmentation 或分析 SPI。Schema 固定 boost，而现代 Lucene 倾向查询时 boost。
详见[Lucene 映射](../../lucene-mapping.md)与
[行为矩阵](../../behavior-matrix.md)的分析、短语和高亮条目。

## 动手实验：观察 gap

```bash
export UV_CACHE_DIR=/tmp/minilucene-uv-cache
uv run --offline python - <<'PY'
from minilucene.analysis import StandardAnalyzer
from minilucene import MemoryIndex, Schema, TextField
from minilucene.query import PhraseQuery

tokens = StandardAnalyzer().analyze("Fast THE search")
print([(t.term, t.position, t.start_offset, t.end_offset) for t in tokens])
index = MemoryIndex(Schema(body=TextField(stored=True)))
index.add_document(body="fast the search")
index.add_document(body="fast search")
result = index.search(PhraseQuery("body", ("fast", "search")))
print(result.total_hits, [dict(hit.stored_fields) for hit in result.hits])
PY
```

实测输出：

```text
[('fast', 0, 0, 4), ('search', 2, 9, 15)]
1 [{'body': 'fast search'}]
```

`THE` 先 lowercase 再被删除，`search` 仍在 position 2，offset 仍指向原文字符 9。
只有真正相邻的第二个文档命中。

```bash
uv run --offline pytest -q tests/unit/analysis/test_pipeline.py \
  tests/contract/test_query_matching.py
```

实测为 `18 passed in 0.08s`；耗时因机器而异，pass 数才是验收信号。

## 练习

1. **理解题：** lowercase 后为什么还能保留原 offset？

    ??? note "参考答案"
        offset 描述原文区间，不是规范化 term 内的下标，供恢复与高亮原文使用。

2. **理解题：** 只有 term frequency 能否完成精确短语匹配？

    ??? note "参考答案"
        不能。频率不说明各 term 是否处在连续兼容的位置，必须保存 positions。

3. **动手题：** 分析 `"Fast, search!"`。验收：两个 lowercase token 位于
   0、1，offset 对应原词。

    ??? note "参考答案"
        结果为 `[('fast', 0, 0, 4), ('search', 1, 6, 12)]`。

4. **动手题：** 不改 `src/`，用
   `StandardAnalyzer(stopwords=frozenset({"fast"}))` 分析
   `"fast reliable search"`。验收：位置仍为 1、2。

    ??? note "参考答案"
        传入自定义集合并打印 token；删除首 token 不会平移坐标系。

## 小结

分析是受控的信息丢失：标点和停用词可消失，大小写可规范化，但 position 与原文
offset 必须保留。下一章跟随 token 进入 RAM 倒排索引，观察 term 如何变成 posting
list，字段长度如何变成计分 norms。
