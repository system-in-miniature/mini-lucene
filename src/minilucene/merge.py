from collections import defaultdict

from minilucene.index.postings import Posting
from minilucene.storage.image import SegmentImage


def merge_segment_images(
    *,
    generation: int,
    schema_fingerprint: str,
    segments: tuple[tuple[SegmentImage, frozenset[int]], ...],
) -> SegmentImage:
    doc_id_maps: list[dict[int, int]] = []
    stored_documents: dict[int, dict[str, str]] = {}
    next_doc_id = 0
    all_fields = {
        field
        for image, _ in segments
        for field in image.field_lengths
    }
    field_lengths: dict[str, list[int]] = {
        field: [] for field in all_fields
    }

    for image, live_docs in segments:
        mapping: dict[int, int] = {}
        for old_doc_id in sorted(live_docs):
            mapping[old_doc_id] = next_doc_id
            stored_documents[next_doc_id] = dict(
                image.stored_documents[old_doc_id]
            )
            for field in all_fields:
                lengths = image.field_lengths.get(field)
                field_lengths[field].append(
                    lengths[old_doc_id] if lengths is not None else 0
                )
            next_doc_id += 1
        doc_id_maps.append(mapping)

    postings: dict[str, dict[str, list[Posting]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for (image, _), mapping in zip(
        segments, doc_id_maps, strict=True
    ):
        for field, terms in image.postings.items():
            for term, term_postings in terms.items():
                for posting in term_postings:
                    if posting.doc_id in mapping:
                        postings[field][term].append(
                            Posting(
                                doc_id=mapping[posting.doc_id],
                                term_frequency=posting.term_frequency,
                                positions=posting.positions,
                            )
                        )

    return SegmentImage(
        generation=generation,
        schema_fingerprint=schema_fingerprint,
        stored_documents=stored_documents,
        postings={
            field: {
                term: tuple(term_postings)
                for term, term_postings in terms.items()
            }
            for field, terms in postings.items()
        },
        field_lengths={
            field: tuple(lengths)
            for field, lengths in field_lengths.items()
        },
    )
