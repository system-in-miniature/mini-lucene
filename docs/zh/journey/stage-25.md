# Stage 25 · 有界 Prefix Rewrite

### 目标

实现有界 Prefix Rewrite，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/errors.py`
    - `src/minilucene/reader.py`
    - `src/minilucene/search/reader.py`
    - `src/minilucene/search/rewrite.py`
    - `tests/contract/test_prefix_rewrite.py`

### 当前遇到的问题

Prefix Query 无法直接执行 Exact-term Posting，且无界展开会把一次 Query 变成穷举工作。

### 测试契约

#### 先看会坏在哪里

测试创建超过 Limit 的匹配 Term、改变 Default Field，并要求确定性 Expansion 或类型化 Too-many-clauses Failure。

??? note "文件差异：tests/contract/test_prefix_rewrite.py"
    ```diff
    diff --git a/tests/contract/test_prefix_rewrite.py b/tests/contract/test_prefix_rewrite.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..8f8f94680d531307a0453c4bf821fc6b45e72a37
    --- /dev/null
    +++ b/tests/contract/test_prefix_rewrite.py
    @@ -0,0 +1,90 @@
    +import pytest
    +
    +from minilucene.errors import TooManyTermsError
    +from minilucene.index.memory import RamIndexBuilder
    +from minilucene.query import (
    +    BooleanClause,
    +    BooleanQuery,
    +    MatchAllQuery,
    +    Occur,
    +    PrefixQuery,
    +    TermQuery,
    +)
    +from minilucene.schema import Schema, TextField
    +from minilucene.search.reader import ReaderView
    +
    +
    +@pytest.fixture
    +def reader():
    +    schema = Schema(body=TextField(stored=True))
    +    builder = RamIndexBuilder(schema)
    +    builder.add_document(
    +        {
    +            "body": (
    +                "application banana apple app apricot application"
    +            )
    +        }
    +    )
    +    return ReaderView(schema, (builder.freeze(generation=1),))
    +
    +
    +def test_prefix_expands_sorted_terms_without_scanning_stored_docs(reader):
    +    assert reader.rewrite(
    +        PrefixQuery("body", "app"), max_terms=3
    +    ) == BooleanQuery(
    +        (
    +            BooleanClause(
    +                Occur.SHOULD, TermQuery("body", "app")
    +            ),
    +            BooleanClause(
    +                Occur.SHOULD, TermQuery("body", "apple")
    +            ),
    +            BooleanClause(
    +                Occur.SHOULD, TermQuery("body", "application")
    +            ),
    +        )
    +    )
    +
    +
    +def test_prefix_expansion_fails_instead_of_truncating(reader):
    +    with pytest.raises(TooManyTermsError) as error:
    +        reader.rewrite(PrefixQuery("body", "a"), max_terms=2)
    +    assert error.value.limit == 2
    +    assert error.value.field == "body"
    +    assert error.value.prefix == "a"
    +
    +
    +def test_prefix_rewrite_is_recursive_and_zero_terms_match_nothing(reader):
    +    query = BooleanQuery(
    +        (
    +            BooleanClause(
    +                Occur.MUST, PrefixQuery("body", "ban")
    +            ),
    +            BooleanClause(
    +                Occur.MUST_NOT, PrefixQuery("body", "missing")
    +            ),
    +        )
    +    )
    +    assert reader.rewrite(query, max_terms=3) == BooleanQuery(
    +        (
    +            BooleanClause(
    +                Occur.MUST, TermQuery("body", "banana")
    +            ),
    +            BooleanClause(
    +                Occur.MUST_NOT,
    +                BooleanQuery(
    +                    (
    +                        BooleanClause(
    +                            Occur.MUST_NOT, MatchAllQuery()
    +                        ),
    +                    )
    +                ),
    +            ),
    +        )
    +    )
    +
    +
    +@pytest.mark.parametrize("limit", [0, -1, 1.5])
    +def test_prefix_rewrite_rejects_invalid_limits(reader, limit):
    +    with pytest.raises(ValueError, match="positive integer"):
    +        reader.rewrite(PrefixQuery("body", "app"), max_terms=limit)
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

测试创建超过 Limit 的匹配 Term、改变 Default Field，并要求确定性 Expansion 或类型化 Too-many-clauses Failure。

**关键测试语句**

```python
assert reader.rewrite(
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Rewrite 使用当前 Reader Vocabulary，把高层 Prefix Node 翻译成有界 Exact TermQuery OR。

### 为什么需要这个机制

Prefix Query 无法直接执行 Exact-term Posting，且无界展开会把一次 Query 变成穷举工作。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

它解析 Field Context、枚举有序匹配 Term、在 Limit+1 停止，并递归 Rewrite Composite Child。

### 机制板块

#### 有界 Prefix Rewrite机制

它解析 Field Context、枚举有序匹配 Term、在 Limit+1 停止，并递归 Rewrite Composite Child。

??? note "文件差异：src/minilucene/errors.py"
    ```diff
    diff --git a/src/minilucene/errors.py b/src/minilucene/errors.py
    index 64409edb4e9eb9257b7b4f668dca14462b40e803..09ef3d61601abd0368843325ed6411919fe7140a 100644
    --- a/src/minilucene/errors.py
    +++ b/src/minilucene/errors.py
    @@ -28,3 +28,13 @@ class CloseError(MiniLuceneError):
             super().__init__(
                 f"close encountered {len(errors)} cleanup error(s)"
             )
    +
    +
    +class TooManyTermsError(MiniLuceneError, ValueError):
    +    def __init__(self, field: str, prefix: str, limit: int) -> None:
    +        self.field = field
    +        self.prefix = prefix
    +        self.limit = limit
    +        super().__init__(
    +            f"prefix expansion for {field}:{prefix} exceeds {limit} terms"
    +        )
    ```

??? note "文件差异：src/minilucene/reader.py"
    ```diff
    diff --git a/src/minilucene/reader.py b/src/minilucene/reader.py
    index 2323983cba3f2fe8940f73ac584e219f286da568..88024c49213de83c9ce5aaa8ea19d3d47146a8fc 100644
    --- a/src/minilucene/reader.py
    +++ b/src/minilucene/reader.py
    @@ -86,6 +86,12 @@ class IndexReader(ReaderView):
             self._ensure_open()
             return super().field_length(field, doc_id)

    +    def rewrite(
    +        self, query: Query, *, max_terms: int | None = None
    +    ) -> Query:
    +        self._ensure_open()
    +        return super().rewrite(query, max_terms=max_terms)
    +
         def close(self) -> None:
             if self._closed:
                 return
    ```

??? note "文件差异：src/minilucene/search/reader.py"
    ```diff
    diff --git a/src/minilucene/search/reader.py b/src/minilucene/search/reader.py
    index 2f80ce0073fdfabc8e1581bb29133003c20b6eea..30fb536a85fa0b7355d0b3f9fcad9c3a53e0be23 100644
    --- a/src/minilucene/search/reader.py
    +++ b/src/minilucene/search/reader.py
    @@ -147,6 +147,21 @@ class ReaderView:
         def match(self, query: Query) -> set[int]:
             return match_query(self, query)

    +    def rewrite(
    +        self, query: Query, *, max_terms: int | None = None
    +    ) -> Query:
    +        from minilucene.search.rewrite import rewrite_query
    +
    +        return rewrite_query(
    +            self,
    +            query,
    +            max_terms=(
    +                self.max_prefix_expansions
    +                if max_terms is None
    +                else max_terms
    +            ),
    +        )
    +
         def _build_corpus_stats(self) -> CorpusStats:
             doc_frequencies: dict[tuple[str, str], int] = {}
             for segment, live in zip(
    ```

??? note "文件差异：src/minilucene/search/rewrite.py"
    ```diff
    diff --git a/src/minilucene/search/rewrite.py b/src/minilucene/search/rewrite.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..1b83fa046190347c36e5f9ba664c26e14ef924cc
    --- /dev/null
    +++ b/src/minilucene/search/rewrite.py
    @@ -0,0 +1,78 @@
    +from bisect import bisect_left
    +from typing import Protocol
    +
    +from minilucene.errors import TooManyTermsError
    +from minilucene.query import (
    +    BooleanClause,
    +    BooleanQuery,
    +    MatchAllQuery,
    +    Occur,
    +    PrefixQuery,
    +    Query,
    +    TermQuery,
    +)
    +
    +
    +class RewriteReader(Protocol):
    +    def terms_with_prefix(
    +        self, field: str, prefix: str
    +    ) -> tuple[str, ...]: ...
    +
    +
    +def _expand_prefix(
    +    reader: RewriteReader,
    +    query: PrefixQuery,
    +    *,
    +    max_terms: int,
    +) -> Query:
    +    terms = reader.terms_with_prefix(query.field, query.prefix)
    +    start = bisect_left(terms, query.prefix)
    +    matches: list[str] = []
    +    for term in terms[start:]:
    +        if not term.startswith(query.prefix):
    +            break
    +        if len(matches) == max_terms:
    +            raise TooManyTermsError(
    +                query.field, query.prefix, max_terms
    +            )
    +        matches.append(term)
    +    if not matches:
    +        return BooleanQuery(
    +            (BooleanClause(Occur.MUST_NOT, MatchAllQuery()),)
    +        )
    +    if len(matches) == 1:
    +        return TermQuery(query.field, matches[0])
    +    return BooleanQuery(
    +        tuple(
    +            BooleanClause(
    +                Occur.SHOULD, TermQuery(query.field, term)
    +            )
    +            for term in matches
    +        )
    +    )
    +
    +
    +def rewrite_query(
    +    reader: RewriteReader, query: Query, *, max_terms: int
    +) -> Query:
    +    if (
    +        not isinstance(max_terms, int)
    +        or isinstance(max_terms, bool)
    +        or max_terms <= 0
    +    ):
    +        raise ValueError("max_terms must be a positive integer")
    +    if isinstance(query, PrefixQuery):
    +        return _expand_prefix(reader, query, max_terms=max_terms)
    +    if isinstance(query, BooleanQuery):
    +        return BooleanQuery(
    +            tuple(
    +                BooleanClause(
    +                    clause.occur,
    +                    rewrite_query(
    +                        reader, clause.query, max_terms=max_terms
    +                    ),
    +                )
    +                for clause in query.clauses
    +            )
    +        )
    +    return query
    ```

**是什么，为什么现在需要**

Rewrite 使用当前 Reader Vocabulary，把高层 Prefix Node 翻译成有界 Exact TermQuery OR。

**在运行时做什么**

它解析 Field Context、枚举有序匹配 Term、在 Limit+1 停止，并递归 Rewrite Composite Child。

**关键语句理解**

检查 Limit 之外一个 Term，区分恰好填满的合法 Rewrite 与会丢 Match 的静默截断。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/25-prefix-rewrite/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

检查 Limit 之外一个 Term，区分恰好填满的合法 Rewrite 与会丢 Match 的静默截断。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 9 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/09-query-language.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/25-prefix-rewrite/stage.patch)
