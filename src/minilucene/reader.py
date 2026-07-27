from minilucene.query.model import Query
from minilucene.schema import Schema
from minilucene.search.collector import TopDocs
from minilucene.search.reader import ReaderView
from minilucene.search.searcher import IndexSearcher
from minilucene.storage.image import SegmentImage


class IndexReader(ReaderView):
    def __init__(
        self,
        schema: Schema,
        segments: tuple[SegmentImage, ...],
    ) -> None:
        super().__init__(schema, segments)  # type: ignore[arg-type]

    def search(self, query: Query, *, top_k: int = 10) -> TopDocs:
        return IndexSearcher(self).search(query, top_k=top_k)
