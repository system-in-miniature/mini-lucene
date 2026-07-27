import pytest

from minilucene.document import freeze_document
from minilucene.schema import (
    FieldType,
    KeywordField,
    Schema,
    SchemaError,
    StoredField,
    TextField,
)


def test_stored_indexed_and_tokenized_are_independent():
    schema = Schema(
        id=KeywordField(stored=True),
        body=TextField(stored=False, boost=2.0),
        source=StoredField(),
    )
    assert schema["id"].indexed and not schema["id"].tokenized
    assert schema["body"].indexed and schema["body"].store_positions
    assert schema["source"].stored and not schema["source"].indexed
    assert schema.fingerprint == schema.fingerprint


def test_document_rejects_unknown_fields_and_non_strings():
    schema = Schema(body=TextField())
    with pytest.raises(SchemaError, match="unknown field"):
        freeze_document(schema, {"missing": "x"})
    with pytest.raises(SchemaError, match="must be str"):
        freeze_document(schema, {"body": 1})


@pytest.mark.parametrize("boost", [0.0, -1.0, float("inf"), float("nan")])
def test_field_boost_must_be_finite_and_positive(boost):
    with pytest.raises(SchemaError, match="finite and positive"):
        TextField(boost=boost)


def test_positions_require_an_indexed_field():
    with pytest.raises(SchemaError, match="positions require"):
        FieldType(
            indexed=False,
            tokenized=False,
            stored=True,
            store_positions=True,
            boost=1.0,
            analyzer_name=None,
        )


def test_schema_fingerprint_is_order_independent():
    first = Schema(id=KeywordField(), body=TextField(stored=True))
    second = Schema(body=TextField(stored=True), id=KeywordField())
    assert first == second
    assert first.fingerprint == second.fingerprint


def test_frozen_document_is_sorted_and_immutable():
    document = freeze_document(
        Schema(id=KeywordField(), body=TextField()),
        {"id": "1", "body": "search"},
    )
    assert tuple(document) == ("body", "id")
    with pytest.raises(TypeError):
        document["id"] = "2"
