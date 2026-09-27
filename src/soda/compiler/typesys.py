from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Type:
    name: str
    args: tuple["Type", ...] = ()

    def __str__(self) -> str:
        if not self.args:
            return self.name
        return f"{self.name}<{', '.join(map(str, self.args))}>"

    @property
    def is_bound(self) -> bool:
        return self.name == "Bound" and len(self.args) == 1

    @property
    def bound_inner(self) -> "Type":
        if not self.is_bound:
            raise TypeError(f"{self} is not a bound type")
        return self.args[0]


ANY = Type("Any")
UNIT = Type("Unit")
BOOL = Type("Bool")
INT = Type("Int")
FLOAT = Type("Float")
STRING = Type("String")
DURATION = Type("Duration")
VEC2 = Type("Vec2")
EASING = Type("Easing")
DIRECTION = Type("Direction")

TEXT = Type("Text")
MATH = Type("Math")
CODE = Type("Code")
IMAGE = Type("Image")
VIDEO = Type("Video")
ZANIM_SCENE = Type("ZanimScene")
GROUP = Type("Group")
SLIDE_OBJECT = Type("SlideObject")
TRANSITION = Type("Transition")

NUMERIC_TYPES = {INT, FLOAT}


def array_of(inner: Type) -> Type:
    return Type("Array", (inner,))


def bound_of(inner: Type) -> Type:
    return Type("Bound", (inner,))


def is_numeric(value: Type) -> bool:
    return value in NUMERIC_TYPES


def common_numeric(left: Type, right: Type) -> Type | None:
    if not is_numeric(left) or not is_numeric(right):
        return None
    return FLOAT if FLOAT in {left, right} else INT


def assignable(actual: Type, expected: Type) -> bool:
    if expected == ANY or actual == ANY or actual == expected:
        return True
    if actual == INT and expected == FLOAT:
        return True
    if actual.name == expected.name and len(actual.args) == len(expected.args):
        return all(assignable(a, e) for a, e in zip(actual.args, expected.args))
    return False
