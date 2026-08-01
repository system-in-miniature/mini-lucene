# Stage 02 · Positional analysis

### Goal

Build positional analysis and explain its boundary from an executable counterexample, runtime state, and the critical statement.

??? note "Deliverable files"
    - `src/minilucene/analysis/__init__.py`
    - `src/minilucene/analysis/model.py`
    - `src/minilucene/analysis/pipeline.py`
    - `src/minilucene/analysis/standard.py`
    - `tests/unit/analysis/test_pipeline.py`

### The problem at this point

Raw text cannot support term, phrase, or highlighting semantics until token attributes are stable.

### Test contract

#### See the failure first

The suite uses punctuation, stop words, position gaps, offsets, and invalid token ranges to expose lossy analyzers.

??? note "File diff: tests/unit/analysis/test_pipeline.py"
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

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

The suite uses punctuation, stop words, position gaps, offsets, and invalid token ranges to expose lossy analyzers.

**Key test statement**

```python
assert analyzer.analyze("Kafka AND Replicas") == (
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

A Token carries term text, position, and source offsets; an Analyzer is a deterministic pipeline over those attributes.

### Why this mechanism is necessary

Raw text cannot support term, phrase, or highlighting semantics until token attributes are stable. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Character filtering and tokenization create evidence; filters normalize or remove tokens while preserving position and offset meaning.

### Mechanism blocks

#### Positional analysis mechanism

Character filtering and tokenization create evidence; filters normalize or remove tokens while preserving position and offset meaning.

??? note "File diff: src/minilucene/analysis/model.py"
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

??? note "File diff: src/minilucene/analysis/pipeline.py"
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

??? note "File diff: src/minilucene/analysis/standard.py"
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

**What it is and why it appears**

A Token carries term text, position, and source offsets; an Analyzer is a deterministic pipeline over those attributes.

**Runtime role**

Character filtering and tokenization create evidence; filters normalize or remove tokens while preserving position and offset meaning.

**Statement understanding**

Position increments preserve phrase distance across removed tokens, while offsets preserve the original text span for highlighting.

#### Package, fixture, and project support

Keep exports, test corpora, dependencies, and the runtime environment reproducible.

??? note "Supporting file diffs (1 file)"
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


### Verification evidence

Run `uv run pytest -q $(cat journey/stages/02-positional-analysis/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Position increments preserve phrase distance across removed tokens, while offsets preserve the original text span for highlighting.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 2](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/02-analysis.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/02-positional-analysis/stage.patch)
