import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ReferenceQuery:
    id: str
    text: str
    default_field: str


@dataclass(frozen=True, slots=True)
class ReferenceCorpus:
    documents: tuple[dict[str, str], ...]
    queries: tuple[ReferenceQuery, ...]
    qrels: dict[str, dict[str, int]]


def _read_object(path: Path) -> dict[str, object]:
    payload = json.loads(
        path.read_text(encoding="utf-8", errors="strict")
    )
    if not isinstance(payload, dict):
        raise TypeError(f"fixture must contain an object: {path}")
    return payload


def load_reference_corpus(directory: Path) -> ReferenceCorpus:
    corpus_payload = _read_object(directory / "corpus.json")
    queries_payload = _read_object(directory / "queries.json")
    qrels_payload = _read_object(directory / "qrels.json")

    raw_documents = corpus_payload.get("documents")
    raw_queries = queries_payload.get("queries")
    raw_qrels = qrels_payload.get("qrels")
    if not isinstance(raw_documents, list):
        raise TypeError("corpus documents must be a list")
    if not isinstance(raw_queries, list):
        raise TypeError("queries must be a list")
    if not isinstance(raw_qrels, dict):
        raise TypeError("qrels must be an object")

    documents: list[dict[str, str]] = []
    for raw in raw_documents:
        if (
            not isinstance(raw, dict)
            or any(
                not isinstance(key, str)
                or not isinstance(value, str)
                for key, value in raw.items()
            )
            or not raw.get("id")
        ):
            raise ValueError("every document requires string fields and id")
        documents.append(dict(raw))
    if len({document["id"] for document in documents}) != len(
        documents
    ):
        raise ValueError("document IDs must be unique")

    queries: list[ReferenceQuery] = []
    for raw in raw_queries:
        if not isinstance(raw, dict):
            raise TypeError("every query must be an object")
        try:
            query = ReferenceQuery(
                id=raw["id"],
                text=raw["text"],
                default_field=raw["default_field"],
            )
        except (KeyError, TypeError) as error:
            raise ValueError("query fixture is invalid") from error
        if any(
            not isinstance(value, str) or not value
            for value in (
                query.id,
                query.text,
                query.default_field,
            )
        ):
            raise ValueError("query fields must be non-empty strings")
        queries.append(query)
    if len({query.id for query in queries}) != len(queries):
        raise ValueError("query IDs must be unique")

    qrels: dict[str, dict[str, int]] = {}
    for query_id, raw_grades in raw_qrels.items():
        if not isinstance(query_id, str) or not isinstance(
            raw_grades, dict
        ):
            raise TypeError("qrels entries must be objects")
        grades: dict[str, int] = {}
        for document_id, grade in raw_grades.items():
            if (
                not isinstance(document_id, str)
                or not isinstance(grade, int)
                or isinstance(grade, bool)
                or grade < 0
            ):
                raise ValueError(
                    "qrel grades must be non-negative integers"
                )
            grades[document_id] = grade
        qrels[query_id] = grades

    query_ids = {query.id for query in queries}
    document_ids = {document["id"] for document in documents}
    if set(qrels) != query_ids:
        raise ValueError("qrels must cover every query exactly")
    if any(set(grades) - document_ids for grades in qrels.values()):
        raise ValueError("qrels reference unknown documents")
    return ReferenceCorpus(
        documents=tuple(documents),
        queries=tuple(queries),
        qrels=qrels,
    )
