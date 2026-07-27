from minilucene.search.collector import TopKCollector


def test_heap_topk_matches_complete_sort_oracle():
    scored = (
        (score, 1, doc)
        for doc, score in enumerate((1.0, 5.0, 3.0, 5.0))
    )
    collector = TopKCollector(2)
    for score, segment, doc in scored:
        collector.collect(score, segment, doc)
    assert [
        (hit.score, hit.local_doc_id)
        for hit in collector.top_docs().hits
    ] == [
        (5.0, 1),
        (5.0, 3),
    ]
    assert collector.max_retained == 2
    assert collector.top_docs().total_hits == 4


def test_ties_prefer_lower_segment_then_lower_local_doc_id():
    collector = TopKCollector(2)
    for segment, doc in ((2, 0), (1, 4), (1, 2)):
        collector.collect(1.0, segment, doc)
    assert [
        (hit.segment_generation, hit.local_doc_id)
        for hit in collector.top_docs().hits
    ] == [(1, 2), (1, 4)]


def test_zero_topk_counts_hits_without_retaining_them():
    collector = TopKCollector(0)
    collector.collect(1.0, 1, 0)
    result = collector.top_docs()
    assert result.total_hits == 1
    assert result.hits == ()
    assert collector.max_retained == 0
