# Chapter 2: The Analysis Chain

A lexical index cannot use raw prose directly. It needs a repeatable rule that
turns both documents and queries into comparable terms. That rule is an
analysis chain: a tokenizer discovers token boundaries and attributes, then
ordered filters transform or remove tokens. The deceptively difficult part is
preserving information that later query types need. MiniLucene's smallest but
most important example is the position gap left by a removed stopword.

## Learning objectives

By the end of this chapter, you can:

1. distinguish a tokenizer from a token filter;
2. read a MiniLucene `Token` as term, position, and source offsets;
3. explain why stopword removal must not renumber positions;
4. predict the difference between standard and keyword analysis; and
5. verify phrase behavior using an in-memory index.

## Mechanism: attributes survive the pipeline

`src/minilucene/analysis/model.py` defines the immutable `Token`. Its
`__post_init__` validates that the term is non-empty, the position and offsets
are non-negative, and the end offset is not before the start. These checks make
bad analyzer output fail near its source.

The pipeline abstractions live in `src/minilucene/analysis/pipeline.py`.
`Tokenizer.tokenize` produces a tuple of tokens; `TokenFilter.apply` consumes an
iterable and returns another tuple. `Analyzer.analyze` runs exactly one
tokenizer and then each configured filter in order:

```python
def analyze(self, text: str) -> tuple[Token, ...]:
    tokens = self.tokenizer.tokenize(text)
    for token_filter in self.filters:
        tokens = token_filter.apply(tokens)
    return tokens
```

This is composition, not an inheritance tree. A filter can change one
attribute while preserving the others. `LowercaseFilter.apply` uses
`dataclasses.replace` to change only `term`; position and offsets survive.
`StopwordFilter.apply` removes matching tokens but deliberately returns the
survivors unchanged.

The standard implementation is in
`src/minilucene/analysis/standard.py`. `StandardTokenizer.tokenize` applies the
Unicode-aware regular expression `\w+`. For every match it records:

- `term`: the exact matched substring before filtering;
- `position`: the match's ordinal among all tokenizer output;
- `start_offset`: the Python string index where the match begins; and
- `end_offset`: the exclusive index where it ends.

`StandardAnalyzer` composes that tokenizer with lowercase and stopword filters.
The default stopword set contains only `"the"`, keeping the educational behavior
easy to inspect. `KeywordAnalyzer`, by contrast, uses `KeywordTokenizer` and no
filters. A non-empty input becomes one token at position zero whose offsets span
the full string. It is appropriate for identifiers and exact labels, not prose.

### Why the gap matters

Consider `fast the search`. The tokenizer assigns positions 0, 1, and 2.
Lowercasing changes no coordinates. Stopword filtering removes the token at
position 1 but leaves `fast@0` and `search@2`. If the filter compressed the
survivors to positions 0 and 1, the index would claim that `fast` and `search`
were adjacent even though another source token intervened.

That false adjacency would make an exact phrase query for `"fast search"`
match `fast the search`. MiniLucene prevents it at analysis time. In
`src/minilucene/index/memory.py`, `RamIndexBuilder.add_prepared` groups each
term's positions and stores them in `Posting.positions`. The phrase matcher can
therefore require the expected consecutive offsets instead of relying on term
co-occurrence.

Offsets solve a different problem. They locate token text in the original
stored string. `LowercaseFilter` may turn `Fast` into the searchable term
`fast`, but the offsets still point to characters 0 through 4 of `Fast`.
MiniLucene's highlighter can re-analyze a stored text field, select matching
spans, escape the original content, and wrap the correct original characters.
Positions answer “where in token order?”; offsets answer “where in the source
string?” They are not interchangeable.

### Document analysis and query analysis

`RamIndexBuilder.prepare_document` in
`src/minilucene/index/memory.py` calls the private `_analyze` function for each
indexed field. `_analyze` selects `StandardAnalyzer` or `KeywordAnalyzer` from
the schema's `analyzer_name`. This binds analysis to the field contract.

The query parser also needs compatible normalization. Query text is parsed into
a query AST and the matching layer compares its normalized terms with indexed
terms. The key invariant is not “run any tokenizer everywhere”; it is “document
and query terms for one field must inhabit the same vocabulary.” An exact
keyword field and a standard text field intentionally inhabit different
vocabularies.

### Analyzer choice is part of the index contract

Analysis cannot be changed casually after documents have been indexed. Suppose
old documents were lowercased but new queries retained case. A query for
`FAST` would look for a dictionary entry that was never written. Suppose a
later analyzer began removing another stopword: old and new segments would
encode phrase positions under different rules. MiniLucene reduces that drift
by persisting the complete field definitions in `schema.json` and checking
`Schema.fingerprint` in `Index.open`.

The fingerprint proves equality of declared field configuration, not equality
of arbitrary analyzer code. Built-in analyzer names currently map to fixed
factories in `_analyze`; there is no plugin registry or analyzer-version field.
If those implementations changed incompatibly without a format or schema
change, an old index could be queried under new behavior. That simplification
teaches a production lesson: analyzer identity includes configuration and
implementation version, not merely a human name.

Multi-valued fields expose another position issue in real systems. Lucene can
insert a position gap between successive values so a phrase does not
accidentally span two values. MiniLucene accepts one string per field, so it has
no multi-value gap policy. The same coordinate-system idea applies, but that
case is outside this project's contract.

Analysis is usually selected per field because identifiers, titles,
natural-language bodies, paths, and code have different vocabularies. Applying
one supposedly smart analyzer everywhere can destroy exact identifiers or fail
to normalize prose. MiniLucene offers only two choices, but their contrast
teaches the decision.

### What this implementation does not claim

The regex tokenizer recognizes Unicode word characters, but it is not a full
linguistic segmenter. Languages without whitespace boundaries, stemming,
lemmatization, synonyms, decompounding, and domain-specific normalization need
additional components. Even English punctuation behavior follows Python's
regular expression semantics rather than Lucene's StandardTokenizer rules.
The pipeline boundary makes extensions conceivable; it does not make the
default analyzer universally correct.

## Compared with Apache Lucene

Apache Lucene models analysis with `Analyzer`, `Tokenizer`, `TokenStream`, and
token attributes such as `CharTermAttribute`, `PositionIncrementAttribute`, and
`OffsetAttribute`. A removed token is commonly represented through the next
surviving token's position increment. Lucene analyzers are reusable streaming
components and include rich standard, language, synonym, and normalization
support.

MiniLucene keeps materialized tuples and absolute positions. This is easier to
read but allocates all tokens at once. Its `StandardTokenizer` is a small
`\w+` regex, its default stopword list is one word, and its schema supports
only the built-in standard and keyword analyzer names. It does not reproduce
Lucene's Unicode Text Segmentation behavior or analysis SPI. The field boost is
also fixed in MiniLucene's schema, whereas modern Lucene favors query-time
boosting. Consult the [Lucene mapping](../lucene-mapping.md) and the analysis,
phrase, and highlighting rows of the
[behavior matrix](../behavior-matrix.md).

## Hands-on experiment: observe the gap

Run from the repository root:

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

Measured output:

```text
[('fast', 0, 0, 4), ('search', 2, 9, 15)]
1 [{'body': 'fast search'}]
```

Three details deserve attention. `THE` becomes the lowercase stopword before it
is removed. `search` retains position 2, proving the gap survived. Its offsets
still point to the original source substring beginning at character 9. The
phrase matches only the genuinely adjacent second document.

For a focused regression check, run:

```bash
uv run --offline pytest -q tests/unit/analysis/test_pipeline.py \
  tests/contract/test_query_matching.py
```

The repository's measured result is:

```text
18 passed in 0.08s
```

Timing is machine-dependent; the pass count is the acceptance signal.

## Exercises

1. **Understanding:** Why is lowercasing allowed to preserve offsets even when
   the replacement term may have a different representation?

    ??? note "Reference answer"
        Offsets describe the original source span, not indexes into the
        normalized term. They are later used to recover/highlight source text.

2. **Understanding:** Would storing only term frequency be enough for exact
   phrase matching?

    ??? note "Reference answer"
        No. Frequency says how often a term occurs but not whether terms occur
        at consecutive compatible positions. Phrase matching needs positions.

3. **Hands-on:** Run the script with `"Fast, search!"` and predict the tokens
   before executing. Acceptance: two lowercase tokens appear at positions 0
   and 1, with offsets matching the original words.

    ??? note "Reference answer"
        The expected tuple is
        `[('fast', 0, 0, 4), ('search', 1, 6, 12)]`. Punctuation is a separator
        and is not included in either offset span.

4. **Hands-on:** Without changing `src/`, construct
   `StandardAnalyzer(stopwords=frozenset({"fast"}))` and analyze
   `"fast reliable search"`. Acceptance: `reliable` stays at position 1 and
   `search` at 2.

    ??? note "Reference answer"
        Import `StandardAnalyzer`, pass the custom set, and print the tokens.
        The result demonstrates that removal of the first token does not shift
        the remaining coordinate system.

## Summary

Analysis is a controlled loss of information: punctuation and stopwords may
disappear, case may normalize, but positions and source offsets survive because
later mechanisms need them. MiniLucene's tuple pipeline makes that contract
visible. The next chapter follows those analyzed tokens into the RAM inverted
index, where terms become posting lists and document lengths become scoring
norms.
