# Stage 02 · 位置化文本分析

### 目标

实现位置化文本分析，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/analysis/__init__.py`
    - `src/minilucene/analysis/model.py`
    - `src/minilucene/analysis/pipeline.py`
    - `src/minilucene/analysis/standard.py`
    - `tests/unit/analysis/test_pipeline.py`

### 当前遇到的问题

原始文本只有形成稳定 Token 属性后，才能支持 Term、Phrase 与 Highlight 语义。

### 测试契约

#### 先看会坏在哪里

测试用标点、Stop Word、Position Gap、Offset 与非法 Token Range 暴露有损 Analyzer。

??? note "文件差异：tests/unit/analysis/test_pipeline.py"
    ```diff
    diff --git a/tests/unit/analysis/test_pipeline.py b/tests/unit/analysis/test_pipeline.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..92749340d7908236432a8e9403a203ad961e4994
    --- /dev/null
    +++ b/tests/unit/analysis/test_pipeline.py
    @@ -0,0 +1,33 @@
    +from minilucene.analysis import KeywordAnalyzer, StandardAnalyzer, Token
    +from minilucene.analysis.pipeline import Analyzer, LowercaseFilter
    +from minilucene.analysis.standard import KeywordTokenizer
    +
    +
    +def test_standard_analysis_preserves_offsets_and_stopword_gap():
    +    analyzer = StandardAnalyzer(stopwords=frozenset({"and"}))
    +    assert analyzer.analyze("Kafka AND Replicas") == (
    +        Token("kafka", 0, 0, 5),
    +        Token("replicas", 2, 10, 18),
    +    )
    +
    +
    +def test_keyword_analyzer_emits_whole_value():
    +    assert KeywordAnalyzer().analyze("Jonah Smith") == (
    +        Token("Jonah Smith", 0, 0, 11),
    +    )
    +
    +
    +def test_keyword_analyzer_emits_no_token_for_empty_value():
    +    assert KeywordAnalyzer().analyze("") == ()
    +
    +
    +def test_pipeline_applies_filters_in_order_without_changing_offsets():
    +    analyzer = Analyzer(KeywordTokenizer(), (LowercaseFilter(),))
    +    assert analyzer.analyze("MiXeD") == (Token("mixed", 0, 0, 5),)
    +
    +
    +def test_unicode_words_keep_original_character_offsets():
    +    assert StandardAnalyzer().analyze("你好 Kafka") == (
    +        Token("你好", 0, 0, 2),
    +        Token("kafka", 1, 3, 8),
    +    )
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

测试用标点、Stop Word、Position Gap、Offset 与非法 Token Range 暴露有损 Analyzer。

**关键测试语句**

```python
assert analyzer.analyze("Kafka AND Replicas") == (
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Token 携带 Term、Position 与源 Offset；Analyzer 是这些属性上的确定性 Pipeline。

### 为什么需要这个机制

原始文本只有形成稳定 Token 属性后，才能支持 Term、Phrase 与 Highlight 语义。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

字符过滤与 Tokenization 产生证据；Filter 在保留 Position 与 Offset 含义的前提下归一化或移除 Token。

### 机制板块

#### 位置化文本分析机制

字符过滤与 Tokenization 产生证据；Filter 在保留 Position 与 Offset 含义的前提下归一化或移除 Token。

??? note "文件差异：src/minilucene/analysis/model.py"
    ```diff
    diff --git a/src/minilucene/analysis/model.py b/src/minilucene/analysis/model.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..d797f1467bd3250ce993c93a664f1a4cc7284942
    --- /dev/null
    +++ b/src/minilucene/analysis/model.py
    @@ -0,0 +1,9 @@
    +from dataclasses import dataclass
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class Token:
    +    term: str
    +    position: int
    +    start_offset: int
    +    end_offset: int
    ```

??? note "文件差异：src/minilucene/analysis/pipeline.py"
    ```diff
    diff --git a/src/minilucene/analysis/pipeline.py b/src/minilucene/analysis/pipeline.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..08bb259d211a6dd4cd144dca631cfbfdcbcaee7c
    --- /dev/null
    +++ b/src/minilucene/analysis/pipeline.py
    @@ -0,0 +1,44 @@
    +from collections.abc import Iterable
    +from dataclasses import replace
    +from typing import Protocol
    +
    +from minilucene.analysis.model import Token
    +
    +
    +class Tokenizer(Protocol):
    +    def tokenize(self, text: str) -> tuple[Token, ...]: ...
    +
    +
    +class TokenFilter(Protocol):
    +    def apply(self, tokens: Iterable[Token]) -> tuple[Token, ...]: ...
    +
    +
    +class LowercaseFilter:
    +    def apply(self, tokens: Iterable[Token]) -> tuple[Token, ...]:
    +        return tuple(
    +            replace(token, term=token.term.lower()) for token in tokens
    +        )
    +
    +
    +class StopwordFilter:
    +    def __init__(self, stopwords: frozenset[str]) -> None:
    +        self.stopwords = stopwords
    +
    +    def apply(self, tokens: Iterable[Token]) -> tuple[Token, ...]:
    +        return tuple(
    +            token for token in tokens if token.term not in self.stopwords
    +        )
    +
    +
    +class Analyzer:
    +    def __init__(
    +        self, tokenizer: Tokenizer, filters: tuple[TokenFilter, ...]
    +    ) -> None:
    +        self.tokenizer = tokenizer
    +        self.filters = filters
    +
    +    def analyze(self, text: str) -> tuple[Token, ...]:
    +        tokens = self.tokenizer.tokenize(text)
    +        for token_filter in self.filters:
    +            tokens = token_filter.apply(tokens)
    +        return tokens
    ```

??? note "文件差异：src/minilucene/analysis/standard.py"
    ```diff
    diff --git a/src/minilucene/analysis/standard.py b/src/minilucene/analysis/standard.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..ff4ce43259b37fda72f547db51a33dcf8834aff1
    --- /dev/null
    +++ b/src/minilucene/analysis/standard.py
    @@ -0,0 +1,43 @@
    +import re
    +
    +from minilucene.analysis.model import Token
    +from minilucene.analysis.pipeline import (
    +    Analyzer,
    +    LowercaseFilter,
    +    StopwordFilter,
    +)
    +
    +_WORD_PATTERN = re.compile(r"\w+", re.UNICODE)
    +
    +
    +class StandardTokenizer:
    +    def tokenize(self, text: str) -> tuple[Token, ...]:
    +        return tuple(
    +            Token(
    +                term=match.group(),
    +                position=position,
    +                start_offset=match.start(),
    +                end_offset=match.end(),
    +            )
    +            for position, match in enumerate(_WORD_PATTERN.finditer(text))
    +        )
    +
    +
    +class KeywordTokenizer:
    +    def tokenize(self, text: str) -> tuple[Token, ...]:
    +        if not text:
    +            return ()
    +        return (Token(text, 0, 0, len(text)),)
    +
    +
    +def StandardAnalyzer(
    +    *, stopwords: frozenset[str] = frozenset()
    +) -> Analyzer:
    +    return Analyzer(
    +        StandardTokenizer(),
    +        (LowercaseFilter(), StopwordFilter(stopwords)),
    +    )
    +
    +
    +def KeywordAnalyzer() -> Analyzer:
    +    return Analyzer(KeywordTokenizer(), ())
    ```

**是什么，为什么现在需要**

Token 携带 Term、Position 与源 Offset；Analyzer 是这些属性上的确定性 Pipeline。

**在运行时做什么**

字符过滤与 Tokenization 产生证据；Filter 在保留 Position 与 Offset 含义的前提下归一化或移除 Token。

**关键语句理解**

Position Increment 保留被移除 Token 造成的 Phrase 距离，Offset 保留 Highlight 所需的原文范围。

#### 包、Fixture 与工程支撑

保持包导出、测试语料、依赖与运行环境可复现。

??? note "支撑文件差异（1 个文件）"
    **`src/minilucene/analysis/__init__.py`**

    ```diff
    diff --git a/src/minilucene/analysis/__init__.py b/src/minilucene/analysis/__init__.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..f1339dd84438ed95df6c8c13fe19ac468aeda6be
    --- /dev/null
    +++ b/src/minilucene/analysis/__init__.py
    @@ -0,0 +1,4 @@
    +from minilucene.analysis.model import Token
    +from minilucene.analysis.standard import KeywordAnalyzer, StandardAnalyzer
    +
    +__all__ = ["KeywordAnalyzer", "StandardAnalyzer", "Token"]
    ```


### 验证证据

运行 `uv run pytest -q $(cat journey/stages/02-positional-analysis/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

Position Increment 保留被移除 Token 造成的 Phrase 距离，Offset 保留 Highlight 所需的原文范围。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 2 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/02-analysis.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/02-positional-analysis/stage.patch)
