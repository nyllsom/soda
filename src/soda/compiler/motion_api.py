from __future__ import annotations

DEFAULT_CLIP_DURATION = 1.0
INSTANT_CLIP_DURATION = 0.001

GENERIC_MOTION_METHOD_ORDER = (
    "fade_in",
    "fade_out",
    "move",
    "rotate",
    "scale",
    "opacity",
    "create",
    "fit_to",
)
CODE_MOTION_METHOD_ORDER = ("focus", "highlight")
MATH_MOTION_METHOD_ORDER = ("highlight",)
ZANIM_MOTION_METHOD_ORDER = ("set", "animate")

GENERIC_MOTION_METHODS = frozenset(GENERIC_MOTION_METHOD_ORDER)
CODE_MOTION_METHODS = frozenset(CODE_MOTION_METHOD_ORDER)
MATH_MOTION_METHODS = frozenset(MATH_MOTION_METHOD_ORDER)
ZANIM_MOTION_METHODS = frozenset(ZANIM_MOTION_METHOD_ORDER)

SUPPORTED_MOTION_METHODS = (
    GENERIC_MOTION_METHODS
    | CODE_MOTION_METHODS
    | MATH_MOTION_METHODS
    | ZANIM_MOTION_METHODS
)

TRANSFORM_OPS = frozenset({"move", "rotate", "scale", "fit_to"})
OPACITY_OPS = frozenset({"fade_in", "fade_out", "opacity"})
ZANIM_OPS = frozenset({"set", "animate"})

TRANSITION_KINDS = frozenset({"cut", "fade", "push", "embed_zoom", "shared"})


def channel_for(op: str) -> str:
    if op in TRANSFORM_OPS:
        return "transform"
    if op in OPACITY_OPS:
        return "opacity"
    if op in ZANIM_OPS:
        return "zanim"
    return op


def default_duration_for(op: str, inherited: float | None = None) -> float:
    if op == "set":
        return INSTANT_CLIP_DURATION
    if inherited is not None:
        return inherited
    return DEFAULT_CLIP_DURATION
