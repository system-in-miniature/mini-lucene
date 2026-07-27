from collections import defaultdict
from collections.abc import Mapping
from types import MappingProxyType

from minilucene.analysis import KeywordAnalyzer, StandardAnalyzer
from minilucene.analysis.model import Token
from minilucene.document import FrozenDocument, freeze_document
from minilucene.index.postings import MemorySegment, Posting
from minilucene.query.model import Query
from minilucene.schema import FieldType, Schema


def _analyze(field: FieldType, value: str) -> tuple[Token, ...]:
    if field.analyzer_name == "standard":
        return StandardAnalyzer().analyze(value)
    if field.analyzer_name == "keyword":
        return KeywordAnalyzer().analyze(value)
    raise ValueError(f"unknown analyzer: {field.analyzer_name}")


class RamIndexBuilder:
    def __init__(self, schema: Schema) -> None:
        self.schema = schema
        self._stored_documents: list[FrozenDocument] = []
        self._field_lengths: dict[str, list[int]] = {
            name: [] for name, field in schema.items() if field.indexed
        }
        self._postings: dict[
            str, dict[str, list[Posting]]
        ] = defaultdict(lambda: defaultdict(list))

    @property
    def document_count(self) -> int:
        return len(self._stored_documents)

    def add_document(self, values: Mapping[str, object]) -> int:
        document = freeze_document(self.schema, values)
        prepared: dict[str, tuple[Token, ...]] = {}
        for name, field in self.schema.items():
            if field.indexed and name in document:
                prepared[name] = _analyze(field, document[name])

        doc_id = self.document_count
        stored = MappingProxyType(
            {
                name: value
                for name, value in document.items()
                if self.schema[name].stored
            }
        )
        self._stored_documents.append(stored)

        for name, lengths in self._field_lengths.items():
            tokens = prepared.get(name, ())
            lengths.append(len(tokens))
            positions_by_term: dict[str, list[int]] = defaultdict(list)
            for token in tokens:
                positions_by_term[token.term].append(token.position)
            field = self.schema[name]
            for term, positions in positions_by_term.items():
                posting_positions = (
                    tuple(positions) if field.store_positions else ()
                )
                self._postings[name][term].append(
                    Posting(
                        doc_id=doc_id,
                        term_frequency=len(positions),
                        positions=posting_positions,
                    )
                )
        return doc_id

    def freeze(self, *, generation: int) -> MemorySegment:
        if generation < 0:
            raise ValueError("segment generation must be non-negative")
        postings = MappingProxyType(
            {
                field: MappingProxyType(
                    {
                        term: tuple(term_postings)
                        for term, term_postings in sorted(terms.items())
                    }
                )
                for field, terms in sorted(self._postings.items())
            }
        )
        field_lengths = MappingProxyType(
            {
                field: tuple(lengths)
                for field, lengths in sorted(self._field_lengths.items())
            }
        )
        return MemorySegment(
            generation=generation,
            max_doc=self.document_count,
            postings=postings,
            stored_documents=tuple(self._stored_documents),
            field_lengths=field_lengths,
        )


class MemoryIndex:
    def __init__(self, schema: Schema) -> None:
        self.schema = schema
        self._builder = RamIndexBuilder(schema)

    def add_document(self, **values: object) -> int:
        return self._builder.add_document(values)

    def search(self, query: Query, *, top_k: int = 10):
        from minilucene.search.reader import ReaderView
        from minilucene.search.searcher import IndexSearcher

        segment = self._builder.freeze(generation=0)
        reader = ReaderView(self.schema, (segment,))
        return IndexSearcher(reader).search(query, top_k=top_k)
