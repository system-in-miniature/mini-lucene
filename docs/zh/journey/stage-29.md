# Stage 29 · Query 与 Token 回归

### 目标

实现Query 与 Token 回归，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/analysis/__init__.py`
    - `src/minilucene/analysis/model.py`
    - `src/minilucene/analysis/pipeline.py`
    - `src/minilucene/analysis/standard.py`
    - `src/minilucene/query_parser/lexer.py`
    - `src/minilucene/query_parser/parser.py`
    - `src/minilucene/reader.py`
    - `src/minilucene/search/reader.py`
    - `src/minilucene/storage/codec.py`
    - `src/minilucene/storage/manifest.py`
    - `src/minilucene/writer.py`
    - `tests/acceptance/test_phase1_retrieval_kernel.py`
    - `tests/unit/analysis/test_pipeline.py`
    - `tests/unit/query_parser/test_lexer.py`
    - `tests/unit/query_parser/test_parser.py`

### 当前遇到的问题

单 Token Quote、Hyphenated Term、非法 Token Attribute、零长度统计与 Boolean Varint 暴露文档契约与可执行契约间缺口。

### 测试契约

#### 先看会坏在哪里

回归测试保留早期 Lexer/Parser 错误处理的精确字符串，并直接构造非法 Token 与 Primitive Value。

??? note "文件差异：tests/acceptance/test_phase1_retrieval_kernel.py"
    ```diff
    diff --git a/tests/acceptance/test_phase1_retrieval_kernel.py b/tests/acceptance/test_phase1_retrieval_kernel.py
    index 11d79bdda942017dbae48dbb690db02977e7d59f..45849ca74c77c20c5a60d5d73065eef1a7003dd9 100644
    --- a/tests/acceptance/test_phase1_retrieval_kernel.py
    +++ b/tests/acceptance/test_phase1_retrieval_kernel.py
    @@ -1,3 +1,5 @@
    +import pytest
    +
     from minilucene import KeywordField, MemoryIndex, Schema, TextField
     from minilucene.query import (
         BooleanClause,
    @@ -6,6 +8,7 @@ from minilucene.query import (
         PhraseQuery,
         TermQuery,
     )
    +from minilucene.query_parser import parse_query


     def test_fielded_phrase_bm25_topk_and_stored_fields_close_one_loop():
    @@ -41,3 +44,18 @@ def test_fielded_phrase_bm25_topk_and_stored_fields_close_one_loop():
         assert result.total_hits == 1
         assert result.hits[0].stored_fields["id"] == "1"
         assert result.hits[0].score > 0
    +
    +
    +@pytest.mark.parametrize("source", ['id:"doc-1"', "id:doc-1"])
    +def test_hyphenated_keyword_id_is_searchable_from_query_string(source):
    +    schema = Schema(
    +        id=KeywordField(stored=True),
    +        body=TextField(stored=True),
    +    )
    +    index = MemoryIndex(schema)
    +    index.add_document(id="doc-1", body="searchable")
    +
    +    result = index.search(parse_query(source, schema, "body"))
    +
    +    assert result.total_hits == 1
    +    assert result.hits[0].stored_fields["id"] == "doc-1"
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

回归测试保留早期 Lexer/Parser 错误处理的精确字符串，并直接构造非法 Token 与 Primitive Value。

**关键测试语句**

```python
assert result.total_hits == 1
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

??? note "文件差异：tests/unit/analysis/test_pipeline.py"
    ```diff
    diff --git a/tests/unit/analysis/test_pipeline.py b/tests/unit/analysis/test_pipeline.py
    index 92749340d7908236432a8e9403a203ad961e4994..1ab8ee1f98fdb2a3543cb1913cd72417ba961d03 100644
    --- a/tests/unit/analysis/test_pipeline.py
    +++ b/tests/unit/analysis/test_pipeline.py
    @@ -1,8 +1,28 @@
    +import pytest
    +
     from minilucene.analysis import KeywordAnalyzer, StandardAnalyzer, Token
     from minilucene.analysis.pipeline import Analyzer, LowercaseFilter
     from minilucene.analysis.standard import KeywordTokenizer


    +@pytest.mark.parametrize(
    +    ("token", "message"),
    +    [
    +        (("", 0, 0, 0), "term must be non-empty"),
    +        (("term", -1, 0, 4), "position must be non-negative"),
    +        (("term", 0, -1, 4), "offsets must be non-negative"),
    +        (("term", 0, 0, -1), "offsets must be non-negative"),
    +        (("term", 0, 4, 3), "end offset must not precede start offset"),
    +    ],
    +)
    +def test_token_rejects_invalid_attributes(
    +    token: tuple[str, int, int, int],
    +    message: str,
    +):
    +    with pytest.raises(ValueError, match=message):
    +        Token(*token)
    +
    +
     def test_standard_analysis_preserves_offsets_and_stopword_gap():
         analyzer = StandardAnalyzer(stopwords=frozenset({"and"}))
         assert analyzer.analyze("Kafka AND Replicas") == (
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

回归测试保留早期 Lexer/Parser 错误处理的精确字符串，并直接构造非法 Token 与 Primitive Value。

**关键测试语句**

```python
assert result.total_hits == 1
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

??? note "文件差异：tests/unit/query_parser/test_lexer.py"
    ```diff
    diff --git a/tests/unit/query_parser/test_lexer.py b/tests/unit/query_parser/test_lexer.py
    index 7c11d3b431745c3deece7031d497fc9390dcf2dc..d02b2d9b58aa55d7f56088a4cb3df07e61bd84c3 100644
    --- a/tests/unit/query_parser/test_lexer.py
    +++ b/tests/unit/query_parser/test_lexer.py
    @@ -34,6 +34,16 @@ def test_lexer_recognizes_grouping_unary_and_case_insensitive_operators():
         ]


    +def test_lexer_keeps_internal_hyphen_in_word():
    +    tokens = lex("id:doc-1")
    +    assert [(token.kind, token.text) for token in tokens] == [
    +        (TokenKind.WORD, "id"),
    +        (TokenKind.COLON, ":"),
    +        (TokenKind.WORD, "doc-1"),
    +        (TokenKind.EOF, ""),
    +    ]
    +
    +
     def test_lexer_decodes_only_quote_and_backslash_escapes_in_phrases():
         tokens = lex(r'"a \"quote\" and \\ path"')
         assert tokens[0].kind is TokenKind.PHRASE
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

回归测试保留早期 Lexer/Parser 错误处理的精确字符串，并直接构造非法 Token 与 Primitive Value。

**关键测试语句**

```python
assert result.total_hits == 1
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

??? note "文件差异：tests/unit/query_parser/test_parser.py"
    ```diff
    diff --git a/tests/unit/query_parser/test_parser.py b/tests/unit/query_parser/test_parser.py
    index 7fbfae514708da6539673e6b3fdbbe319fba30e1..dc98024e2d3af5a6f40e3c8ed9ab6dd7c27f6214 100644
    --- a/tests/unit/query_parser/test_parser.py
    +++ b/tests/unit/query_parser/test_parser.py
    @@ -1,6 +1,6 @@
     import pytest

    -from minilucene import Schema, StoredField, TextField
    +from minilucene import KeywordField, Schema, StoredField, TextField
     from minilucene.query import (
         BooleanClause,
         BooleanQuery,
    @@ -15,6 +15,7 @@ from minilucene.query_parser import QuerySyntaxError, parse_query
     @pytest.fixture
     def schema():
         return Schema(
    +        id=KeywordField(stored=True),
             title=TextField(stored=True),
             body=TextField(stored=True),
             raw=StoredField(),
    @@ -46,6 +47,12 @@ def test_fielded_phrase_is_analyzed_with_positions(schema):
         )


    +def test_single_token_phrase_is_a_term_query(schema):
    +    assert parse_query('id:"doc-1"', schema, "body") == TermQuery(
    +        "id", "doc-1"
    +    )
    +
    +
     def test_fielded_prefix_is_analyzed(schema):
         assert parse_query("title:KAF*", schema, "body") == PrefixQuery(
             "title", "kaf"
    @@ -85,6 +92,12 @@ def test_only_negative_query_remains_explicit(schema):
         )


    +def test_leading_minus_remains_not(schema):
    +    assert parse_query("-term", schema, "body") == BooleanQuery(
    +        (BooleanClause(Occur.MUST_NOT, TermQuery("body", "term")),)
    +    )
    +
    +
     @pytest.mark.parametrize(
         ("source", "message"),
         [
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

回归测试保留早期 Lexer/Parser 错误处理的精确字符串，并直接构造非法 Token 与 Primitive Value。

**关键测试语句**

```python
assert result.total_hits == 1
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Regression Stage 把已发现反例变成 Parsing、Analysis、Scoring 与 Codec Primitive 的永久边界。

### 为什么需要这个机制

单 Token Quote、Hyphenated Term、非法 Token Attribute、零长度统计与 Boolean Varint 暴露文档契约与可执行契约间缺口。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Parser 识别单 Term Phrase 而不丢 Quote Evidence；Lexer 保留 Term 内 Hyphen；Constructor 与 Primitive 在创建时校验 Value。

### 机制板块

#### Query 与 Token 回归机制

Parser 识别单 Term Phrase 而不丢 Quote Evidence；Lexer 保留 Term 内 Hyphen；Constructor 与 Primitive 在创建时校验 Value。

??? note "文件差异：src/minilucene/analysis/model.py"
    ```diff
    diff --git a/src/minilucene/analysis/model.py b/src/minilucene/analysis/model.py
    index d797f1467bd3250ce993c93a664f1a4cc7284942..c94aa04ae65655ba5bf16a225e62a4423b08e840 100644
    --- a/src/minilucene/analysis/model.py
    +++ b/src/minilucene/analysis/model.py
    @@ -1,9 +1,23 @@
    +"""Token attributes shared unchanged across tokenizer and filter stages."""
    +
     from dataclasses import dataclass


     @dataclass(frozen=True, slots=True)
     class Token:
    +    """A term plus its source position and half-open character offsets."""
    +
         term: str
         position: int
         start_offset: int
         end_offset: int
    +
    +    def __post_init__(self) -> None:
    +        if not self.term:
    +            raise ValueError("term must be non-empty")
    +        if self.position < 0:
    +            raise ValueError("position must be non-negative")
    +        if self.start_offset < 0 or self.end_offset < 0:
    +            raise ValueError("offsets must be non-negative")
    +        if self.end_offset < self.start_offset:
    +            raise ValueError("end offset must not precede start offset")
    ```

??? note "文件差异：src/minilucene/analysis/pipeline.py"
    ```diff
    diff --git a/src/minilucene/analysis/pipeline.py b/src/minilucene/analysis/pipeline.py
    index 08bb259d211a6dd4cd144dca631cfbfdcbcaee7c..f196f2fce9a07c60c929b6ca41dc835d9561658b 100644
    --- a/src/minilucene/analysis/pipeline.py
    +++ b/src/minilucene/analysis/pipeline.py
    @@ -1,3 +1,5 @@
    +"""Composable tokenizer/filter pipeline modeled after Lucene TokenStream."""
    +
     from collections.abc import Iterable
     from dataclasses import replace
     from typing import Protocol
    @@ -25,12 +27,17 @@ class StopwordFilter:
             self.stopwords = stopwords

         def apply(self, tokens: Iterable[Token]) -> tuple[Token, ...]:
    +        # Filtering must not renumber surviving positions.  The resulting gap
    +        # records that source text intervened, preventing an exact PhraseQuery
    +        # from matching terms that only become adjacent after stopword removal.
             return tuple(
                 token for token in tokens if token.term not in self.stopwords
             )


     class Analyzer:
    +    """Run one tokenizer followed by ordered, attribute-preserving filters."""
    +
         def __init__(
             self, tokenizer: Tokenizer, filters: tuple[TokenFilter, ...]
         ) -> None:
    ```

??? note "文件差异：src/minilucene/analysis/standard.py"
    ```diff
    diff --git a/src/minilucene/analysis/standard.py b/src/minilucene/analysis/standard.py
    index 5eb10552d786f616dde6ab269d7e6f54e1dd84f4..8fc1e27b0888a47e209b25ee6b3041c216c83325 100644
    --- a/src/minilucene/analysis/standard.py
    +++ b/src/minilucene/analysis/standard.py
    @@ -1,3 +1,5 @@
    +"""Standard and keyword analyzer factories with positional token output."""
    +
     import re

     from minilucene.analysis.model import Token
    @@ -13,6 +15,8 @@ _DEFAULT_STOPWORDS = frozenset({"the"})

     class StandardTokenizer:
         def tokenize(self, text: str) -> tuple[Token, ...]:
    +        # Positions are assigned before filtering.  Keeping this original
    +        # coordinate system is what lets later stopword removal preserve gaps.
             return tuple(
                 Token(
                     term=match.group(),
    ```

??? note "文件差异：src/minilucene/query_parser/lexer.py"
    ```diff
    diff --git a/src/minilucene/query_parser/lexer.py b/src/minilucene/query_parser/lexer.py
    index d62c96b96fbeeaeb7977170b74953cf6b7eeadf5..ef2f4ca491e8c231a380b5a24184dc6bcd6d6c10 100644
    --- a/src/minilucene/query_parser/lexer.py
    +++ b/src/minilucene/query_parser/lexer.py
    @@ -75,13 +75,23 @@ def _lex_phrase(source: str, start: int) -> tuple[LexToken, int]:
         raise QuerySyntaxError("unclosed phrase", start, source)


    +def _is_internal_hyphen(source: str, index: int) -> bool:
    +    return (
    +        index > 0
    +        and index + 1 < len(source)
    +        and source[index - 1].isalnum()
    +        and source[index + 1].isalnum()
    +    )
    +
    +
     def _lex_word(source: str, start: int) -> tuple[LexToken, int]:
         index = start
    -    while (
    -        index < len(source)
    -        and not source[index].isspace()
    -        and source[index] not in ':()-"'
    -    ):
    +    while index < len(source):
    +        character = source[index]
    +        if character.isspace() or character in ':()"':
    +            break
    +        if character == "-" and not _is_internal_hyphen(source, index):
    +            break
             index += 1
         text = source[start:index]
         star = text.find("*")
    ```

??? note "文件差异：src/minilucene/query_parser/parser.py"
    ```diff
    diff --git a/src/minilucene/query_parser/parser.py b/src/minilucene/query_parser/parser.py
    index 2906eb8ebc3e77685823dbde20d0c45f1b0ba1b6..e6434d453c3fada733bc45c1932882d8140d1f81 100644
    --- a/src/minilucene/query_parser/parser.py
    +++ b/src/minilucene/query_parser/parser.py
    @@ -196,6 +196,8 @@ class _Parser:
             if token.kind is TokenKind.PHRASE:
                 self.advance()
                 tokens = self._analyze(field, token.text, token)
    +            if len(tokens) == 1:
    +                return _Parsed(TermQuery(field, tokens[0].term))
                 first_position = tokens[0].position
                 return _Parsed(
                     PhraseQuery(
    ```

??? note "文件差异：src/minilucene/reader.py"
    ```diff
    diff --git a/src/minilucene/reader.py b/src/minilucene/reader.py
    index 3f78c1b6d381b8346a75ee66afc494fd915d14fb..8434c3bf85b4332a790fa50abbc7d59ad3bf77b8 100644
    --- a/src/minilucene/reader.py
    +++ b/src/minilucene/reader.py
    @@ -1,3 +1,11 @@
    +"""Public point-in-time IndexReader with lifecycle and search conveniences.
    +
    +The similarly named ``minilucene.search.reader.ReaderView`` is the internal
    +query-facing base that resolves postings and document addresses.  This module
    +wraps that view with snapshot metadata, segment ownership, closed-state checks,
    +and the user-visible search API.
    +"""
    +
     from collections.abc import Mapping
     from typing import Self

    ```

??? note "文件差异：src/minilucene/search/reader.py"
    ```diff
    diff --git a/src/minilucene/search/reader.py b/src/minilucene/search/reader.py
    index 30fb536a85fa0b7355d0b3f9fcad9c3a53e0be23..9bc3667c78e7d891748392030a5fe59e6bc25ad4 100644
    --- a/src/minilucene/search/reader.py
    +++ b/src/minilucene/search/reader.py
    @@ -1,3 +1,11 @@
    +"""Query-facing reader view over segments, postings, and corpus statistics.
    +
    +This is the low-level search adapter: it resolves global document IDs and
    +offers matching/scoring primitives.  The distinct top-level
    +``minilucene.reader.IndexReader`` adds public lifecycle, snapshot ownership,
    +search convenience methods, and close semantics.
    +"""
    +
     from collections.abc import Mapping
     from dataclasses import dataclass

    ```

??? note "文件差异：src/minilucene/storage/codec.py"
    ```diff
    diff --git a/src/minilucene/storage/codec.py b/src/minilucene/storage/codec.py
    index 2285dda6532220b4c97f50734575780623d55405..a62991fdc384739735795031072bba2c500a9b5b 100644
    --- a/src/minilucene/storage/codec.py
    +++ b/src/minilucene/storage/codec.py
    @@ -1,3 +1,12 @@
    +"""Strict educational encoding for one immutable segment's data files.
    +
    +The layout favors inspectable invariants over Lucene compatibility: terms
    +name contiguous slices in one postings file, while stored documents and norms
    +have explicit frame counts.  Decoders reject non-canonical ordering, gaps,
    +overlap, truncation, and trailing bytes so corrupt input cannot be accepted as
    +a plausible but different index.
    +"""
    +
     import json
     from collections.abc import Mapping

    @@ -78,6 +87,8 @@ def _decode_posting_list(data: bytes) -> tuple[Posting, ...]:
                 )
             )
             previous_doc_id = doc_id
    +    # Consuming the frame exactly prevents a valid posting prefix from hiding
    +    # appended garbage or a second ambiguous interpretation.
         if offset != len(data):
             raise ValueError("trailing bytes in posting list")
         return tuple(postings)
    @@ -135,6 +146,9 @@ class SegmentDataCodec:
             schema_fingerprint: str,
             files: Mapping[str, bytes],
         ) -> SegmentImage:
    +        # Fail closed on both missing and unknown files.  Silently ignoring an
    +        # extra component could open bytes written by a newer/incompatible
    +        # format under the wrong semantics.
             if set(files) != _DATA_FILES:
                 raise ValueError(
                     "segment data requires exactly terms, postings, stored, "
    @@ -168,6 +182,8 @@ class SegmentDataCodec:
             count, offset = decode_uvarint(data, 0)
             entries: list[tuple[str, str, int, int]] = []
             previous_key: tuple[str, str] | None = None
    +        # Requiring a canonical, gap-free partition catches overlap, aliasing,
    +        # reordered slices, and unreferenced bytes before postings are decoded.
             expected_postings_offset = 0
             for _ in range(count):
                 field, offset = _decode_text(
    @@ -209,6 +225,8 @@ class SegmentDataCodec:
                     data[offset:end]
                 )
                 expected_end = end
    +        # Every postings byte must be owned by exactly one sorted term entry;
    +        # otherwise corruption could remain invisible to query results.
             if expected_end != len(data):
                 raise ValueError("trailing bytes in postings file")
             return postings
    ```

??? note "文件差异：src/minilucene/storage/manifest.py"
    ```diff
    diff --git a/src/minilucene/storage/manifest.py b/src/minilucene/storage/manifest.py
    index ae6451ebd86da3135ef5515a692a13453606bd4e..48940bc4320353e5080ac83d6f38811828172a80 100644
    --- a/src/minilucene/storage/manifest.py
    +++ b/src/minilucene/storage/manifest.py
    @@ -1,3 +1,11 @@
    +"""Validate and atomically publish the durable index commit root.
    +
    +Segment files may exist without being committed, but recovery follows only
    +``manifest.json``.  Publishing uses temp-write, file fsync, atomic rename, and
    +directory fsync so a restart observes either the previous complete manifest or
    +the new complete manifest, never a partially written root.
    +"""
    +
     import json
     from dataclasses import asdict, dataclass
     from pathlib import Path
    @@ -33,6 +41,8 @@ class SegmentCommit:

     @dataclass(frozen=True, slots=True)
     class Manifest:
    +    """A validated point-in-time list of committed segment generations."""
    +
         format_version: int
         schema_fingerprint: str
         commit_generation: int
    @@ -106,6 +116,8 @@ class Manifest:


     class ManifestStore:
    +    """Persist the single restart-visible commit root."""
    +
         def __init__(
             self, root: Path, *, fs: FileSystemOps | None = None
         ) -> None:
    @@ -123,6 +135,8 @@ class ManifestStore:
             return manifest

         def write_atomic(self, manifest: Manifest) -> None:
    +        """Durably replace the current manifest without exposing partial JSON."""
    +
             data = json.dumps(
                 {
                     "format_version": manifest.format_version,
    @@ -139,6 +153,10 @@ class ManifestStore:
                 sort_keys=True,
                 separators=(",", ":"),
             ).encode("utf-8")
    +        # Durability needs both levels: fsync the temporary file before rename,
    +        # then fsync the directory so the name replacement itself survives a
    +        # crash.  The manifest is last because it makes earlier segment and
    +        # live-doc files reachable during recovery.
             self.fs.write_bytes(self.temporary_path, data)
             self.fs.fsync_file(self.temporary_path)
             self.fs.replace(self.temporary_path, self.path)
    ```

??? note "文件差异：src/minilucene/writer.py"
    ```diff
    diff --git a/src/minilucene/writer.py b/src/minilucene/writer.py
    index 4b71f3c23361a7c17530c3ca8f114ee3ed0e1423..9dfb562cd1eb87c4ef3c74695ecc091b616ea037 100644
    --- a/src/minilucene/writer.py
    +++ b/src/minilucene/writer.py
    @@ -1,3 +1,12 @@
    +"""Single-writer indexing, NRT snapshots, and durable commit generations.
    +
    +The writer is the lifecycle coordinator: RAM documents become immutable
    +segments, deletions become separately versioned live-doc masks, and only a
    +manifest replacement makes that state recoverable after restart.  Unlike
    +Lucene's IndexWriter, this teaching version has one RAM buffer and no DWPT,
    +rollback, prepareCommit, automatic merge policy, or stale-lock recovery.
    +"""
    +
     import json
     import os
     from dataclasses import dataclass
    @@ -46,6 +55,8 @@ class WriterState(StrEnum):


     class IndexWriter:
    +    """Own one mutable indexing session and its process-local segment refs."""
    +
         def __init__(
             self,
             index: "Index",
    @@ -56,6 +67,10 @@ class IndexWriter:
             self.flush_policy = flush_policy or FlushPolicy()
             self._lock_path = Path(index.path) / ".writer.lock"
             self._state = WriterState.OPEN
    +        # O_EXCL makes writer admission an atomic filesystem decision rather
    +        # than a racy "exists then create" check.  The PID is diagnostic only:
    +        # a crash strands this file because MiniLucene has no safe stale-lock
    +        # validation or force-unlock API.
             try:
                 descriptor = os.open(
                     self._lock_path,
    @@ -152,9 +167,13 @@ class IndexWriter:
             return doc_id

         def flush(self) -> SegmentDescriptor | None:
    +        """Freeze live RAM documents into a new, still-uncommitted segment."""
    +
             self._ensure_open()
             if self.buffered_document_count == 0:
                 return None
    +        # Buffer deletions never need an on-disk live-doc generation: compact
    +        # the live subset while doc IDs are still private to the RAM buffer.
             compacted = RamIndexBuilder(self.index.schema)
             for doc_id in sorted(self._buffer_live_docs):
                 compacted.add_document(dict(self._buffer.documents[doc_id]))
    @@ -183,7 +202,12 @@ class IndexWriter:
             return descriptor

         def refresh(self) -> IndexReader:
    +        """Return a point-in-time reader without publishing a restart root."""
    +
             self._ensure_open()
    +        # Flushing first gives the new reader immutable inputs.  Older readers
    +        # retain their own segment/mask tuple, so refresh never mutates a view
    +        # that a caller may still be using.
             self.flush()
             segments = tuple(
                 self._segment_store.open(
    @@ -288,6 +312,8 @@ class IndexWriter:
         def merge(
             self, segment_generations: tuple[int, ...] | list[int]
         ) -> SegmentDescriptor:
    +        """Replace selected generations in writer state with one live-only segment."""
    +
             self._ensure_open()
             selected = tuple(segment_generations)
             if len(selected) < 2:
    @@ -324,6 +350,8 @@ class IndexWriter:
             )
             descriptor = self._segment_store.publish(image)

    +        # Keep the replacement at the earliest selected slot so global doc-ID
    +        # order remains deterministic even when non-adjacent segments merge.
             insertion_index = min(
                 self._segment_generations.index(item)
                 for item in ordered_selected
    @@ -359,8 +387,13 @@ class IndexWriter:
             return descriptor

         def commit(self) -> Manifest:
    +        """Publish all current segments and deletion masks as one commit."""
    +
             self._ensure_open()
             self.flush()
    +        # Reopen every referenced segment before publishing the manifest.
    +        # A commit root must fail closed rather than name bytes that cannot be
    +        # fully validated with the current schema.
             for generation in self._segment_generations:
                 self._segment_store.open(
                     generation, self.index.schema.fingerprint
    @@ -376,6 +409,9 @@ class IndexWriter:
                 metadata = pending_metadata[generation]
                 if live_docs != frozenset(range(image.max_doc)):
                     if generation in self._dirty_live_docs:
    +                    # A segment is immutable, so each changed deletion view is
    +                    # a fresh live-doc generation.  Existing readers keep the
    +                    # prior mask while this commit can name the new one.
                         live_generation = (
                             metadata[0] + 1 if metadata is not None else 1
                         )
    @@ -410,6 +446,9 @@ class IndexWriter:
                         SegmentCommit(segment_generation=generation)
                     )

    +        # Segment and live-doc files are durable before this point.  The
    +        # atomic manifest replacement below is the sole publication boundary:
    +        # a crash before it leaves only ignorable orphan generations.
             manifest = Manifest.next_from(
                 current,
                 segments=tuple(segment_commits),
    ```

**是什么，为什么现在需要**

Regression Stage 把已发现反例变成 Parsing、Analysis、Scoring 与 Codec Primitive 的永久边界。

**在运行时做什么**

Parser 识别单 Term Phrase 而不丢 Quote Evidence；Lexer 保留 Term 内 Hyphen；Constructor 与 Primitive 在创建时校验 Value。

**关键语句理解**

Validation 必须位于最早的所有权边界，使每个下游调用方收到的 Token、Score Denominator 或 Integer 已经有效。

#### 包、Fixture 与工程支撑

保持包导出、测试语料、依赖与运行环境可复现。

??? note "支撑文件差异（1 个文件）"
    **`src/minilucene/analysis/__init__.py`**

    ```diff
    diff --git a/src/minilucene/analysis/__init__.py b/src/minilucene/analysis/__init__.py
    index f1339dd84438ed95df6c8c13fe19ac468aeda6be..0ed95edfa564c232562342e1adf2960cc71780ee 100644
    --- a/src/minilucene/analysis/__init__.py
    +++ b/src/minilucene/analysis/__init__.py
    @@ -1,3 +1,5 @@
    +"""Public analyzers and token attributes for the indexing/query pipeline."""
    +
     from minilucene.analysis.model import Token
     from minilucene.analysis.standard import KeywordAnalyzer, StandardAnalyzer

    ```


### 验证证据

运行 `uv run pytest -q $(cat journey/stages/29-query-regressions/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

Validation 必须位于最早的所有权边界，使每个下游调用方收到的 Token、Score Denominator 或 Integer 已经有效。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 9 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/09-query-language.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/29-query-regressions/stage.patch)
