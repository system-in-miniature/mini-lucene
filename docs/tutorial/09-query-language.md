# Query Language

## Learning objectives

By the end of this chapter, you will be able to:

1. trace a query string through lexer, recursive-descent parser, analyzer, and rewrite;
2. explain field qualification, operator precedence, implicit OR, and unary negation;
3. predict the AST for quoted single-token phrases and internal hyphens;
4. explain why prefix expansion is sorted, bounded, and fail-fast; and
5. identify the syntax and query types intentionally absent from MiniLucene.

## 1. The language ends at a closed AST

`IndexReader.search_text()` and `IndexSearcher.search_text()` are adapters.
The latter, in `src/minilucene/search/searcher.py`, calls
`src/minilucene/query_parser/parser.py`, `parse_query()`, then sends the
resulting `Query` object through the same `search()` path used by programmatic
queries.

The accepted AST is defined in `src/minilucene/query/model.py`: term, exact
phrase, prefix, match-all, and Boolean queries with `MUST`, `SHOULD`, and
`MUST_NOT` clauses. The parser cannot manufacture arbitrary executable code or
unknown query subclasses. This closed boundary makes later matching and
scoring exhaustive over known dataclasses.

The textual pipeline is:

```text
source string
  → lex(): offset-preserving LexToken tuple
  → _Parser: precedence and field scope
  → field analyzer: searchable terms and phrase positions
  → closed Query AST
  → reader.rewrite(): bounded multi-term expansion
  → DAAT matching/scoring or explicit oracle fallback
```

Parsing and rewriting are separate. `kaf*` first becomes a `PrefixQuery`; only
a reader snapshot knows which indexed terms currently start with `kaf`.

## 2. Lexing preserves evidence for errors

`src/minilucene/query_parser/lexer.py`, `lex()` emits tokens with `kind`,
decoded `text`, and half-open source offsets `start` and `end`. It recognizes
words, phrases, prefixes, `AND`, `OR`, `NOT`, colon, parentheses, and unary
minus. Operators are case-insensitive when an entire word equals an operator.

`_lex_phrase()` removes the quote delimiters and permits only two escapes:
`\"` and `\\`. An unclosed phrase or unsupported escape raises
`QuerySyntaxError` at the relevant source offset. These offsets let
`src/minilucene/query_parser/errors.py`, `QuerySyntaxError` render the source
and a caret instead of returning a context-free “bad query.”

The hyphen rule is deliberately narrow.
`_is_internal_hyphen()` keeps `-` inside a word only when both neighboring
characters are alphanumeric. Therefore:

```text
id:doc-1   → WORD("doc-1")
-slow      → MINUS, WORD("slow")
a--b       → WORD("a"), MINUS, MINUS, WORD("b")
```

This preserves keyword identifiers such as `doc-1` while retaining unary
negation. It is a MiniLucene grammar choice, not a promise of full Lucene query
parser compatibility.

`_lex_word()` recognizes exactly one trailing `*` after a non-empty prefix.
Leading, embedded, or repeated asterisks fail with an offset. There is no `?`,
general wildcard, regex, fuzzy suffix, range bracket, proximity suffix, or
boost syntax.

## 3. Recursive descent fixes precedence

`src/minilucene/query_parser/parser.py`, `_Parser.parse()` delegates through:

```text
parse_or()
  └── parse_and()
        └── parse_unary()
              └── parse_primary()
```

Deeper functions bind more tightly. Consequently `a OR b AND c` means
`a OR (b AND c)`. Parentheses invoke `parse_or()` recursively and override the
default. Adjacent primaries without an explicit operator are collected by
`parse_or()`, so `kafka rabbit` is implicit OR.

`parse_unary()` consumes any run of `NOT` or `-` and toggles prohibition.
One negation produces a prohibited result; two cancel. When a prohibited
child enters a Boolean group, it becomes a `MUST_NOT` clause. A top-level
negative query is materialized as a Boolean query containing only that
`MUST_NOT`; MiniLucene's frozen Boolean matching semantics then define its
result.

This is a good place to resist importing assumptions from another parser.
“Only negative” handling, implicit OR, and repeated unary negation are part of
MiniLucene's own AST contract. The parser does not rewrite user intent into an
unstated match-all query at the text layer. Instead, it preserves the explicit
prohibited structure and lets `match_boolean()` in
`src/minilucene/query/match.py` apply the repository's documented set
semantics. Tests should therefore assert AST shape as well as final hits when
grammar changes.

Field qualification is handled in `parse_primary()`. A `WORD` followed by a
colon must name a schema field, and that field must be indexed. The selected
field applies to the immediately following primary; `title:(kafka rabbit)`
passes `title` into the parenthesized recursive parse. Stored-only fields fail
at the colon instead of yielding a silent no-match.

Syntax failures are also part of the API. `_Parser.syntax()` attaches the
current token's original offset, and validation errors for unknown or
non-indexed fields point to the field occurrence. Because analysis can reject
text that produces no searchable terms, a syntactically well-formed token may
still be an invalid query. Keeping lexing, field validation, and analysis
errors distinct makes a CLI or UI capable of showing the user what to change.

## 4. Query text uses the field's analyzer

The parser does not lowercase by hand. `_Parser._analyze()` selects
`StandardAnalyzer` or `KeywordAnalyzer` from the field's frozen schema
metadata. This makes query terms and indexed terms meet under the same basic
analysis contract.

A word that analyzes to several tokens becomes an implicit SHOULD Boolean
query. A phrase keeps analyzed positions. For example, with the standard
analyzer's stopword behavior:

```text
body:"distributed the system"
→ PhraseQuery("body", ("distributed", "system"), positions=(0, 2))
```

The gap prevents a phrase matcher from pretending the retained terms were
adjacent. If a quoted value analyzes to exactly one token, `parse_primary()`
returns a `TermQuery`, not a one-term `PhraseQuery`. This single-token phrase
downgrade avoids requiring positions on a `KeywordField`, so
`id:"doc-1"` works as the exact `TermQuery("id", "doc-1")`.

A prefix must analyze to exactly one token. `title:KAF*` becomes the normalized
`PrefixQuery("title", "kaf")`. A prefix whose analysis is empty or produces
multiple terms fails rather than choosing one silently.

## 5. Prefix rewrite is bounded semantic work

`src/minilucene/search/rewrite.py`, `rewrite_query()` recursively visits
Boolean children. For a prefix, `_expand_prefix()` asks the reader for sorted
terms through `ReaderView.terms_with_prefix()`, starts with `bisect_left`, and
collects consecutive terms sharing the prefix.

Three outcomes are explicit:

1. zero matching terms becomes a Boolean query that can match nothing;
2. one term becomes a `TermQuery`; and
3. several terms become SHOULD clauses over `TermQuery` objects.

`max_terms` must be a positive integer. If another matching term exists after
the limit has been filled, `_expand_prefix()` raises
`TooManyTermsError`; it does not truncate. Truncation would silently change
query meaning according to dictionary order. Fail-fast makes cost and
correctness visible to the caller.

`IndexReader.rewrite()` in `src/minilucene/reader.py` supplies a default limit
of 1024. The limit bounds expansion size, not total search cost. Expanded
term/Boolean trees execute through DAAT, but every match is still scored and
the system has no WAND/MaxScore pruning. See [Chapter 11](11-daat.md).

## 6. Contrast with Apache Lucene

The transferable architecture is a parser producing `Query` objects, analysis
using field rules, and multi-term queries being rewritten against an index
reader. Apache Lucene also has query subclasses, Boolean occurrence rules, and
multiple rewrite strategies.

MiniLucene's language is intentionally much smaller:

- no phrase slop or proximity syntax;
- no fuzzy, arbitrary wildcard, regular-expression, range, numeric, or date
  queries;
- no query-time boosts, field groups with production parser edge cases, or
  pluggable parser configuration;
- no `MultiTermQuery` rewrite selection such as constant-score or
  top-terms-scoring strategies; and
- no numeric points, doc values, sorting, faceting, or aggregations behind the
  grammar.

Even familiar surface syntax can differ, especially escaping and hyphens.
Treat MiniLucene's query language as its own closed teaching grammar. The
[query lexer](../behavior-matrix.md), query parser, and prefix rewrite rows in
the behavior matrix define its executable contract. The query model row in
the [MiniLucene-to-Lucene mapping](../lucene-mapping.md) lists the missing
production query families.

## 7. Hands-on experiment: see tokens, ASTs, and rewrite

Run from the repository root:

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

Measured output:

```text
[('WORD', 'title'), ('COLON', ':'), ('PREFIX', 'KAF'), ('AND', 'AND'), ('WORD', 'id'), ('COLON', ':'), ('PHRASE', 'doc-1'), ('EOF', '')]
BooleanQuery(clauses=(BooleanClause(occur=<Occur.MUST: 'MUST'>, query=PrefixQuery(field='title', prefix='kaf')), BooleanClause(occur=<Occur.MUST: 'MUST'>, query=TermQuery(field='id', term='doc-1'))))
BooleanQuery(clauses=(BooleanClause(occur=<Occur.MUST: 'MUST'>, query=TermQuery(field='title', term='kafka')), BooleanClause(occur=<Occur.MUST: 'MUST'>, query=TermQuery(field='id', term='doc-1'))))
PhraseQuery(field='body', terms=('distributed', 'system'), positions=(0, 2), slop=0)
```

The lexer preserves the original uppercase prefix text. The parser applies
the title analyzer and normalizes it to lowercase. Rewrite then consults the
reader's actual dictionary and replaces the prefix with `kafka`.

To observe the fail-fast cap:

```bash
UV_CACHE_DIR=/tmp/minilucene-uv-cache uv run pytest tests/contract/test_prefix_rewrite.py -q
```

Measured output:

```text
6 passed in 0.04s
```

## 8. Exercises

### Exercise 1 — parsing

Without running code, parenthesize `a b AND NOT c OR d` according to the
parser's precedence and implicit operator.

??? note "Reference answer"

    Implicit adjacency is handled at the OR level, while AND binds tighter:
    `a OR (b AND (NOT c)) OR d`. The exact AST uses SHOULD clauses at the outer
    level, and the `b`/prohibited-`c` group uses MUST and MUST_NOT clauses.

### Exercise 2 — correctness

Why does prefix overflow raise instead of returning the first `max_terms`
alphabetical terms?

??? note "Reference answer"

    Returning a prefix of the dictionary would silently change the set of
    matching documents and make results depend on term order. The hard failure
    preserves semantic honesty and makes the caller narrow the prefix or
    explicitly raise the bound.

### Exercise 3 — hands-on code change

Do not edit `src/`. Copy the lexer and parser modules to a scratch directory
and design support for `+term` as an explicit MUST operator. Include token,
precedence, and AST changes plus three examples.

Acceptance: the scratch diff must preserve internal hyphens and source offsets,
reject a bare trailing `+`, and specify how `+a b` differs from `a b`. Run your
scratch tests outside the repository source tree.

??? note "Reference answer"

    Add a `PLUS` token emitted for standalone `+`, consume it in
    `parse_unary()`, and carry an explicit required flag distinct from
    `prohibited`. Boolean materialization must translate required children to
    MUST and ordinary adjacent children to SHOULD. Tests should cover `+a b`,
    `title:+kafka`, and a syntax error for `+` at EOF. This is a design
    exercise; production Lucene parser compatibility requires more rules than
    this patch.

## Summary

MiniLucene turns text into an offset-preserving token stream, applies fixed
recursive-descent precedence, analyzes terms by field, and emits a closed AST.
Reader-dependent prefix rewrite is a later, bounded stage that fails rather
than truncating semantics. Chapter 10 follows explicit merge; Chapter 11 then
returns to the rewritten AST and executes it through DAAT cursors.
