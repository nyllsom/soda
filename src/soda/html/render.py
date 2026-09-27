from __future__ import annotations

import base64
import hashlib
import html
import json
import math
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from soda.adapters.typst import compile_typst_file
from soda.compiler.project import PresentationObject, PresentationProgram, PresentationSlide
from soda.compiler.serde import to_jsonable
from soda.compiler.timeline_ir import TimelineIR, compile_timeline
from soda.html.academic import (
    BibEntry,
    format_reference,
    load_bibliography,
    load_chart_rows,
    short_citation,
)
from soda.html.assets import AssetExporter, resolve_asset_reference
from soda.html.code import render_code
from soda.html.math import math_svg_asset
from soda.html.themed_assets import themed_asset_resolver
from soda.themes import Theme, css_variables, resolve_theme, typst_theme_inputs


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _slide_title(slides: tuple[PresentationSlide, ...], slide_id: str) -> str:
    for slide in slides:
        if slide.id == slide_id:
            return slide.title
    return slide_id


def _style_for_layout(layout: dict | None) -> str:
    if not layout:
        return ""
    kind = layout.get("kind")
    # An omitted gap belongs to the theme. Explicit values keep the original
    # language unit (1 = 2rem = 32 logical pixels), including an explicit zero.
    gap = (
        f"{float(layout['gap']) * 2.0:.2f}rem"
        if "gap" in layout
        else "var(--soda-layout-gap,0.70rem)"
    )
    gap_token = f"--soda-layout-gap:{gap};" if "gap" in layout else ""
    if kind in {"columns", "rows"}:
        ratio = layout.get("ratio", [1, 1])
        template = " ".join(f"minmax(0,{float(part)}fr)" for part in ratio)
        prop = "grid-template-columns" if kind == "columns" else "grid-template-rows"
        return f' style="{prop}:{template};{gap_token}gap:{gap}"'
    if kind == "grid":
        cols = int(layout.get("cols", 2))
        rows = int(layout.get("rows", 2))
        return (
            f' style="grid-template-columns:repeat({cols},minmax(0,1fr));'
            f'grid-template-rows:repeat({rows},minmax(0,1fr));{gap_token}gap:{gap}"'
        )
    if kind in {"stack", "overlay"}:
        return f' style="gap:{gap}"' if "gap" in layout else ""
    return ""


_INLINE_SPAN_RE = re.compile(r"(?<!\\)(?:\$([^$\n]+)\$|`([^`\n]+)`|\[(@[^]\n]+)\])")


def _render_basic_markdown(value: str) -> str:
    text = _e(value)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank" rel="noreferrer">\1</a>', text
    )
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    return text.replace("\n", "<br>")


def _citation_html(raw: str, bibliography: dict[str, BibEntry] | None) -> str:
    keys = [part.strip().lstrip("@").strip() for part in re.split(r"[;,]", raw) if part.strip()]
    if not bibliography:
        raise ValueError(
            f"citation {raw!r} requires front matter bibliography: <relative .bib path>"
        )
    labels: list[str] = []
    for key in keys:
        entry = bibliography.get(key)
        if entry is None:
            raise ValueError(f"unknown bibliography key {key!r}")
        labels.append(short_citation(entry))
    return f'<span class="citation">({_e("; ".join(labels))})</span>'


def _render_inline_text(
    value: object, theme: Theme, bibliography: dict[str, BibEntry] | None = None
) -> str:
    text = str(value)
    parts: list[str] = []
    cursor = 0
    for match in _INLINE_SPAN_RE.finditer(text):
        parts.append(_render_basic_markdown(text[cursor : match.start()]))
        math_source, code_source, citation_source = match.groups()
        if math_source is not None:
            source = math_source.strip()
            asset = math_svg_asset(source, font_size=22.0, color=theme.foreground)
            width_em = min(24.0, max(0.7, asset.aspect_ratio * 1.06))
            parts.append(
                f'<img class="inline-math" style="width:{width_em:.3f}em" '
                f'src="{_e(asset.data_uri)}" alt="{_e(source)}">'
            )
        elif code_source is not None:
            parts.append(f'<code class="inline-code">{_e(code_source)}</code>')
        else:
            parts.append(_citation_html(citation_source or "", bibliography))
        cursor = match.end()
    parts.append(_render_basic_markdown(text[cursor:]))
    return "".join(parts)


def _inline_svg(svg: str, prefix: str, css_class: str) -> str:
    safe_prefix = re.sub(r"[^A-Za-z0-9_-]", "-", prefix)
    ids = set(re.findall(r'\bid="([^"]+)"', svg))
    for old in sorted(ids, key=len, reverse=True):
        new = f"{safe_prefix}-{old}"
        svg = svg.replace(f'id="{old}"', f'id="{new}"')
        svg = svg.replace(f'xlink:href="#{old}"', f'xlink:href="#{new}"')
        svg = svg.replace(f'href="#{old}"', f'href="#{new}"')
    return svg.replace("<svg ", f'<svg class="{css_class}" aria-hidden="true" ', 1)


def _theme_color(theme: Theme, value: object, fallback: str) -> str:
    name = str(value or "").strip().lower()
    aliases = {
        "foreground": theme.foreground,
        "primary": theme.primary,
        "accent": theme.accent,
        "muted": theme.muted,
    }
    if name in aliases:
        return aliases[name]
    if name.startswith("#"):
        return name
    return fallback


def _code_language(path: Path, explicit: object = None) -> str:
    if explicit:
        return str(explicit)
    aliases = {
        ".py": "python",
        ".js": "javascript",
        ".mjs": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".jsx": "jsx",
        ".zig": "zig",
        ".rs": "rust",
        ".c": "c",
        ".cc": "cpp",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".java": "java",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "zsh",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".go": "go",
        ".lua": "lua",
    }
    return aliases.get(path.suffix.lower(), path.suffix.lower().lstrip(".") or "text")


def _code_file_source(authored: str, source_path: str, lines: object) -> tuple[str, str]:
    ref = resolve_asset_reference(authored, source_path)
    if ref.remote or ref.resolved_path is None:
        raise ValueError("@code/@embed type=code requires a local relative file")
    path = ref.resolved_path
    if not path.is_file():
        raise ValueError(f"code source does not exist: {path}")
    values = path.read_text(encoding="utf-8").splitlines()
    label = path.name
    if lines is None:
        return "\n".join(values), label
    raw = str(lines).strip()
    match = re.fullmatch(r"(\d+)(?::(\d+))?", raw)
    if not match:
        raise ValueError(f"invalid code line range {raw!r}; use lines=start:end")
    start = int(match.group(1))
    end = int(match.group(2) or start)
    if start < 1 or end < start:
        raise ValueError(f"invalid code line range {raw!r}")
    return "\n".join(
        values[start - 1 : end]
    ), f"{label} · L{start}{f'–{end}' if end != start else ''}"


def _render_object(
    node: PresentationObject,
    slide_id: str,
    slides: tuple[PresentationSlide, ...],
    theme: Theme,
    source_path: str,
    asset_resolver: Callable[[str, str], str],
    bibliography: dict[str, BibEntry] | None = None,
) -> str:
    extra_classes = " ".join(str(value) for value in node.props.get("classes", []))
    cls = f"obj slide-object-frame kind-{_e(node.kind)}" + (
        f" {_e(extra_classes)}" if extra_classes else ""
    )
    runtime_id = "slide" if node.kind == "slide" else node.id
    attrs = (
        f'class="{cls}" data-object="{_e(runtime_id)}" data-kind="{_e(node.kind)}" '
        f'data-slide-object="true" data-frame="visual"'
    )
    children = "".join(
        _render_object(child, slide_id, slides, theme, source_path, asset_resolver, bibliography)
        for child in node.children
    )

    if node.kind == "slide":
        return f"<div {attrs}>{children}</div>"
    if node.kind == "heading":
        level = int(node.props.get("level", 2))
        tag = "h1" if level <= 1 else "h2" if level == 2 else "h3"
        return f"<{tag} {attrs}>{_render_inline_text(node.props.get('text', ''), theme, bibliography)}</{tag}>"
    if node.kind == "paragraph":
        return (
            f"<p {attrs}>{_render_inline_text(node.props.get('text', ''), theme, bibliography)}</p>"
        )
    if node.kind == "list":
        tag = "ol" if bool(node.props.get("ordered")) else "ul"
        return f"<{tag} {attrs}>{children}</{tag}>"
    if node.kind == "list-item":
        return f"<li {attrs}>{_render_inline_text(node.props.get('text', ''), theme, bibliography)}</li>"
    if node.kind == "quote":
        return f"<blockquote {attrs}>{_render_inline_text(node.props.get('text', ''), theme, bibliography)}</blockquote>"
    if node.kind == "rule":
        return f"<hr {attrs}>"
    if node.kind == "table":
        return f"<table {attrs}><tbody>{children}</tbody></table>"
    if node.kind == "table-row":
        return f"<tr {attrs}>{children}</tr>"
    if node.kind == "table-cell":
        tag = "th" if bool(node.props.get("header")) else "td"
        align = str(node.props.get("align", "left"))
        return f'<{tag} {attrs} style="text-align:{_e(align)}">{_render_inline_text(node.props.get("text", ""), theme, bibliography)}</{tag}>'
    if node.kind == "citation":
        raw = ";".join(f"@{key}" for key in node.props.get("keys", []))
        return f"<p {attrs}>{_citation_html(raw, bibliography)}</p>"
    if node.kind == "references":
        if not bibliography:
            raise ValueError("@references requires front matter bibliography: <relative .bib path>")
        items = "".join(
            f'<li><span class="ref-key">[{index}]</span>{_e(format_reference(entry))}</li>'
            for index, entry in enumerate(bibliography.values(), 1)
        )
        return f"<div {attrs}><ol>{items}</ol></div>"
    if node.kind == "chart":
        rows = load_chart_rows(str(node.props.get("src", "")), source_path)
        x_name = str(node.props.get("x", ""))
        y_names = [str(value) for value in node.props.get("y", [])]
        if not rows:
            raise ValueError(f"chart {slide_id}.{node.id} has no data rows")
        missing = [name for name in [x_name, *y_names] if name not in rows[0]]
        if missing:
            raise ValueError(
                f"chart {slide_id}.{node.id} CSV is missing columns: {', '.join(missing)}"
            )
        x_raw = [row.get(x_name, "") for row in rows]
        try:
            x_values = [float(value) for value in x_raw]
            numeric_x = True
        except (TypeError, ValueError):
            x_values = [float(index) for index in range(len(rows))]
            numeric_x = False
        series_values: list[list[float]] = []
        for name in y_names:
            try:
                series_values.append([float(row.get(name, "")) for row in rows])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"chart {slide_id}.{node.id} column {name!r} must contain numeric values"
                ) from exc
        x_min, x_max = min(x_values), max(x_values)
        if math.isclose(x_min, x_max):
            x_min -= 0.5
            x_max += 0.5
        all_y = [value for values in series_values for value in values]
        y_min, y_max = min(all_y), max(all_y)
        if math.isclose(y_min, y_max):
            y_min -= 0.5
            y_max += 0.5
        y_pad = (y_max - y_min) * 0.08
        y_min -= y_pad
        y_max += y_pad
        width, height = 760.0, 360.0
        left, right, top, bottom = 66.0, 22.0, 24.0, 48.0
        plot_w, plot_h = width - left - right, height - top - bottom

        def sx(value: float) -> float:
            return left + (value - x_min) / (x_max - x_min) * plot_w

        def sy(value: float) -> float:
            return top + (y_max - value) / (y_max - y_min) * plot_h

        grid: list[str] = []
        for tick in range(5):
            value = y_min + (y_max - y_min) * tick / 4
            y = sy(value)
            grid.append(
                f'<line x1="{left}" y1="{y:.2f}" x2="{width - right}" y2="{y:.2f}" class="chart-grid"/>'
            )
            grid.append(
                f'<text x="{left - 10}" y="{y + 4:.2f}" text-anchor="end" class="chart-tick">{_e(f"{value:.3g}")}</text>'
            )
        x_tick_indices = sorted(
            set(
                round(i * (len(rows) - 1) / min(5, max(1, len(rows) - 1)))
                for i in range(min(6, len(rows)))
            )
        )
        for idx in x_tick_indices:
            x = sx(x_values[idx])
            label = f"{x_values[idx]:.3g}" if numeric_x else str(x_raw[idx])
            grid.append(
                f'<text x="{x:.2f}" y="{height - 18}" text-anchor="middle" class="chart-tick">{_e(label)}</text>'
            )
        x_label = str(node.props.get("xlabel", x_name))
        y_label = str(node.props.get("ylabel", y_names[0] if len(y_names) == 1 else "value"))
        grid.append(
            f'<text x="{left + plot_w / 2:.2f}" y="{height - 2:.2f}" text-anchor="middle" class="chart-axis-label">{_e(x_label)}</text>'
        )
        grid.append(
            f'<text x="14" y="{top + plot_h / 2:.2f}" text-anchor="middle" class="chart-axis-label" transform="rotate(-90 14 {top + plot_h / 2:.2f})">{_e(y_label)}</text>'
        )
        palette = [theme.primary, theme.accent, "#3159a6", "#4d7c5b", "#9a4b35", "#6d5aa6"]
        series_svg: list[str] = []
        chart_type = str(node.props.get("type", "line")).lower()
        for child, values in zip(node.children, series_values):
            color = palette[int(child.props.get("index", 0)) % len(palette)]
            child_attrs = f'class="obj slide-object-frame kind-chart-series chart-series" data-object="{_e(child.id)}" data-kind="chart-series" data-slide-object="true" data-frame="visual" style="--series-color:{_e(color)}"'
            points = [(sx(x), sy(y)) for x, y in zip(x_values, values)]
            if chart_type == "bar":
                group_w = plot_w / max(1, len(rows)) * 0.72
                bar_w = group_w / max(1, len(series_values))
                index = int(child.props.get("index", 0))
                baseline = sy(max(0.0, y_min)) if y_min <= 0 <= y_max else sy(y_min)
                shapes = []
                for px, py in points:
                    x = px - group_w / 2 + index * bar_w
                    y = min(py, baseline)
                    h = max(1.0, abs(baseline - py))
                    shapes.append(
                        f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(1.0, bar_w - 2):.2f}" height="{h:.2f}" rx="2"/>'
                    )
                body = "".join(shapes)
            elif chart_type == "scatter":
                body = "".join(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.2"/>' for x, y in points)
            else:
                path = " ".join(
                    ("M" if index == 0 else "L") + f" {x:.2f} {y:.2f}"
                    for index, (x, y) in enumerate(points)
                )
                body = f'<path d="{path}" fill="none"/>' + "".join(
                    f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.2"/>' for x, y in points
                )
            series_svg.append(f"<g {child_attrs}>{body}</g>")
        legend = "".join(
            f'<span><i style="--series-color:{_e(palette[i % len(palette)])}"></i>{_e(name)}</span>'
            for i, name in enumerate(y_names)
        )
        title = node.props.get("title")
        title_html = (
            f'<figcaption class="chart-title">{_render_inline_text(title, theme, bibliography)}</figcaption>'
            if title
            else ""
        )
        svg = f'<svg viewBox="0 0 {width:g} {height:g}" role="img" aria-label="{_e(title or node.id)}"><g class="chart-axes">{"".join(grid)}</g>{"".join(series_svg)}</svg>'
        return f'<figure {attrs}>{title_html}{svg}<div class="chart-legend">{legend}</div></figure>'
    if node.kind == "diagram":
        nodes = [child for child in node.children if child.kind == "diagram-node"]
        edges = [child for child in node.children if child.kind == "diagram-edge"]
        incoming = {child.id: [] for child in nodes}
        outgoing = {child.id: [] for child in nodes}
        for edge in edges:
            source, target = str(edge.props["source"]), str(edge.props["target"])
            if source in outgoing and target in incoming:
                outgoing[source].append(target)
                incoming[target].append(source)
        rank = {child.id: 0 for child in nodes}
        queue = [node_id for node_id, parents in incoming.items() if not parents]
        seen: set[str] = set()
        while queue:
            current = queue.pop(0)
            seen.add(current)
            for target in outgoing[current]:
                rank[target] = max(rank[target], rank[current] + 1)
                if all(parent in seen for parent in incoming[target]) and target not in queue:
                    queue.append(target)
        if len(seen) != len(nodes):
            rank = {child.id: index for index, child in enumerate(nodes)}
        levels: dict[int, list[PresentationObject]] = {}
        for child in nodes:
            levels.setdefault(rank[child.id], []).append(child)
        width, height = 760.0, 340.0
        margin_x, margin_y = 85.0, 54.0
        positions: dict[str, tuple[float, float]] = {}
        direction = str(node.props.get("direction", "LR")).upper()
        max_rank = max(levels, default=0)
        for level, items in levels.items():
            for index, child in enumerate(items):
                if direction == "TB":
                    x = margin_x + (width - 2 * margin_x) * (index + 1) / (len(items) + 1)
                    y = margin_y + (height - 2 * margin_y) * (level / max(1, max_rank))
                else:
                    x = margin_x + (width - 2 * margin_x) * (level / max(1, max_rank))
                    y = margin_y + (height - 2 * margin_y) * (index + 1) / (len(items) + 1)
                positions[child.id] = (x, y)
        marker = f"arrow-{slide_id}-{node.id}"
        edge_svg: list[str] = []
        for edge in edges:
            source, target = str(edge.props["source"]), str(edge.props["target"])
            if source not in positions or target not in positions:
                continue
            x1, y1 = positions[source]
            x2, y2 = positions[target]
            if direction == "TB":
                sign = 1.0 if y2 >= y1 else -1.0
                y1 += 24.0 * sign
                y2 -= 28.0 * sign
            else:
                sign = 1.0 if x2 >= x1 else -1.0
                x1 += 62.0 * sign
                x2 -= 68.0 * sign
            edge_attrs = f'class="obj slide-object-frame kind-diagram-edge diagram-edge" data-object="{_e(edge.id)}" data-kind="diagram-edge" data-slide-object="true" data-frame="visual"'
            edge_svg.append(
                f'<path {edge_attrs} d="M {x1:.2f} {y1:.2f} L {x2:.2f} {y2:.2f}" marker-end="url(#{_e(marker)})"/>'
            )
        node_svg: list[str] = []
        for child in nodes:
            x, y = positions[child.id]
            node_attrs = f'class="obj slide-object-frame kind-diagram-node diagram-node" data-object="{_e(child.id)}" data-kind="diagram-node" data-slide-object="true" data-frame="visual"'
            label = str(child.props.get("label", child.id))
            node_svg.append(
                f'<g {node_attrs}><g transform="translate({x:.2f},{y:.2f})"><rect x="-62" y="-24" width="124" height="48" rx="12"/><text text-anchor="middle" dominant-baseline="middle">{_e(label)}</text></g></g>'
            )
        svg = f'<svg viewBox="0 0 {width:g} {height:g}" role="img" aria-label="diagram {_e(node.id)}"><defs><marker id="{_e(marker)}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z"/></marker></defs>{"".join(edge_svg)}{"".join(node_svg)}</svg>'
        return f"<figure {attrs}>{svg}</figure>"
    if node.kind == "code-file":
        authored = str(node.props.get("src", ""))
        source, source_label = _code_file_source(authored, source_path, node.props.get("lines"))
        ref = resolve_asset_reference(authored, source_path)
        assert ref.resolved_path is not None
        language = _code_language(
            ref.resolved_path, node.props.get("lang", node.props.get("language"))
        )
        line_numbers = bool(node.props.get("line_numbers", True))
        max_lines_raw = node.props.get("max_lines")
        max_lines = int(max_lines_raw) if max_lines_raw is not None else None
        dim_inactive = bool(node.props.get("dim_inactive", False))
        body = render_code(
            source,
            language,
            line_numbers=line_numbers,
            max_lines=max_lines,
            dim_inactive=dim_inactive,
        )
        code_attrs = (
            f'class="{cls} code-block" data-object="{_e(node.id)}" data-kind="code-file" '
            f'data-slide-object="true" data-frame="visual"'
        )
        return (
            f"<div {code_attrs}><div class='code-header'><span>{_e(source_label)}</span>"
            f"<span>{_e(language.upper())}</span></div>{body}</div>"
        )
    if node.kind == "code":
        language = str(node.props.get("language", "text"))
        source = str(node.props.get("source", ""))
        line_numbers = bool(node.props.get("line_numbers", True))
        max_lines_raw = node.props.get("max_lines")
        max_lines = int(max_lines_raw) if max_lines_raw is not None else None
        dim_inactive = bool(node.props.get("dim_inactive", False))
        body = render_code(
            source,
            language,
            line_numbers=line_numbers,
            max_lines=max_lines,
            dim_inactive=dim_inactive,
        )
        code_attrs = (
            f'class="{cls} code-block" data-object="{_e(node.id)}" data-kind="code" '
            f'data-slide-object="true" data-frame="visual"'
        )
        return (
            f"<div {code_attrs}><div class='code-header'><span>{_e(language.upper())}</span>"
            f"<span class='code-range'></span></div>{body}</div>"
        )
    if node.kind == "math":
        source = str(node.props.get("source", ""))
        font_size = float(node.props.get("font_size", node.props.get("size", 38.0)))
        color = _theme_color(theme, node.props.get("color"), theme.foreground)
        try:
            asset = math_svg_asset(source, font_size=font_size, color=color)
        except ValueError as exc:
            raise ValueError(f"failed to compile math object {slide_id}.{node.id}: {exc}") from exc
        align = str(node.props.get("align", "center")).lower()
        if align not in {"left", "center", "right"}:
            raise ValueError(f"math object {slide_id}.{node.id} has invalid align={align!r}")
        natural_width = asset.width_pt / 12.0
        natural_height = asset.height_pt / 12.0
        math_attrs = (
            f'class="{cls} math-object math-align-{align}" data-object="{_e(node.id)}" data-kind="math" '
            f'data-slide-object="true" data-frame="visual" '
            f'style="--math-natural-width:{natural_width:.3f}rem;--math-natural-height:{natural_height:.3f}rem;'
            f'--math-aspect:{asset.aspect_ratio:.6f}"'
        )
        svg = _inline_svg(asset.svg, f"{slide_id}-{node.id}", "math-svg")
        return f'<div {math_attrs} role="img" aria-label="{_e(source)}">{svg}</div>'
    if node.kind == "typst":
        authored = str(node.props.get("src", ""))
        ref = resolve_asset_reference(authored, source_path)
        if ref.remote or ref.resolved_path is None:
            raise ValueError("@typst/@embed type=typst requires a local relative .typ file")
        page = int(node.props.get("page", 1))
        try:
            asset = compile_typst_file(
                ref.resolved_path, page=page, inputs=typst_theme_inputs(theme)
            )
        except ValueError as exc:
            raise ValueError(f"failed to compile Typst object {slide_id}.{node.id}: {exc}") from exc
        svg = _inline_svg(asset.svg, f"{slide_id}-{node.id}", "typst-svg")
        label = str(node.props.get("label", node.id))
        caption = str(node.props.get("caption", ""))
        figure_attrs = (
            f'class="{cls} media-object typst-media" data-object="{_e(node.id)}" data-kind="typst" '
            f'data-slide-object="true" data-frame="visual" style="--typst-aspect:{asset.aspect_ratio:.6f}"'
        )
        caption_html = (
            f"<figcaption>{_render_inline_text(caption, theme, bibliography)}</figcaption>"
            if caption
            else ""
        )
        return f'<figure {figure_attrs} role="img" aria-label="{_e(label)}">{svg}{caption_html}</figure>'
    if node.kind == "pdf":
        authored = str(node.props.get("src", ""))
        src = asset_resolver(authored, source_path)
        page = int(node.props.get("page", 1))
        label = str(node.props.get("label", node.id))
        caption = str(node.props.get("caption", ""))
        pdf_src = f"{src}#page={page}&toolbar=0&navpanes=0&scrollbar=0"
        caption_html = (
            f"<figcaption>{_render_inline_text(caption, theme, bibliography)}</figcaption>"
            if caption
            else ""
        )
        # Keep the referenced document reachable in browsers without a PDF
        # plugin. Data URLs need download rather than top-level navigation.
        download = ' download="document.pdf"' if src.startswith("data:") else ' target="_blank" rel="noopener"'
        return (
            f'<figure class="{cls} media-object pdf-media" data-object="{_e(node.id)}" data-kind="pdf" '
            f'data-slide-object="true" data-frame="visual">'
            f'<iframe src="{_e(pdf_src)}" title="{_e(label)}"></iframe>'
            f'<a class="pdf-fallback" href="{_e(src)}"{download}>PDF ↗</a>{caption_html}</figure>'
        )
    if node.kind == "web":
        authored = str(node.props.get("src", ""))
        src = asset_resolver(authored, source_path)
        label = str(node.props.get("label", node.id))
        return (
            f'<figure class="{cls} media-object web-media" data-object="{_e(node.id)}" data-kind="web" '
            f'data-slide-object="true" data-frame="visual">'
            f'<iframe src="{_e(src)}" title="{_e(label)}" loading="lazy" allowfullscreen></iframe>'
            f'<a class="web-fallback" href="{_e(src)}" target="_blank" rel="noopener">{_e(label)}</a></figure>'
        )
    if node.kind == "image":
        authored = str(node.props.get("src", ""))
        alt_raw = str(node.props.get("alt", ""))
        alt = _e(alt_raw)
        caption_raw = str(node.props.get("caption", alt_raw))
        label_raw = str(node.props.get("label", "")).strip()
        caption_text = f"({label_raw}) {caption_raw}" if label_raw else caption_raw
        if authored:
            src = asset_resolver(authored, source_path)
            fit = str(node.props.get("fit", "contain")).lower()
            if fit not in {"contain", "cover", "fill", "scale-down"}:
                raise ValueError(f"image object {slide_id}.{node.id} has invalid fit={fit!r}")
            media_attrs = (
                f'class="{cls} media-object image-media" data-object="{_e(node.id)}" data-kind="image" '
                f'data-slide-object="true" data-frame="visual"'
            )
            return (
                f"<figure {media_attrs}>"
                f"<img src='{_e(src)}' alt='{alt}' data-fit='{_e(fit)}'>"
                f"<figcaption>{_render_inline_text(caption_text, theme, bibliography)}</figcaption></figure>"
            )
        return f"<figure {attrs}><div class='image-object'>Image</div><figcaption>{_render_inline_text(caption_text, theme, bibliography)}</figcaption></figure>"
    if node.kind == "zanim":
        authored = str(node.props.get("src", ""))
        src = asset_resolver(authored, source_path)
        label = _e(node.props.get("label", node.id))
        initial = {
            key: value
            for key, value in node.props.items()
            if key not in {"src", "classes", "label", "fit", "height"}
        }
        initial_json = _e(json.dumps(initial, ensure_ascii=False))
        fit = str(node.props.get("fit", "contain")).lower()
        if fit not in {"contain", "cover", "fill"}:
            raise ValueError(f"zanim object {slide_id}.{node.id} has invalid fit={fit!r}")
        return (
            f'<figure class="{cls} zanim-object" data-object="{_e(node.id)}" data-kind="zanim" '
            f'data-slide-object="true" data-frame="visual" data-zanim-src="{_e(src)}" '
            f'data-zanim-fit="{_e(fit)}" data-zanim-props="{initial_json}" aria-label="{label}">'
            f'<div class="zanim-viewport"><div class="zanim-loading">Loading Zanim Web scene…</div></div></figure>'
        )
    if node.kind == "video":
        authored = str(node.props.get("src", ""))
        src = asset_resolver(authored, source_path)
        poster_authored = node.props.get("poster")
        poster = asset_resolver(str(poster_authored), source_path) if poster_authored else None
        fit = str(node.props.get("fit", "contain")).lower()
        if fit not in {"contain", "cover", "fill", "scale-down"}:
            raise ValueError(f"video object {slide_id}.{node.id} has invalid fit={fit!r}")
        flags = []
        for name, default in (
            ("controls", True),
            ("muted", False),
            ("loop", False),
            ("playsinline", True),
        ):
            if bool(node.props.get(name, default)):
                flags.append(name)
        autoplay = bool(node.props.get("autoplay", False))
        preload = str(node.props.get("preload", "metadata")).lower()
        if preload not in {"none", "metadata", "auto"}:
            raise ValueError(f"video object {slide_id}.{node.id} has invalid preload={preload!r}")
        poster_attr = f" poster='{_e(poster)}'" if poster else ""
        label = _e(node.props.get("label", node.id))
        media_attrs = (
            f'class="{cls} media-object video-media" data-object="{_e(node.id)}" data-kind="video" '
            f'data-slide-object="true" data-frame="visual"'
        )
        return (
            f"<figure {media_attrs}>"
            f"<video src='{_e(src)}'{poster_attr} {' '.join(flags)} preload='{_e(preload)}' "
            f"data-fit='{_e(fit)}' data-autoplay='{str(autoplay).lower()}' aria-label='{label}'></video></figure>"
        )
    if node.kind == "slide-ref":
        target = str(node.props.get("slide", ""))
        return (
            f"<div {attrs} data-target-slide='{_e(target)}'><div class='mini-slide'>"
            f"<div class='placeholder'><strong>{_e(_slide_title(slides, target))}</strong>"
            f"<span>embedded Slide object</span></div></div></div>"
        )
    return f"<section {attrs}{_style_for_layout(node.layout)}>{children}</section>"


def _slide_classes(slide: PresentationSlide) -> tuple[str, bool]:
    values = {str(value) for value in slide.root.props.get("classes", [])}
    cover = "cover" in values or bool(slide.root.props.get("cover"))
    classes = ["slide"]
    if cover:
        classes.append("soda-cover")
    classes.extend(f"slide-{value}" for value in sorted(values - {"cover"}))
    return " ".join(classes), cover


def _brand_chrome(theme: Theme) -> str:
    parts = []
    if theme.brand_logo:
        parts.append(
            f'<div class="brand-logo" role="img" aria-label="{_e(theme.brand_label or theme.name)}"></div>'
        )
    if theme.affiliation_logo:
        parts.append(
            f'<div class="brand-affiliation" role="img" aria-label="{_e(theme.affiliation_label)}"></div>'
        )
    return "".join(parts)


def _identity_asset_resolver(authored: str, source_path: str) -> str:
    resolve_asset_reference(authored, source_path)
    return authored


def render_html(
    program: PresentationProgram,
    *,
    asset_resolver: Callable[[str, str], str] | None = None,
    zanim_head: str | None = None,
    theme: Theme | None = None,
    timeline: TimelineIR | None = None,
) -> str:
    title = program.metadata.get("deck", "SODA deck")
    theme = theme or resolve_theme(
        program.metadata.get("theme"),
        base_dir=Path(program.slides[0].source).parent if program.slides else None,
    )
    lang = str(program.metadata.get("lang", "en")).lower()
    labels = {
        "ready": "就绪" if lang.startswith("zh") else "ready",
        "hint": "空格 / → 下一步 · ← 上一步 · D 布局诊断 · 拖动底部边缘跳转"
        if lang.startswith("zh")
        else "Space / → next · ← previous · D layout diagnostics · drag bottom edge to seek",
        "html_lang": "zh-CN" if lang.startswith("zh") else "en",
    }
    asset_resolver = themed_asset_resolver(theme, asset_resolver or _identity_asset_resolver)
    bibliography: dict[str, BibEntry] | None = None
    bibliography_path = program.metadata.get("bibliography")
    if bibliography_path:
        if not program.slides:
            raise ValueError("bibliography requires at least one slide source")
        bibliography = load_bibliography(str(bibliography_path), program.slides[0].source)
    slides: list[str] = []
    for index, slide in enumerate(program.slides, 1):
        slide_classes, _ = _slide_classes(slide)
        slides.append(
            f"<article class='{_e(slide_classes)}' data-slide='{_e(slide.id)}' data-index='{index - 1}'>"
            f"{_brand_chrome(theme)}"
            f"{_render_object(slide.root, slide.id, program.slides, theme, slide.source, asset_resolver, bibliography)}"
            "</article>"
        )

    runtime = {"timeline": to_jsonable(timeline if timeline is not None else compile_timeline(program))}
    runtime_json = json.dumps(runtime, ensure_ascii=False).replace("</", "<\\/")
    if zanim_head is None:
        zanim_head = (
            '<script type="importmap">{"imports":{"@zanim/web":"./assets/zanim-web/src/zanim.js",'
            '"@zanim/web/ir":"./assets/zanim-web/src/ir.js"}}</script>'
            if _program_uses_zanim(program)
            else ""
        )

    return (
        TEMPLATE.replace("__TITLE__", _e(title))
        .replace("__ZANIM_HEAD__", zanim_head)
        .replace("__HTML_LANG__", _e(labels["html_lang"]))
        .replace("__THEME_ID__", _e(theme.id))
        .replace("__THEME_LAYOUT__", _e(theme.layout))
        .replace("__THEME_VARS__", _e(css_variables(theme)))
        .replace("__SLIDES__", "\n".join(slides))
        .replace("__RUNTIME__", runtime_json)
        .replace("__READY_LABEL__", _e(labels["ready"]))
        .replace("__HINT_LABEL__", _e(labels["hint"]))
    )


def _program_uses_zanim(program: PresentationProgram) -> bool:
    def visit(node: PresentationObject) -> bool:
        return node.kind == "zanim" or any(visit(child) for child in node.children)

    return any(visit(slide.root) for slide in program.slides)


def _valid_zanim_web_root(root: Path) -> bool:
    return (root / "src" / "zanim.js").is_file() and (
        root / "dist" / "zanim_web_core.wasm"
    ).is_file()


def _zanim_web_root() -> Path:
    configured = os.environ.get("ZANIM_WEB_ROOT")
    if configured:
        root = Path(configured).expanduser().resolve()
        if not _valid_zanim_web_root(root):
            raise ValueError(
                f"ZANIM_WEB_ROOT does not contain a complete @zanim/web runtime: {root}"
            )
        return root

    # Release wheels carry a tested snapshot of @zanim/web so HTML export is
    # independent of the source checkout layout. ZANIM_WEB_ROOT remains an
    # explicit development override for working on both projects together.
    vendored = Path(__file__).resolve().parent.parent / "vendor" / "zanim_web"
    if _valid_zanim_web_root(vendored):
        return vendored

    raise ValueError("Bundled Zanim Web runtime is missing; reinstall SODA from a complete wheel.")


def _export_zanim_web_runtime(output: Path) -> None:
    root = _zanim_web_root()
    target = output.parent / "assets" / "zanim-web"
    shutil.copytree(root / "src", target / "src", dirs_exist_ok=True)
    (target / "dist").mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / "dist" / "zanim_web_core.wasm", target / "dist" / "zanim_web_core.wasm")


def _esbuild_names() -> tuple[str, ...]:
    return ("esbuild.cmd", "esbuild.exe", "esbuild") if os.name == "nt" else ("esbuild",)


def _project_esbuild(start: Path) -> Path | None:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        bin_dir = directory / "node_modules" / ".bin"
        for name in _esbuild_names():
            candidate = bin_dir / name
            if candidate.is_file():
                return candidate
    return None


def _esbuild_executable(search_from: Path | None = None) -> Path:
    configured = os.environ.get("SODA_ESBUILD")
    if configured:
        path = Path(configured).expanduser().resolve()
        if path.is_file():
            return path
        raise ValueError(f"SODA_ESBUILD does not point to an esbuild executable: {path}")
    system = shutil.which("esbuild")
    if system:
        return Path(system)
    for start in (search_from, Path.cwd()):
        if start is None:
            continue
        local = _project_esbuild(start)
        if local is not None:
            return local
    raise ValueError(
        "portable Zanim JS scenes require esbuild. Install it in the project "
        "with `npm install --save-dev esbuild`, put `esbuild` on PATH, or set SODA_ESBUILD."
    )


def _bundle_zanim_modules(paths: list[Path]) -> bytes:
    """Bundle all local Zanim scene modules once.

    The output module exports a registry mapping stable keys to each authored
    scene module. This avoids embedding @zanim/web once per scene in portable
    HTML exports.
    """
    root = _zanim_web_root()
    unique = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    executable = _esbuild_executable(unique[0] if unique else None)
    imports = []
    entries = []
    for index, path in enumerate(unique):
        key = _single_scene_key(path)
        imports.append(f"import * as m{index} from {json.dumps(path.as_posix())};")
        entries.append(f"  {json.dumps(key)}: m{index}")
    source = (
        "\n".join(imports)
        + "\nexport const scenes = {\n"
        + ",\n".join(entries)
        + "\n};\nexport default scenes;\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", encoding="utf-8", delete=False) as tmp:
        tmp.write(source)
        tmp_path = Path(tmp.name)
    try:
        command = [
            str(executable),
            str(tmp_path),
            "--bundle",
            "--format=esm",
            "--platform=browser",
            "--minify",
            "--log-level=error",
            "--tree-shaking=true",
            f"--alias:@zanim/web={root / 'src' / 'zanim.js'}",
            f"--alias:@zanim/web/ir={root / 'src' / 'ir.js'}",
        ]
        result = subprocess.run(command, check=False, capture_output=True)
    finally:
        tmp_path.unlink(missing_ok=True)
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"failed to bundle Zanim scenes: {message or 'esbuild failed'}")
    return result.stdout


def _single_scene_key(path: Path) -> str:
    return hashlib.sha256(path.resolve().as_posix().encode("utf-8")).hexdigest()[:16]


def _collect_zanim_scene_paths(program: PresentationProgram) -> list[Path]:
    paths: list[Path] = []

    def visit(source_path: str, node: PresentationObject) -> None:
        if node.kind == "zanim" and node.props.get("src"):
            ref = resolve_asset_reference(str(node.props["src"]), source_path)
            if ref.remote:
                return
            assert ref.resolved_path is not None
            if ref.resolved_path.suffix.lower() in {".js", ".mjs"}:
                paths.append(ref.resolved_path)
        for child in node.children:
            visit(source_path, child)

    for slide in program.slides:
        visit(slide.source, slide.root)
    return paths


def _single_file_resolver() -> Callable[[str, str], str]:
    cache: dict[tuple[str, str], str] = {}

    def resolve(authored: str, source_path: str) -> str:
        ref = resolve_asset_reference(authored, source_path)
        if ref.remote:
            return ref.authored
        assert ref.resolved_path is not None
        path = ref.resolved_path
        if not path.is_file():
            raise ValueError(
                f"asset {authored!r} referenced from {source_path!r} does not exist at {path}"
            )
        if path.suffix.lower() in {".js", ".mjs"}:
            return f"soda-single-scene:{_single_scene_key(path)}"
        key = (str(path), path.suffix.lower())
        cached = cache.get(key)
        if cached is not None:
            return cached
        payload = path.read_bytes()
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        value = f"data:{mime};base64,{base64.b64encode(payload).decode('ascii')}"
        cache[key] = value
        return value

    return resolve


def _single_file_zanim_head(program: PresentationProgram) -> str:
    if not _program_uses_zanim(program):
        return ""
    wasm = _zanim_web_root() / "dist" / "zanim_web_core.wasm"
    wasm_encoded = base64.b64encode(wasm.read_bytes()).decode("ascii")
    scene_paths = _collect_zanim_scene_paths(program)
    bundle = _bundle_zanim_modules(scene_paths) if scene_paths else b"export default {};\n"
    bundle_url = "data:text/javascript;base64," + base64.b64encode(bundle).decode("ascii")
    return (
        "<script>"
        + "globalThis.__ZANIM_WASM_URL__="
        + json.dumps(f"data:application/wasm;base64,{wasm_encoded}")
        + ";globalThis.__SODA_ZANIM_SCENE_BUNDLE_URL__="
        + json.dumps(bundle_url)
        + ";</script>"
    )


def export_html(
    program: PresentationProgram, output_path: str | Path, *, single_file: bool = False,
    theme: Theme | None = None, timeline: TimelineIR | None = None
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if single_file:
        rendered = render_html(
            program,
            theme=theme, timeline=timeline,
            asset_resolver=_single_file_resolver(),
            zanim_head=_single_file_zanim_head(program),
        )
    else:
        exporter = AssetExporter(output)
        if _program_uses_zanim(program):
            _export_zanim_web_runtime(output)
        rendered = render_html(program, asset_resolver=exporter.export, theme=theme, timeline=timeline)
    output.write_text(rendered, encoding="utf-8")
    return output


def _web_resource(name: str) -> str:
    from importlib.resources import files

    return files("soda.html").joinpath(name).read_text(encoding="utf-8")


TEMPLATE = (
    _web_resource("template.html")
    .replace("__RUNTIME_LICENSE__", (
        Path(__file__).resolve().parent.parent / "vendor" / "zanim_web" / "LICENSE"
    ).read_text(encoding="utf-8").rstrip())
    .replace("__STYLE__", _web_resource("style.css") + "\n" + _web_resource("academic.css"))
    .replace("__PLAYER_JS__", _web_resource("runtime.js").rstrip())
)
