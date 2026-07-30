# Chapter 1: Meet MiniLucene

MiniLucene is a small, executable explanation of lexical search. It is not a
Python binding for Apache Lucene and does not copy Lucene's public API or disk
format. Instead, it keeps the mechanisms that make a search engine intelligible:
a schema decides what a field means, an analyzer turns text into positioned
tokens, an inverted index maps terms to documents, BM25 ranks matches, immutable
segments make persistence manageable, and a manifest defines the recoverable
index.

That scope is useful for learning. Reading production Lucene first means meeting
decades of compatibility constraints, specialized codecs, iterator hierarchies,
concurrency, and performance engineering at the same time as the basic idea.
MiniLucene lets us follow one complete path before comparing it with that larger
system. The trade-off is explicit: success here proves the teaching kernel's
contract, not Lucene compatibility or production readiness.

## Learning objectives

By the end of this chapter, you can:

1. explain why MiniLucene is a reference implementation rather than a Lucene
   clone;
2. create a disk index from a schema with the local CLI;
3. add JSON documents and execute a fielded/phrase query;
4. identify the responsibilities of analysis, indexing, persistence, and
   search; and
5. distinguish indexed, stored, tokenized, and positional field properties.

## Mechanism: from JSON to a ranked hit

The public disk-index boundary is `src/minilucene/index/directory.py`. The
`Index.create` class method writes an immutable schema and creates the initial
manifest. `Index.open` reads both artifacts and checks their fingerprints
before returning an index. This is already an important design choice: a caller
does not reopen arbitrary segment directories. It reopens one validated root.

A schema is more than a list of field names. In
`src/minilucene/schema.py`, `TextField`, `KeywordField`, and `StoredField`
construct different `FieldType` values:

```python
def TextField(*, stored: bool = False, boost: float = 1.0) -> FieldType:
    return FieldType(
        indexed=True, tokenized=True, stored=stored,
        store_positions=True, boost=boost, analyzer_name="standard",
    )
```

An indexed field participates in lookup. A stored field can be returned in a
hit. Those properties are independent. `TextField` is analyzed into terms and
positions; `KeywordField` indexes the complete string as one exact term;
`StoredField` is retrievable but not searchable. `Schema.__init__` sorts the
field definitions, serializes their properties canonically, and computes a
SHA-256 fingerprint. `Index.open` uses that fingerprint to reject a mismatched
schema instead of guessing how existing bytes should be interpreted.

The CLI is deliberately thin. In `src/minilucene/cli.py`, `_create` parses the
schema and calls `Index.create`; `_add` calls `Index.open`, obtains an
`IndexWriter`, invokes `IndexWriter.add_document` for every JSON document, and
then commits; `_search` opens an `IndexReader` and calls
`IndexReader.search_text`. The command-line layer does not implement separate
search semantics.

The write path continues in `src/minilucene/writer.py`.
`IndexWriter.add_document` asks `RamIndexBuilder.prepare_document` to validate
and analyze the document, then adds the prepared representation to the RAM
buffer. In `src/minilucene/index/memory.py`,
`RamIndexBuilder.prepare_document` separates stored values from analyzed
values. `RamIndexBuilder.add_prepared` groups positions by term and produces a
posting containing a local document ID, term frequency, and positions.
`IndexWriter.commit` flushes the buffer, validates every segment, and atomically
publishes a new manifest. Chapter 3 examines the RAM representation; Chapters 4
and 5 examine the disk and visibility boundaries.

The query path starts with text but does not stay text. `IndexReader.search_text`
in `src/minilucene/reader.py` delegates to
`IndexSearcher.search_text` in `src/minilucene/search/searcher.py`. The query
lexer and parser construct a closed query AST; matching and scoring operate on
that AST. The CLI output contains `total_hits` separately from the bounded hit
list, along with score, segment generation, segment-local document ID, stored
fields, and optional highlights.

The complete first-chapter model is:

```text
schema + JSON document
        │
        ▼
validation → analysis → RAM postings → immutable segment → manifest
                                                        │
query text → query AST → matching → BM25 → Top-K hits ◀─┘
```

Each arrow names a boundary we can inspect and test. There is no server hidden
behind the CLI: MiniLucene is direct-first and local-only.

### How to read the rest of the book

Chapters 2 through 4 follow the write path downward. Chapter 2 studies token
attributes and phrase correctness. Chapter 3 builds postings and scoring norms
in RAM. Chapter 4 turns the frozen representation into strict disk frames.
Chapters 5 through 7 then study time: NRT visibility, deletion generations,
reader snapshots, and crash-atomic manifest publication. Chapters 8 and 9 move
back to the read path for BM25, bounded collection, and the query language.
Chapter 10 closes the loop with explicit merge and a roadmap into real Lucene.

While reading, keep three questions separate. First, **what logical fact is
represented?** A posting means that a term occurred in a field of a local
document. Second, **who can currently observe it?** A writer buffer, refresh
reader, and manifest reader may disagree by design. Third, **what evidence
supports the claim?** A source function describes the mechanism, while a
focused test or reproduced command demonstrates behavior. Neither a familiar
class name nor a diagram alone proves runtime semantics.

The CLI is convenient for end-to-end experiments, but later chapters often use
the direct Python API. Direct calls expose snapshot objects, posting contents,
and generations without parsing presentation output. Both routes share the same
implementation underneath. When an API looks unlike Lucene, compare
responsibilities rather than spelling: ask which object owns schema validation,
segment publication, reader lifetime, and query execution.

Treat each chapter's measured output as a reproducible observation, not a
golden protocol transcript. File paths and elapsed time can vary; semantic
fields, counts, generations, and explicit errors are the acceptance criteria.
That distinction keeps the tutorial useful across machines without weakening
the behavior contract that every command is meant to demonstrate.

## Compared with Apache Lucene

Apache Lucene expresses comparable concepts through `IndexWriter`,
`IndexWriterConfig`, `Directory`, `Analyzer`, `IndexSearcher`, `QueryParser`,
`Document`, and field types. A real application normally uses those Java APIs
or a service built above them. Lucene's codecs, segment metadata, query
execution, merge scheduling, and compatibility promises are substantially more
sophisticated.

MiniLucene preserves the conceptual separation but intentionally changes the
surface and implementation. Its JSON CLI is a local adapter, its schema is
frozen at index creation, its file format is educational rather than Lucene
compatible, and it has no TCP/HTTP service. It also lacks numeric fields, doc
values, range queries, faceting, vector search, automatic merge scheduling, and
Lucene's document-at-a-time iterator stack. These are declared limitations, not
features implied by the project name. See the repository's
[MiniLucene-to-Lucene mapping](../lucene-mapping.md) and
[executable behavior matrix](../behavior-matrix.md) for the exact supported and
excluded rows.

## Hands-on experiment: build the first index

Run from the repository root. `UV_CACHE_DIR` keeps `uv` writable in restricted
environments; it does not change MiniLucene behavior.

```bash
export UV_CACHE_DIR=/tmp/minilucene-uv-cache
LAB=$(mktemp -d /tmp/minilucene-tutorial-ch1.XXXXXX)
printf '%s\n' '{"fields":{"id":{"indexed":true,"tokenized":false,"stored":true,"store_positions":false,"boost":1.0,"analyzer_name":"keyword"},"title":{"indexed":true,"tokenized":true,"stored":true,"store_positions":true,"boost":2.0,"analyzer_name":"standard"},"body":{"indexed":true,"tokenized":true,"stored":true,"store_positions":true,"boost":1.0,"analyzer_name":"standard"}}}' > "$LAB/schema.json"
printf '%s\n' '{"id":"doc-1","title":"Search systems","body":"An inverted index makes search fast"}' > "$LAB/doc1.json"
printf '%s\n' '{"id":"doc-2","title":"Storage systems","body":"A commit publishes durable state"}' > "$LAB/doc2.json"
uv run --offline minilucene create "$LAB/index" --schema "$LAB/schema.json"
uv run --offline minilucene add "$LAB/index" "$LAB/doc1.json" "$LAB/doc2.json"
uv run --offline minilucene search "$LAB/index" \
  'title:search OR body:"durable state"' --default-field body --top-k 10
```

Measured output (the first path contains your generated suffix):

```text
{"index":"/tmp/minilucene-tutorial-ch1.<suffix>/index","status":"created"}
{"added":2,"commit_generation":1}
{"hits":[{"highlights":{},"local_doc_id":1,"score":1.4398422119785987,"segment_generation":1,"stored_fields":{"body":"A commit publishes durable state","id":"doc-2","title":"Storage systems"}},{"highlights":{},"local_doc_id":0,"score":1.3862943611198906,"segment_generation":1,"stored_fields":{"body":"An inverted index makes search fast","id":"doc-1","title":"Search systems"}}],"total_hits":2}
```

Both documents match different Boolean branches. The title field's boost and
the phrase contribution make the second document rank slightly higher. Scores
are deterministic for this exact corpus and implementation, but they are not a
cross-engine compatibility promise.

There is no TCP experiment in this chapter. MiniLucene exposes no socket
server, a boundary recorded in the behavior matrix; therefore no network result
is marked as tested or as pending runtime verification.

## Exercises

1. **Understanding:** Why is `stored=True` insufficient to make a field
   searchable?

    ??? note "Reference answer"
        Storage controls retrieval of the original value. Searchability is
        controlled independently by `indexed`; tokenization and positions then
        determine which queries are meaningful.

2. **Understanding:** Which artifact is the restart root: a newly written
   segment directory or `manifest.json`?

    ??? note "Reference answer"
        `manifest.json`. A flushed segment not named by the committed manifest
        is not visible after reopen.

3. **Hands-on:** Add a third document whose body contains `durable state`, then
   repeat the search. Do not edit `src/`. Acceptance: the `add` command reports
   `added:1`, the next commit generation is `2`, and `total_hits` becomes `3`.

    ??? note "Reference answer"
        Create another JSON file under `$LAB`, run
        `uv run --offline minilucene add "$LAB/index" "$LAB/doc3.json"`, and
        rerun the same search. The exact ordering depends on the third
        document's lengths and matching fields, but the acceptance counts must
        hold.

4. **Hands-on:** Change only the schema input so `id` is not stored, build a
   new index, and confirm that a hit omits `id`. Acceptance: `id` remains
   searchable as a keyword but is absent from `stored_fields`.

    ??? note "Reference answer"
        Set the `id` field's `"stored"` property to `false`, create a fresh
        index, add a document, and search `id:doc-1`. This demonstrates that
        indexing and storage are orthogonal without changing project source.

## Summary

MiniLucene turns a schema and documents into a validated, committed search
snapshot, then turns query text into ranked hits. Its value is the visible chain
of mechanisms, not compatibility by naming. The next chapter zooms into the
first transformation in that chain: how text becomes terms, positions, and
offsets without destroying phrase semantics.
