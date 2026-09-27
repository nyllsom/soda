from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from soda.compiler.diagnostics import Diagnostic, ParseError
from soda.compiler.span import Span

_ATTR_RE = re.compile(r"\s*\{([^{}]*)\}\s*$")
_HEADING_RE = re.compile(r"^(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
_IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*(\{[^{}]*\})?\s*$")
_VIDEO_RE = re.compile(r'^@video\s+(?:"([^"]+)"|(\S+))\s*(\{[^{}]*\})?\s*$')
_ZANIM_RE = re.compile(r'^@zanim\s+(?:"([^"]+)"|(\S+))\s*(\{[^{}]*\})?\s*$')
_TYPST_RE = re.compile(r'^@typst\s+(?:"([^"]+)"|(\S+))\s*(\{[^{}]*\})?\s*$')
_PDF_RE = re.compile(r'^@pdf\s+(?:"([^"]+)"|(\S+))\s*(\{[^{}]*\})?\s*$')
_WEB_RE = re.compile(r'^@web\s+(?:"([^"]+)"|(\S+))\s*(\{[^{}]*\})?\s*$')
_CODE_FILE_RE = re.compile(r'^@code\s+(?:"([^"]+)"|(\S+))\s*(\{[^{}]*\})?\s*$')
_ASSET_EMBED_RE = re.compile(r'^@embed\s+(?:"([^"]+)"|(\S+))\s*(\{[^{}]*\})?\s*$')
_FENCE_RE = re.compile(r"^```([^\s{`]*)\s*(\{[^{}]*\})?\s*$")
_EMBED_RE = re.compile(r"^@slide\s+([A-Za-z_][A-Za-z0-9_]*)\s*(\{[^{}]*\})?\s*$")
_CHART_RE = re.compile(r'^@chart\s+(?:"([^"]+)"|(\S+))\s*(\{[^{}]*\})?\s*$')
_DIAGRAM_START_RE = re.compile(r"^@diagram\s*(\{[^{}]*\})?\s*$")
_DIAGRAM_END_RE = re.compile(r"^@enddiagram\s*$")
_CITE_RE = re.compile(r"^@cite\s+([^{}]+?)\s*(\{[^{}]*\})?\s*$")
_REFERENCES_RE = re.compile(r"^@references\s*(\{[^{}]*\})?\s*$")
_ATTR_ONLY_RE = re.compile(r"^\s*\{[^{}]*\}\s*$")
_TABLE_DELIM_CELL_RE = re.compile(r"^:?-{3,}:?$")
_RULE_RE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})\s*$")
_UL_RE = re.compile(r"^\s*[-+*]\s+(.+)$")
_OL_RE = re.compile(r"^\s*\d+[.)]\s+(.+)$")
_RATIO_RE = re.compile(r"^\d+(?:\.\d+)?(?::\d+(?:\.\d+)?)+$")
_GRID_RE = re.compile(r"^grid:(\d+)x(\d+)$", re.IGNORECASE)
_LAYOUT_NAMES = {
    "left|right",
    "right|left",
    "top|bottom",
    "bottom|top",
    "columns",
    "column",
    "cols",
    "rows",
    "row",
    "stack",
    "overlay",
}


@dataclass(slots=True)
class ContentObject:
    id: str
    kind: str
    props: dict[str, Any]
    children: list["ContentObject"] = field(default_factory=list)
    span: Span | None = None


@dataclass(slots=True)
class ContentSlide:
    id: str
    title: str
    root: ContentObject
    objects: dict[str, ContentObject]
    path: str
    span: Span


@dataclass(slots=True)
class ContentDocument:
    metadata: dict[str, str]
    slides: list[ContentSlide]
    path: str


@dataclass(slots=True)
class _HeadingInfo:
    line: int
    level: int
    raw: str


@dataclass(slots=True)
class _HeadingSpec:
    title: str
    explicit_id: str | None
    attrs: dict[str, Any]
    layout: dict[str, Any] | None


@dataclass(slots=True)
class _Section:
    heading: _HeadingInfo
    spec: _HeadingSpec
    children: list["_Section"] = field(default_factory=list)
    end_line: int = 0


class _ContentParser:
    def __init__(self, source: str, path: str) -> None:
        self.source = source
        self.path = path
        self.lines = source.splitlines(keepends=True)
        self.offsets: list[int] = []
        offset = 0
        for line in self.lines:
            self.offsets.append(offset)
            offset += len(line)
        self.metadata: dict[str, str] = {}
        self.slides: list[ContentSlide] = []
        self.current_slide: ContentSlide | None = None
        self.auto_counts: dict[str, int] = {}

    def parse(self) -> ContentDocument:
        headings = self._scan_headings()
        slide_headings = [heading for heading in headings if heading.level <= 2]
        if not slide_headings:
            self._error(0, "Markdown presentation requires at least one # or ## slide heading")

        self._parse_frontmatter(slide_headings[0].line)
        for index, heading in enumerate(slide_headings):
            end_line = (
                slide_headings[index + 1].line
                if index + 1 < len(slide_headings)
                else len(self.lines)
            )
            internal = [
                item for item in headings if heading.line < item.line < end_line and item.level >= 3
            ]
            self._parse_slide(heading, end_line, internal)
        return ContentDocument(dict(self.metadata), self.slides, self.path)

    def _scan_headings(self) -> list[_HeadingInfo]:
        result: list[_HeadingInfo] = []
        in_fence = False
        in_math = False
        frontmatter_end = -1
        first_nonempty = next((i for i, raw in enumerate(self.lines) if raw.strip()), None)
        if first_nonempty is not None and self.lines[first_nonempty].strip() == "---":
            for line in range(first_nonempty + 1, len(self.lines)):
                if self.lines[line].strip() == "---":
                    frontmatter_end = line
                    break
        for line, raw_line in enumerate(self.lines):
            if line <= frontmatter_end:
                continue
            raw = raw_line.rstrip("\r\n")
            stripped = raw.strip()
            if in_fence:
                if stripped.startswith("```"):
                    in_fence = False
                continue
            if in_math:
                if stripped.startswith("$$"):
                    in_math = False
                continue
            if stripped.startswith("```"):
                in_fence = True
                continue
            if stripped == "$$":
                in_math = True
                continue
            match = _HEADING_RE.match(raw)
            if match:
                result.append(
                    _HeadingInfo(line, len(match.group(1)), (match.group(2) or "").strip())
                )
        return result

    def _parse_frontmatter(self, first_slide_line: int) -> None:
        nonempty = [i for i in range(first_slide_line) if self.lines[i].strip()]
        if not nonempty:
            return
        start = nonempty[0]
        if self.lines[start].strip() != "---":
            self._error(start, "only YAML-style front matter may appear before the first slide")
        close = None
        for line in range(start + 1, first_slide_line):
            if self.lines[line].strip() == "---":
                close = line
                break
        if close is None:
            self._error(start, "unterminated front matter")
        for line in range(start + 1, close):
            stripped = self.lines[line].strip()
            if not stripped or stripped.startswith("#"):
                continue
            if ":" not in stripped:
                self._error(line, "front matter entries must use 'key: value'")
            key, value = stripped.split(":", 1)
            key = key.strip()
            if key not in {"deck", "author", "theme", "lang", "bibliography"}:
                self._error(line, f"unknown front matter key {key!r}")
            self.metadata[key] = value.strip().strip("\"'")
        for line in range(close + 1, first_slide_line):
            if self.lines[line].strip():
                self._error(line, "content before the first slide is not allowed")

    def _parse_slide(
        self, heading: _HeadingInfo, end_line: int, internals: list[_HeadingInfo]
    ) -> None:
        spec = self._parse_heading_spec(heading.raw, heading.line)
        slide_id = self._reserve_global_id(
            spec.explicit_id or self._slug(spec.title, "slide"),
            heading.line,
            explicit=spec.explicit_id is not None,
        )
        props = {"title": spec.title, **spec.attrs}
        classes = list(props.get("classes", []))
        if heading.level == 1 and "cover" not in classes:
            classes.append("cover")
        if classes:
            props["classes"] = classes
        root = ContentObject(slide_id, "slide", props, span=self._span(heading.line))
        title_obj = ContentObject(
            "title",
            "heading",
            {"text": spec.title, "level": 1, "role": "title"},
            span=self._span(heading.line),
        )
        root.children.append(title_obj)
        slide = ContentSlide(
            slide_id,
            spec.title,
            root,
            {slide_id: root, "title": title_obj},
            self.path,
            self._span(heading.line),
        )
        self.slides.append(slide)
        self.current_slide = slide
        self.auto_counts = {}

        sections = self._build_sections(internals, end_line)
        prefix_end = sections[0].heading.line if sections else end_line
        self._emit_blocks(heading.line + 1, prefix_end, root)
        if spec.layout is not None:
            if not sections:
                self._error(heading.line, "slide layout requires ### child sections")
            self._append_layout(root, spec.layout, sections, owner_id=slide_id, owner_level=2)
        else:
            for section in sections:
                root.children.append(self._emit_section(section))

    def _build_sections(self, headings: list[_HeadingInfo], end_line: int) -> list[_Section]:
        roots: list[_Section] = []
        stack: list[_Section] = []
        for heading in headings:
            section = _Section(
                heading, self._parse_heading_spec(heading.raw, heading.line), end_line=end_line
            )
            while stack and heading.level <= stack[-1].heading.level:
                stack[-1].end_line = heading.line
                stack.pop()
            if stack:
                stack[-1].children.append(section)
            else:
                roots.append(section)
            stack.append(section)
        for section in stack:
            section.end_line = end_line
        return roots

    def _emit_section(self, section: _Section) -> ContentObject:
        suggested = self._slug(section.spec.title, "section")
        section_id = self._reserve_id(
            section.spec.explicit_id or suggested,
            section.heading.line,
            explicit=section.spec.explicit_id is not None,
        )
        props = {"markdown_section": True, **section.spec.attrs}
        classes = list(props.get("classes", []))
        if props.pop("card", False) and "card" not in classes:
            classes.append("card")
        classes.append("markdown-section")
        props["classes"] = list(dict.fromkeys(classes))
        region = ContentObject(
            section_id,
            "region",
            props,
            span=self._span(section.heading.line, max(section.heading.line, section.end_line - 1)),
        )
        self._register(region, section.heading.line)

        if section.spec.title:
            title_id = self._reserve_id(f"{section_id}_title", section.heading.line)
            title = ContentObject(
                title_id,
                "heading",
                {
                    "text": section.spec.title,
                    "level": section.heading.level,
                    "role": "section-title",
                },
                span=self._span(section.heading.line),
            )
            self._register(title, section.heading.line)
            region.children.append(title)

        prefix_end = section.children[0].heading.line if section.children else section.end_line
        self._emit_blocks(section.heading.line + 1, prefix_end, region)
        if section.spec.layout is not None:
            if not section.children:
                self._error(
                    section.heading.line, "layout section requires child headings one level deeper"
                )
            self._append_layout(
                region,
                section.spec.layout,
                section.children,
                owner_id=section_id,
                owner_level=section.heading.level,
            )
        else:
            for child in section.children:
                region.children.append(self._emit_section(child))
        return region

    def _append_layout(
        self,
        parent: ContentObject,
        layout: dict[str, Any],
        sections: list[_Section],
        *,
        owner_id: str,
        owner_level: int,
    ) -> None:
        expected_level = 3 if parent.kind == "slide" else owner_level + 1
        if any(section.heading.level != expected_level for section in sections):
            self._error(
                sections[0].heading.line,
                f"layout children must use {'#' * expected_level} headings",
            )
        kind = str(layout["kind"])
        props = {key: value for key, value in layout.items() if key not in {"kind", "reverse"}}
        reverse = bool(layout.get("reverse"))
        children = [self._emit_section(section) for section in sections]
        if reverse:
            children.reverse()
            if "ratio" in props:
                props["ratio"] = list(reversed(props["ratio"]))
        self._validate_layout_arity(kind, props, len(children), sections[0].heading.line)
        authored_layout_id = props.pop("id", None)
        layout_id = self._reserve_id(
            str(authored_layout_id or f"{owner_id}_layout"),
            sections[0].heading.line,
            explicit=authored_layout_id is not None,
        )
        node = ContentObject(
            layout_id,
            kind,
            props,
            children,
            span=self._span(
                sections[0].heading.line, max(sections[-1].heading.line, sections[-1].end_line - 1)
            ),
        )
        self._register(node, sections[0].heading.line)
        parent.children.append(node)

    def _validate_layout_arity(
        self, kind: str, props: dict[str, Any], count: int, line: int
    ) -> None:
        if kind in {"columns", "rows"}:
            ratio = props.get("ratio", [1.0, 1.0])
            if len(ratio) != count:
                self._error(
                    line,
                    f"{kind} layout ratio defines {len(ratio)} regions but found {count} child sections",
                )
        elif kind == "grid":
            capacity = int(props["cols"]) * int(props["rows"])
            if capacity != count:
                self._error(
                    line, f"grid layout requires exactly {capacity} child sections, found {count}"
                )

    def _emit_blocks(self, start: int, end: int, parent: ContentObject) -> None:
        i = start
        while i < end:
            raw = self.lines[i].rstrip("\r\n")
            stripped = raw.strip()
            if not stripped:
                i += 1
                continue
            fence = _FENCE_RE.match(stripped)
            if fence:
                i = self._parse_code(i, end, parent, fence.group(1) or "text", fence.group(2))
                continue
            if stripped == "$$":
                i = self._parse_math(i, end, parent)
                continue
            if self._looks_like_table(i, end):
                i = self._parse_table(i, end, parent)
                continue
            chart = _CHART_RE.match(stripped)
            if chart:
                i = self._parse_chart(
                    i, parent, chart.group(1) or chart.group(2) or "", chart.group(3)
                )
                continue
            diagram = _DIAGRAM_START_RE.match(stripped)
            if diagram:
                i = self._parse_diagram(i, end, parent, diagram.group(1))
                continue
            cite = _CITE_RE.match(stripped)
            if cite:
                oid, attrs = self._attrs_from_group(cite.group(2), i)
                keys = [
                    part.strip().lstrip("@").strip()
                    for part in re.split(r"[,;]", cite.group(1))
                    if part.strip()
                ]
                if not keys:
                    self._error(i, "@cite requires at least one bibliography key")
                self._add_object(parent, i, "citation", {"keys": keys, **attrs}, explicit_id=oid)
                i += 1
                continue
            refs = _REFERENCES_RE.match(stripped)
            if refs:
                oid, attrs = self._attrs_from_group(refs.group(1), i)
                self._add_object(parent, i, "references", attrs, explicit_id=oid)
                i += 1
                continue
            image = _IMAGE_RE.match(stripped)
            if image:
                oid, attrs = self._attrs_from_group(image.group(3), i)
                self._add_object(
                    parent,
                    i,
                    "image",
                    {"alt": image.group(1), "src": image.group(2), **attrs},
                    explicit_id=oid,
                )
                i += 1
                continue
            video = _VIDEO_RE.match(stripped)
            if video:
                oid, attrs = self._attrs_from_group(video.group(3), i)
                src = video.group(1) if video.group(1) is not None else video.group(2)
                assert src is not None
                self._add_object(parent, i, "video", {"src": src, **attrs}, explicit_id=oid)
                i += 1
                continue
            typst = _TYPST_RE.match(stripped)
            if typst:
                oid, attrs = self._attrs_from_group(typst.group(3), i)
                src = typst.group(1) if typst.group(1) is not None else typst.group(2)
                assert src is not None
                self._add_object(parent, i, "typst", {"src": src, **attrs}, explicit_id=oid)
                i += 1
                continue
            pdf = _PDF_RE.match(stripped)
            if pdf:
                oid, attrs = self._attrs_from_group(pdf.group(3), i)
                src = pdf.group(1) if pdf.group(1) is not None else pdf.group(2)
                assert src is not None
                self._add_object(parent, i, "pdf", {"src": src, **attrs}, explicit_id=oid)
                i += 1
                continue
            web = _WEB_RE.match(stripped)
            if web:
                oid, attrs = self._attrs_from_group(web.group(3), i)
                src = web.group(1) if web.group(1) is not None else web.group(2)
                assert src is not None
                if urlparse(src).scheme != "https":
                    self._error(i, "@web requires an https:// URL")
                self._add_object(parent, i, "web", {"src": src, **attrs}, explicit_id=oid)
                i += 1
                continue
            code_file = _CODE_FILE_RE.match(stripped)
            if code_file:
                oid, attrs = self._attrs_from_group(code_file.group(3), i)
                src = code_file.group(1) if code_file.group(1) is not None else code_file.group(2)
                assert src is not None
                self._add_object(parent, i, "code-file", {"src": src, **attrs}, explicit_id=oid)
                i += 1
                continue
            asset_embed = _ASSET_EMBED_RE.match(stripped)
            if asset_embed:
                oid, attrs = self._attrs_from_group(asset_embed.group(3), i)
                src = (
                    asset_embed.group(1)
                    if asset_embed.group(1) is not None
                    else asset_embed.group(2)
                )
                assert src is not None
                kind = self._embed_kind(src, attrs.pop("type", None), i)
                props = {"src": src, **attrs}
                if kind == "image":
                    props.setdefault("alt", str(attrs.get("label", "")))
                self._add_object(parent, i, kind, props, explicit_id=oid)
                i += 1
                continue
            zanim = _ZANIM_RE.match(stripped)
            if zanim:
                oid, attrs = self._attrs_from_group(zanim.group(3), i)
                src = zanim.group(1) if zanim.group(1) is not None else zanim.group(2)
                assert src is not None
                self._add_object(parent, i, "zanim", {"src": src, **attrs}, explicit_id=oid)
                i += 1
                continue
            embed = _EMBED_RE.match(stripped)
            if embed:
                oid, attrs = self._attrs_from_group(embed.group(2), i)
                self._add_object(
                    parent, i, "slide-ref", {"slide": embed.group(1), **attrs}, explicit_id=oid
                )
                i += 1
                continue
            if _RULE_RE.match(stripped):
                self._add_object(parent, i, "rule", {})
                i += 1
                continue
            if stripped.startswith(">"):
                lines: list[str] = []
                first = i
                while i < end and self.lines[i].lstrip().startswith(">"):
                    lines.append(self.lines[i].lstrip()[1:].lstrip().rstrip("\r\n"))
                    i += 1
                self._add_object(parent, first, "quote", {"text": "\n".join(lines)}, end_line=i - 1)
                continue
            ul = _UL_RE.match(raw)
            ol = _OL_RE.match(raw)
            if ul or ol:
                i = self._parse_list(i, end, parent, ordered=bool(ol))
                continue
            if _HEADING_RE.match(raw):
                self._error(i, "internal heading escaped section parsing")
            i = self._parse_paragraph(i, end, parent)

    def _split_table_row(self, raw: str) -> list[str]:
        value = raw.strip()
        if value.startswith("|"):
            value = value[1:]
        if value.endswith("|"):
            value = value[:-1]
        cells = re.split(r"(?<!\\)\|", value)
        return [cell.replace(r"\|", "|").strip() for cell in cells]

    def _looks_like_table(self, start: int, end: int) -> bool:
        if start + 1 >= end:
            return False
        first = self.lines[start].rstrip("\r\n")
        second = self.lines[start + 1].rstrip("\r\n")
        if "|" not in first or "|" not in second:
            return False
        header = self._split_table_row(first)
        delim = self._split_table_row(second)
        return (
            bool(header)
            and len(header) == len(delim)
            and all(_TABLE_DELIM_CELL_RE.fullmatch(cell) for cell in delim)
        )

    def _parse_table(self, start: int, end: int, parent: ContentObject) -> int:
        header = self._split_table_row(self.lines[start].rstrip("\r\n"))
        delimiter = self._split_table_row(self.lines[start + 1].rstrip("\r\n"))
        align: list[str] = []
        for cell in delimiter:
            left, right = cell.startswith(":"), cell.endswith(":")
            align.append(
                "center" if left and right else "left" if left else "right" if right else "left"
            )
        rows: list[tuple[int, list[str]]] = []
        i = start + 2
        while i < end:
            raw = self.lines[i].rstrip("\r\n")
            if not raw.strip() or "|" not in raw or _ATTR_ONLY_RE.match(raw.strip()):
                break
            cells = self._split_table_row(raw)
            if len(cells) != len(header):
                self._error(i, f"table row has {len(cells)} cells; expected {len(header)}")
            rows.append((i, cells))
            i += 1
        oid: str | None = None
        attrs: dict[str, Any] = {}
        attr_line: int | None = None
        if i < end and _ATTR_ONLY_RE.match(self.lines[i].strip()):
            attr_line = i
            oid, attrs = self._attrs_from_group(self.lines[i].strip(), i)
            i += 1
        table = self._add_object(
            parent,
            start,
            "table",
            {"align": align, **attrs},
            explicit_id=oid,
            end_line=(attr_line if attr_line is not None else max(start + 1, i - 1)),
        )
        table_id = table.id
        all_rows = [(start, header, True)] + [(line, cells, False) for line, cells in rows]
        for r_index, (line, cells, is_header) in enumerate(all_rows):
            row_id = self._reserve_id(
                f"{table_id}_{'header' if is_header else f'r{r_index}'}", line
            )
            row = ContentObject(
                row_id, "table-row", {"header": is_header, "row": r_index}, span=self._span(line)
            )
            self._register(row, line)
            table.children.append(row)
            for c_index, text in enumerate(cells, 1):
                cell_id = self._reserve_id(f"{row_id}_c{c_index}", line)
                cell = ContentObject(
                    cell_id,
                    "table-cell",
                    {
                        "text": text,
                        "header": is_header,
                        "row": r_index,
                        "col": c_index,
                        "align": align[c_index - 1],
                    },
                    span=self._span(line),
                )
                self._register(cell, line)
                row.children.append(cell)
        return i

    def _embed_kind(self, src: str, explicit: object, line: int) -> str:
        aliases = {
            "image": "image",
            "video": "video",
            "zanim": "zanim",
            "scene": "zanim",
            "typst": "typst",
            "pdf": "pdf",
            "web": "web",
            "code": "code-file",
        }
        if explicit is not None:
            kind = aliases.get(str(explicit).lower())
            if kind is None:
                self._error(
                    line, "@embed type must be image, video, zanim, typst, pdf, web, or code"
                )
            if kind == "web" and urlparse(src).scheme != "https":
                self._error(line, "@embed type=web requires an https:// URL")
            return kind

        path = urlparse(src).path
        suffix = Path(path).suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif"}:
            return "image"
        if suffix in {".mp4", ".webm", ".mov", ".m4v", ".ogv"}:
            return "video"
        if suffix in {".js", ".mjs"}:
            return "zanim"
        if suffix == ".typ":
            return "typst"
        if suffix == ".pdf":
            return "pdf"
        if suffix in {
            ".py",
            ".zig",
            ".rs",
            ".c",
            ".cc",
            ".cpp",
            ".h",
            ".hpp",
            ".java",
            ".go",
            ".lua",
            ".js",
            ".ts",
            ".tsx",
            ".jsx",
            ".sh",
            ".bash",
            ".zsh",
            ".json",
            ".yaml",
            ".yml",
            ".toml",
        }:
            return "code-file"
        self._error(
            line,
            "cannot infer @embed type from the source; add type=image|video|zanim|typst|pdf|web|code",
        )

    def _parse_chart(
        self, line: int, parent: ContentObject, src: str, attrs_group: str | None
    ) -> int:
        oid, attrs = self._attrs_from_group(attrs_group, line)
        chart_type = str(attrs.get("type", "line")).lower()
        if chart_type not in {"line", "bar", "scatter"}:
            self._error(line, "chart type must be line, bar, or scatter")
        x = str(attrs.get("x", "")).strip()
        y_raw = str(attrs.get("y", "")).strip()
        if not x or not y_raw:
            self._error(line, "@chart requires x=<column> and y=<column[,column...]> attributes")
        series = [part.strip() for part in y_raw.split(",") if part.strip()]
        chart = self._add_object(
            parent,
            line,
            "chart",
            {**attrs, "src": src, "type": chart_type, "x": x, "y": series},
            explicit_id=oid,
        )
        for index, name in enumerate(series, 1):
            stem = self._slug(name, "series")
            series_id = self._reserve_id(f"{chart.id}_{stem}", line)
            child = ContentObject(
                series_id, "chart-series", {"name": name, "index": index - 1}, span=self._span(line)
            )
            self._register(child, line)
            chart.children.append(child)
        return line + 1

    def _parse_diagram(
        self, start: int, end: int, parent: ContentObject, attrs_group: str | None
    ) -> int:
        oid, attrs = self._attrs_from_group(attrs_group, start)
        direction = str(attrs.get("direction", "LR")).upper()
        if direction not in {"LR", "TB"}:
            self._error(start, "diagram direction must be LR or TB")
        i = start + 1
        edges: list[tuple[int, str, str]] = []
        labels: dict[str, str] = {}
        token_re = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)(?:\["([^"]+)"\])?$')
        while i < end and not _DIAGRAM_END_RE.match(self.lines[i].strip()):
            raw = self.lines[i].strip()
            if raw:
                parts = [part.strip() for part in raw.split("->")]
                if len(parts) < 2:
                    self._error(i, "diagram lines must connect nodes with ->")
                ids: list[str] = []
                for part in parts:
                    match = token_re.fullmatch(part)
                    if not match:
                        self._error(i, f'invalid diagram node {part!r}; use id or id["Label"]')
                    node_id = match.group(1)
                    label = match.group(2) or node_id.replace("_", " ")
                    previous = labels.get(node_id)
                    if previous is not None and previous != label:
                        self._error(i, f"diagram node {node_id!r} uses conflicting labels")
                    labels[node_id] = label
                    ids.append(node_id)
                for left, right in zip(ids, ids[1:]):
                    edges.append((i, left, right))
            i += 1
        if i >= end:
            self._error(start, "unterminated @diagram block; add @enddiagram")
        diagram = self._add_object(
            parent, start, "diagram", {**attrs, "direction": direction}, explicit_id=oid, end_line=i
        )
        for node_id, label in labels.items():
            stable_id = self._reserve_id(node_id, start, explicit=True)
            node = ContentObject(
                stable_id, "diagram-node", {"label": label}, span=self._span(start, i)
            )
            self._register(node, start)
            diagram.children.append(node)
        for edge_index, (line, source, target) in enumerate(edges, 1):
            edge_id = self._reserve_id(f"{diagram.id}_edge_{edge_index}", line)
            edge = ContentObject(
                edge_id, "diagram-edge", {"source": source, "target": target}, span=self._span(line)
            )
            self._register(edge, line)
            diagram.children.append(edge)
        return i + 1

    def _parse_code(
        self, start: int, end: int, parent: ContentObject, language: str, attrs_group: str | None
    ) -> int:
        body: list[str] = []
        i = start + 1
        while i < end:
            raw = self.lines[i].rstrip("\r\n")
            if raw.strip().startswith("```"):
                oid, attrs = self._attrs_from_group(attrs_group, start)
                self._add_object(
                    parent,
                    start,
                    "code",
                    {"language": language, "source": "\n".join(body), **attrs},
                    explicit_id=oid,
                    end_line=i,
                )
                return i + 1
            body.append(raw)
            i += 1
        self._error(start, "unterminated fenced code block")

    def _parse_math(self, start: int, end: int, parent: ContentObject) -> int:
        body: list[str] = []
        i = start + 1
        while i < end:
            raw = self.lines[i].rstrip("\r\n")
            stripped = raw.strip()
            if stripped.startswith("$$"):
                suffix = stripped[2:].strip()
                oid, attrs = self._attrs_from_group(suffix if suffix.startswith("{") else None, i)
                self._add_object(
                    parent,
                    start,
                    "math",
                    {"source": "\n".join(body), **attrs},
                    explicit_id=oid,
                    end_line=i,
                )
                return i + 1
            body.append(raw)
            i += 1
        self._error(start, "unterminated math block")

    def _parse_list(self, start: int, end: int, parent: ContentObject, *, ordered: bool) -> int:
        matcher = _OL_RE if ordered else _UL_RE
        items: list[tuple[int, str]] = []
        i = start
        while i < end:
            match = matcher.match(self.lines[i].rstrip("\r\n"))
            if not match:
                break
            items.append((i, match.group(1).strip()))
            i += 1
        list_node = self._add_object(
            parent, start, "list", {"ordered": ordered}, end_line=max(start, i - 1)
        )
        for line, text in items:
            clean, oid, attrs = self._split_trailing_attrs(text, line)
            item_id = self._reserve_id(oid or self._auto_id("item"), line, explicit=oid is not None)
            item = ContentObject(
                item_id, "list-item", {"text": clean, **attrs}, span=self._span(line)
            )
            self._register(item, line)
            list_node.children.append(item)
        return i

    def _parse_paragraph(self, start: int, end: int, parent: ContentObject) -> int:
        lines: list[str] = []
        i = start
        while i < end:
            raw = self.lines[i].rstrip("\r\n")
            stripped = raw.strip()
            if not stripped:
                break
            if i != start and (
                _FENCE_RE.match(stripped)
                or _IMAGE_RE.match(stripped)
                or _VIDEO_RE.match(stripped)
                or _EMBED_RE.match(stripped)
                or _ZANIM_RE.match(stripped)
                or _TYPST_RE.match(stripped)
                or _PDF_RE.match(stripped)
                or _WEB_RE.match(stripped)
                or _CODE_FILE_RE.match(stripped)
                or _ASSET_EMBED_RE.match(stripped)
                or _CHART_RE.match(stripped)
                or _DIAGRAM_START_RE.match(stripped)
                or _CITE_RE.match(stripped)
                or _REFERENCES_RE.match(stripped)
                or self._looks_like_table(i, end)
                or _RULE_RE.match(stripped)
                or stripped == "$$"
                or stripped.startswith(">")
                or _UL_RE.match(raw)
                or _OL_RE.match(raw)
                or _HEADING_RE.match(raw)
            ):
                break
            lines.append(stripped)
            i += 1
        text = "\n".join(lines)
        clean, oid, attrs = self._split_trailing_attrs(text, max(start, i - 1))
        self._add_object(
            parent,
            start,
            "paragraph",
            {"text": clean, **attrs},
            explicit_id=oid,
            end_line=max(start, i - 1),
        )
        return i

    def _add_object(
        self,
        parent: ContentObject,
        line: int,
        kind: str,
        props: dict[str, Any],
        *,
        explicit_id: str | None = None,
        end_line: int | None = None,
    ) -> ContentObject:
        object_id = self._reserve_id(
            explicit_id or self._auto_id(kind), line, explicit=explicit_id is not None
        )
        node = ContentObject(object_id, kind, props, span=self._span(line, end_line))
        self._register(node, line)
        parent.children.append(node)
        return node

    def _register(self, node: ContentObject, line: int) -> None:
        assert self.current_slide is not None
        if node.id in self.current_slide.objects:
            self._error(line, f"duplicate object id {node.id!r} in slide {self.current_slide.id!r}")
        self.current_slide.objects[node.id] = node

    def _reserve_global_id(self, candidate: str, line: int, *, explicit: bool = False) -> str:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", candidate):
            self._error(line, f"invalid slide id {candidate!r}")
        existing = {slide.id for slide in self.slides}
        if candidate not in existing:
            return candidate
        if explicit:
            self._error(line, f"duplicate slide id {candidate!r}")
        suffix = 2
        while f"{candidate}_{suffix}" in existing:
            suffix += 1
        return f"{candidate}_{suffix}"

    def _reserve_id(self, candidate: str, line: int, *, explicit: bool = False) -> str:
        assert self.current_slide is not None
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", candidate):
            self._error(line, f"invalid object id {candidate!r}")
        if candidate not in self.current_slide.objects:
            return candidate
        if explicit:
            self._error(
                line, f"duplicate object id {candidate!r} in slide {self.current_slide.id!r}"
            )
        suffix = 2
        while f"{candidate}_{suffix}" in self.current_slide.objects:
            suffix += 1
        return f"{candidate}_{suffix}"

    def _auto_id(self, kind: str) -> str:
        stem = kind.replace("-", "_")
        value = self.auto_counts.get(stem, 0) + 1
        self.auto_counts[stem] = value
        return f"{stem}_{value}"

    def _slug(self, text: str, fallback: str) -> str:
        ascii_text = text.encode("ascii", "ignore").decode("ascii").lower()
        value = re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_")
        if not value:
            if fallback == "slide":
                return f"slide_{len(self.slides) + 1}"
            return self._auto_id(fallback)
        if value[0].isdigit():
            value = f"{fallback}_{value}"
        return value

    def _parse_heading_spec(self, text: str, line: int) -> _HeadingSpec:
        match = _ATTR_RE.search(text)
        if not match:
            return _HeadingSpec(text.strip(), None, {}, None)
        title = text[: match.start()].rstrip()
        try:
            tokens = shlex.split(match.group(1).strip(), posix=True)
        except ValueError as exc:
            self._error(line, f"invalid heading attribute block: {exc}")
        layout: dict[str, Any] | None = None
        layout_index: int | None = None
        for index, token in enumerate(tokens):
            lowered = token.lower()
            if lowered in _LAYOUT_NAMES or _GRID_RE.match(lowered):
                layout_index = index
                layout = self._layout_from_token(lowered, line)
                break
        remaining = list(tokens)
        if layout_index is not None:
            remaining.pop(layout_index)
            if layout is not None and layout["kind"] in {"columns", "rows"}:
                ratio_index = next(
                    (i for i, token in enumerate(remaining) if _RATIO_RE.match(token)), None
                )
                if ratio_index is not None:
                    layout["ratio"] = self._parse_ratio(remaining.pop(ratio_index), line)
        explicit_id, attrs = self._parse_attr_tokens(remaining, line)
        if layout is not None and "gap" in attrs:
            layout["gap"] = float(attrs.pop("gap"))
        if layout is not None and "layout_id" in attrs:
            layout_id = str(attrs.pop("layout_id"))
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", layout_id):
                self._error(line, f"invalid layout id {layout_id!r}")
            layout["id"] = layout_id
        return _HeadingSpec(title, explicit_id, attrs, layout)

    def _layout_from_token(self, token: str, line: int) -> dict[str, Any]:
        grid = _GRID_RE.match(token)
        if grid:
            cols, rows = int(grid.group(1)), int(grid.group(2))
            if cols < 1 or rows < 1 or cols > 8 or rows > 8:
                self._error(line, "grid dimensions must be between 1 and 8")
            return {"kind": "grid", "cols": cols, "rows": rows}
        if token in {"left|right", "right|left", "columns", "column", "cols"}:
            return {
                "kind": "columns",
                "ratio": [1.0, 1.0],
                "reverse": token == "right|left",
            }
        if token in {"top|bottom", "bottom|top", "rows", "row"}:
            return {
                "kind": "rows",
                "ratio": [1.0, 1.0],
                "reverse": token == "bottom|top",
            }
        if token in {"stack", "overlay"}:
            return {"kind": token}
        self._error(line, f"unknown layout annotation {token!r}")

    def _parse_ratio(self, raw: str, line: int) -> list[float]:
        try:
            values = [float(part) for part in raw.split(":")]
        except ValueError:
            self._error(line, f"invalid layout ratio {raw!r}")
        if len(values) < 2 or any(value <= 0 for value in values):
            self._error(line, "layout ratio requires at least two positive values")
        return values

    def _attrs_from_group(self, group: str | None, line: int) -> tuple[str | None, dict[str, Any]]:
        if not group:
            return None, {}
        try:
            tokens = shlex.split(group[1:-1], posix=True)
        except ValueError as exc:
            self._error(line, f"invalid attribute block: {exc}")
        return self._parse_attr_tokens(tokens, line)

    def _split_trailing_attrs(self, text: str, line: int) -> tuple[str, str | None, dict[str, Any]]:
        match = _ATTR_RE.search(text)
        if not match:
            return text.strip(), None, {}
        try:
            tokens = shlex.split(match.group(1), posix=True)
        except ValueError as exc:
            self._error(line, f"invalid attribute block: {exc}")
        oid, attrs = self._parse_attr_tokens(tokens, line)
        return text[: match.start()].rstrip(), oid, attrs

    def _parse_attr_tokens(self, tokens: list[str], line: int) -> tuple[str | None, dict[str, Any]]:
        explicit_id: str | None = None
        attrs: dict[str, Any] = {}
        for token in tokens:
            if token.startswith("#"):
                if explicit_id is not None:
                    self._error(line, "attribute block may contain only one #id")
                explicit_id = token[1:]
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", explicit_id or ""):
                    self._error(line, f"invalid object id {explicit_id!r}")
                continue
            if token.startswith("."):
                attrs.setdefault("classes", []).append(token[1:])
                continue
            if _RATIO_RE.match(token):
                self._error(line, f"ratio {token!r} requires a layout annotation")
            if "=" not in token:
                attrs[token] = True
                continue
            key, value = token.split("=", 1)
            attrs[key] = self._attr_value(key, value, line)
        return explicit_id, attrs

    def _attr_value(self, key: str, value: str, line: int) -> Any:
        value = value.strip("\"'")
        if value.lower() in {"true", "false"}:
            return value.lower() == "true"
        if key in {"gap", "width", "height", "scale", "size", "font_size"}:
            try:
                return float(value)
            except ValueError:
                self._error(line, f"{key} must be numeric")
        if key in {"cols", "rows", "max_lines", "page"}:
            try:
                number = int(value)
            except ValueError:
                self._error(line, f"{key} must be an integer")
            if number <= 0:
                self._error(line, f"{key} must be positive")
            return number
        if key in {"line_numbers", "dim_inactive"}:
            lowered = value.lower()
            if lowered not in {"true", "false"}:
                self._error(line, f"{key} must be true or false")
            return lowered == "true"
        return value

    def _span(self, line: int, end_line: int | None = None) -> Span:
        if not self.lines:
            return Span(0, 0, 1, 1, 1, 1)
        line = max(0, min(line, len(self.lines) - 1))
        end_line = line if end_line is None else max(line, min(end_line, len(self.lines) - 1))
        start = self.offsets[line]
        end = self.offsets[end_line] + len(self.lines[end_line].rstrip("\r\n"))
        return Span(start, end, line + 1, 1, end_line + 1, max(1, end - self.offsets[end_line] + 1))

    def _error(self, line: int, message: str):
        raise ParseError(Diagnostic(message, self._span(line), self.path))


def parse_content(source: str, *, path: str = "<input>") -> ContentDocument:
    return _ContentParser(source, path).parse()
