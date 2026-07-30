"""Strict educational encoding for one immutable segment's data files.

The layout favors inspectable invariants over Lucene compatibility: terms
name contiguous slices in one postings file, while stored documents and norms
have explicit frame counts.  Decoders reject non-canonical ordering, gaps,
overlap, truncation, and trailing bytes so corrupt input cannot be accepted as
a plausible but different index.
"""

import json
from collections.abc import Mapping

from minilucene.index.postings import Posting
from minilucene.storage.image import SegmentImage
from minilucene.storage.varint import (
    decode_delta_sequence,
    decode_uvarint,
    encode_delta_sequence,
    encode_uvarint,
)

_DATA_FILES = frozenset(
    {"terms.bin", "postings.bin", "stored.bin", "norms.bin"}
)


def _encode_bytes(value: bytes) -> bytes:
    return encode_uvarint(len(value)) + value


def _decode_bytes(
    data: bytes, offset: int, *, label: str
) -> tuple[bytes, int]:
    length, offset = decode_uvarint(data, offset)
    end = offset + length
    if end > len(data):
        raise ValueError(f"{label} frame outside input")
    return data[offset:end], end


def _decode_text(
    data: bytes, offset: int, *, label: str
) -> tuple[str, int]:
    encoded, offset = _decode_bytes(data, offset, label=label)
    try:
        return encoded.decode("utf-8", errors="strict"), offset
    except UnicodeDecodeError as error:
        raise ValueError(f"{label} must be strict UTF-8") from error


def _encode_posting_list(postings: tuple[Posting, ...]) -> bytes:
    encoded = bytearray(encode_uvarint(len(postings)))
    previous_doc_id = 0
    for index, posting in enumerate(postings):
        doc_delta = (
            posting.doc_id
            if index == 0
            else posting.doc_id - previous_doc_id
        )
        encoded.extend(encode_uvarint(doc_delta))
        encoded.extend(encode_uvarint(posting.term_frequency))
        encoded.extend(encode_uvarint(len(posting.positions)))
        encoded.extend(encode_delta_sequence(posting.positions))
        previous_doc_id = posting.doc_id
    return bytes(encoded)


def _decode_posting_list(data: bytes) -> tuple[Posting, ...]:
    count, offset = decode_uvarint(data, 0)
    postings: list[Posting] = []
    previous_doc_id = 0
    for index in range(count):
        delta, offset = decode_uvarint(data, offset)
        if index and delta == 0:
            raise ValueError("posting doc IDs must be strictly increasing")
        doc_id = delta if index == 0 else previous_doc_id + delta
        term_frequency, offset = decode_uvarint(data, offset)
        position_count, offset = decode_uvarint(data, offset)
        positions, offset = decode_delta_sequence(
            data, offset, position_count
        )
        postings.append(
            Posting(
                doc_id=doc_id,
                term_frequency=term_frequency,
                positions=positions,
            )
        )
        previous_doc_id = doc_id
    # Consuming the frame exactly prevents a valid posting prefix from hiding
    # appended garbage or a second ambiguous interpretation.
    if offset != len(data):
        raise ValueError("trailing bytes in posting list")
    return tuple(postings)


class SegmentDataCodec:
    @staticmethod
    def encode(image: SegmentImage) -> dict[str, bytes]:
        postings_data = bytearray()
        term_entries: list[tuple[str, str, int, int]] = []
        for field, terms in image.postings.items():
            for term, postings in terms.items():
                encoded = _encode_posting_list(postings)
                offset = len(postings_data)
                postings_data.extend(encoded)
                term_entries.append((field, term, offset, len(encoded)))

        terms_data = bytearray(encode_uvarint(len(term_entries)))
        for field, term, offset, length in term_entries:
            terms_data.extend(_encode_bytes(field.encode("utf-8")))
            terms_data.extend(_encode_bytes(term.encode("utf-8")))
            terms_data.extend(encode_uvarint(offset))
            terms_data.extend(encode_uvarint(length))

        stored_data = bytearray(encode_uvarint(image.max_doc))
        for doc_id in range(image.max_doc):
            encoded = json.dumps(
                dict(image.stored_documents[doc_id]),
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            stored_data.extend(_encode_bytes(encoded))

        norms_data = bytearray(
            encode_uvarint(len(image.field_lengths))
        )
        for field, lengths in image.field_lengths.items():
            norms_data.extend(_encode_bytes(field.encode("utf-8")))
            norms_data.extend(encode_uvarint(len(lengths)))
            for length in lengths:
                norms_data.extend(encode_uvarint(length))

        return {
            "terms.bin": bytes(terms_data),
            "postings.bin": bytes(postings_data),
            "stored.bin": bytes(stored_data),
            "norms.bin": bytes(norms_data),
        }

    @staticmethod
    def decode(
        *,
        generation: int,
        schema_fingerprint: str,
        files: Mapping[str, bytes],
    ) -> SegmentImage:
        # Fail closed on both missing and unknown files.  Silently ignoring an
        # extra component could open bytes written by a newer/incompatible
        # format under the wrong semantics.
        if set(files) != _DATA_FILES:
            raise ValueError(
                "segment data requires exactly terms, postings, stored, "
                "and norms files"
            )
        if any(not isinstance(value, bytes) for value in files.values()):
            raise ValueError("segment file values must be bytes")

        term_entries = SegmentDataCodec._decode_terms(files["terms.bin"])
        postings = SegmentDataCodec._decode_postings(
            term_entries, files["postings.bin"]
        )
        stored_documents = SegmentDataCodec._decode_stored(
            files["stored.bin"]
        )
        field_lengths = SegmentDataCodec._decode_norms(
            files["norms.bin"]
        )
        return SegmentImage(
            generation=generation,
            schema_fingerprint=schema_fingerprint,
            stored_documents=stored_documents,
            postings=postings,
            field_lengths=field_lengths,
        )

    @staticmethod
    def _decode_terms(
        data: bytes,
    ) -> tuple[tuple[str, str, int, int], ...]:
        count, offset = decode_uvarint(data, 0)
        entries: list[tuple[str, str, int, int]] = []
        previous_key: tuple[str, str] | None = None
        # Requiring a canonical, gap-free partition catches overlap, aliasing,
        # reordered slices, and unreferenced bytes before postings are decoded.
        expected_postings_offset = 0
        for _ in range(count):
            field, offset = _decode_text(
                data, offset, label="term field"
            )
            term, offset = _decode_text(
                data, offset, label="term value"
            )
            postings_offset, offset = decode_uvarint(data, offset)
            postings_length, offset = decode_uvarint(data, offset)
            key = (field, term)
            if previous_key is not None and key <= previous_key:
                raise ValueError("term dictionary must be strictly sorted")
            if postings_offset != expected_postings_offset:
                raise ValueError(
                    "posting offsets must be contiguous and ordered"
                )
            entries.append(
                (field, term, postings_offset, postings_length)
            )
            previous_key = key
            expected_postings_offset += postings_length
        if offset != len(data):
            raise ValueError("trailing bytes in term dictionary")
        return tuple(entries)

    @staticmethod
    def _decode_postings(
        entries: tuple[tuple[str, str, int, int], ...],
        data: bytes,
    ) -> dict[str, dict[str, tuple[Posting, ...]]]:
        postings: dict[str, dict[str, tuple[Posting, ...]]] = {}
        expected_end = 0
        for field, term, offset, length in entries:
            end = offset + length
            if end > len(data):
                raise ValueError("posting slice outside postings file")
            postings.setdefault(field, {})[term] = _decode_posting_list(
                data[offset:end]
            )
            expected_end = end
        # Every postings byte must be owned by exactly one sorted term entry;
        # otherwise corruption could remain invisible to query results.
        if expected_end != len(data):
            raise ValueError("trailing bytes in postings file")
        return postings

    @staticmethod
    def _decode_stored(
        data: bytes,
    ) -> dict[int, dict[str, str]]:
        count, offset = decode_uvarint(data, 0)
        documents: dict[int, dict[str, str]] = {}
        for doc_id in range(count):
            encoded, offset = _decode_bytes(
                data, offset, label="stored document"
            )
            try:
                value = json.loads(encoded.decode("utf-8", errors="strict"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("invalid stored JSON") from error
            if not isinstance(value, dict) or any(
                not isinstance(key, str) or not isinstance(item, str)
                for key, item in value.items()
            ):
                raise ValueError("stored JSON must map strings to strings")
            documents[doc_id] = value
        if offset != len(data):
            raise ValueError("trailing bytes in stored fields")
        return documents

    @staticmethod
    def _decode_norms(data: bytes) -> dict[str, tuple[int, ...]]:
        count, offset = decode_uvarint(data, 0)
        norms: dict[str, tuple[int, ...]] = {}
        previous_field: str | None = None
        for _ in range(count):
            field, offset = _decode_text(
                data, offset, label="norm field"
            )
            if previous_field is not None and field <= previous_field:
                raise ValueError("norm fields must be strictly sorted")
            length_count, offset = decode_uvarint(data, offset)
            lengths: list[int] = []
            for _ in range(length_count):
                length, offset = decode_uvarint(data, offset)
                lengths.append(length)
            norms[field] = tuple(lengths)
            previous_field = field
        if offset != len(data):
            raise ValueError("trailing bytes in norms file")
        return norms
