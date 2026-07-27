from minilucene.query import MatchAllQuery, TermQuery
from tests.helpers.corpus import build_multi_segment_reader


def test_corpus_stats_span_segments_and_only_live_documents():
    reader = build_multi_segment_reader(
        segments=(("kafka kafka", "rabbit"), ("kafka replicas",)),
        deleted=((1,), ()),
    )
    stats = reader.corpus_stats
    assert stats.live_doc_count == 2
    assert stats.doc_frequency("body", "kafka") == 2
    assert stats.average_length("body") == 2.0


def test_reader_translates_segment_local_ids_to_snapshot_ids_and_addresses():
    reader = build_multi_segment_reader(
        segments=(("alpha", "deleted"), ("alpha",)),
        deleted=((1,), ()),
    )
    assert [posting.doc_id for posting in reader.postings("body", "alpha")] == [
        0,
        2,
    ]
    assert reader.address(0).segment_generation == 1
    assert reader.address(2).segment_generation == 2
    assert reader.address(2).local_doc_id == 0


def test_match_all_and_term_queries_exclude_deleted_documents():
    reader = build_multi_segment_reader(
        segments=(("alpha", "alpha"),),
        deleted=((0,),),
    )
    assert reader.match(MatchAllQuery()) == {1}
    assert reader.match(TermQuery("body", "alpha")) == {1}


def test_stored_fields_and_lengths_resolve_through_snapshot_address():
    reader = build_multi_segment_reader(
        segments=(("one two",), ("three",)),
        deleted=((), ()),
    )
    assert reader.stored_fields(1) == {"body": "three"}
    assert reader.field_length("body", 0) == 2
    assert reader.field_length("body", 1) == 1
