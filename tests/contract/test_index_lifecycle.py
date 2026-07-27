import json

import pytest

from minilucene import Index, KeywordField, Schema, TextField
from minilucene.errors import (
    IndexAlreadyExistsError,
    SchemaMismatchError,
    WriterAlreadyOpenError,
)


def build_schema():
    return Schema(
        id=KeywordField(stored=True),
        body=TextField(stored=True),
    )


def test_create_open_and_schema_fingerprint(tmp_path):
    schema = build_schema()
    Index.create(tmp_path, schema)
    reopened = Index.open(tmp_path)
    assert reopened.schema == schema
    assert reopened.schema.fingerprint == schema.fingerprint
    assert reopened.manifest().schema_fingerprint == schema.fingerprint


def test_create_rejects_nonempty_path(tmp_path):
    (tmp_path / "foreign.txt").write_text("foreign", encoding="utf-8")
    with pytest.raises(IndexAlreadyExistsError):
        Index.create(tmp_path, build_schema())


def test_open_rejects_supplied_different_schema(tmp_path):
    Index.create(tmp_path, build_schema())
    with pytest.raises(SchemaMismatchError):
        Index.open(tmp_path, Schema(body=TextField(stored=True)))


def test_open_rejects_tampered_persisted_schema(tmp_path):
    Index.create(tmp_path, build_schema())
    schema_path = tmp_path / "schema.json"
    payload = json.loads(schema_path.read_text(encoding="utf-8"))
    payload["fingerprint"] = "tampered"
    schema_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SchemaMismatchError):
        Index.open(tmp_path)


def test_only_one_writer_can_be_open(tmp_path):
    index = Index.create(tmp_path, build_schema())
    first = index.writer()
    with pytest.raises(WriterAlreadyOpenError):
        index.writer()
    first.close()
    first.close()
    second = index.writer()
    second.close()
    assert not (tmp_path / ".writer.lock").exists()


def test_writer_context_releases_lock(tmp_path):
    index = Index.create(tmp_path, build_schema())
    with index.writer() as writer:
        assert writer.index is index
        assert (tmp_path / ".writer.lock").exists()
    assert not (tmp_path / ".writer.lock").exists()
