"""Restricted, standards-based Markdown for speaker notes.

Notes are independent of the presentation layout and SODA's object syntax.
Raw HTML is deliberately disabled; do not re-enable it for exported decks.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from markdown_it import MarkdownIt
from markdown_it.token import Token

MARKDOWN = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"])

# Directives are only meaningful in slide content, never in speaker notes.
_FENCE_START = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_NOTES_END = re.compile(r"^ {0,3}:::[ \t]*$")


def find_notes_close(lines: Sequence[str], start: int, end: int) -> int | None:
    """Locate a ::: closer outside Markdown fenced and indented code blocks."""
    fence: str | None = None
    for i in range(start, end):
        raw = lines[i].rstrip("\r\n")
        match = _FENCE_START.match(raw)
        if fence:
            if (match and match.group(1)[0] == fence[0]
                    and len(match.group(1)) >= len(fence)
                    and not raw[match.end():].strip()):
                fence = None
            continue
        if _NOTES_END.fullmatch(raw):
            return i
        if match:
            fence = match.group(1)
    return None


_SODA_DIRECTIVE = re.compile(
    r"^ {0,3}@(?:slide|video|remotion|zanim|typst|pdf|web|code|embed|chart|"
    r"diagram|enddiagram|cite|references)(?:\s|$)"
)
_SODA_ATTRIBUTES = re.compile(r"(?:^|\s)\{(?:\#[^{}]*|(?:columns|rows|grid|stack|overlay)\b[^{}]*)\}\s*$")


def parse_notes(source: str) -> list[Token]:
    return MARKDOWN.parse(source)


def invalid_notes_line(source: str) -> tuple[int, str] | None:
    """Return a zero-based line and the first unsupported notes construct."""
    tokens = parse_notes(source)
    code_lines: set[int] = set()
    for token in tokens:
        if token.type in {"fence", "code_block"} and token.map:
            code_lines.update(range(*token.map))
    errors: list[tuple[int, str]] = []
    for token in tokens:
        if token.type == "heading_open" and token.map:
            errors.append((token.map[0], "Markdown headings are not allowed inside ::: notes"))
    for i, line in enumerate(source.splitlines()):
        if i in code_lines:
            continue
        if line.strip().startswith(":::"):
            errors.append((i, "nested ::: containers are not allowed inside ::: notes"))
        elif _SODA_DIRECTIVE.match(line) or _SODA_ATTRIBUTES.search(line):
            errors.append((i, "SODA directives and layout attributes are not allowed inside ::: notes"))
    return min(errors, key=lambda error: error[0]) if errors else None
