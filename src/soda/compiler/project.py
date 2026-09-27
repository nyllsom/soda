from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from soda.compiler import ast
from soda.compiler.content import ContentDocument, ContentObject, ContentSlide, parse_content
from soda.compiler.diagnostics import Diagnostic, SemanticError
from soda.compiler.hir import HirConstant, HirFlowEdge
from soda.compiler.lower import lower
from soda.compiler.parser import parse
from soda.compiler.semantics import check
from soda.compiler.typesys import (
    CODE,
    GROUP,
    IMAGE,
    MATH,
    SLIDE_OBJECT,
    TEXT,
    VIDEO,
    ZANIM_SCENE,
    Type,
)


@dataclass(frozen=True, slots=True)
class SourceUnit:
    path: str
    source: str


@dataclass(frozen=True, slots=True)
class PresentationObject:
    id: str
    kind: str
    props: dict[str, Any]
    layout: dict[str, Any] | None
    children: tuple["PresentationObject", ...]


@dataclass(frozen=True, slots=True)
class PresentationSlide:
    id: str
    title: str
    root: PresentationObject
    source: str


@dataclass(frozen=True, slots=True)
class PresentationModule:
    source: str
    constants: tuple[HirConstant, ...]


@dataclass(frozen=True, slots=True)
class PresentationMotion:
    slide: str
    timeline: object
    source: str


@dataclass(frozen=True, slots=True)
class PresentationFlowEdge:
    edge: HirFlowEdge
    source: str


@dataclass(frozen=True, slots=True)
class PresentationProgram:
    metadata: dict[str, str]
    slides: tuple[PresentationSlide, ...]
    modules: tuple[PresentationModule, ...]
    motions: tuple[PresentationMotion, ...]
    flow: tuple[PresentationFlowEdge, ...]


_SHARED_SURFACE_KINDS = {"region"}
_SHARED_VISUAL_KINDS = {"image", "video", "math", "typst", "pdf", "slide-ref"}
_SHARED_SUPPORTED_KINDS = _SHARED_SURFACE_KINDS | _SHARED_VISUAL_KINDS


def _shared_visual_signature(obj: ContentObject) -> tuple[object, ...]:
    if obj.kind in {"image", "video"}:
        return (obj.kind, obj.props.get("src"), obj.props.get("fit"))
    if obj.kind == "math":
        return (
            obj.kind,
            obj.props.get("source"),
            obj.props.get("font_size", obj.props.get("size")),
            obj.props.get("color"),
        )
    if obj.kind == "slide-ref":
        return (obj.kind, obj.props.get("slide"))
    if obj.kind in {"typst", "pdf"}:
        return (obj.kind, obj.props.get("src"), obj.props.get("page", 1))
    return (obj.kind,)


def _validate_shared_edge(
    decl: ast.FlowEdge,
    slides: dict[str, ContentSlide],
    path: str,
) -> None:
    transition = decl.transition
    if not (
        isinstance(transition, ast.CallExpr)
        and isinstance(transition.callee, ast.NameExpr)
        and transition.callee.name == "shared"
    ):
        return

    for arg in transition.args:
        if arg.name is not None:
            continue
        assert isinstance(arg.value, ast.LiteralExpr)
        object_id = str(arg.value.value)
        source = slides[decl.source].objects[object_id]
        target = slides[decl.target].objects[object_id]
        if source.kind != target.kind:
            raise SemanticError(
                Diagnostic(
                    f"shared object {object_id!r} changes kind from "
                    f"{source.kind!r} to {target.kind!r}",
                    arg.value.span,
                    path,
                )
            )
        if source.kind not in _SHARED_SUPPORTED_KINDS:
            raise SemanticError(
                Diagnostic(
                    f"shared object {object_id!r} has unsupported kind {source.kind!r}; "
                    "share a region surface or stable image/video/math/slide-ref",
                    arg.value.span,
                    path,
                )
            )
        if source.kind in _SHARED_VISUAL_KINDS and _shared_visual_signature(
            source
        ) != _shared_visual_signature(target):
            raise SemanticError(
                Diagnostic(
                    f"shared object {object_id!r} changes visual content across slides",
                    arg.value.span,
                    path,
                )
            )


_KIND_TYPE: dict[str, Type] = {
    "slide": SLIDE_OBJECT,
    "slide-ref": SLIDE_OBJECT,
    "heading": TEXT,
    "paragraph": TEXT,
    "list-item": TEXT,
    "quote": TEXT,
    "rule": TEXT,
    "math": MATH,
    "code": CODE,
    "code-file": CODE,
    "image": IMAGE,
    "typst": IMAGE,
    "pdf": IMAGE,
    "video": VIDEO,
    "zanim": ZANIM_SCENE,
    "web": SLIDE_OBJECT,
    "columns": GROUP,
    "rows": GROUP,
    "grid": GROUP,
    "group": GROUP,
    "region": GROUP,
    "stack": GROUP,
    "overlay": GROUP,
    "list": GROUP,
    "table": GROUP,
    "table-row": GROUP,
    "table-cell": TEXT,
    "chart": GROUP,
    "chart-series": GROUP,
    "diagram": GROUP,
    "diagram-node": TEXT,
    "diagram-edge": TEXT,
    "citation": TEXT,
    "references": GROUP,
}


def _content_type_env(slides: dict[str, ContentSlide]) -> dict[str, dict[str, Type]]:
    result: dict[str, dict[str, Type]] = {}
    for slide_id, slide in slides.items():
        values: dict[str, Type] = {}
        for object_id, obj in slide.objects.items():
            typ = _KIND_TYPE.get(obj.kind)
            if typ is None:
                raise AssertionError(f"unhandled content object kind {obj.kind!r}")
            values[object_id] = typ
        result[slide_id] = values
    return result


def _layout_spec(node: ContentObject) -> dict[str, Any] | None:
    gap = {"gap": node.props["gap"]} if "gap" in node.props else {}
    if node.kind == "slide":
        return {"kind": "slide-flow"}
    if node.kind in {"columns", "rows"}:
        return {
            "kind": node.kind,
            "ratio": list(node.props.get("ratio", [1.0, 1.0])),
            **gap,
        }
    if node.kind == "grid":
        spec: dict[str, Any] = {
            "kind": "grid",
            "cols": node.props.get("cols", 2),
            **gap,
        }
        if "rows" in node.props:
            spec["rows"] = node.props["rows"]
        return spec
    if node.kind in {"stack", "region", "list"}:
        return {"kind": "stack", **gap}
    if node.kind == "overlay":
        return {"kind": "overlay", **gap}
    return None


def _presentation_object(node: ContentObject) -> PresentationObject:
    return PresentationObject(
        node.id,
        node.kind,
        dict(node.props),
        _layout_spec(node),
        tuple(_presentation_object(child) for child in node.children),
    )


def _fallback_span():
    from soda.compiler.span import Span

    return Span(0, 0, 1, 1, 1, 1)


def _merge_content(
    documents: list[ContentDocument],
) -> tuple[dict[str, str], dict[str, ContentSlide]]:
    metadata: dict[str, str] = {}
    slides: dict[str, ContentSlide] = {}
    for document in documents:
        for key, value in document.metadata.items():
            existing = metadata.get(key)
            if existing is not None and existing != value:
                span = document.slides[0].span if document.slides else _fallback_span()
                raise SemanticError(
                    Diagnostic(
                        f"conflicting @{key} metadata: {existing!r} vs {value!r}",
                        span,
                        document.path,
                    )
                )
            metadata[key] = value
        for slide in document.slides:
            if slide.id in slides:
                raise SemanticError(
                    Diagnostic(
                        f"duplicate slide id {slide.id!r} across content files",
                        slide.span,
                        slide.path,
                    )
                )
            slides[slide.id] = slide
    return metadata, slides


def _validate_layout(slide: ContentSlide, node: ContentObject) -> None:
    if node.kind in {"columns", "rows"}:
        ratio = node.props.get("ratio", [1.0, 1.0])
        if len(node.children) != len(ratio):
            raise SemanticError(
                Diagnostic(
                    f"{node.kind} object {node.id!r} has {len(node.children)} children "
                    f"but ratio defines {len(ratio)} regions",
                    node.span or slide.span,
                    slide.path,
                )
            )
    elif node.kind == "grid":
        cols = int(node.props.get("cols", 2))
        rows = node.props.get("rows")
        if rows is not None and cols * int(rows) < len(node.children):
            raise SemanticError(
                Diagnostic(
                    f"grid object {node.id!r} cannot fit {len(node.children)} children "
                    f"in {cols}x{rows}",
                    node.span or slide.span,
                    slide.path,
                )
            )
    for child in node.children:
        _validate_layout(slide, child)


def _validate_flow_edge(
    edge: ast.FlowEdge,
    *,
    slide_order: list[str],
    seen: dict[tuple[str, str], str],
    path: str,
) -> None:
    source_index = slide_order.index(edge.source)
    expected = slide_order[source_index + 1] if source_index + 1 < len(slide_order) else None
    if expected is None:
        raise SemanticError(
            Diagnostic(
                f"flow source {edge.source!r} is the final slide and has no successor",
                edge.span,
                path,
            )
        )
    if edge.target != expected:
        raise SemanticError(
            Diagnostic(
                f"flow edges must follow Markdown slide order: "
                f"{edge.source!r} must transition to {expected!r}, not {edge.target!r}",
                edge.span,
                path,
            )
        )
    key = (edge.source, edge.target)
    previous = seen.get(key)
    if previous is not None:
        raise SemanticError(
            Diagnostic(
                f"transition {edge.source!r} -> {edge.target!r} is already defined in {previous}",
                edge.span,
                path,
            )
        )
    seen[key] = path


def compile_project(
    content_units: list[SourceUnit],
    motion_units: list[SourceUnit],
) -> PresentationProgram:
    documents = [parse_content(unit.source, path=unit.path) for unit in content_units]
    metadata, slides = _merge_content(documents)
    if not slides:
        raise SemanticError(
            Diagnostic(
                "project contains no content slides",
                _fallback_span(),
                content_units[0].path if content_units else "<project>",
            )
        )

    for slide in slides.values():
        _validate_layout(slide, slide.root)
        for obj in slide.objects.values():
            if obj.kind == "slide-ref":
                target = str(obj.props["slide"])
                if target not in slides:
                    raise SemanticError(
                        Diagnostic(
                            f"slide object {obj.id!r} references unknown slide {target!r}",
                            obj.span or slide.span,
                            slide.path,
                        )
                    )

    env = _content_type_env(slides)
    modules: list[PresentationModule] = []
    motions: list[PresentationMotion] = []
    flow: list[PresentationFlowEdge] = []
    seen_motion: dict[str, str] = {}
    seen_flow: dict[tuple[str, str], str] = {}
    slide_order = list(slides)

    for unit in motion_units:
        program = parse(unit.source, path=unit.path)
        model = check(program, path=unit.path, content_objects=env)

        for decl in program.declarations:
            if not isinstance(decl, ast.FlowDecl):
                continue
            for edge in decl.edges:
                _validate_flow_edge(
                    edge,
                    slide_order=slide_order,
                    seen=seen_flow,
                    path=unit.path,
                )
                _validate_shared_edge(edge, slides, unit.path)

        hir = lower(program, model)
        modules.append(PresentationModule(unit.path, hir.constants))

        motion_decls = [decl for decl in program.declarations if isinstance(decl, ast.MotionDecl)]
        for decl, motion in zip(motion_decls, hir.motions):
            previous = seen_motion.get(decl.slide_name)
            if previous is not None:
                raise SemanticError(
                    Diagnostic(
                        f"slide {decl.slide_name!r} already has a motion block in {previous}",
                        decl.span,
                        unit.path,
                    )
                )
            seen_motion[decl.slide_name] = unit.path
            motions.append(PresentationMotion(motion.slide_name, motion.timeline, unit.path))
        flow.extend(PresentationFlowEdge(edge, unit.path) for edge in hir.flow)

    compiled_slides = tuple(
        PresentationSlide(
            slide.id,
            slide.title,
            _presentation_object(slide.root),
            slide.path,
        )
        for slide in slides.values()
    )
    return PresentationProgram(
        metadata,
        compiled_slides,
        tuple(modules),
        tuple(motions),
        tuple(flow),
    )


def compile_paths(paths: list[str]) -> PresentationProgram:
    content_units: list[SourceUnit] = []
    motion_units: list[SourceUnit] = []
    for raw_path in paths:
        path = Path(raw_path)
        unit = SourceUnit(str(path), path.read_text(encoding="utf-8"))
        lower_name = path.name.lower()
        if lower_name.endswith(".md"):
            content_units.append(unit)
        elif lower_name.endswith(".soda"):
            motion_units.append(unit)
        else:
            raise ValueError(
                f"unsupported source extension for {path}; use .md for content and .soda for motion"
            )
    return compile_project(content_units, motion_units)
