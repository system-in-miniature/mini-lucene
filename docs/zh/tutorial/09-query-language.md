# 查询语言

## 学习目标

完成本章后，你将能够：

1. 追踪查询字符串经过 lexer、递归下降 parser、analyzer 和 rewrite 的过程；
2. 解释字段限定、运算符优先级、隐式 OR 与一元否定；
3. 预测单 token 引号短语和内部连字符对应的 AST；
4. 解释为什么 prefix 展开经过排序、具有上限并且超限立即失败；以及
5. 指出 MiniLucene 有意不支持的语法和查询类型。

## 1. 查询语言止于封闭 AST

`IndexReader.search_text()` 与 `IndexSearcher.search_text()` 是适配器。后者位于 `src/minilucene/search/searcher.py`，调用
`src/minilucene/query_parser/parser.py` 的 `parse_query()`，再把得到的
`Query` 对象送进程序化查询共用的 `search()` 路径。

可接受 AST 定义在 `src/minilucene/query/model.py`：term、精确 phrase、prefix、match-all，以及包含 `MUST`、`SHOULD`、`MUST_NOT` 子句的
Boolean 查询。parser 无法制造任意可执行代码或未知查询子类。该封闭边界让之后的匹配与打分能穷举所有已知 dataclass。

文本路径如下：

```text
源字符串
  → lex()：保留 offset 的 LexToken tuple
  → _Parser：优先级与字段作用域
  → 字段 analyzer：可搜索词项和 phrase positions
  → 封闭 Query AST
  → reader.rewrite()：有界 multi-term 展开
  → 匹配与打分
```

解析与 rewrite 分离。`kaf*` 先变成 `PrefixQuery`；只有 reader 快照知道当前有哪些索引词项以 `kaf` 开头。

## 2. Lexing 为错误保留证据

`src/minilucene/query_parser/lexer.py` 的 `lex()` 产生带 `kind`、解码后
`text` 和半开源 offset `start`/`end` 的 token。它识别 word、phrase、prefix、`AND`、`OR`、`NOT`、冒号、括号和一元减号。当完整 word 等于运算符时，运算符不区分大小写。

`_lex_phrase()` 去掉引号分隔符，只允许两种转义：`\"` 与 `\\`。未闭合 phrase 或不支持的转义会在相应源 offset 抛出
`QuerySyntaxError`。这些 offset 让
`src/minilucene/query_parser/errors.py` 的 `QuerySyntaxError` 能渲染原文和插入符，而不是只返回缺少上下文的“bad query”。

连字符规则有意保持狭窄。`_is_internal_hyphen()` 只在 `-` 两侧都是字母数字时把它保留在 word 内：

```text
id:doc-1   → WORD("doc-1")
-slow      → MINUS, WORD("slow")
a--b       → WORD("a"), MINUS, MINUS, WORD("b")
```

这既保留 `doc-1` 之类 keyword 标识符，也保留一元否定。它是
MiniLucene 的语法选择，不承诺完整 Lucene query parser 兼容性。

`_lex_word()` 只识别非空 prefix 后的一个尾随 `*`。前导、内部或重复星号都会在对应 offset 失败。不存在 `?`、通用 wildcard、regex、fuzzy 后缀、range 括号、proximity 后缀或 boost 语法。

## 3. 递归下降固定优先级

`src/minilucene/query_parser/parser.py` 的 `_Parser.parse()` 按以下层次委托：

```text
parse_or()
  └── parse_and()
        └── parse_unary()
              └── parse_primary()
```

更深的函数绑定更紧。因此 `a OR b AND c` 表示 `a OR (b AND c)`。括号会递归调用 `parse_or()`，覆盖默认优先级。没有显式运算符的相邻 primary 会由
`parse_or()` 收集，所以 `kafka rabbit` 是隐式 OR。

`parse_unary()` 消费连续的 `NOT` 或 `-` 并切换 prohibited 状态。一次否定产生 prohibited 结果，两次抵消。当 prohibited 子项进入 Boolean 组时，它变成
`MUST_NOT` 子句。顶层负查询物化为只含该 `MUST_NOT` 的 Boolean 查询；随后由 MiniLucene 冻结的 Boolean 匹配语义定义结果。

这里不应套用其他 parser 的假设。“纯负查询”处理、隐式 OR 与重复一元否定都属于 MiniLucene 自身 AST 契约。parser 不会在文本层把用户意图重写成未声明的 match-all；它保留显式 prohibited 结构，再由
`src/minilucene/query/match.py` 的 `match_boolean()` 应用仓库记录的集合语义。因此，语法变化的测试既应断言最终命中，也应断言 AST 形状。

字段限定在 `parse_primary()` 中处理。后接冒号的 `WORD` 必须是 schema 字段，而且该字段必须已索引。选中字段作用于紧随其后的 primary；
`title:(kafka rabbit)` 会把 `title` 传入括号内递归解析。stored-only 字段会在冒号处失败，而不是静默产生零匹配。

语法失败也是 API 的一部分。`_Parser.syntax()` 附带当前 token 的原始 offset；未知或未索引字段的验证错误会指向字段出现位置。由于 analysis 可以拒绝没有产生可搜索词项的文本，一个语法形式正确的 token 仍可能构成无效查询。把 lexing、字段验证和 analysis 错误分开，才能让 CLI 或 UI 告诉用户具体应修改什么。

## 4. 查询文本使用字段 analyzer

parser 不会自行硬编码 lowercase。`_Parser._analyze()` 根据字段冻结 schema 元数据选择 `StandardAnalyzer` 或 `KeywordAnalyzer`。因此，查询词项与索引词项在同一基本分析契约下相遇。

一个 word 若分析成多个 token，会变成隐式 SHOULD Boolean 查询。phrase 会保留分析后 positions。例如，在 standard analyzer 的 stopword 行为下：

```text
body:"distributed the system"
→ PhraseQuery("body", ("distributed", "system"), positions=(0, 2))
```

这个 gap 防止 phrase matcher 假装保留下来的词项原本相邻。如果引号值只分析成一个 token，`parse_primary()` 会返回 `TermQuery`，而不是单词项
`PhraseQuery`。这种单 token phrase 降级避免要求 `KeywordField` 提供 positions，因此 `id:"doc-1"` 可以成为精确的
`TermQuery("id", "doc-1")`。

prefix 必须恰好分析成一个 token。`title:KAF*` 变成规范化的
`PrefixQuery("title", "kaf")`。分析为空或产生多个词项的 prefix 会失败，而不会静默选择一个。

## 5. Prefix rewrite 是有界语义工作

`src/minilucene/search/rewrite.py` 的 `rewrite_query()` 递归访问 Boolean 子项。对于 prefix，`_expand_prefix()` 通过
`ReaderView.terms_with_prefix()` 请求有序词项，用 `bisect_left` 定位起点，并收集连续共享 prefix 的词项。

三种结果都很明确：

1. 零个匹配词项变成不可能匹配的 Boolean 查询；
2. 一个词项变成 `TermQuery`；以及
3. 多个词项变成由 `TermQuery` 组成的 SHOULD 子句。

`max_terms` 必须是正整数。如果填满上限后仍存在下一个匹配词项，
`_expand_prefix()` 会抛出 `TooManyTermsError`，不会截断。截断会根据字典顺序静默改变查询含义。立即失败把成本和正确性暴露给调用者。

`src/minilucene/reader.py` 的 `IndexReader.rewrite()` 提供默认上限 128。该上限限制展开大小，不限制展开后整个 MiniLucene 搜索成本；如第 8 章所述，匹配与打分仍物化完整集合。

## 6. 与 Apache Lucene 对照

可迁移架构是：parser 产生 `Query` 对象，使用字段规则进行分析，多词项查询针对 index reader rewrite。Apache Lucene 同样有查询子类、Boolean occurrence 规则和多种 rewrite 策略。

MiniLucene 的语言有意小得多：

- 没有 phrase slop 或 proximity 语法；
- 没有 fuzzy、任意 wildcard、正则、range、numeric 或 date 查询；
- 没有查询时 boost、包含生产级边界情况的字段组或可插拔 parser 配置；
- 没有 `MultiTermQuery` 的 constant-score、top-terms-scoring 等 rewrite 选择；以及
- 语法背后没有 numeric points、doc values、sorting、faceting 或 aggregation。

即使熟悉的表面语法也可能不同，尤其是转义和连字符。应把 MiniLucene 查询语言视为自有的封闭教学语法。行为矩阵中的
[query lexer](../behavior-matrix.md)、query parser 和 prefix rewrite 条目定义其可执行契约。[MiniLucene 到 Lucene 映射](../lucene-mapping.md)中的查询模型行列出了缺失的生产查询族。

## 7. 动手实验：观察 token、AST 与 rewrite

在仓库根目录运行：

```bash
UV_CACHE_DIR=/tmp/minilucene-uv-cache uv run python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory

from minilucene import Index, KeywordField, Schema, TextField
from minilucene.query_parser import parse_query
from minilucene.query_parser.lexer import lex

schema = Schema(
    id=KeywordField(stored=True),
    title=TextField(stored=True),
    body=TextField(stored=True),
)
with TemporaryDirectory() as directory:
    index = Index.create(Path(directory), schema)
    with index.writer() as writer:
        writer.add_document(
            id="doc-1",
            title="Kafka internals",
            body="distributed the system application apple",
        )
        writer.commit()
    reader = index.open_reader()

    source = 'title:KAF* AND id:"doc-1"'
    print([(token.kind.value, token.text) for token in lex(source)])
    parsed = parse_query(source, schema, "body")
    print(parsed)
    print(reader.rewrite(parsed, max_terms=4))

    phrase = parse_query(
        'body:"distributed the system"', schema, "body"
    )
    print(phrase)
    reader.close()
    index.close()
PY
```

实测输出：

```text
[('WORD', 'title'), ('COLON', ':'), ('PREFIX', 'KAF'), ('AND', 'AND'), ('WORD', 'id'), ('COLON', ':'), ('PHRASE', 'doc-1'), ('EOF', '')]
BooleanQuery(clauses=(BooleanClause(occur=<Occur.MUST: 'MUST'>, query=PrefixQuery(field='title', prefix='kaf')), BooleanClause(occur=<Occur.MUST: 'MUST'>, query=TermQuery(field='id', term='doc-1'))))
BooleanQuery(clauses=(BooleanClause(occur=<Occur.MUST: 'MUST'>, query=TermQuery(field='title', term='kafka')), BooleanClause(occur=<Occur.MUST: 'MUST'>, query=TermQuery(field='id', term='doc-1'))))
PhraseQuery(field='body', terms=('distributed', 'system'), positions=(0, 2), slop=0)
```

lexer 保留原始大写 prefix 文本。parser 使用 title analyzer，把它规范化成小写。rewrite 随后查询 reader 的真实字典，把 prefix 替换成 `kafka`。

观察超限立即失败：

```bash
UV_CACHE_DIR=/tmp/minilucene-uv-cache uv run pytest tests/contract/test_prefix_rewrite.py -q
```

实测输出：

```text
6 passed in 0.09s
```

## 8. 练习

### 练习 1——解析题

不运行代码，根据 parser 优先级和隐式运算符，为
`a b AND NOT c OR d` 加括号。

??? note "参考答案"

    隐式相邻在 OR 层处理，而 AND 绑定更紧：
    `a OR (b AND (NOT c)) OR d`。精确 AST 在外层使用 SHOULD 子句，
    `b`/prohibited-`c` 组使用 MUST 与 MUST_NOT 子句。

### 练习 2——正确性题

为什么 prefix 超限要报错，而不是返回字母序前 `max_terms` 个词项？

??? note "参考答案"

    返回字典前缀会静默改变匹配文档集合，并让结果依赖词项顺序。硬失败保持语义诚实，要求调用者缩窄 prefix 或显式提高上限。

### 练习 3——动手题

不要修改 `src/`。把 lexer 与 parser 模块复制到临时目录，设计对
`+term` 显式 MUST 运算符的支持。包括 token、优先级和 AST 变化，并给出三个示例。

验收方式：临时 diff 必须保留内部连字符和源 offset，拒绝结尾孤立 `+`，并说明 `+a b` 与 `a b` 的差别。在仓库源码树外运行临时测试。

??? note "参考答案"

    添加独立 `+` 产生的 `PLUS` token，在 `parse_unary()` 中消费它，并携带与
    `prohibited` 不同的显式 required 标志。Boolean 物化必须把 required 子项转成 MUST，把普通相邻子项转成 SHOULD。测试应覆盖 `+a b`、
    `title:+kafka` 和 EOF 处 `+` 的语法错误。这只是设计练习；生产 Lucene parser 兼容性需要更多规则。

## 小结

MiniLucene 把文本转成保留 offset 的 token 流，应用固定递归下降优先级，按字段分析词项，并产生封闭 AST。依赖 reader 的 prefix rewrite 是更晚的有界阶段；它在超限时失败，而不是截断语义。最后一章将跟随另一个生命周期操作——显式 merge——并用项目有意省略的机制形成通往真实 Lucene 的路线图。
