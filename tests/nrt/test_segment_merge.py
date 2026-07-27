import pytest

from minilucene import Index, KeywordField, Schema, TextField
from minilucene.query import PhraseQuery, TermQuery
from minilucene.storage.filesystem import FileSystemOps


def build_index(tmp_path):
    index = Index.create(
        tmp_path,
        Schema(
            id=KeywordField(stored=True),
            body=TextField(stored=False),
        ),
    )
    with index.writer() as writer:
        writer.add_document(id="1", body="kafka kafka replicas")
        writer.flush()
        writer.add_document(id="2", body="deleted document")
        writer.flush()
        writer.add_document(id="3", body="kafka follower replicas")
        writer.commit()
    return index


def snapshot_results(reader):
    results = {}
    for name, query in (
        ("term", TermQuery("body", "kafka")),
        ("phrase", PhraseQuery("body", ("follower", "replicas"))),
    ):
        top_docs = reader.search(query, top_k=10)
        results[name] = (
            top_docs.total_hits,
            tuple(hit.stored_fields["id"] for hit in top_docs.hits),
            tuple(hit.score for hit in top_docs.hits),
        )
    return results


def test_merge_skips_deletes_and_preserves_search_results(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.delete_by_term("id", "2")
        before = writer.refresh()
        expected = snapshot_results(before)
        merged = writer.merge(writer.segment_generations)
        after = writer.refresh()

    assert merged.max_doc == before.num_live_docs
    actual = snapshot_results(after)
    assert actual.keys() == expected.keys()
    for name in expected:
        assert actual[name][:2] == expected[name][:2]
        assert actual[name][2] == pytest.approx(expected[name][2])
    assert after.snapshot.segments[0].generation == merged.generation
    assert after.snapshot.segments[0].image.max_doc == 2
    assert tuple(after.snapshot.segments[0].image.stored_documents) == (0, 1)


class PostingWriteFailingFileSystem(FileSystemOps):
    def write_bytes(self, path, data):
        if path.name == "postings.bin":
            raise OSError("injected merge write failure")
        super().write_bytes(path, data)


def test_merge_failure_leaves_writer_segment_set_unchanged(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        before_generations = writer.segment_generations
        before = snapshot_results(writer.refresh())
        writer._segment_store.fs = PostingWriteFailingFileSystem()
        with pytest.raises(OSError, match="injected"):
            writer.merge(before_generations)
        assert writer.segment_generations == before_generations
        writer._segment_store.fs = FileSystemOps()
        assert snapshot_results(writer.refresh()) == before


@pytest.mark.parametrize(
    "selected",
    [(1,), (1, 1), (99, 1)],
)
def test_merge_rejects_invalid_selection_without_mutation(tmp_path, selected):
    index = build_index(tmp_path)
    with index.writer() as writer:
        before = writer.segment_generations
        with pytest.raises(ValueError):
            writer.merge(selected)
        assert writer.segment_generations == before


def test_merged_segment_commits_and_reopens(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.delete_by_term("id", "2")
        writer.merge(writer.segment_generations)
        manifest = writer.commit()
    assert len(manifest.segments) == 1
    reader = Index.open(tmp_path).open_reader()
    assert reader.num_live_docs == 2
    assert reader.search(TermQuery("body", "deleted"), top_k=10).total_hits == 0
    assert reader.search(TermQuery("body", "kafka"), top_k=10).total_hits == 2
