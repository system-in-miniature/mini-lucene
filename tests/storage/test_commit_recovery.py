import pytest

from minilucene import Index, KeywordField, Schema, TextField
from minilucene.query import TermQuery
from minilucene.storage.filesystem import FileSystemOps
from minilucene.storage.manifest import ManifestStore


class ReplaceFailingFileSystem(FileSystemOps):
    def replace(self, source, destination):
        if destination.name == "manifest.json":
            raise OSError("injected manifest replacement failure")
        super().replace(source, destination)


def build_index(tmp_path):
    return Index.create(
        tmp_path,
        Schema(
            id=KeywordField(stored=True),
            body=TextField(stored=True),
        ),
    )


def test_complete_segment_without_manifest_is_ignored_after_reopen(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.add_document(id="1", body="orphan")
        writer.flush()
    reopened = Index.open(tmp_path)
    assert reopened.open_reader().max_doc == 0


def test_commit_flushes_and_reopen_searches_committed_data(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.add_document(id="1", body="committed data")
        manifest = writer.commit()
    assert manifest.commit_generation == 1
    reopened = Index.open(tmp_path)
    result = reopened.open_reader().search(
        TermQuery("body", "committed"),
        top_k=10,
    )
    assert result.total_hits == 1
    assert result.hits[0].stored_fields["id"] == "1"


def test_manifest_replace_failure_preserves_previous_commit(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.add_document(id="old", body="stable")
        writer.commit()

    with index.writer() as writer:
        writer.add_document(id="new", body="unpublished")
        writer._manifest_store = ManifestStore(
            tmp_path,
            fs=ReplaceFailingFileSystem(),
        )
        with pytest.raises(OSError, match="injected"):
            writer.commit()

    reader = Index.open(tmp_path).open_reader()
    assert reader.search(TermQuery("body", "stable"), top_k=10).total_hits == 1
    assert (
        reader.search(TermQuery("body", "unpublished"), top_k=10).total_hits
        == 0
    )


def test_commit_preserves_explicit_segment_order(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.add_document(id="1", body="first")
        writer.flush()
        writer.add_document(id="2", body="second")
        manifest = writer.commit()
    assert manifest.segment_generations == (1, 2)
    assert Index.open(tmp_path).open_reader().max_doc == 2
