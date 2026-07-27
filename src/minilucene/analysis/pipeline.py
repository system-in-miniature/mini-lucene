from collections.abc import Iterable
from dataclasses import replace
from typing import Protocol

from minilucene.analysis.model import Token


class Tokenizer(Protocol):
    def tokenize(self, text: str) -> tuple[Token, ...]: ...


class TokenFilter(Protocol):
    def apply(self, tokens: Iterable[Token]) -> tuple[Token, ...]: ...


class LowercaseFilter:
    def apply(self, tokens: Iterable[Token]) -> tuple[Token, ...]:
        return tuple(
            replace(token, term=token.term.lower()) for token in tokens
        )


class StopwordFilter:
    def __init__(self, stopwords: frozenset[str]) -> None:
        self.stopwords = stopwords

    def apply(self, tokens: Iterable[Token]) -> tuple[Token, ...]:
        return tuple(
            token for token in tokens if token.term not in self.stopwords
        )


class Analyzer:
    def __init__(
        self, tokenizer: Tokenizer, filters: tuple[TokenFilter, ...]
    ) -> None:
        self.tokenizer = tokenizer
        self.filters = filters

    def analyze(self, text: str) -> tuple[Token, ...]:
        tokens = self.tokenizer.tokenize(text)
        for token_filter in self.filters:
            tokens = token_filter.apply(tokens)
        return tokens
