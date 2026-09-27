from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from soda.compiler.hir import HirBlock, HirExpr, HirStmt
from soda.compiler.motion_api import DEFAULT_CLIP_DURATION, channel_for, default_duration_for
from soda.compiler.project import PresentationProgram

_CUT_DURATION = 0.001


def _time(value: float) -> float:
    return round(float(value), 9)


@dataclass(frozen=True, slots=True)
class TimelineClip:
    slide: str
    target: str
    op: str
    channel: str
    start: float
    end: float
    args: dict[str, Any]
    easing: str = "SMOOTHSTEP"


@dataclass(frozen=True, slots=True)
class SlideSpan:
    id: str
    index: int
    start: float
    motion_end: float
    end: float


@dataclass(frozen=True, slots=True)
class TransitionClip:
    source: str
    target: str
    kind: str
    start: float
    end: float
    args: dict[str, Any]
    easing: str = "SMOOTHSTEP"


@dataclass(frozen=True, slots=True)
class TimelineStop:
    time: float
    slide: str
    slide_index: int
    label: str
    kind: str


@dataclass(frozen=True, slots=True)
class TimelineIR:
    clips: tuple[TimelineClip, ...]
    slides: tuple[SlideSpan, ...]
    transitions: tuple[TransitionClip, ...]
    stops: tuple[TimelineStop, ...]
    total_duration: float


def _const_env(program: PresentationProgram) -> dict[str, dict[str, HirExpr]]:
    return {
        module.source: {constant.name: constant.value for constant in module.constants}
        for module in program.modules
    }


def _value(expr: HirExpr | None, constants: dict[str, HirExpr]) -> Any:
    if expr is None:
        return None
    if expr.kind == "literal":
        return expr.data["value"]
    if expr.kind == "name":
        name = str(expr.data["name"])
        bound = constants.get(name)
        return _value(bound, constants) if bound is not None else name
    if expr.kind == "array":
        return [_value(item, constants) for item in expr.data["items"]]
    if expr.kind == "unary":
        value = _value(expr.data["operand"], constants)
        op = expr.data["op"]
        if op == "-":
            return -value
        if op == "+":
            return +value
        if op == "!":
            return not value
    if expr.kind == "binary":
        left = _value(expr.data["left"], constants)
        right = _value(expr.data["right"], constants)
        op = expr.data["op"]
        operations = {
            "+": lambda: left + right,
            "-": lambda: left - right,
            "*": lambda: left * right,
            "/": lambda: left / right,
            "%": lambda: left % right,
            "==": lambda: left == right,
            "!=": lambda: left != right,
            "<": lambda: left < right,
            "<=": lambda: left <= right,
            ">": lambda: left > right,
            ">=": lambda: left >= right,
            "&&": lambda: bool(left) and bool(right),
            "||": lambda: bool(left) or bool(right),
        }
        operation = operations.get(op)
        return operation() if operation is not None else None
    if expr.kind == "call":
        callee = expr.data["callee"]
        if callee.kind == "name" and callee.data["name"] == "vec2":
            return [_value(arg["value"], constants) for arg in expr.data["args"]]
    return None


def _args(
    items: tuple[dict[str, object], ...],
    constants: dict[str, HirExpr],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    positional = 0
    for item in items:
        name = item["name"]
        key = str(name) if name is not None else f"_{positional}"
        if name is None:
            positional += 1
        out[key] = _value(item["value"], constants)  # type: ignore[arg-type]
    return out


def _explicit_duration(args: dict[str, Any]) -> float | None:
    value = args.get("duration")
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    return None


def _clip_duration(
    op: str,
    args: dict[str, Any],
    inherited: float | None,
) -> float:
    explicit = _explicit_duration(args)
    if explicit is not None:
        return explicit
    return default_duration_for(op, inherited)


def _easing(args: dict[str, Any]) -> str:
    return str(args.get("easing", "SMOOTHSTEP")).upper()


def _call(
    stmt: HirStmt,
    constants: dict[str, HirExpr],
) -> tuple[str, str, dict[str, Any]] | None:
    if stmt.kind != "expr":
        return None
    expr = stmt.data["expr"]
    if not isinstance(expr, HirExpr) or expr.kind != "call":
        return None
    callee = expr.data["callee"]
    if not isinstance(callee, HirExpr) or callee.kind != "member":
        return None
    target = callee.data["target"]
    if not isinstance(target, HirExpr) or target.kind != "name":
        return None
    return (
        str(target.data["name"]),
        str(callee.data["name"]),
        _args(expr.data["args"], constants),
    )


def _compile_stmt(
    stmt: HirStmt,
    start: float,
    *,
    slide: str,
    constants: dict[str, HirExpr],
    clips: list[TimelineClip],
    default_duration: float | None = None,
) -> float:
    call = _call(stmt, constants)
    if call is not None:
        target, op, args = call
        at = args.get("at", 0.0)
        offset = float(at) if isinstance(at, (int, float)) else 0.0
        clip_start = _time(start + offset)
        end = _time(clip_start + _clip_duration(op, args, default_duration))
        clips.append(
            TimelineClip(
                slide,
                target,
                op,
                channel_for(op),
                clip_start,
                end,
                args,
                _easing(args),
            )
        )
        return end

    if stmt.kind == "wait":
        seconds = _value(stmt.data["duration"], constants)
        return _time(start + max(0.0, float(seconds or 0.0)))

    if stmt.kind == "parallel":
        body = stmt.data["body"]
        assert isinstance(body, HirBlock)
        args = _args(stmt.data["args"], constants)
        child_default = _explicit_duration(args)
        if child_default is None:
            child_default = DEFAULT_CLIP_DURATION
        ends = [
            _compile_stmt(
                child,
                start,
                slide=slide,
                constants=constants,
                clips=clips,
                default_duration=child_default,
            )
            for child in body.statements
        ]
        return _time(max([start, *ends]))

    if stmt.kind == "step":
        body = stmt.data["body"]
        assert isinstance(body, HirBlock)
        return _compile_block(
            body,
            start,
            slide=slide,
            constants=constants,
            clips=clips,
            default_duration=default_duration,
        )

    raise AssertionError(f"unhandled timeline statement {stmt.kind!r}")


def _compile_block(
    block: HirBlock,
    start: float,
    *,
    slide: str,
    constants: dict[str, HirExpr],
    clips: list[TimelineClip],
    default_duration: float | None = None,
) -> float:
    cursor = start
    for stmt in block.statements:
        cursor = _compile_stmt(
            stmt,
            cursor,
            slide=slide,
            constants=constants,
            clips=clips,
            default_duration=default_duration,
        )
    return cursor


def _transition_spec(
    expr: HirExpr | None,
    constants: dict[str, HirExpr],
    *,
    default_kind: str = "push",
) -> tuple[str, dict[str, Any], float, str]:
    if expr is None or expr.kind != "call":
        duration = _CUT_DURATION if default_kind == "cut" else 0.46
        return default_kind, {}, duration, "SMOOTHSTEP"
    callee = expr.data["callee"]
    kind = (
        str(callee.data["name"])
        if isinstance(callee, HirExpr) and callee.kind == "name"
        else "push"
    )
    args = _args(expr.data["args"], constants)
    fallback = {
        "cut": _CUT_DURATION,
        "fade": 0.4,
        "push": 0.46,
        "embed_zoom": 0.7,
        "shared": 0.65,
    }[kind]
    duration = _explicit_duration(args)
    if duration is None:
        duration = fallback
    if kind == "cut":
        duration = max(_CUT_DURATION, duration)
    return kind, args, duration, _easing(args)


def _validate_channel_conflicts(clips: list[TimelineClip]) -> None:
    by_channel: dict[tuple[str, str, str], list[TimelineClip]] = {}
    for clip in clips:
        key = (clip.slide, clip.target, clip.channel)
        entries = by_channel.setdefault(key, [])
        for previous in entries:
            if max(previous.start, clip.start) < min(previous.end, clip.end) - 1e-9:
                raise ValueError(
                    f"overlapping {key[2]} clips for {clip.slide}.{clip.target}: "
                    f"[{previous.start:g}, {previous.end:g}) and "
                    f"[{clip.start:g}, {clip.end:g})"
                )
        entries.append(clip)


def compile_timeline(program: PresentationProgram) -> TimelineIR:
    constants_by_source = _const_env(program)
    motion_by_slide = {motion.slide: motion for motion in program.motions}
    flow_by_pair = {(item.edge.source, item.edge.target): item for item in program.flow}

    clips: list[TimelineClip] = []
    spans: list[SlideSpan] = []
    transitions: list[TransitionClip] = []
    stops: list[TimelineStop] = []
    cursor = 0.0

    for index, slide in enumerate(program.slides):
        slide_start = cursor
        stops.append(TimelineStop(slide_start, slide.id, index, "ready", "ready"))

        motion = motion_by_slide.get(slide.id)
        motion_cursor = slide_start
        if motion is not None:
            constants = constants_by_source.get(motion.source, {})
            for stmt in motion.timeline.statements:
                motion_cursor = _compile_stmt(
                    stmt,
                    motion_cursor,
                    slide=slide.id,
                    constants=constants,
                    clips=clips,
                )
                if stmt.kind == "step":
                    stops.append(
                        TimelineStop(
                            motion_cursor,
                            slide.id,
                            index,
                            str(stmt.data.get("label") or "step"),
                            "step",
                        )
                    )

        motion_end = motion_cursor
        end = motion_end
        if index + 1 < len(program.slides):
            target = program.slides[index + 1].id
            edge = flow_by_pair.get((slide.id, target))
            constants = constants_by_source.get(edge.source, {}) if edge else {}
            kind, args, duration, easing = _transition_spec(
                edge.edge.transition if edge else None,
                constants,
                default_kind="cut" if not program.modules else "push",
            )
            end = _time(motion_end + duration)
            transitions.append(
                TransitionClip(
                    slide.id,
                    target,
                    kind,
                    motion_end,
                    end,
                    args,
                    easing,
                )
            )

        spans.append(SlideSpan(slide.id, index, slide_start, motion_end, end))
        cursor = end

    _validate_channel_conflicts(clips)
    return TimelineIR(
        tuple(clips),
        tuple(spans),
        tuple(transitions),
        tuple(stops),
        cursor,
    )
