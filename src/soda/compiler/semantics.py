from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from soda.compiler import ast
from soda.compiler.diagnostics import Diagnostic, SemanticError
from soda.compiler.motion_api import (
    CODE_MOTION_METHODS,
    GENERIC_MOTION_METHODS,
    MATH_MOTION_METHODS,
    TRANSITION_KINDS,
    ZANIM_MOTION_METHODS,
)
from soda.compiler.typesys import (
    ANY,
    BOOL,
    CODE,
    DIRECTION,
    DURATION,
    EASING,
    FLOAT,
    INT,
    MATH,
    STRING,
    TRANSITION,
    UNIT,
    VEC2,
    ZANIM_SCENE,
    Type,
    array_of,
    assignable,
    bound_of,
    common_numeric,
    is_numeric,
)


class Phase(Enum):
    TOP = auto()
    TIMELINE = auto()


@dataclass(slots=True)
class SemanticModel:
    expr_types: dict[int, Type] = field(default_factory=dict)
    constant_types: dict[int, Type] = field(default_factory=dict)

    def type_of(self, expr: ast.Expr) -> Type:
        return self.expr_types[id(expr)]


class Scope:
    def __init__(self, parent: "Scope | None" = None) -> None:
        self.parent = parent
        self.values: dict[str, Type] = {}

    def define(self, name: str, value_type: Type) -> bool:
        if name in self.values:
            return False
        self.values[name] = value_type
        return True

    def lookup(self, name: str) -> Type | None:
        scope: Scope | None = self
        while scope is not None:
            if name in scope.values:
                return scope.values[name]
            scope = scope.parent
        return None


_TYPE_NAMES = {
    value.name: value
    for value in (
        ANY,
        UNIT,
        BOOL,
        INT,
        FLOAT,
        STRING,
        DURATION,
        VEC2,
        EASING,
        DIRECTION,
    )
}

_TIMING_ARGS = {
    "duration": DURATION,
    "at": DURATION,
    "easing": EASING,
}


class SemanticChecker:
    def __init__(
        self,
        *,
        path: str = "<input>",
        content_objects: dict[str, dict[str, Type]] | None = None,
    ) -> None:
        self.path = path
        self.model = SemanticModel()
        self.global_scope = Scope()
        self.content_objects = content_objects or {}
        self._parallel_depth = 0
        self._install_builtins()

    def _install_builtins(self) -> None:
        for name in ("LINEAR", "SMOOTHSTEP"):
            self.global_scope.define(name, EASING)
        for name in ("LEFT", "RIGHT", "UP", "DOWN"):
            self.global_scope.define(name, DIRECTION)

    def check(self, program: ast.Program) -> SemanticModel:
        for decl in program.declarations:
            if isinstance(decl, ast.ConstDecl):
                self._check_const(decl)

        for decl in program.declarations:
            if isinstance(decl, ast.MotionDecl):
                self._check_motion(decl)
            elif isinstance(decl, ast.FlowDecl):
                self._check_flow(decl)
            elif not isinstance(decl, ast.ConstDecl):
                raise AssertionError(type(decl).__name__)
        return self.model

    def _check_const(self, decl: ast.ConstDecl) -> None:
        if self.global_scope.lookup(decl.name) is not None:
            self._error(decl, f"duplicate top-level name {decl.name!r}")
        actual = self._infer(decl.value, self.global_scope, Phase.TOP)
        declared = self._resolve_type(decl.type_ref) if decl.type_ref else actual
        self._require_assignable(actual, declared, decl.value)
        self.global_scope.define(decl.name, declared)
        self.model.constant_types[id(decl)] = declared

    def _check_motion(self, decl: ast.MotionDecl) -> None:
        objects = self.content_objects.get(decl.slide_name)
        if objects is None:
            self._error(decl, f"unknown content slide {decl.slide_name!r} for motion block")
        scope = Scope(self.global_scope)
        scope.define("slide", bound_of(self.content_objects[decl.slide_name][decl.slide_name]))
        for name, typ in objects.items():
            if name == decl.slide_name:
                continue
            if not scope.define(name, bound_of(typ)):
                self._error(decl, f"content object id {name!r} conflicts with a motion symbol")
        self._check_block(decl.timeline, scope)

    def _check_flow(self, decl: ast.FlowDecl) -> None:
        known_slides = set(self.content_objects)
        for edge in decl.edges:
            if edge.source not in known_slides:
                self._error(edge, f"unknown source slide {edge.source!r}")
            if edge.target not in known_slides:
                self._error(edge, f"unknown target slide {edge.target!r}")
            if edge.transition is None:
                continue
            self._check_transition(edge)

    def _check_transition(self, edge: ast.FlowEdge) -> None:
        expr = edge.transition
        assert expr is not None
        if not isinstance(expr, ast.CallExpr) or not isinstance(expr.callee, ast.NameExpr):
            self._error(expr, "flow transitions must be transition calls")
        name = expr.callee.name
        if name not in TRANSITION_KINDS:
            self._error(expr.callee, f"unknown transition {name!r}")

        positional = [arg for arg in expr.args if arg.name is None]
        named = self._named_args(expr.args)

        allowed_named = {"duration", "easing"}
        for key in named:
            if key not in allowed_named:
                self._error(named[key], f"unknown {name}() option {key!r}")
        self._check_timing(named, allow_at=False)

        if name in {"fade", "cut"}:
            if positional:
                self._error(positional[0], f"{name}() does not accept positional arguments")
        elif name in {"push", "embed_zoom"}:
            if len(positional) > 1:
                self._error(expr, f"{name}() accepts at most one direction")
            if positional:
                actual = self._infer(positional[0].value, self.global_scope, Phase.TOP)
                self._require_assignable(actual, DIRECTION, positional[0].value)
        elif name == "shared":
            if not positional:
                self._error(expr, "shared() requires at least one object id")
            for arg in positional:
                if not isinstance(arg.value, ast.LiteralExpr) or arg.value.literal_kind != "String":
                    self._error(arg.value, "shared() object ids must be string literals")
                object_id = str(arg.value.value)
                for slide_id in (edge.source, edge.target):
                    if object_id not in self.content_objects.get(slide_id, {}):
                        self._error(
                            arg.value,
                            f"shared object {object_id!r} does not exist on slide {slide_id!r}",
                        )

        for arg in positional:
            self._infer(arg.value, self.global_scope, Phase.TOP)
        self.model.expr_types[id(expr.callee)] = Type("Function")
        self.model.expr_types[id(expr)] = TRANSITION

    def _check_block(self, block: ast.Block, scope: Scope) -> None:
        for stmt in block.statements:
            if isinstance(stmt, ast.ExprStmt):
                if not (
                    isinstance(stmt.expr, ast.CallExpr)
                    and isinstance(stmt.expr.callee, ast.MemberExpr)
                ):
                    self._error(
                        stmt,
                        "timeline statements must call a presentation object method",
                    )
                self._infer(stmt.expr, scope, Phase.TIMELINE)
                continue

            if isinstance(stmt, ast.WaitStmt):
                if self._parallel_depth:
                    self._error(
                        stmt,
                        "wait is not allowed inside parallel(), matching timeline semantics",
                    )
                typ = self._infer(stmt.duration, scope, Phase.TIMELINE)
                self._require_assignable(typ, DURATION, stmt.duration)
                continue

            if isinstance(stmt, ast.StepStmt):
                self._check_block(stmt.body, Scope(scope))
                continue

            if isinstance(stmt, ast.ParallelStmt):
                if self._parallel_depth:
                    self._error(stmt, "nested parallel() blocks are not supported")
                named = self._named_args(stmt.args)
                if any(arg.name is None for arg in stmt.args):
                    self._error(stmt, "parallel() options must use named arguments")
                for key in named:
                    if key != "duration":
                        self._error(named[key], f"unknown parallel() option {key!r}")
                if "duration" in named:
                    actual = self._infer(named["duration"].value, scope, Phase.TIMELINE)
                    self._require_assignable(actual, DURATION, named["duration"].value)
                self._parallel_depth += 1
                try:
                    self._check_block(stmt.body, Scope(scope))
                finally:
                    self._parallel_depth -= 1
                continue

            raise AssertionError(f"unhandled statement {type(stmt).__name__}")

    def _infer(self, expr: ast.Expr, scope: Scope, phase: Phase) -> Type:
        typ: Type
        if isinstance(expr, ast.LiteralExpr):
            typ = _TYPE_NAMES[expr.literal_kind]
        elif isinstance(expr, ast.NameExpr):
            value = scope.lookup(expr.name)
            if value is None:
                self._error(expr, f"unknown name {expr.name!r}")
            typ = value
        elif isinstance(expr, ast.ArrayExpr):
            typ = self._infer_array(expr, scope, phase)
        elif isinstance(expr, ast.UnaryExpr):
            typ = self._infer_unary(expr, scope, phase)
        elif isinstance(expr, ast.BinaryExpr):
            typ = self._infer_binary(expr, scope, phase)
        elif isinstance(expr, ast.MemberExpr):
            target = self._infer(expr.target, scope, phase)
            if not target.is_bound:
                self._error(expr, f"type {target} has no presentation methods")
            typ = Type("Method")
        elif isinstance(expr, ast.IndexExpr):
            target = self._infer(expr.target, scope, phase)
            index = self._infer(expr.index, scope, phase)
            self._require_assignable(index, INT, expr.index)
            if target.name != "Array" or len(target.args) != 1:
                self._error(expr.target, f"cannot index value of type {target}")
            typ = target.args[0]
        elif isinstance(expr, ast.CallExpr):
            typ = self._infer_call(expr, scope, phase)
        else:
            raise AssertionError(f"unhandled expression {type(expr).__name__}")

        self.model.expr_types[id(expr)] = typ
        return typ

    def _infer_array(self, expr: ast.ArrayExpr, scope: Scope, phase: Phase) -> Type:
        if not expr.items:
            return array_of(ANY)
        inner = self._infer(expr.items[0], scope, phase)
        for item in expr.items[1:]:
            item_type = self._infer(item, scope, phase)
            if assignable(item_type, inner):
                continue
            if assignable(inner, item_type):
                inner = item_type
                continue
            self._error(item, f"array element type {item_type} is incompatible with {inner}")
        return array_of(inner)

    def _infer_unary(self, expr: ast.UnaryExpr, scope: Scope, phase: Phase) -> Type:
        operand = self._infer(expr.operand, scope, phase)
        if expr.op == "!":
            self._require_assignable(operand, BOOL, expr.operand)
            return BOOL
        if expr.op in {"+", "-"} and (is_numeric(operand) or operand == DURATION):
            return operand
        self._error(expr, f"operator {expr.op!r} is not defined for {operand}")

    def _infer_binary(self, expr: ast.BinaryExpr, scope: Scope, phase: Phase) -> Type:
        left = self._infer(expr.left, scope, phase)
        right = self._infer(expr.right, scope, phase)
        op = expr.op

        if op in {"&&", "||"}:
            self._require_assignable(left, BOOL, expr.left)
            self._require_assignable(right, BOOL, expr.right)
            return BOOL
        if op in {"==", "!="}:
            if not (assignable(left, right) or assignable(right, left)):
                self._error(expr, f"cannot compare {left} and {right}")
            return BOOL
        if op in {"<", "<=", ">", ">="}:
            if common_numeric(left, right) is None and not (left == right == DURATION):
                self._error(expr, f"operator {op!r} is not defined for {left} and {right}")
            return BOOL
        if op == "+" and left == right == STRING:
            return STRING
        if op in {"+", "-"} and left == right == DURATION:
            return DURATION
        numeric = common_numeric(left, right)
        if numeric is not None and op in {"+", "-", "*", "/", "%"}:
            return FLOAT if op == "/" else numeric
        if op == "*" and (
            (left == DURATION and is_numeric(right))
            or (right == DURATION and is_numeric(left))
        ):
            return DURATION
        if op == "/" and left == DURATION and is_numeric(right):
            return DURATION
        self._error(expr, f"operator {op!r} is not defined for {left} and {right}")

    def _infer_call(self, expr: ast.CallExpr, scope: Scope, phase: Phase) -> Type:
        if isinstance(expr.callee, ast.NameExpr):
            if expr.callee.name == "vec2":
                self._check_vec2(expr, scope, phase)
                self.model.expr_types[id(expr.callee)] = Type("Function")
                return VEC2
            self._error(expr.callee, f"unknown function {expr.callee.name!r}")

        if isinstance(expr.callee, ast.MemberExpr):
            return self._infer_method_call(expr, expr.callee, scope, phase)

        self._error(expr.callee, "only built-ins and presentation object methods are callable")

    def _check_vec2(self, expr: ast.CallExpr, scope: Scope, phase: Phase) -> None:
        if len(expr.args) != 2 or any(arg.name is not None for arg in expr.args):
            self._error(expr, "vec2() requires exactly two positional numeric arguments")
        for arg in expr.args:
            actual = self._infer(arg.value, scope, phase)
            self._require_assignable(actual, FLOAT, arg.value)

    def _infer_method_call(
        self,
        expr: ast.CallExpr,
        member: ast.MemberExpr,
        scope: Scope,
        phase: Phase,
    ) -> Type:
        if phase is not Phase.TIMELINE:
            self._error(expr, "presentation object methods are only valid in motion blocks")

        target_type = self._infer(member.target, scope, phase)
        self.model.expr_types[id(member)] = Type("Method")
        if not target_type.is_bound:
            self._error(member, f"type {target_type} has no presentation methods")

        inner = target_type.bound_inner
        method = member.name
        allowed = set(GENERIC_MOTION_METHODS)
        if inner == CODE:
            allowed.update(CODE_MOTION_METHODS)
        if inner == MATH:
            allowed.update(MATH_MOTION_METHODS)
        if inner == ZANIM_SCENE:
            allowed.update(ZANIM_MOTION_METHODS)
        if method not in allowed:
            self._error(member, f"{target_type} has no temporal method {method!r}")

        self._check_method_args(method, inner, expr.args, scope, expr)
        return UNIT

    def _check_method_args(
        self,
        method: str,
        inner: Type,
        args: tuple[ast.CallArg, ...],
        scope: Scope,
        node: ast.Node,
    ) -> None:
        if any(arg.name is None for arg in args):
            self._error(node, f"{method}() arguments must be named")
        named = self._named_args(args)

        allowed = set(_TIMING_ARGS)
        required: set[str] = set()
        expected: dict[str, Type] = {}

        if method in {"fade_in", "fade_out", "create"}:
            pass
        elif method == "move":
            allowed.add("by")
            required.add("by")
            expected["by"] = VEC2
        elif method in {"scale", "rotate"}:
            allowed.add("by")
            required.add("by")
            expected["by"] = FLOAT
        elif method == "opacity":
            allowed.add("to")
            required.add("to")
            expected["to"] = FLOAT
        elif method == "fit_to":
            allowed.update({"target", "show_target"})
            required.add("target")
            expected["show_target"] = BOOL
        elif method in {"focus", "highlight"}:
            if inner == MATH:
                allowed = set(_TIMING_ARGS)
            else:
                allowed.update({"line", "range"})
                has_line = "line" in named
                has_range = "range" in named
                if has_line == has_range:
                    self._error(node, f"{method}() requires exactly one of line= or range=")
                expected["line"] = INT
                expected["range"] = array_of(INT)
        elif method == "set":
            allowed = {"name", "value", "at"}
            required.update({"name", "value"})
            expected["name"] = STRING
        elif method == "animate":
            allowed.update({"name", "from", "to"})
            required.update({"name", "to"})
            expected["name"] = STRING
        else:
            raise AssertionError(method)

        for key, arg in named.items():
            if key not in allowed:
                self._error(arg, f"unknown {method}() option {key!r}")

        missing = sorted(required - set(named))
        if missing:
            self._error(node, f"{method}() requires {', '.join(name + '=' for name in missing)}")

        self._check_timing(named, allow_at=True)

        for key, typ in expected.items():
            arg = named.get(key)
            if arg is None:
                continue
            actual = self._infer(arg.value, scope, Phase.TIMELINE)
            self._require_assignable(actual, typ, arg.value)

        if method == "fit_to":
            target = named["target"]
            actual = self._infer(target.value, scope, Phase.TIMELINE)
            if not actual.is_bound:
                self._error(target.value, f"fit_to(target=...) requires another slide object, got {actual}")

        for key in {"value", "from", "to"}:
            arg = named.get(key)
            if arg is not None and key not in expected:
                self._infer(arg.value, scope, Phase.TIMELINE)

    def _check_timing(self, named: dict[str, ast.CallArg], *, allow_at: bool) -> None:
        for key, typ in _TIMING_ARGS.items():
            arg = named.get(key)
            if arg is None:
                continue
            if key == "at" and not allow_at:
                self._error(arg, "flow transitions do not accept at=")
            actual = self._infer(arg.value, self.global_scope, Phase.TOP)
            self._require_assignable(actual, typ, arg.value)

    def _named_args(self, args: tuple[ast.CallArg, ...]) -> dict[str, ast.CallArg]:
        result: dict[str, ast.CallArg] = {}
        for arg in args:
            if arg.name is None:
                continue
            if arg.name in result:
                self._error(arg, f"duplicate argument {arg.name!r}")
            result[arg.name] = arg
        return result

    def _resolve_type(self, ref: ast.TypeRef | None) -> Type:
        if ref is None:
            return UNIT
        name = ".".join(ref.name)
        if name == "Array":
            if len(ref.args) != 1:
                self._error(ref, "Array requires exactly one type argument")
            return array_of(self._resolve_type(ref.args[0]))
        if ref.args:
            self._error(ref, f"type {name} does not accept type arguments")
        typ = _TYPE_NAMES.get(name)
        if typ is None:
            self._error(ref, f"unknown type {name!r}")
        return typ

    def _require_assignable(self, actual: Type, expected: Type, node: ast.Node) -> None:
        if not assignable(actual, expected):
            self._error(node, f"expected {expected}, got {actual}")

    def _error(self, node: ast.Node, message: str):
        raise SemanticError(Diagnostic(message, node.span, self.path))


def check(
    program: ast.Program,
    *,
    path: str = "<input>",
    content_objects: dict[str, dict[str, Type]] | None = None,
) -> SemanticModel:
    return SemanticChecker(path=path, content_objects=content_objects).check(program)
