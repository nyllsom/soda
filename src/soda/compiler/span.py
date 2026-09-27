from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Span:
    start: int
    end: int
    line: int
    column: int
    end_line: int
    end_column: int

    @staticmethod
    def merge(first: "Span", last: "Span") -> "Span":
        return Span(
            first.start,
            last.end,
            first.line,
            first.column,
            last.end_line,
            last.end_column,
        )

    def short(self) -> str:
        return f"{self.line}:{self.column}"
