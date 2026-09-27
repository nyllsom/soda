from __future__ import annotations

from soda.compiler import ast
from soda.compiler.hir import (
    HirBlock,
    HirConstant,
    HirExpr,
    HirFlowEdge,
    HirMotion,
    HirProgram,
    HirStmt,
)
from soda.compiler.semantics import SemanticModel


class Lowerer:
    def __init__(self, model: SemanticModel) -> None:
        self.model = model

    def lower(self, program: ast.Program) -> HirProgram:
        constants: list[HirConstant] = []
        motions: list[HirMotion] = []
        flow: list[HirFlowEdge] = []

        for decl in program.declarations:
            if isinstance(decl, ast.ConstDecl):
                constants.append(
                    HirConstant(
                        decl.name,
                        str(self.model.constant_types[id(decl)]),
                        self._expr(decl.value),
                    )
                )
            elif isinstance(decl, ast.MotionDecl):
                motions.append(HirMotion(decl.slide_name, self._block(decl.timeline)))
            elif isinstance(decl, ast.FlowDecl):
                flow.extend(
                    HirFlowEdge(
                        edge.source,
                        edge.target,
                        None if edge.transition is None else self._expr(edge.transition),
                    )
                    for edge in decl.edges
                )
            else:
                raise AssertionError(type(decl).__name__)

        return HirProgram(tuple(constants), tuple(motions), tuple(flow))

    def _block(self, block: ast.Block) -> HirBlock:
        return HirBlock(tuple(self._stmt(stmt) for stmt in block.statements))

    def _stmt(self, stmt: ast.Stmt) -> HirStmt:
        if isinstance(stmt, ast.ExprStmt):
            return HirStmt("expr", {"expr": self._expr(stmt.expr)})
        if isinstance(stmt, ast.WaitStmt):
            return HirStmt("wait", {"duration": self._expr(stmt.duration)})
        if isinstance(stmt, ast.StepStmt):
            return HirStmt(
                "step",
                {"label": stmt.label, "body": self._block(stmt.body)},
            )
        if isinstance(stmt, ast.ParallelStmt):
            return HirStmt(
                "parallel",
                {
                    "args": tuple(self._arg(arg) for arg in stmt.args),
                    "body": self._block(stmt.body),
                },
            )
        raise AssertionError(type(stmt).__name__)

    def _arg(self, arg: ast.CallArg) -> dict[str, object]:
        return {"name": arg.name, "value": self._expr(arg.value)}

    def _expr(self, expr: ast.Expr) -> HirExpr:
        typ = str(self.model.type_of(expr))
        if isinstance(expr, ast.LiteralExpr):
            return HirExpr("literal", typ, {"value": expr.value, "literal_kind": expr.literal_kind})
        if isinstance(expr, ast.NameExpr):
            return HirExpr("name", typ, {"name": expr.name})
        if isinstance(expr, ast.ArrayExpr):
            return HirExpr("array", typ, {"items": tuple(self._expr(item) for item in expr.items)})
        if isinstance(expr, ast.UnaryExpr):
            return HirExpr("unary", typ, {"op": expr.op, "operand": self._expr(expr.operand)})
        if isinstance(expr, ast.BinaryExpr):
            return HirExpr(
                "binary",
                typ,
                {"op": expr.op, "left": self._expr(expr.left), "right": self._expr(expr.right)},
            )
        if isinstance(expr, ast.MemberExpr):
            return HirExpr("member", typ, {"target": self._expr(expr.target), "name": expr.name})
        if isinstance(expr, ast.IndexExpr):
            return HirExpr(
                "index",
                typ,
                {"target": self._expr(expr.target), "index": self._expr(expr.index)},
            )
        if isinstance(expr, ast.CallExpr):
            return HirExpr(
                "call",
                typ,
                {"callee": self._expr(expr.callee), "args": tuple(self._arg(arg) for arg in expr.args)},
            )
        raise AssertionError(type(expr).__name__)


def lower(program: ast.Program, model: SemanticModel) -> HirProgram:
    return Lowerer(model).lower(program)
