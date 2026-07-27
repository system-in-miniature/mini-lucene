import pytest

from minilucene.index.memory import RamIndexBuilder
from minilucene.schema import (
    KeywordField,
    Schema,
    SchemaError,
    StoredField,
    TextField,
)


def test_ram_segment_contains_positions_lengths_and_only_stored_values():
    schema = Schema(
        id=KeywordField(stored=True),
        body=TextField(stored=False),
        source=StoredField(),
    )
    builder = RamIndexBuilder(schema)
    builder.add_document(
        {"id": "d1", "body": "Kafka kafka replicas", "source": "manual"}
    )
    segment = builder.freeze(generation=1)

    posting = segment.postings["body"]["kafka"][0]
    assert (posting.doc_id, posting.term_frequency, posting.positions) == (
        0,
        2,
        (0, 1),
    )
    assert segment.field_lengths["body"] == (3,)
    assert segment.stored_documents == (
        {"id": "d1", "source": "manual"},
    )


def test_keyword_field_indexes_one_exact_term_without_positions():
    builder = RamIndexBuilder(Schema(author=KeywordField()))
    builder.add_document({"author": "Jonah Smith"})
    segment = builder.freeze(generation=3)
    posting = segment.postings["author"]["Jonah Smith"][0]
    assert posting.term_frequency == 1
    assert posting.positions == ()


def test_missing_indexed_field_has_zero_length():
    builder = RamIndexBuilder(
        Schema(id=KeywordField(stored=True), body=TextField())
    )
    builder.add_document({"id": "1"})
    segment = builder.freeze(generation=1)
    assert segment.field_lengths["body"] == (0,)
    assert segment.field_lengths["id"] == (1,)


def test_failed_document_validation_does_not_mutate_builder():
    builder = RamIndexBuilder(Schema(body=TextField()))
    with pytest.raises(SchemaError):
        builder.add_document({"unknown": "value"})
    assert builder.freeze(generation=1).max_doc == 0


def test_frozen_segment_collections_are_immutable():
    builder = RamIndexBuilder(Schema(body=TextField(stored=True)))
    builder.add_document({"body": "search"})
    segment = builder.freeze(generation=1)
    with pytest.raises(TypeError):
        segment.postings["body"]["search"] = ()
    with pytest.raises(TypeError):
        segment.stored_documents[0]["body"] = "changed"
