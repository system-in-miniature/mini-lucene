# Stage 20 · Update and live-only statistics

### Goal

Build update and live-only statistics and explain its boundary from an executable counterexample, runtime state, and the critical statement.

??? note "Deliverable files"
    - `src/minilucene/writer.py`
    - `tests/nrt/test_live_bm25_stats.py`
    - `tests/nrt/test_update_document.py`

### The problem at this point

Implementing update as add-then-delete can delete the replacement, and deleted documents must stop influencing ranking.

### Test contract

#### See the failure first

The counterexample updates multiple matches, injects add failure, and compares BM25 before and after deletions across snapshots.

??? note "File diff: tests/nrt/test_live_bm25_stats.py"
    ```diff
    diff --git a/tests/nrt/test_live_bm25_stats.py b/tests/nrt/test_live_bm25_stats.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..c52ea9b67cc1e5017bf226683b7925973a0ee323
    --- /dev/null
    +++ b/tests/nrt/test_live_bm25_stats.py
    @@ -0,0 +1,48 @@
    +import pytest
    +
    +from minilucene import Index, KeywordField, MemoryIndex, Schema, TextField
    +from minilucene.query import TermQuery
    +
    +
    +def test_deleted_documents_do_not_change_global_multisegment_bm25(tmp_path):
    +    schema = Schema(
    +        id=KeywordField(stored=True),
    +        body=TextField(stored=True),
    +    )
    +    live_documents = (
    +        {"id": "1", "body": "kafka kafka"},
    +        {"id": "3", "body": "kafka replicas"},
    +    )
    +    oracle = MemoryIndex(schema)
    +    for document in live_documents:
    +        oracle.add_document(**document)
    +
    +    index = Index.create(tmp_path, schema)
    +    with index.writer() as writer:
    +        writer.add_document(**live_documents[0])
    +        writer.flush()
    +        writer.add_document(
    +            id="2",
    +            body=("kafka " * 50) + "deleted noise",
    +        )
    +        writer.flush()
    +        writer.add_document(**live_documents[1])
    +        writer.commit()
    +    with index.writer() as writer:
    +        writer.delete_by_term("id", "2")
    +        reader = writer.refresh()
    +
    +    stats = reader.corpus_stats
    +    assert stats.live_doc_count == 2
    +    assert stats.doc_frequency("body", "kafka") == 2
    +    assert stats.average_length("body") == 2.0
    +
    +    query = TermQuery("body", "kafka")
    +    expected = oracle.search(query, top_k=10)
    +    actual = reader.search(query, top_k=10)
    +    assert [hit.stored_fields["id"] for hit in actual.hits] == [
    +        hit.stored_fields["id"] for hit in expected.hits
    +    ]
    +    assert [hit.score for hit in actual.hits] == pytest.approx(
    +        [hit.score for hit in expected.hits]
    +    )
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

The counterexample updates multiple matches, injects add failure, and compares BM25 before and after deletions across snapshots.

**Key test statement**

```python
assert stats.live_doc_count == 2
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

??? note "File diff: tests/nrt/test_update_document.py"
    ```diff
    diff --git a/tests/nrt/test_update_document.py b/tests/nrt/test_update_document.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..e286f0970c1e3bfc26f22267452f915252076fc2
    --- /dev/null
    +++ b/tests/nrt/test_update_document.py
    @@ -0,0 +1,98 @@
    +import pytest
    +
    +from minilucene import Index, KeywordField, Schema, TextField
    +from minilucene.query import TermQuery
    +from minilucene.schema import SchemaError
    +
    +
    +def build_index(tmp_path):
    +    return Index.create(
    +        tmp_path,
    +        Schema(
    +            id=KeywordField(stored=True),
    +            body=TextField(stored=True),
    +        ),
    +    )
    +
    +
    +def test_update_deletes_all_matches_then_adds_one_replacement(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="old one")
    +        writer.add_document(id="1", body="old two")
    +        writer.commit()
    +        deleted = writer.update_document(
    +            field="id",
    +            term="1",
    +            id="1",
    +            body="replacement",
    +        )
    +        assert deleted == 2
    +        reader = writer.refresh()
    +    assert reader.search(TermQuery("body", "old"), top_k=10).total_hits == 0
    +    assert (
    +        reader.search(
    +            TermQuery("body", "replacement"),
    +            top_k=10,
    +        ).total_hits
    +        == 1
    +    )
    +
    +
    +def test_invalid_replacement_leaves_delete_state_unchanged(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="old")
    +        writer.commit()
    +        with pytest.raises(SchemaError):
    +            writer.update_document(
    +                field="id",
    +                term="1",
    +                id="1",
    +                body=7,
    +            )
    +        assert (
    +            writer.refresh().search(
    +                TermQuery("body", "old"),
    +                top_k=10,
    +            ).total_hits
    +            == 1
    +        )
    +
    +
    +def test_update_replaces_buffered_document_without_intermediate_visibility(
    +    tmp_path,
    +):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="buffered old")
    +        assert (
    +            writer.update_document(
    +                field="id",
    +                term="1",
    +                id="1",
    +                body="buffered new",
    +            )
    +            == 1
    +        )
    +        reader = writer.refresh()
    +    assert reader.search(TermQuery("body", "old"), top_k=10).total_hits == 0
    +    assert reader.search(TermQuery("body", "new"), top_k=10).total_hits == 1
    +
    +
    +def test_committed_update_survives_reopen(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="before")
    +        writer.commit()
    +    with index.writer() as writer:
    +        writer.update_document(
    +            field="id",
    +            term="1",
    +            id="1",
    +            body="after",
    +        )
    +        writer.commit()
    +    reader = Index.open(tmp_path).open_reader()
    +    assert reader.search(TermQuery("body", "before"), top_k=10).total_hits == 0
    +    assert reader.search(TermQuery("body", "after"), top_k=10).total_hits == 1
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

The counterexample updates multiple matches, injects add failure, and compares BM25 before and after deletions across snapshots.

**Key test statement**

```python
assert stats.live_doc_count == 2
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

Update is delete-all matching old identity plus one validated add under one writer operation; corpus statistics count only live documents.

### Why this mechanism is necessary

Implementing update as add-then-delete can delete the replacement, and deleted documents must stop influencing ranking. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

The writer validates replacement first, derives deletion masks from the pre-update view, then buffers the new document; readers aggregate only live postings and norms.

### Mechanism blocks

#### Update and live-only statistics mechanism

The writer validates replacement first, derives deletion masks from the pre-update view, then buffers the new document; readers aggregate only live postings and norms.

??? note "File diff: src/minilucene/writer.py"
    ```diff
    diff --git a/src/minilucene/writer.py b/src/minilucene/writer.py
    index 214a9fd68607a3051d3725739b590a3df345cb8f..b703e8bb89d69b5a628e36e4e50f2da52fc8df5f 100644
    --- a/src/minilucene/writer.py
    +++ b/src/minilucene/writer.py
    @@ -183,8 +183,9 @@ class IndexWriter:
                 commit_generation=None,
             )

    -    def delete_by_term(self, field: str, term: str) -> int:
    -        self._ensure_open()
    +    def _derive_delete(
    +        self, field: str, term: str
    +    ) -> tuple[dict[int, frozenset[int]], set[int], set[int], int]:
             if field not in self.index.schema:
                 raise ValueError(f"unknown field: {field}")
             if not self.index.schema[field].indexed:
    @@ -216,9 +217,51 @@ class IndexWriter:
             )
             next_buffer_live_docs = self._buffer_live_docs - buffered_matches
             deleted += len(buffered_matches)
    +        return (
    +            derived_masks,
    +            changed_generations,
    +            next_buffer_live_docs,
    +            deleted,
    +        )
    +
    +    def delete_by_term(self, field: str, term: str) -> int:
    +        self._ensure_open()
    +        (
    +            derived_masks,
    +            changed_generations,
    +            next_buffer_live_docs,
    +            deleted,
    +        ) = self._derive_delete(field, term)
    +        self._live_docs = derived_masks
    +        self._dirty_live_docs.update(changed_generations)
    +        self._buffer_live_docs = next_buffer_live_docs
    +        return deleted
    +
    +    def update_document(
    +        self,
    +        *,
    +        field: str,
    +        term: str,
    +        **replacement: object,
    +    ) -> int:
    +        self._ensure_open()
    +        prepared = self._buffer.prepare_document(replacement)
    +        (
    +            derived_masks,
    +            changed_generations,
    +            next_buffer_live_docs,
    +            deleted,
    +        ) = self._derive_delete(field, term)
    +
    +        next_buffer = RamIndexBuilder(self.index.schema)
    +        for document in self._buffer.documents:
    +            next_buffer.add_document(dict(document))
    +        replacement_doc_id = next_buffer.add_prepared(prepared)
    +        next_buffer_live_docs.add(replacement_doc_id)

             self._live_docs = derived_masks
             self._dirty_live_docs.update(changed_generations)
    +        self._buffer = next_buffer
             self._buffer_live_docs = next_buffer_live_docs
             return deleted

    ```

**What it is and why it appears**

Update is delete-all matching old identity plus one validated add under one writer operation; corpus statistics count only live documents.

**Runtime role**

The writer validates replacement first, derives deletion masks from the pre-update view, then buffers the new document; readers aggregate only live postings and norms.

**Statement understanding**

Validating before deletion prevents a bad replacement from destroying old data; live filtering keeps ranking consistent with visible hits.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/20-update-live-stats/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Validating before deletion prevents a bad replacement from destroying old data; live filtering keeps ranking consistent with visible hits.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 6](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/06-deletes-updates.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/20-update-live-stats/stage.patch)
