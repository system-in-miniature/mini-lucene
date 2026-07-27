from minilucene import Index, KeywordField, Schema, TextField


def build_two_segment_index(tmp_path):
    index = Index.create(
        tmp_path,
        Schema(
            id=KeywordField(stored=True),
            body=TextField(stored=True),
        ),
    )
    with index.writer() as writer:
        writer.add_document(id="1", body="first")
        writer.flush()
        writer.add_document(id="2", body="second")
        writer.commit()
    return index


def test_obsolete_segments_wait_for_old_reader_close(tmp_path):
    index = build_two_segment_index(tmp_path)
    old = index.open_reader()
    old_paths = tuple(
        tmp_path / "segments" / f"seg_{generation:06d}"
        for generation in (1, 2)
    )

    with index.writer() as writer:
        writer.merge(writer.segment_generations)
        writer.commit()

    index.collect_garbage()
    assert all(path.exists() for path in old_paths)
    old.close()
    index.collect_garbage()
    assert all(not path.exists() for path in old_paths)
    assert (tmp_path / "segments" / "seg_000003").exists()


def test_two_readers_retain_independently(tmp_path):
    index = build_two_segment_index(tmp_path)
    first = index.open_reader()
    second = index.open_reader()
    with index.writer() as writer:
        writer.merge(writer.segment_generations)
        writer.commit()
    first.close()
    index.collect_garbage()
    assert (tmp_path / "segments" / "seg_000001").exists()
    second.close()
    index.collect_garbage()
    assert not (tmp_path / "segments" / "seg_000001").exists()


def test_writer_retains_uncommitted_segment_until_close(tmp_path):
    index = Index.create(
        tmp_path,
        Schema(body=TextField(stored=True)),
    )
    writer = index.writer()
    writer.add_document(body="orphan")
    descriptor = writer.flush()
    path = tmp_path / descriptor.path
    index.collect_garbage()
    assert path.exists()
    writer.close()
    index.collect_garbage()
    assert not path.exists()


def test_garbage_collection_retains_malformed_directory(tmp_path):
    index = build_two_segment_index(tmp_path)
    malformed = tmp_path / "segments" / "seg_unknown"
    malformed.mkdir()
    index.collect_garbage()
    assert malformed.exists()


def test_registry_reports_reader_and_writer_owners(tmp_path):
    index = build_two_segment_index(tmp_path)
    reader = index.open_reader()
    writer = index.writer()
    diagnostics = index.lifecycle_diagnostics()
    assert len(diagnostics.reader_owners) == 1
    assert diagnostics.writer_owner is not None
    reader.close()
    writer.close()
    settled = index.lifecycle_diagnostics()
    assert settled.reader_owners == ()
    assert settled.writer_owner is None
