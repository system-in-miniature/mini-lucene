import pytest

from minilucene.storage.live_docs import LiveDocsStore


def test_live_docs_store_publishes_and_reads_immutable_generation(tmp_path):
    segment = tmp_path / "segments" / "seg_000001"
    segment.mkdir(parents=True)
    store = LiveDocsStore(tmp_path)
    published = store.publish(
        segment_generation=1,
        live_docs_generation=1,
        max_doc=4,
        live_docs=frozenset({0, 3}),
    )
    assert published.path.name == "live_000001.bin"
    assert store.read(
        segment_generation=1,
        live_docs_generation=1,
        expected_checksum=published.checksum,
        max_doc=4,
    ) == frozenset({0, 3})


def test_live_docs_store_refuses_generation_overwrite(tmp_path):
    segment = tmp_path / "segments" / "seg_000001"
    segment.mkdir(parents=True)
    store = LiveDocsStore(tmp_path)
    store.publish(
        segment_generation=1,
        live_docs_generation=1,
        max_doc=1,
        live_docs=frozenset(),
    )
    with pytest.raises(FileExistsError):
        store.publish(
            segment_generation=1,
            live_docs_generation=1,
            max_doc=1,
            live_docs=frozenset({0}),
        )


def test_live_docs_store_rejects_checksum_mismatch(tmp_path):
    segment = tmp_path / "segments" / "seg_000001"
    segment.mkdir(parents=True)
    store = LiveDocsStore(tmp_path)
    store.publish(
        segment_generation=1,
        live_docs_generation=1,
        max_doc=1,
        live_docs=frozenset({0}),
    )
    with pytest.raises(ValueError, match="checksum"):
        store.read(
            segment_generation=1,
            live_docs_generation=1,
            expected_checksum="wrong",
            max_doc=1,
        )
