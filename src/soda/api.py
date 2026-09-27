"""The small public API, shared by scripts and the command line."""

from dataclasses import dataclass
from pathlib import Path

from soda.compiler.project import PresentationProgram, SourceUnit, compile_project
from soda.compiler.timeline_ir import TimelineIR, compile_timeline
from soda.html.assets import validate_asset_references
from soda.themes import Theme, resolve_theme


@dataclass(frozen=True, slots=True)
class Deck:
    """A validated presentation and its absolute-time animation schedule."""

    program: PresentationProgram
    timeline: TimelineIR
    theme: Theme
    base_dir: Path


def _compile(content: SourceUnit, motion: SourceUnit | None, base_dir: Path) -> Deck:
    program = compile_project([content], [motion] if motion else [])
    validate_asset_references(program)
    timeline = compile_timeline(program)
    theme = resolve_theme(program.metadata.get("theme"), base_dir=base_dir)
    return Deck(program, timeline, theme, base_dir)


def compile_deck(
    source: str | Path, *, motion: str | Path | None = None, static: bool = False
) -> Deck:
    """Read a .md file and its optional sibling .soda; resolve assets from the .md.

    An explicit relative motion path is also relative to the Markdown file.
    ``static=True`` ignores the sibling motion file. Compilation validates
    references and timing without invoking Typst, Node, or the browser.
    """
    source = Path(source).expanduser().resolve()
    if source.suffix.lower() != ".md":
        raise ValueError("content must be a .md file")
    if static and motion is not None:
        raise ValueError("static=True cannot be combined with an explicit motion file")
    content = SourceUnit(str(source), source.read_text(encoding="utf-8"))
    motion_unit = None
    if not static:
        motion_path = source.with_suffix(".soda") if motion is None else Path(motion).expanduser()
        if not motion_path.is_absolute():
            motion_path = source.parent / motion_path
        if motion_path.suffix.lower() != ".soda":
            raise ValueError("motion must be a .soda file")
        if motion is not None or motion_path.exists():
            motion_path = motion_path.resolve()
            motion_unit = SourceUnit(str(motion_path), motion_path.read_text(encoding="utf-8"))
    return _compile(content, motion_unit, source.parent)


def compile_text(
    markdown: str, *, motion: str | None = None, base_dir: str | Path | None = None
) -> Deck:
    """Compile strings; base_dir anchors assets and themes. No file is auto-loaded."""
    base = Path(base_dir or Path.cwd()).expanduser().resolve()
    content = SourceUnit(str(base / "deck.md"), markdown)
    animation = SourceUnit(str(base / "deck.soda"), motion) if motion is not None else None
    return _compile(content, animation, base)


def export_html(
    deck: Deck,
    output: str | Path,
    *,
    theme: str | Path | Theme | None = None,
    portable: bool = True,
) -> Path:
    """Export a single shareable HTML by default; theme changes do not mutate deck.

    ``portable=False`` emits HTML with a sibling assets/ directory. A custom
    theme JSON path is relative to the deck's base_dir. Output is relative to
    the caller's current directory. Existing output files are overwritten.
    """
    from soda.html.render import export_html as render_to_file

    selected = deck.theme if theme is None else (
        theme if isinstance(theme, Theme) else resolve_theme(theme, base_dir=deck.base_dir)
    )
    return render_to_file(
        deck.program, output, single_file=portable, theme=selected, timeline=deck.timeline
    )
