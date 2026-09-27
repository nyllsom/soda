from pathlib import Path

from soda.compiler.content import parse_content
from soda.compiler.project import SourceUnit, compile_project
from soda.compiler.timeline_ir import compile_timeline
from soda.html.assets import collect_asset_references
from soda.html.render import export_html, render_html


def _objects(source: str):
    slide = parse_content(source, path="deck.md").slides[0]
    return {obj.id: obj for obj in slide.objects.values()}


def test_embed_infers_common_research_asset_types():
    objects = _objects(
        """# Demo {#demo}
@embed figure.typ {#figure}
@embed scene.js {#scene}
@embed plot.svg {#plot}
@embed demo.mp4 {#video}
@embed paper.pdf {#paper}
@embed source.py {#source}
"""
    )
    assert objects["figure"].kind == "typst"
    assert objects["scene"].kind == "zanim"
    assert objects["plot"].kind == "image"
    assert objects["video"].kind == "video"
    assert objects["paper"].kind == "pdf"
    assert objects["source"].kind == "code-file"


def test_embed_explicit_type_handles_ambiguous_sources():
    objects = _objects(
        """# Demo {#demo}
@embed https://example.com/demo {#web type=web}
@embed script.js {#source type=code}
"""
    )
    assert objects["web"].kind == "web"
    assert objects["source"].kind == "code-file"


def test_markdown_only_deck_uses_direct_cut_navigation():
    project = compile_project(
        [SourceUnit("deck.md", "# A {#a}\nA.\n# B {#b}\nB.\n# C {#c}\nC.\n")],
        [],
    )
    timeline = compile_timeline(project)
    assert not timeline.clips
    assert [item.kind for item in timeline.transitions] == ["cut", "cut"]
    assert all(item.end - item.start <= 0.001001 for item in timeline.transitions)


def test_external_code_reference_is_inlined_and_sliceable(tmp_path: Path):
    code = tmp_path / "policy.py"
    code.write_text("a = 1\nb = 2\nc = a + b\nprint(c)\n", encoding="utf-8")
    md = tmp_path / "deck.md"
    md.write_text(
        "# Code {#code_slide}\n@code policy.py {#policy lines=2:3 max_lines=4}\n",
        encoding="utf-8",
    )
    html = render_html(compile_project([SourceUnit(str(md), md.read_text())], []))
    assert "policy.py · L2–3" in html
    code_html = html.split("policy.py · L2–3", 1)[1].split("</div></div></article>", 1)[0]
    assert (
        '>b</span><span class="tok tok-plain"> = </span><span class="tok tok-number">2</span>'
        in code_html
    )
    assert (
        '>c</span><span class="tok tok-plain"> = </span><span class="tok tok-plain">a</span>'
        in code_html
    )
    assert (
        '>a</span><span class="tok tok-plain"> = </span><span class="tok tok-number">1</span>'
        not in code_html
    )
    assert 'data-kind="code-file"' in html


def test_typst_reference_renders_as_inline_vector_svg(tmp_path: Path):
    figure = tmp_path / "pipeline.typ"
    figure.write_text(
        "#set page(width: auto, height: auto, margin: 4pt, fill: none)\n"
        '#rect(width: 120pt, height: 50pt, radius: 4pt, fill: rgb("eeeeff"))[Pipeline]\n',
        encoding="utf-8",
    )
    md = tmp_path / "deck.md"
    md.write_text(
        '# Figure {#figure_slide}\n@typst pipeline.typ {#pipeline label="Pipeline"}\n',
        encoding="utf-8",
    )
    html = render_html(compile_project([SourceUnit(str(md), md.read_text())], []))
    assert 'data-kind="typst"' in html
    assert 'class="typst-svg"' in html
    assert "<svg" in html
    assert "pipeline.typ" not in html


def test_pdf_and_web_references_render_as_presentation_objects(tmp_path: Path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    md = tmp_path / "deck.md"
    md.write_text(
        """# References {#references}
@pdf paper.pdf {#paper page=2 label="Paper"}
@web https://example.com/demo {#live label="Live demo"}
""",
        encoding="utf-8",
    )
    out = tmp_path / "deck.html"
    program = compile_project([SourceUnit(str(md), md.read_text())], [])
    export_html(program, out)
    roles = {(entry.object_id, entry.role) for entry in collect_asset_references(program)}
    assert ("paper", "pdf") in roles
    assert ("live", "web") in roles
    html = out.read_text(encoding="utf-8")
    assert 'data-kind="pdf"' in html
    assert "#page=2&amp;toolbar=0" in html
    assert 'data-kind="web"' in html
    assert 'src="https://example.com/demo"' in html



def test_referenced_code_remains_a_typed_code_object_for_optional_soda(tmp_path: Path):
    code = tmp_path / "policy.py"
    code.write_text("print(1)\n", encoding="utf-8")
    md = SourceUnit(str(tmp_path / "deck.md"), "# Demo {#demo}\n@code policy.py {#policy}\n")
    motion = SourceUnit(
        str(tmp_path / "deck.soda"), "motion demo { policy.focus(line = 1, duration = 100ms); }"
    )
    program = compile_project([md], [motion])
    assert program.motions[0].slide == "demo"
