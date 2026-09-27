from pathlib import Path

import pytest

from soda.cli import main


@pytest.mark.parametrize("command", [[], ["compile"], ["html"]])
def test_compile_forms_discover_motion_and_write_next_to_markdown(tmp_path, monkeypatch, command):
    talk = tmp_path / "我的 演示"
    talk.mkdir()
    source = talk / "deck.md"
    source.write_text("## 结果 {#result}\n结论。 {#finding}\n")
    source.with_suffix(".soda").write_text("motion result { finding.fade_in(duration = 400ms); }")
    monkeypatch.chdir(tmp_path)
    assert main([*command, str(source)]) == 0
    html = source.with_suffix(".html").read_text()
    assert '"end": 0.4' in html
    assert 'theme-nju' in html


def test_explicit_motion_is_relative_to_cli_working_directory(tmp_path, monkeypatch):
    (tmp_path / "slides").mkdir()
    (tmp_path / "slides/deck.md").write_text("## 结果 {#result}\n结论。 {#finding}\n")
    (tmp_path / "slides/deck.soda").write_text("bad default motion")
    (tmp_path / "custom.soda").write_text("motion result { finding.fade_in(duration = 250ms); }")
    monkeypatch.chdir(tmp_path)
    assert main(["slides/deck.md", "custom.soda", "-o", "输出/demo.html", "--theme", "ipads"]) == 0
    html = (tmp_path / "输出/demo.html").read_text()
    assert '"end": 0.25' in html
    assert 'theme-ipads' in html
    assert not (tmp_path / "slides/deck.html").exists()
    assert main(["check", "slides/deck.md", "custom.soda"]) == 0


@pytest.mark.parametrize("output", ["deck.md", "deck.soda"])
def test_export_cannot_overwrite_source_files(tmp_path, monkeypatch, output):
    (tmp_path / "deck.md").write_text("## 结果 {#result}\n结论。\n")
    (tmp_path / "deck.soda").write_text("motion result {}")
    monkeypatch.chdir(tmp_path)
    before = Path(output).read_bytes()
    assert main(["deck.md", "-o", output]) == 1
    assert Path(output).read_bytes() == before


def test_static_ignores_invalid_sibling_but_rejects_explicit_motion(tmp_path):
    source = tmp_path / "deck.md"
    source.write_text("## 结果\n结论。\n")
    source.with_suffix(".soda").write_text("bad motion")
    assert main([str(source), "--static"]) == 0
    source.with_suffix(".html").unlink()
    assert main([str(source), str(source.with_suffix('.soda')), "--static"]) == 1
    assert not source.with_suffix(".html").exists()
