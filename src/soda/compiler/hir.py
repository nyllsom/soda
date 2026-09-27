from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class HirExpr:
    kind: str
    type: str
    data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class HirConstant:
    name: str
    type: str
    value: HirExpr


@dataclass(frozen=True, slots=True)
class HirStmt:
    kind: str
    data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class HirBlock:
    statements: tuple[HirStmt, ...]


@dataclass(frozen=True, slots=True)
class HirMotion:
    slide_name: str
    timeline: HirBlock


@dataclass(frozen=True, slots=True)
class HirFlowEdge:
    source: str
    target: str
    transition: HirExpr | None


@dataclass(frozen=True, slots=True)
class HirProgram:
    constants: tuple[HirConstant, ...]
    motions: tuple[HirMotion, ...]
    flow: tuple[HirFlowEdge, ...]
