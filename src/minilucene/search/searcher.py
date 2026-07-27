from minilucene.query.model import Query
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

    def search(self, query: Query, *, top_k: int = 10) -> TopDocs:
        collector = TopKCollector(top_k)
        for doc_id, score in score_query(
            self.reader, query, self.similarity
        ).items():
            address = self.reader.address(doc_id)
            collector.collect(
                score,
                address.segment_generation,
                address.local_doc_id,
                self.reader.stored_fields(doc_id),
            )
        return collector.top_docs()
