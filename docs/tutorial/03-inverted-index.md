# Chapter 3: The Inverted Index

A document collection is arranged for writing and reading whole documents.
Search asks the opposite question: given a term, which documents contain it?
An inverted index answers by turning terms into keys and document occurrences
into posting lists. MiniLucene builds that structure in RAM before freezing it
as an immutable segment. The implementation is small enough to expose the four
pieces that later chapters persist: a term dictionary, postings, stored fields,
and field-length norms.

## Learning objectives

By the end of this chapter, you can:

1. trace an analyzed document into term posting lists;
2. distinguish term frequency, positions, field length, and stored fields;
3. explain why document IDs are local to a segment;
4. inspect the RAM segment and relate it to search results; and
5. distinguish bounded Top-K storage from a document-at-a-time search engine.

## Mechanism: building the RAM segment

`src/minilucene/index/memory.py` separates preparation from mutation.
`RamIndexBuilder.prepare_document` first calls `freeze_document` from
`src/minilucene/document.py`. That function validates field names and string
values against the schema and returns an immutable mapping. Validation occurs
before the builder changes, so a malformed document cannot leave a partial
posting behind.

For each indexed field, preparation calls `_analyze`. The result is stored in a
`PreparedDocument` alongside the full frozen document and the stored-only
projection. `PreparedDocument.posting_count` counts distinct terms per field,
not raw token occurrences. This is the unit used by the writer's posting-based
flush threshold.

`RamIndexBuilder.add_prepared` performs the actual inversion. The next local
document ID is the current stored-document count. For each indexed field it
records the number of analyzed tokens as the field length, then groups token
positions by term:

```python
positions_by_term: dict[str, list[int]] = defaultdict(list)
for token in tokens:
    positions_by_term[token.term].append(token.position)
```

One `Posting` is appended per distinct `(field, term, document)` occurrence.
The immutable dataclass in `src/minilucene/index/postings.py` contains
`doc_id`, `term_frequency`, and `positions`. Term frequency is the number of
positions collected. A positional text field stores the position tuple;
a keyword field deliberately stores no positions because phrase queries are
not part of its contract.

The internal shape can be read as:

```text
postings[field][term] = (
    Posting(local_doc_id, term_frequency, positions),
    ...
)
field_lengths[field][local_doc_id] = analyzed token count
stored_documents[local_doc_id] = retrievable field/value mapping
```

The first two dimensions include the field. The term `python` in `title` is a
different lookup key from `python` in `body`. This permits different boosts,
length statistics, and query clauses per field.

### Why each component exists

The **term dictionary** lets a search find one posting list without scanning
every document. In RAM it is a nested mapping; Chapter 4 shows its disk form.

The **posting list** is sorted by local document ID because documents are added
monotonically. It gives term membership. Term frequency supports BM25's
saturating frequency contribution. Positions support phrase verification.

The **field lengths**, called norms in the educational disk format, support
BM25 length normalization. The length is the number of tokens surviving
analysis, not the character count or byte count. A document with `blue blue
sky` therefore has body length 3, while `blue sea` has length 2.

The **stored fields** support result presentation. Search could rank an
indexed-but-not-stored body, but it could not return or highlight the original
body text. Conversely, a stored-only metadata field contributes no terms.

`RamIndexBuilder.freeze` copies those mutable collections into tuples and
mapping proxies and returns a `MemorySegment`. A segment has its own generation
and local document-ID space. Two segments can both contain local document 0;
search results disambiguate them using `(segment_generation, local_doc_id)`.
This keeps immutable segment contents independent and lets merges remap IDs.

### From postings to a result

`MemoryIndex.search` freezes its builder as generation 0, wraps it in
`ReaderView`, and calls `IndexSearcher.search`. `ReaderView` in
`src/minilucene/search/reader.py` presents postings and stored fields across
segments. `CorpusStats.from_segments` in
`src/minilucene/search/stats.py` computes reader-wide live-document counts,
document frequencies, and average lengths. That global scope is important:
ranking should not depend on which flush happened to place a document in which
segment.

For a term query, matching identifies candidates from postings and scoring uses
term frequency, document frequency, field length, average field length, and
the schema field boost. `TopKCollector.collect` in
`src/minilucene/search/collector.py` retains at most K hit objects with
deterministic tie-breaking while still incrementing the complete hit count.
Thus `total_hits` may exceed `len(hits)`.

That memory bound must not be overstated. `IndexSearcher.search` now streams
supported term/Boolean trees through DAAT cursors and performs
collect-then-fetch, so stored fields/highlights are built only for final
winners. Phrase-containing trees still fall back to complete matching maps,
and there is no skip data, WAND, or competitive-score pruning. “Top-K hit
materialization is bounded” is true; “all query work is O(K)” is false.
[Chapter 11](11-daat.md) develops this boundary.

### Immutability as a simplifying boundary

The RAM builder is mutable because indexing is incremental. The frozen segment
is immutable because readers need stable inputs. Later deletion does not edit
posting lists; it publishes a separate live-document mask. Later merge creates
a replacement segment. This division avoids in-place coordination between
readers and writers and is the foundation of point-in-time readers.

### Cost model and deterministic ordering

Inversion moves work from query time to index time. Adding a document analyzes
all indexed fields and updates one posting list per distinct term. A term query
then reaches candidates through a dictionary lookup instead of reading every
stored document. Phrase queries intersect candidate postings and inspect
positions; Boolean queries combine ordered cursors. This beats a full document
scan for selective terms. Phrase currently uses the preserved set/map oracle
fallback, while rewritten term/Boolean trees execute DAAT.

Ordering is part of reproducibility. `RamIndexBuilder.freeze` sorts fields and
terms before wrapping them in read-only mappings. Documents follow insertion
order, so posting document IDs increase. The disk codec relies on these
invariants and rejects reordered data. Deterministic Top-K tie-breaking uses
score and document address rather than incidental dictionary iteration.

The posting counter illustrates a subtle capacity choice. Repeating one term a
hundred times increases term frequency and token length, but adds one distinct
posting for that document. A `max_postings` flush threshold therefore
approximates term-document edges, not token count or serialized bytes.
Production engines use richer RAM accounting because long position lists and
stored values consume memory. MiniLucene's policy is deterministic and
testable, but is not an accurate heap budget.

A local document ID also has no application meaning. Applications should store
their own stable identifier in a keyword field. Deletes and updates can then
find documents by that exact term even while merges rewrite internal
segment-local addresses.

## Compared with Apache Lucene

Apache Lucene also indexes fields into term dictionaries, postings, frequencies,
positions, norms, and stored fields. Its concrete implementation is much more
compressed and optimized: BlockTree terms dictionaries, specialized postings
formats, skip data, packed integers, impacts, doc values, and iterator APIs such
as `TermsEnum` and `PostingsEnum`. MiniLucene now transfers the basic ordered
iterator model but not these production data structures or optimizations.

MiniLucene's mappings and tuples prioritize inspectability. It has no FST,
BlockTree, skip lists, impacts, WAND, doc values, numeric points, payloads, or
per-field codec selection. Its document frequency immediately excludes deleted
documents in a reader snapshot; Lucene segment statistics can retain deleted
documents until merge, so score movement around deletion/merge differs. Phrase
scores in MiniLucene are the sum of term BM25 scores rather than phrase
frequency scoring. These differences are recorded in the
[Lucene mapping](../lucene-mapping.md) and ranking/index rows of the
[behavior matrix](../behavior-matrix.md).

## Hands-on experiment: inspect postings and norms

```bash
export UV_CACHE_DIR=/tmp/minilucene-uv-cache
uv run --offline python - <<'PY'
from minilucene import MemoryIndex, Schema, TextField
from minilucene.query import TermQuery

index = MemoryIndex(Schema(body=TextField(stored=True)))
index.add_document(body="blue blue sky")
index.add_document(body="blue sea")

segment = index._builder.freeze(generation=0)
print(segment.postings["body"]["blue"])
print(segment.field_lengths["body"])

results = index.search(TermQuery("body", "blue"), top_k=1)
print(results.total_hits, len(results.hits), dict(results.hits[0].stored_fields))
PY
```

Measured output:

```text
(Posting(doc_id=0, term_frequency=2, positions=(0, 1)), Posting(doc_id=1, term_frequency=1, positions=(0,)))
(3, 2)
2 1 {'body': 'blue blue sky'}
```

The posting list contains two candidate documents. Document 0 records two
occurrences and positions 0 and 1. Norms record lengths 3 and 2. `top_k=1`
returns one hit but `total_hits=2`, proving that result truncation does not
change the match count. Document 0 wins because its higher term frequency
outweighs its slightly greater length for this corpus.

Run the focused contract tests:

```bash
uv run --offline pytest -q tests/contract/test_memory_index.py \
  tests/contract/test_memory_search.py tests/unit/search/test_topk.py
```

Measured result:

```text
11 passed in 0.07s
```

## Exercises

1. **Understanding:** Why does one posting store a segment-local ID rather than
   a globally permanent document ID?

    ??? note "Reference answer"
        Immutable segments are built independently, and merge may compact or
        remap their live documents. The stable address inside a reader is the
        segment identity plus local ID, not one mutable global ordinal.

2. **Understanding:** Which value changes when `blue blue sky` becomes
   `blue sky`: document frequency, term frequency, or both?

    ??? note "Reference answer"
        Term frequency for that document changes from 2 to 1. Document
        frequency remains 2 as long as both documents still contain `blue`.
        The first field length also changes from 3 to 2.

3. **Hands-on:** Add a third document `red sky` and print postings for both
   `blue` and `sky`. Acceptance: `blue` has document IDs 0 and 1; `sky` has
   document IDs 0 and 2.

    ??? note "Reference answer"
        Add `index.add_document(body="red sky")` before freezing, then inspect
        `segment.postings["body"][term]`. No source edit is required.

4. **Hands-on:** Change the experiment to `top_k=0`. Acceptance:
   `total_hits` stays 2 and the hit tuple is empty.

    ??? note "Reference answer"
        Call `index.search(TermQuery(...), top_k=0)`. This isolates the complete
        match count from the collector's retained-hit capacity.

## Summary

The inverted index replaces document scanning with field-and-term lookup.
Postings carry membership, frequency, and positions; norms carry analyzed
lengths; stored fields carry presentation data. Freezing turns a mutable RAM
builder into an immutable segment with local IDs. The next chapter serializes
exactly these structures and asks a harder question: how should corrupted or
ambiguous bytes fail?
