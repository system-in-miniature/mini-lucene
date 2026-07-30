"""Token attributes shared unchanged across tokenizer and filter stages."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Token:
    """A term plus its source position and half-open character offsets."""

    term: str
    position: int
    start_offset: int
    end_offset: int
