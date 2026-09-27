from soda.compiler.lexer import lex
from soda.compiler.tokens import TokenKind


def test_duration_and_multiline_string_literals():
    tokens = lex('1s 250ms 1.5s """a\nb"""')
    assert [token.kind for token in tokens[:-1]] == [
        TokenKind.DURATION,
        TokenKind.DURATION,
        TokenKind.DURATION,
        TokenKind.STRING,
    ]
    assert [token.value for token in tokens[:3]] == [1.0, 0.25, 1.5]
    assert tokens[3].value == "a\nb"
