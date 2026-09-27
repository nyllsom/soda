from pathlib import Path

from soda.compiler.content import parse_content
from soda.compiler.project import SourceUnit, compile_paths, compile_project
from soda.html.render import render_html


def test_markdown_table_becomes_addressable_rows_and_cells():
    doc = parse_content("""## Results {#results_slide}
| Method | Acc | FPS |
|:---|---:|---:|
| Baseline | 82.1 | 120 |
| **Ours** | **87.4** | 118 |
{#bench}
""")
    slide = doc.slides[0]
    table = slide.objects["bench"]
    assert table.kind == "table"
    assert table.props["align"] == ["left", "right", "right"]
    assert slide.objects["bench_header_c1"].props["text"] == "Method"
    assert slide.objects["bench_r2"].kind == "table-row"
    assert slide.objects["bench_r2_c2"].props["text"] == "**87.4**"

    motion = SourceUnit(
        "deck.soda",
        "motion results_slide { bench_r2.fade_in(duration = 100ms); bench_r2_c2.scale(by = 1.05, duration = 100ms); }",
    )
    project = compile_project([SourceUnit("deck.md", """## Results {#results_slide}
| Method | Acc |
|---|---:|
| Base | 82.1 |
| Ours | 87.4 |
{#bench}
""")], [motion])
    assert project.motions[0].slide == "results_slide"


def test_chart_and_diagram_create_addressable_child_objects():
    content = SourceUnit("deck.md", """## Curves {#curves}
@chart data.csv {#training type=line x=step y=ours,baseline}

## Pipeline {#pipeline_slide}
@diagram {#pipeline direction=LR}
input["Input"] -> encoder["Encoder"] -> policy["Policy"]
@enddiagram
""")
    project = compile_project([content], [SourceUnit("deck.soda", """motion curves { training_ours.fade_in(duration = 100ms); }
motion pipeline_slide { encoder.scale(by = 1.05, duration = 100ms); pipeline_edge_1.fade_in(duration = 100ms); }
""")])
    curves = project.slides[0]
    ids = {child.id for child in curves.root.children}
    assert "training" in ids
    pipeline = project.slides[1]
    object_ids = set()
    def visit(node):
        object_ids.add(node.id)
        for child in node.children:
            visit(child)
    visit(pipeline.root)
    assert {"pipeline", "input", "encoder", "policy", "pipeline_edge_1"} <= object_ids


def test_academic_html_renders_csv_chart_bibtex_table_and_references(tmp_path: Path):
    (tmp_path / "data.csv").write_text("step,ours,baseline\n0,0.4,0.3\n1,0.7,0.5\n", encoding="utf-8")
    (tmp_path / "refs.bib").write_text("""@inproceedings{vaswani2017attention,
  author = {Ashish Vaswani and Noam Shazeer and Niki Parmar},
  title = {Attention Is All You Need},
  booktitle = {NeurIPS},
  year = {2017}
}
""", encoding="utf-8")
    md = tmp_path / "deck.md"
    md.write_text("""---
deck: Academic
bibliography: refs.bib
---
## Results {#results}
Prior work [@vaswani2017attention].

| Method | Acc |
|---|---:|
| Ours | **87.4** |
{#table}

@chart data.csv {#training type=line x=step y=ours,baseline title="Training"}

@diagram {#pipeline}
input["Input"] -> model["Model"]
@enddiagram

## References {#refs_slide}
@references {#refs}
""", encoding="utf-8")
    soda = tmp_path / "deck.soda"
    soda.write_text("""motion results {
  table_r1.fade_in(duration = 100ms);
  training_ours.fade_in(duration = 100ms);
  model.scale(by = 1.03, duration = 100ms);
}
""", encoding="utf-8")
    program = compile_paths([str(md), str(soda)])
    html = render_html(program)
    assert "Vaswani et al., 2017" in html
    assert "Attention Is All You Need" in html
    assert 'data-object="training_ours"' in html
    assert 'data-object="model"' in html
    assert "kind-table" in html
    assert "chart-legend" in html


def test_image_label_and_caption_support_subfigure_style():
    content = SourceUnit(
        "deck.md",
        "## Figure {#figure}\n![raw alt](https://example.com/a.png) {#panel_a label=a caption=\"Input image\"}\n",
    )
    html = render_html(compile_project([content], []))
    assert "(a) Input image" in html
    assert "alt='raw alt'" in html


def test_check_rejects_missing_chart_columns_and_unknown_citations(tmp_path: Path):
    from soda.html.assets import validate_asset_references

    (tmp_path / "data.csv").write_text("step,ours\n0,1\n", encoding="utf-8")
    md = tmp_path / "chart.md"
    md.write_text("## Chart {#chart}\n@chart data.csv {#plot type=line x=step y=missing}\n", encoding="utf-8")
    program = compile_paths([str(md)])
    import pytest
    with pytest.raises(ValueError, match="missing columns: missing"):
        validate_asset_references(program)

    (tmp_path / "refs.bib").write_text("@article{known, author={A Author}, title={T}, year={2026}}\n", encoding="utf-8")
    cite = tmp_path / "cite.md"
    cite.write_text("---\nbibliography: refs.bib\n---\n## Cite {#cite}\nUnknown [@missing].\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown bibliography keys: missing"):
        validate_asset_references(compile_paths([str(cite)]))
