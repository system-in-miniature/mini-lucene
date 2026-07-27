import re

from minilucene.analysis.model import Token
from minilucene.analysis.pipeline import (
    Analyzer,
    LowercaseFilter,
    StopwordFilter,
)

_WORD_PATTERN = re.compile(r"\w+", re.UNICODE)


class StandardTokenizer:
    def tokenize(self, text: str) -> tuple[Token, ...]:
        return tuple(
            Token(
                term=match.group(),
                position=position,
                start_offset=match.start(),
                end_offset=match.end(),
            )
            for position, match in enumerate(_WORD_PATTERN.finditer(text))
        )


class KeywordTokenizer:
    def tokenize(self, text: str) -> tuple[Token, ...]:
        if not text:
            return ()
        return (Token(text, 0, 0, len(text)),)


def StandardAnalyzer(
    *, stopwords: frozenset[str] = frozenset()
) -> Analyzer:
    return Analyzer(
        StandardTokenizer(),
        (LowercaseFilter(), StopwordFilter(stopwords)),
    )


def KeywordAnalyzer() -> Analyzer:
    return Analyzer(KeywordTokenizer(), ())
