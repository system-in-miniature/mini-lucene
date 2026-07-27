import pytest

from minilucene.query_parser.errors import QuerySyntaxError
from minilucene.query_parser.lexer import TokenKind, lex


def test_lexer_preserves_offsets_and_quoted_text():
    tokens = lex('title:kafka AND body:"follower replicas"')
    assert [(token.kind, token.text, token.start) for token in tokens] == [
        (TokenKind.WORD, "title", 0),
        (TokenKind.COLON, ":", 5),
        (TokenKind.WORD, "kafka", 6),
        (TokenKind.AND, "AND", 12),
        (TokenKind.WORD, "body", 16),
        (TokenKind.COLON, ":", 20),
        (TokenKind.PHRASE, "follower replicas", 21),
        (TokenKind.EOF, "", 40),
    ]


def test_lexer_recognizes_grouping_unary_and_case_insensitive_operators():
    tokens = lex("(a and -b) Or NoT c")
    assert [token.kind for token in tokens] == [
        TokenKind.LPAREN,
        TokenKind.WORD,
        TokenKind.AND,
        TokenKind.MINUS,
        TokenKind.WORD,
        TokenKind.RPAREN,
        TokenKind.OR,
        TokenKind.NOT,
        TokenKind.WORD,
        TokenKind.EOF,
    ]


def test_lexer_decodes_only_quote_and_backslash_escapes_in_phrases():
    tokens = lex(r'"a \"quote\" and \\ path"')
    assert tokens[0].kind is TokenKind.PHRASE
    assert tokens[0].text == 'a "quote" and \\ path'


def test_lexer_marks_one_trailing_star_as_prefix():
    tokens = lex("kaf*")
    assert (tokens[0].kind, tokens[0].text) == (
        TokenKind.PREFIX,
        "kaf",
    )


@pytest.mark.parametrize("source", ["*kaf", "ka*f", "kaf**", "*"])
def test_illegal_wildcard_placement_reports_its_offset(source):
    with pytest.raises(QuerySyntaxError) as error:
        lex(source)
    assert error.value.offset == source.index("*")


def test_unclosed_phrase_reports_opening_offset_and_caret():
    with pytest.raises(QuerySyntaxError) as error:
        lex('"broken')
    assert error.value.offset == 0
    assert '"broken\n^' in str(error.value)
