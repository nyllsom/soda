from pathlib import Path

from soda.compiler.motion_api import SUPPORTED_MOTION_METHODS, TRANSITION_KINDS
from soda.compiler.project import compile_paths
from soda.compiler.timeline_ir import compile_timeline
from soda.html.assets import validate_asset_references


def test_showcase_covers_public_objects_motion_and_flow():
    """Keep the short teaching deck in step with the actual compiler contract."""
    demo = Path(__file__).resolve().parents[1] / "examples" / "showcase" / "deck.md"
    program = compile_paths([str(demo), str(demo.with_suffix(".soda"))])
    validate_asset_references(program)
    timeline = compile_timeline(program)
    assert len(program.slides) == 14
    assert {clip.op for clip in timeline.clips} == set(SUPPORTED_MOTION_METHODS)
    assert {transition.kind for transition in timeline.transitions} == set(TRANSITION_KINDS)

    def kinds(node):
        return {node.kind}.union(*(kinds(child) for child in node.children))

    rendered = set().union(*(kinds(slide.root) for slide in program.slides))
    assert {
        "heading", "paragraph", "list", "quote", "rule", "region", "columns", "rows",
        "grid", "stack", "overlay", "table", "table-row", "table-cell", "math", "code",
        "code-file", "image", "video", "typst", "pdf", "web", "zanim", "slide-ref",
        "chart", "chart-series", "diagram", "diagram-node", "diagram-edge",
        "citation", "references",
    } <= rendered

    # The same content must also form a useful static, cut-only presentation.
    static = compile_timeline(compile_paths([str(demo)]))
    assert not static.clips
    assert all(transition.kind == "cut" for transition in static.transitions)
