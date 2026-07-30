"""Token attributes shared unchanged across tokenizer and filter stages."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Token:
    """A term plus its source position and half-open character offsets."""

    term: str
    position: int
    start_offset: int
    end_offset: int

    def __post_init__(self) -> None:
        if not self.term:
            raise ValueError("term must be non-empty")
        if self.position < 0:
            raise ValueError("position must be non-negative")
        if self.start_offset < 0 or self.end_offset < 0:
            raise ValueError("offsets must be non-negative")
        if self.end_offset < self.start_offset:
            raise ValueError("end offset must not precede start offset")
