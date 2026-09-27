from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from soda.compiler.span import Span


class TokenKind(Enum):
    EOF = auto()
    IDENT = auto()
    INT = auto()
    FLOAT = auto()
    STRING = auto()
    DURATION = auto()

    CONST = auto()
    MOTION = auto()
    STEP = auto()
    PARALLEL = auto()
    WAIT = auto()
    FLOW = auto()
    USING = auto()
    TRUE = auto()
    FALSE = auto()

    LBRACE = auto()
    RBRACE = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()
    DOT = auto()
    COLON = auto()
    SEMICOLON = auto()
    ARROW = auto()

    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    EQ = auto()
    EQEQ = auto()
    BANGEQ = auto()
    LT = auto()
    LTE = auto()
    GT = auto()
    GTE = auto()
    ANDAND = auto()
    OROR = auto()
    BANG = auto()


KEYWORDS = {
    "const": TokenKind.CONST,
    "motion": TokenKind.MOTION,
    "step": TokenKind.STEP,
    "parallel": TokenKind.PARALLEL,
    "wait": TokenKind.WAIT,
    "flow": TokenKind.FLOW,
    "using": TokenKind.USING,
    "true": TokenKind.TRUE,
    "false": TokenKind.FALSE,
}


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    lexeme: str
    span: Span
    value: Any = None
