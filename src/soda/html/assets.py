from __future__ import annotations

import csv
import hashlib
import mimetypes
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class AssetReference:
    authored: str
    source_path: str
    remote: bool
    resolved_path: Path | None = None


@dataclass(slots=True)
class AssetExporter:
    output_path: Path
    asset_dir_name: str = "assets"
    asset_dir: Path = field(init=False)
    _by_digest: dict[str, str] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.output_path = self.output_path.resolve()
        self.asset_dir = self.output_path.parent / self.asset_dir_name
        self._by_digest = {}

    def export(self, authored: str, source_path: str) -> str:
        ref = resolve_asset_reference(authored, source_path)
        if ref.remote:
            return ref.authored
        assert ref.resolved_path is not None
        path = ref.resolved_path
        if not path.is_file():
            raise ValueError(
                f"asset {authored!r} referenced from {source_path!r} does not exist at {path}"
            )
        digest = _sha256_file(path)
        cache_key = f"{digest}:{path.suffix.lower()}"
        existing = self._by_digest.get(cache_key)
        if existing is not None:
            return existing
        suffix = path.suffix.lower()
        stem = _safe_stem(path.stem)
        filename = f"{digest[:12]}-{stem}{suffix}"
        destination = self.asset_dir / filename
        self.asset_dir.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(path, destination)
        relative = destination.relative_to(self.output_path.parent).as_posix()
        self._by_digest[cache_key] = relative
        return relative


def resolve_asset_reference(authored: str, source_path: str) -> AssetReference:
    value = str(authored).strip()
    if not value:
        raise ValueError("asset reference cannot be empty")
    parsed = urlparse(value)
    if parsed.scheme:
        if parsed.scheme != "https":
            raise ValueError(
                f"unsupported asset URL scheme {parsed.scheme!r}; use a relative path or https:// URL"
            )
        return AssetReference(value, source_path, True, None)
    path = Path(value)
    if path.is_absolute():
        raise ValueError(
            f"absolute local asset paths are not portable: {value!r}; use a path relative to the .md file"
        )
    if source_path in {"<input>", "<stdin>", "<project>"}:
        base = Path.cwd()
    else:
        base = Path(source_path).expanduser().resolve().parent
    return AssetReference(value, source_path, False, (base / path).resolve())


def guess_media_type(path_or_url: str) -> str | None:
    path = urlparse(path_or_url).path
    return mimetypes.guess_type(path)[0]


def _safe_stem(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value)
    cleaned = cleaned.strip("-")
    return cleaned or "asset"


@dataclass(frozen=True, slots=True)
class AssetManifestEntry:
    slide: str
    object_id: str
    role: str
    authored: str
    source_path: str
    remote: bool
    resolved_path: str | None
    exists: bool | None


def collect_asset_references(program) -> tuple[AssetManifestEntry, ...]:
    entries: list[AssetManifestEntry] = []

    def visit(slide_id: str, source_path: str, node) -> None:
        references: list[tuple[str, str]] = []
        if node.kind == "image" and node.props.get("src"):
            references.append(("src", str(node.props["src"])))
        elif node.kind == "video":
            if node.props.get("src"):
                references.append(("src", str(node.props["src"])))
            if node.props.get("poster"):
                references.append(("poster", str(node.props["poster"])))
        elif node.kind == "chart" and node.props.get("src"):
            references.append(("data", str(node.props["src"])))
        elif node.kind == "zanim" and node.props.get("src"):
            references.append(("module", str(node.props["src"])))
        elif node.kind == "typst" and node.props.get("src"):
            references.append(("typst", str(node.props["src"])))
        elif node.kind == "pdf" and node.props.get("src"):
            references.append(("pdf", str(node.props["src"])))
        elif node.kind == "code-file" and node.props.get("src"):
            references.append(("code", str(node.props["src"])))
        elif node.kind == "web" and node.props.get("src"):
            references.append(("web", str(node.props["src"])))
        for role, authored in references:
            ref = resolve_asset_reference(authored, source_path)
            entries.append(
                AssetManifestEntry(
                    slide=slide_id,
                    object_id=node.id,
                    role=role,
                    authored=authored,
                    source_path=source_path,
                    remote=ref.remote,
                    resolved_path=str(ref.resolved_path) if ref.resolved_path is not None else None,
                    exists=None
                    if ref.remote
                    else bool(ref.resolved_path and ref.resolved_path.is_file()),
                )
            )
        for child in node.children:
            visit(slide_id, source_path, child)

    for slide in program.slides:
        visit(slide.id, slide.source, slide.root)
    bibliography = program.metadata.get("bibliography")
    if bibliography and program.slides:
        source_path = program.slides[0].source
        ref = resolve_asset_reference(str(bibliography), source_path)
        entries.append(
            AssetManifestEntry(
                slide="__deck__",
                object_id="bibliography",
                role="bibliography",
                authored=str(bibliography),
                source_path=source_path,
                remote=ref.remote,
                resolved_path=str(ref.resolved_path) if ref.resolved_path is not None else None,
                exists=None
                if ref.remote
                else bool(ref.resolved_path and ref.resolved_path.is_file()),
            )
        )
    return tuple(entries)


def validate_asset_references(program) -> tuple[AssetManifestEntry, ...]:
    entries = collect_asset_references(program)
    missing = [entry for entry in entries if entry.exists is False]
    if missing:
        details = ", ".join(
            f"{entry.slide}.{entry.object_id}:{entry.role} -> {entry.resolved_path}"
            for entry in missing
        )
        raise ValueError(f"missing local assets: {details}")

    for entry in entries:
        if entry.role in {"data", "bibliography", "typst", "code"} and entry.remote:
            raise ValueError(
                f"{entry.role} source {entry.authored!r} must be a local relative path"
            )

    def visit_chart(slide_id: str, source_path: str, node) -> None:
        if node.kind == "chart":
            ref = resolve_asset_reference(str(node.props.get("src", "")), source_path)
            assert ref.resolved_path is not None
            with ref.resolved_path.open("r", encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream)
                fields = set(reader.fieldnames or [])
                rows = list(reader)
            required = {str(node.props.get("x", ""))}
            y_columns = [str(value) for value in node.props.get("y", [])]
            required.update(y_columns)
            missing_fields = sorted(field for field in required if field and field not in fields)
            if missing_fields:
                raise ValueError(
                    f"chart {slide_id}.{node.id} CSV is missing columns: {', '.join(missing_fields)}"
                )
            if not rows:
                raise ValueError(f"chart {slide_id}.{node.id} has no data rows")
            for column in y_columns:
                for row_index, row in enumerate(rows, 2):
                    try:
                        float(row.get(column, ""))
                    except (TypeError, ValueError) as exc:
                        raise ValueError(
                            f"chart {slide_id}.{node.id} column {column!r} has non-numeric value at CSV row {row_index}"
                        ) from exc
        for child in node.children:
            visit_chart(slide_id, source_path, child)

    for slide in program.slides:
        visit_chart(slide.id, slide.source, slide.root)

    bibliography = program.metadata.get("bibliography")
    bib_entries = None
    if bibliography and program.slides:
        from soda.html.academic import parse_bibtex

        ref = resolve_asset_reference(str(bibliography), program.slides[0].source)
        assert ref.resolved_path is not None
        bib_entries = parse_bibtex(ref.resolved_path.read_text(encoding="utf-8"))

    citation_re = re.compile(r"\[(@[^]\n]+)\]")
    referenced_keys: set[str] = set()
    has_references = False

    def collect_citations(node) -> None:
        nonlocal has_references
        if node.kind == "citation":
            referenced_keys.update(str(key) for key in node.props.get("keys", []))
        elif node.kind == "references":
            has_references = True
        for field_name in ("text", "caption", "title"):
            text = node.props.get(field_name)
            if not text:
                continue
            for match in citation_re.finditer(str(text)):
                referenced_keys.update(
                    part.strip().lstrip("@").strip()
                    for part in re.split(r"[;,]", match.group(1))
                    if part.strip()
                )
        for child in node.children:
            collect_citations(child)

    for slide in program.slides:
        collect_citations(slide.root)
    if (referenced_keys or has_references) and bib_entries is None:
        raise ValueError(
            "citations/@references require front matter bibliography: <relative .bib path>"
        )
    if bib_entries is not None:
        unknown = sorted(referenced_keys - set(bib_entries))
        if unknown:
            raise ValueError(f"unknown bibliography keys: {', '.join(unknown)}")
    return entries


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()
