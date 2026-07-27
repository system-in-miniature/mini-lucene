from minilucene import Index, KeywordField, Schema, TextField
from minilucene.evaluation import precision_at_k
from minilucene.query_parser import parse_query


def _ids(results):
    return tuple(hit.stored_fields["id"] for hit in results.hits)


def test_documented_public_api_closes_the_v1_product_loop(tmp_path):
    schema = Schema(
        id=KeywordField(stored=True),
        title=TextField(stored=True, boost=2.0),
        body=TextField(stored=True),
        author=KeywordField(stored=True),
    )
    index = Index.create(tmp_path, schema)
    with index.writer() as writer:
        writer.add_document(
            id="1",
            title="Kafka Replication",
            body="Kafka uses follower replicas.",
            author="jonah",
        )
        writer.flush()
        writer.add_document(
            id="2",
            title="Rabbit Messaging",
            body="Rabbit uses durable queues.",
            author="sam",
        )
        writer.commit()

    reopened = Index.open(tmp_path)
    old_reader = reopened.open_reader()
    query_text = 'title:kafka OR body:"follower replicas"'
    query = parse_query(query_text, schema, "body")
    initial = old_reader.search(
        query, top_k=2, highlight_fields=("title", "body")
    )
    assert _ids(initial) == ("1",)
    assert initial.hits[0].highlights["body"] == (
        "Kafka uses <em>follower replicas</em>."
    )

    with reopened.writer() as writer:
        writer.add_document(
            id="3",
            title="Follower Operations",
            body="A follower replica refreshes.",
            author="lee",
        )
        nrt = writer.refresh()
        assert set(
            _ids(
                nrt.search_text(
                    "follower",
                    default_field="body",
                    top_k=10,
                )
            )
        ) == {"1", "3"}
        writer.update_document(
            field="id",
            term="2",
            id="2",
            title="Queue Operations",
            body="Queues isolate consumers.",
            author="sam",
        )
        writer.delete_by_term("id", "1")
        writer.commit()
        nrt.close()

    current_reader = reopened.open_reader()
    assert _ids(old_reader.search(query, top_k=10)) == ("1",)
    assert _ids(current_reader.search(query, top_k=10)) == ()

    with reopened.writer() as writer:
        writer.merge(writer.segment_generations)
        writer.commit()
    final_index = Index.open(tmp_path)
    final_reader = final_index.open_reader()
    final = final_reader.search_text(
        "follower OR queues",
        default_field="body",
        top_k=10,
        highlight_fields=("body",),
    )
    ranked = _ids(final)
    assert set(ranked) == {"2", "3"}
    assert precision_at_k(ranked, {"2", "3"}, 2) == 1.0

    old_reader.close()
    current_reader.close()
    final_reader.close()
    final_index.close()
    reopened.collect_garbage()
    reopened.close()
    index.close()
    diagnostics = reopened.lifecycle_diagnostics()
    assert diagnostics.reader_owners == ()
    assert diagnostics.writer_owner is None
    assert diagnostics.segment_owners == {}
