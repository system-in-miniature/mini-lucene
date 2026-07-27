from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Token:
    term: str
    position: int
    start_offset: int
    end_offset: int
