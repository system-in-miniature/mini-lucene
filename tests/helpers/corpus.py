from minilucene.index.memory import RamIndexBuilder
from minilucene.schema import Schema, TextField


class SingleSegmentReader:
    def __init__(self, segment):
        self.segment = segment
        self.max_doc = segment.max_doc
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
