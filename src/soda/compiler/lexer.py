from __future__ import annotations

from soda.compiler.diagnostics import Diagnostic, LexError
from soda.compiler.span import Span
from soda.compiler.tokens import KEYWORDS, Token, TokenKind


class Lexer:
    def __init__(self, source: str, *, path: str = "<input>") -> None:
        self.source = source
        self.path = path
        self.index = 0
        self.line = 1
        self.column = 1

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while not self._at_end():
            self._skip_trivia()
            if self._at_end():
                break
            tokens.append(self._scan_token())
        eof = Span(self.index, self.index, self.line, self.column, self.line, self.column)
        tokens.append(Token(TokenKind.EOF, "", eof))
        return tokens

    def _at_end(self) -> bool:
        return self.index >= len(self.source)

    def _peek(self, offset: int = 0) -> str:
        i = self.index + offset
        return "\0" if i >= len(self.source) else self.source[i]

    def _advance(self) -> str:
        ch = self.source[self.index]
        self.index += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _mark(self) -> tuple[int, int, int]:
        return self.index, self.line, self.column

    def _span(self, mark: tuple[int, int, int]) -> Span:
        start, line, column = mark
        return Span(start, self.index, line, column, self.line, self.column)

    def _error(self, mark: tuple[int, int, int], message: str) -> LexError:
        return LexError(Diagnostic(message, self._span(mark), self.path))

    def _skip_trivia(self) -> None:
        while not self._at_end():
            ch = self._peek()
            if ch.isspace():
                self._advance()
                continue
            if ch == "/" and self._peek(1) == "/":
                self._advance()
                self._advance()
                while not self._at_end() and self._peek() != "\n":
                    self._advance()
                continue
            if ch == "/" and self._peek(1) == "*":
                mark = self._mark()
                self._advance()
                self._advance()
                while not self._at_end() and not (self._peek() == "*" and self._peek(1) == "/"):
                    self._advance()
                if self._at_end():
                    raise self._error(mark, "unterminated block comment")
                self._advance()
                self._advance()
                continue
            break

    def _scan_token(self) -> Token:
        mark = self._mark()
        ch = self._advance()

        if ch.isalpha() or ch == "_":
            return self._identifier(mark)
        if ch.isdigit():
            return self._number(mark)
        if ch == '"':
            return self._string(mark)

        pairs = {
            "->": TokenKind.ARROW,
            "==": TokenKind.EQEQ,
            "!=": TokenKind.BANGEQ,
            "<=": TokenKind.LTE,
            ">=": TokenKind.GTE,
            "&&": TokenKind.ANDAND,
            "||": TokenKind.OROR,
        }
        pair = ch + self._peek()
        if pair in pairs:
            self._advance()
            span = self._span(mark)
            return Token(pairs[pair], self.source[span.start : span.end], span)

        singles = {
            "{": TokenKind.LBRACE,
            "}": TokenKind.RBRACE,
            "(": TokenKind.LPAREN,
            ")": TokenKind.RPAREN,
            "[": TokenKind.LBRACKET,
            "]": TokenKind.RBRACKET,
            ",": TokenKind.COMMA,
            ".": TokenKind.DOT,
            ":": TokenKind.COLON,
            ";": TokenKind.SEMICOLON,
            "+": TokenKind.PLUS,
            "-": TokenKind.MINUS,
            "*": TokenKind.STAR,
            "/": TokenKind.SLASH,
            "%": TokenKind.PERCENT,
            "=": TokenKind.EQ,
            "<": TokenKind.LT,
            ">": TokenKind.GT,
            "!": TokenKind.BANG,
        }
        kind = singles.get(ch)
        if kind is None:
            raise self._error(mark, f"unexpected character {ch!r}")
        span = self._span(mark)
        return Token(kind, ch, span)

    def _identifier(self, mark: tuple[int, int, int]) -> Token:
        while self._peek().isalnum() or self._peek() == "_":
            self._advance()
        span = self._span(mark)
        text = self.source[span.start : span.end]
        return Token(KEYWORDS.get(text, TokenKind.IDENT), text, span, text)

    def _number(self, mark: tuple[int, int, int]) -> Token:
        while self._peek().isdigit():
            self._advance()

        is_float = False
        if self._peek() == "." and self._peek(1).isdigit():
            is_float = True
            self._advance()
            while self._peek().isdigit():
                self._advance()

        if self._peek() in {"e", "E"}:
            is_float = True
            self._advance()
            if self._peek() in {"+", "-"}:
                self._advance()
            if not self._peek().isdigit():
                raise self._error(mark, "expected exponent digits")
            while self._peek().isdigit():
                self._advance()

        number_end = self.index
        unit = None
        if self.source.startswith("ms", self.index):
            unit = "ms"
            self._advance()
            self._advance()
        elif self._peek() == "s" and not (self._peek(1).isalnum() or self._peek(1) == "_"):
            unit = "s"
            self._advance()

        if self._peek().isalpha() or self._peek() == "_":
            raise self._error(mark, "invalid suffix on numeric literal")

        span = self._span(mark)
        number_text = self.source[mark[0] : number_end]
        value = float(number_text) if is_float else int(number_text)
        if unit is not None:
            seconds = float(value) / 1000.0 if unit == "ms" else float(value)
            return Token(TokenKind.DURATION, self.source[span.start : span.end], span, seconds)
        kind = TokenKind.FLOAT if is_float else TokenKind.INT
        return Token(kind, self.source[span.start : span.end], span, value)

    def _string(self, mark: tuple[int, int, int]) -> Token:
        triple = self._peek() == '"' and self._peek(1) == '"'
        if triple:
            self._advance()
            self._advance()

        out: list[str] = []
        while not self._at_end():
            if triple:
                if self._peek() == '"' and self._peek(1) == '"' and self._peek(2) == '"':
                    self._advance()
                    self._advance()
                    self._advance()
                    span = self._span(mark)
                    return Token(TokenKind.STRING, self.source[span.start : span.end], span, "".join(out))
            elif self._peek() == '"':
                self._advance()
                span = self._span(mark)
                return Token(TokenKind.STRING, self.source[span.start : span.end], span, "".join(out))

            ch = self._advance()
            if ch == "\n" and not triple:
                raise self._error(mark, "unterminated string literal")
            if ch == "\\":
                if self._at_end():
                    raise self._error(mark, "unterminated escape sequence")
                esc = self._advance()
                escapes = {"n": "\n", "r": "\r", "t": "\t", '"': '"', "\\": "\\"}
                if esc not in escapes:
                    raise self._error(mark, f"unsupported escape sequence \\{esc}")
                out.append(escapes[esc])
            else:
                out.append(ch)

        raise self._error(mark, "unterminated string literal")


def lex(source: str, *, path: str = "<input>") -> list[Token]:
    return Lexer(source, path=path).tokenize()
