# Stage 08 · Immutable segment images

### Goal

Build immutable segment images and explain its boundary from an executable counterexample, runtime state, and the critical statement.

??? note "Deliverable files"
    - `src/minilucene/storage/__init__.py`
    - `src/minilucene/storage/image.py`
    - `tests/unit/storage/test_segment_image.py`

### The problem at this point

The in-memory segment needs a canonical value object before a disk codec can preserve it exactly.

### Test contract

#### See the failure first

Round-trip and validation tests construct mismatched doc counts, postings, norms, and stored fields.

??? note "File diff: tests/unit/storage/test_segment_image.py"
    ```diff
    diff --git a/tests/unit/storage/test_segment_image.py b/tests/unit/storage/test_segment_image.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..daaad6b6e37dd629ac376c0cdd566203faec2219
    --- /dev/null
    +++ b/tests/unit/storage/test_segment_image.py
    @@ -0,0 +1,67 @@
    +import pytest
    +
    +from minilucene.index.memory import RamIndexBuilder
    +from minilucene.schema import KeywordField, Schema, TextField
    +from minilucene.storage.image import SegmentImage
    +
    +
    +def test_segment_image_rejects_non_dense_documents():
    +    with pytest.raises(ValueError, match="dense"):
    +        SegmentImage(
    +            generation=1,
    +            schema_fingerprint="abc",
    +            stored_documents={1: {"id": "late"}},
    +            postings={},
    +            field_lengths={},
    +        )
    +
    +
    +def test_segment_image_from_ram_segment_is_deeply_immutable():
    +    schema = Schema(
    +        id=KeywordField(stored=True),
    +        body=TextField(stored=True),
    +    )
    +    builder = RamIndexBuilder(schema)
    +    builder.add_document({"id": "1", "body": "search search"})
    +    image = SegmentImage.from_memory_segment(
    +        generation=7,
    +        schema_fingerprint=schema.fingerprint,
    +        segment=builder.freeze(generation=0),
    +    )
    +    assert image.max_doc == 1
    +    assert image.postings["body"]["search"][0].positions == (0, 1)
    +    with pytest.raises(TypeError):
    +        image.stored_documents[0] = {"id": "changed"}
    +    with pytest.raises(TypeError):
    +        image.stored_documents[0]["id"] = "changed"
    +
    +
    +def test_segment_image_rejects_nonmonotonic_posting_ids():
    +    from minilucene.index.postings import Posting
    +
    +    with pytest.raises(ValueError, match="strictly increasing"):
    +        SegmentImage(
    +            generation=1,
    +            schema_fingerprint="abc",
    +            stored_documents={0: {}, 1: {}},
    +            postings={
    +                "body": {
    +                    "term": (
    +                        Posting(1, 1, (0,)),
    +                        Posting(0, 1, (0,)),
    +                    )
    +                }
    +            },
    +            field_lengths={"body": (1, 1)},
    +        )
    +
    +
    +def test_segment_image_rejects_wrong_field_length_count():
    +    with pytest.raises(ValueError, match="field lengths"):
    +        SegmentImage(
    +            generation=1,
    +            schema_fingerprint="abc",
    +            stored_documents={0: {}},
    +            postings={},
    +            field_lengths={"body": ()},
    +        )
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

Round-trip and validation tests construct mismatched doc counts, postings, norms, and stored fields.

**Key test statement**

```python
assert image.max_doc == 1
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

A SegmentImage is the complete immutable logical payload, independent of file layout and publication protocol.

### Why this mechanism is necessary

The in-memory segment needs a canonical value object before a disk codec can preserve it exactly. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Builders normalize maps and tuples, validate cross-table counts and doc IDs, and expose one deterministic image to codecs.

### Mechanism blocks

#### Immutable segment images mechanism

Builders normalize maps and tuples, validate cross-table counts and doc IDs, and expose one deterministic image to codecs.

??? note "File diff: src/minilucene/storage/image.py"
    ```diff
    diff --git a/src/minilucene/storage/image.py b/src/minilucene/storage/image.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..7ef65e5bf05149773a77f527d88164afdd44da10
    --- /dev/null
    +++ b/src/minilucene/storage/image.py
    @@ -0,0 +1,115 @@
    +from collections.abc import Mapping
    +from dataclasses import dataclass
    +from itertools import pairwise
    +from types import MappingProxyType
    +
    +from minilucene.index.postings import MemorySegment, Posting
    +
    +
    +def _freeze_string_mapping(
    +    values: Mapping[str, str],
    +) -> Mapping[str, str]:
    +    return MappingProxyType(dict(sorted(values.items())))
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class SegmentImage:
    +    generation: int
    +    schema_fingerprint: str
    +    stored_documents: Mapping[int, Mapping[str, str]]
    +    postings: Mapping[str, Mapping[str, tuple[Posting, ...]]]
    +    field_lengths: Mapping[str, tuple[int, ...]]
    +
    +    def __post_init__(self) -> None:
    +        if self.generation <= 0:
    +            raise ValueError("segment generation must be positive")
    +        if not self.schema_fingerprint:
    +            raise ValueError("schema fingerprint must be non-empty")
    +
    +        stored = {
    +            doc_id: _freeze_string_mapping(document)
    +            for doc_id, document in sorted(self.stored_documents.items())
    +        }
    +        if tuple(stored) != tuple(range(len(stored))):
    +            raise ValueError("stored document IDs must be dense")
    +        max_doc = len(stored)
    +
    +        frozen_postings: dict[
    +            str, Mapping[str, tuple[Posting, ...]]
    +        ] = {}
    +        for field, terms in sorted(self.postings.items()):
    +            frozen_terms: dict[str, tuple[Posting, ...]] = {}
    +            for term, term_postings in sorted(terms.items()):
    +                term_postings = tuple(term_postings)
    +                doc_ids = tuple(
    +                    posting.doc_id for posting in term_postings
    +                )
    +                if any(
    +                    right <= left for left, right in pairwise(doc_ids)
    +                ):
    +                    raise ValueError(
    +                        "posting doc IDs must be strictly increasing"
    +                    )
    +                for posting in term_postings:
    +                    if not 0 <= posting.doc_id < max_doc:
    +                        raise ValueError("posting doc ID outside segment")
    +                    if posting.term_frequency <= 0:
    +                        raise ValueError("term frequency must be positive")
    +                    if posting.positions:
    +                        if posting.term_frequency != len(posting.positions):
    +                            raise ValueError(
    +                                "term frequency must equal position count"
    +                            )
    +                        if any(
    +                            right <= left
    +                            for left, right in pairwise(posting.positions)
    +                        ):
    +                            raise ValueError(
    +                                "positions must be strictly increasing"
    +                            )
    +                frozen_terms[term] = term_postings
    +            frozen_postings[field] = MappingProxyType(frozen_terms)
    +
    +        lengths: dict[str, tuple[int, ...]] = {}
    +        for field, values in sorted(self.field_lengths.items()):
    +            values = tuple(values)
    +            if len(values) != max_doc or any(value < 0 for value in values):
    +                raise ValueError(
    +                    "field lengths must match documents and be non-negative"
    +                )
    +            lengths[field] = values
    +
    +        object.__setattr__(
    +            self, "stored_documents", MappingProxyType(stored)
    +        )
    +        object.__setattr__(
    +            self, "postings", MappingProxyType(frozen_postings)
    +        )
    +        object.__setattr__(
    +            self, "field_lengths", MappingProxyType(lengths)
    +        )
    +
    +    @property
    +    def max_doc(self) -> int:
    +        return len(self.stored_documents)
    +
    +    @classmethod
    +    def from_memory_segment(
    +        cls,
    +        *,
    +        generation: int,
    +        schema_fingerprint: str,
    +        segment: MemorySegment,
    +    ) -> "SegmentImage":
    +        return cls(
    +            generation=generation,
    +            schema_fingerprint=schema_fingerprint,
    +            stored_documents={
    +                doc_id: document
    +                for doc_id, document in enumerate(
    +                    segment.stored_documents
    +                )
    +            },
    +            postings=segment.postings,
    +            field_lengths=segment.field_lengths,
    +        )
    ```

**What it is and why it appears**

A SegmentImage is the complete immutable logical payload, independent of file layout and publication protocol.

**Runtime role**

Builders normalize maps and tuples, validate cross-table counts and doc IDs, and expose one deterministic image to codecs.

**Statement understanding**

Separating logical image from bytes lets format validation and filesystem atomicity evolve without changing search semantics.

#### Package, fixture, and project support

Keep exports, test corpora, dependencies, and the runtime environment reproducible.

??? note "Supporting file diffs (1 file)"
    **`src/minilucene/storage/__init__.py`**

    ```diff
    diff --git a/src/minilucene/storage/__init__.py b/src/minilucene/storage/__init__.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..0257b60f52bad1b096decc92d5633870c6a220de
    --- /dev/null
    +++ b/src/minilucene/storage/__init__.py
    @@ -0,0 +1,3 @@
    +from minilucene.storage.image import SegmentImage
    +
    +__all__ = ["SegmentImage"]
    ```


### Verification evidence

Run `uv run pytest -q $(cat journey/stages/08-segment-images/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Separating logical image from bytes lets format validation and filesystem atomicity evolve without changing search semantics.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 4](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/04-codec.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/08-segment-images/stage.patch)
