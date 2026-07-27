from dataclasses import dataclass

from minilucene.index.memory import RamIndexBuilder
from minilucene.schema import KeywordField, Schema, TextField


class SingleSegmentReader:
    def __init__(self, segment):
        self.segment = segment
        self.max_doc = segment.max_doc
        self.live_doc_ids = frozenset(range(segment.max_doc))
        self.max_prefix_expansions = 1_024

    def postings(self, field, term):
        return self.segment.postings.get(field, {}).get(term, ())

    def terms_with_prefix(self, field, prefix):
        return tuple(
            term
            for term in self.segment.postings.get(field, {})
            if term.startswith(prefix)
        )

    def has_phrase(self, field, terms, query_positions, doc_id):
        positions = []
        for term in terms:
            posting = next(
                (
                    item
                    for item in self.postings(field, term)
                    if item.doc_id == doc_id
                ),
                None,
            )
            if posting is None:
                return False
            positions.append(set(posting.positions))
        return any(
            all(
                start + query_position in term_positions
                for query_position, term_positions in zip(
                    query_positions, positions, strict=True
                )
            )
            for start in positions[0]
        )

    def match(self, query):
        from minilucene.query.match import match_query

        return match_query(self, query)


def build_memory_reader(documents):
    builder = RamIndexBuilder(Schema(body=TextField(stored=True)))
    for document in documents:
        builder.add_document({"body": document})
    return SingleSegmentReader(builder.freeze(generation=0))


def build_multi_segment_reader(*, segments, deleted):
    from minilucene.search.reader import ReaderView

    built = []
    live_docs = []
    for generation, (documents, removed) in enumerate(
        zip(segments, deleted, strict=True),
        start=1,
    ):
        builder = RamIndexBuilder(Schema(body=TextField(stored=True)))
        for document in documents:
            builder.add_document({"body": document})
        segment = builder.freeze(generation=generation)
        built.append(segment)
        live_docs.append(frozenset(range(segment.max_doc)) - frozenset(removed))
    schema = Schema(body=TextField(stored=True))
    return ReaderView(schema, tuple(built), tuple(live_docs))


@dataclass(frozen=True)
class OracleHit:
    score: float
    stored_fields: object
    segment_generation: int
    local_doc_id: int


def search_memory(*, documents, query, title_boost=1.0):
    from minilucene.search.reader import ReaderView
    from minilucene.search.scorer import score_query

    schema = Schema(
        id=KeywordField(stored=True),
        title=TextField(stored=True, boost=title_boost),
        body=TextField(stored=True),
    )
    builder = RamIndexBuilder(schema)
    for index, document in enumerate(documents):
        builder.add_document({"id": str(index), **document})
    reader = ReaderView(schema, (builder.freeze(generation=0),))
    scores = score_query(reader, query)
    hits = [
        OracleHit(
            score=score,
            stored_fields=reader.stored_fields(doc_id),
            segment_generation=reader.address(doc_id).segment_generation,
            local_doc_id=reader.address(doc_id).local_doc_id,
        )
        for doc_id, score in scores.items()
    ]
    return sorted(
        hits,
        key=lambda hit: (
            -hit.score,
            hit.segment_generation,
            hit.local_doc_id,
        ),
    )
