from minilucene import Index, KeywordField, Schema, TextField


def test_every_explicit_owner_and_temporary_job_reaches_zero(tmp_path):
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
        first = writer.refresh()
        writer.add_document(id="2", body="second")
        second = writer.refresh()
        writer.merge(writer.segment_generations)
        writer.commit()
        first.close()
        second.close()
    index.collect_garbage()
    index.close()

    diagnostics = index.lifecycle_diagnostics()
    assert diagnostics.writer_owner is None
    assert diagnostics.reader_owners == ()
    assert diagnostics.segment_owners == {}
    assert diagnostics.temporary_jobs == ()
    assert not (index.path / ".writer.lock").exists()
    assert not list(index.path.rglob(".tmp-*"))
