from minilucene.highlight import (
    highlight_document,
    validate_highlight_fields,
)
from minilucene.query.model import Query
from minilucene.query_parser import parse_query
from minilucene.search.bm25 import BM25
from minilucene.search.collector import TopDocs, TopKCollector
from minilucene.search.reader import ReaderView
from minilucene.search.scorer import score_query


class IndexSearcher:
    def __init__(
        self, reader: ReaderView, *, similarity: BM25 | None = None
    ) -> None:
        self.reader = reader
        self.similarity = similarity or BM25()

    def search(
        self,
        query: Query,
        *,
        top_k: int = 10,
        highlight_fields: tuple[str, ...] = (),
    ) -> TopDocs:
        validate_highlight_fields(self.reader.schema, highlight_fields)
        rewritten = self.reader.rewrite(query)
        collector = TopKCollector(top_k)
        for doc_id, score in score_query(
            self.reader, rewritten, self.similarity
        ).items():
            address = self.reader.address(doc_id)
            stored_fields = self.reader.stored_fields(doc_id)
            collector.collect(
                score,
                address.segment_generation,
                address.local_doc_id,
                stored_fields,
                highlight_document(
                    stored_fields, rewritten, highlight_fields
                ),
            )
        return collector.top_docs()

    def search_text(
        self,
        source: str,
        *,
        default_field: str,
        top_k: int = 10,
        highlight_fields: tuple[str, ...] = (),
    ) -> TopDocs:
        return self.search(
            parse_query(source, self.reader.schema, default_field),
            top_k=top_k,
            highlight_fields=highlight_fields,
        )
