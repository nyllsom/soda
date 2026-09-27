from __future__ import annotations

from dataclasses import dataclass

from soda.compiler.span import Span


@dataclass(frozen=True, slots=True)
class Diagnostic:
    message: str
    span: Span
    path: str = "<input>"

    def format(self, source: str) -> str:
        lines = source.splitlines()
        line = lines[self.span.line - 1] if 0 < self.span.line <= len(lines) else ""
        caret_len = max(1, self.span.end - self.span.start)
        if self.span.line != self.span.end_line:
            caret_len = max(1, len(line) - self.span.column + 2)
        caret = " " * max(0, self.span.column - 1) + "^" * min(caret_len, 80)
        return f"{self.path}:{self.span.line}:{self.span.column}: error: {self.message}\n{line}\n{caret}"


class SodaError(Exception):
    def __init__(self, diagnostic: Diagnostic):
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


class LexError(SodaError):
    pass


class ParseError(SodaError):
    pass


class SemanticError(SodaError):
    pass
