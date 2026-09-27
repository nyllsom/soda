from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from soda.compiler.span import Span


@dataclass(frozen=True, slots=True)
class Node:
    span: Span


@dataclass(frozen=True, slots=True)
class TypeRef(Node):
    name: tuple[str, ...]
    args: tuple["TypeRef", ...] = ()

    @property
    def display(self) -> str:
        base = ".".join(self.name)
        if not self.args:
            return base
        return f"{base}<{', '.join(arg.display for arg in self.args)}>"


@dataclass(frozen=True, slots=True)
class Expr(Node):
    pass


@dataclass(frozen=True, slots=True)
class LiteralExpr(Expr):
    value: Any
    literal_kind: str


@dataclass(frozen=True, slots=True)
class NameExpr(Expr):
    name: str


@dataclass(frozen=True, slots=True)
class UnaryExpr(Expr):
    op: str
    operand: Expr


@dataclass(frozen=True, slots=True)
class BinaryExpr(Expr):
    left: Expr
    op: str
    right: Expr


@dataclass(frozen=True, slots=True)
class ArrayExpr(Expr):
    items: tuple[Expr, ...]


@dataclass(frozen=True, slots=True)
class MemberExpr(Expr):
    target: Expr
    name: str


@dataclass(frozen=True, slots=True)
class IndexExpr(Expr):
    target: Expr
    index: Expr


@dataclass(frozen=True, slots=True)
class CallArg(Node):
    value: Expr
    name: str | None = None


@dataclass(frozen=True, slots=True)
class CallExpr(Expr):
    callee: Expr
    args: tuple[CallArg, ...]


@dataclass(frozen=True, slots=True)
class Stmt(Node):
    pass


@dataclass(frozen=True, slots=True)
class ExprStmt(Stmt):
    expr: Expr


@dataclass(frozen=True, slots=True)
class WaitStmt(Stmt):
    duration: Expr


@dataclass(frozen=True, slots=True)
class StepStmt(Stmt):
    label: str | None
    body: "Block"


@dataclass(frozen=True, slots=True)
class ParallelStmt(Stmt):
    args: tuple[CallArg, ...]
    body: "Block"


@dataclass(frozen=True, slots=True)
class Block(Node):
    statements: tuple[Stmt, ...]


@dataclass(frozen=True, slots=True)
class Decl(Node):
    pass


@dataclass(frozen=True, slots=True)
class ConstDecl(Decl):
    name: str
    value: Expr
    type_ref: TypeRef | None


@dataclass(frozen=True, slots=True)
class MotionDecl(Decl):
    slide_name: str
    timeline: Block


@dataclass(frozen=True, slots=True)
class FlowEdge(Node):
    source: str
    target: str
    transition: Expr | None


@dataclass(frozen=True, slots=True)
class FlowDecl(Decl):
    edges: tuple[FlowEdge, ...]


@dataclass(frozen=True, slots=True)
class Program(Node):
    declarations: tuple[Decl, ...]
