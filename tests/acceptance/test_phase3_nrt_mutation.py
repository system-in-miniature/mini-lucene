from minilucene import Index, KeywordField, Schema, TextField
from minilucene.query import TermQuery


def ids(reader, term):
    return tuple(
        hit.stored_fields["id"]
        for hit in reader.search(
            TermQuery("body", term),
            top_k=10,
        ).hits
    )


def test_nrt_mutation_merge_recovery_and_owner_zero(tmp_path):
    schema = Schema(
        id=KeywordField(stored=True),
        body=TextField(stored=True),
    )
    index = Index.create(tmp_path, schema)
    with index.writer() as writer:
        writer.add_document(id="1", body="alpha old")
        writer.flush()
        writer.add_document(id="2", body="beta old")
        writer.commit()

    old_reader = index.open_reader()
    writer = index.writer()
    writer.add_document(id="3", body="gamma nrt")
    first_nrt = writer.refresh()
    assert ids(old_reader, "gamma") == ()
    assert ids(first_nrt, "gamma") == ("3",)
    writer.delete_by_term("id", "1")
    writer.update_document(
        field="id",
        term="2",
        id="2",
        body="beta replacement",
    )
    second_nrt = writer.refresh()
    assert ids(second_nrt, "alpha") == ()
    assert ids(second_nrt, "replacement") == ("2",)
    writer.close()

    crashed = Index.open(tmp_path)
    crash_reader = crashed.open_reader()
    assert ids(crash_reader, "alpha") == ("1",)
    assert ids(crash_reader, "old") == ("1", "2")
    assert ids(crash_reader, "gamma") == ()
    crash_reader.close()

    with crashed.writer() as writer:
        writer.delete_by_term("id", "1")
        writer.update_document(
            field="id",
            term="2",
            id="2",
            body="beta replacement",
        )
        writer.add_document(id="3", body="gamma committed")
        writer.flush()
        writer.merge(writer.segment_generations)
        writer.commit()

    committed = Index.open(tmp_path)
    final_reader = committed.open_reader()
    assert ids(final_reader, "alpha") == ()
    assert ids(final_reader, "replacement") == ("2",)
    assert ids(final_reader, "gamma") == ("3",)
    assert ids(old_reader, "old") == ("1", "2")

    old_reader.close()
    first_nrt.close()
    second_nrt.close()
    final_reader.close()
    committed.collect_garbage()
    diagnostics = committed.lifecycle_diagnostics()
    assert diagnostics.reader_owners == ()
    assert diagnostics.writer_owner is None
    assert diagnostics.segment_owners == {}
