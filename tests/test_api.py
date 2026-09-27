import base64
import json
from pathlib import Path

import pytest

from soda import SodaError, compile_deck, compile_text, export_html
from soda.cli import main

CONTENT = "## 结果 {#result}\n观察。 {#finding}\n"
MOTION = "motion result { finding.fade_in(duration = 400ms); }"


def test_file_api_discovers_sibling_and_static_is_a_complete_alternative(tmp_path):
    source = tmp_path / "deck.md"
    source.write_text(CONTENT)
    source.with_suffix(".soda").write_text(MOTION)
    assert compile_deck(source).timeline.clips[0].end == 0.4
    assert compile_deck(source, static=True).timeline.clips == ()
    source.with_suffix(".soda").unlink()
    assert compile_deck(source).timeline.clips == ()


def test_explicit_motion_is_relative_to_markdown_and_missing_is_an_error(tmp_path, monkeypatch):
    source = tmp_path / "talk" / "deck.md"
    source.parent.mkdir()
    source.write_text(CONTENT)
    (source.parent / "custom.soda").write_text(MOTION)
    monkeypatch.chdir(tmp_path)
    assert compile_deck(source, motion="custom.soda").timeline.clips[0].target == "finding"
    with pytest.raises(FileNotFoundError):
        compile_deck(source, motion="missing.soda")
    with pytest.raises(ValueError, match="static=True"):
        compile_deck(source, static=True, motion="custom.soda")
    with pytest.raises(ValueError, match=".soda"):
        compile_deck(source, motion="custom.zsl")


def test_text_api_never_discovers_unrequested_motion(tmp_path):
    (tmp_path / "deck.soda").write_text("invalid motion")
    assert compile_text(CONTENT, base_dir=tmp_path).timeline.clips == ()
    deck = compile_text(CONTENT, motion=MOTION, base_dir=tmp_path)
    assert deck.timeline.clips[0].end == 0.4


def test_compilation_checks_assets_ids_and_timeline_conflicts(tmp_path):
    with pytest.raises(ValueError, match="missing local assets"):
        compile_text("## 结果\n![图](missing.png)\n", base_dir=tmp_path)
    with pytest.raises(SodaError):
        compile_text(CONTENT, motion="motion result { missing.fade_in(); }")
    with pytest.raises(ValueError, match="overlapping transform clips"):
        compile_text(CONTENT, motion="""motion result {
            parallel {
                finding.move(by = vec2(20, 0));
                finding.scale(by = 2);
            }
        }""")


def test_assets_and_project_theme_survive_change_of_working_directory(tmp_path, monkeypatch):
    project = tmp_path / "talk"
    project.mkdir()
    themes = project / "themes"
    themes.mkdir()
    logo = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="5" height="5"/></svg>'
    (themes / "logo.svg").write_bytes(logo)
    (themes / "lab.json").write_text(json.dumps({
        "extends": "nju", "name": "实验室", "primary": "#123456",
        "brand_logo": "logo.svg", "brand_label": "实验室", "logo_width": "80px",
    }))
    chart = '<svg xmlns="http://www.w3.org/2000/svg"><path stroke="var(--soda-primary)"/></svg>'
    (project / "curve.svg").write_text(chart)
    content = "---\ntheme: themes/lab.json\n---\n## 结果\n![图](curve.svg)\n"
    deck = compile_text(content, base_dir=project)
    monkeypatch.chdir(tmp_path)
    output = export_html(deck, "dist/deck.html")
    html = output.read_text()
    assert "--soda-primary:#123456" in html
    assert base64.b64encode(logo).decode() in html
    assert base64.b64encode(chart.replace("var(--soda-primary)", "#123456").encode()).decode() in html
    assert not (output.parent / "assets").exists()
    assert deck.base_dir == project


def test_export_override_is_reusable_and_does_not_mutate_compiled_deck(tmp_path):
    deck = compile_text(CONTENT, motion=MOTION)
    initial = deck.timeline
    ipads = export_html(deck, tmp_path / "ipads.html", theme="ipads").read_text()
    default = export_html(deck, tmp_path / "default.html").read_text()
    assert 'class="theme-ipads layout-academic"' in ipads
    assert 'class="theme-nju layout-academic"' in default
    assert deck.theme.id == "nju"
    assert deck.timeline == initial


def test_quickstart_is_usable_without_external_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")
    monkeypatch.setenv("SODA_TYPST", "/missing/typst")
    monkeypatch.setenv("SODA_ESBUILD", "/missing/esbuild")
    source = Path(__file__).resolve().parents[1] / "examples/quickstart/deck.md"
    deck = compile_deck(source)
    assert len(deck.program.slides) == 4
    output = export_html(deck, tmp_path / "quickstart.html")
    assert 'id="soda-runtime"' in output.read_text()
    assert "Copyright (c) 2026 Zanim contributors" in output.read_text()
    # Even a formula only needs Typst during rendering, not during compilation.
    compile_text("## 公式\n$$\nx^2\n$$\n")


def test_web_export_keeps_local_assets_next_to_html(tmp_path):
    (tmp_path / "image.png").write_bytes(b"image-content")
    deck = compile_text("## 图\n![图](image.png)\n", base_dir=tmp_path)
    output = export_html(deck, tmp_path / "web/index.html", portable=False)
    assets = list((output.parent / "assets").glob("*.png"))
    assert len(assets) == 1
    assert assets[0].read_bytes() == b"image-content"


def test_cli_reports_source_context_without_a_traceback(tmp_path, capsys):
    source = tmp_path / "deck.md"
    source.write_text(CONTENT)
    source.with_suffix(".soda").write_text("motion result { missing.fade_in(); }")
    assert main(["check", str(source)]) == 1
    error = capsys.readouterr().err
    assert "deck.soda:1:" in error
    assert "missing" in error
    assert "Traceback" not in error
    assert main(["html", str(source), "--static", "-o", str(tmp_path / "static.html")]) == 0
