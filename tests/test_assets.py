from pathlib import Path

import pytest

from soda.compiler.project import SourceUnit, compile_project
from soda.html.assets import resolve_asset_reference
from soda.html.render import export_html, render_html


def test_relative_assets_are_resolved_from_each_zmd_and_exported(tmp_path: Path):
    chapter = tmp_path / "chapter"
    media = chapter / "media"
    media.mkdir(parents=True)
    (media / "image.png").write_bytes(b"fake-png")
    (media / "clip.mp4").write_bytes(b"fake-mp4")
    (media / "poster.jpg").write_bytes(b"fake-jpg")
    source_path = chapter / "deck.md"
    source = '''# Media {#media}
![Result](media/image.png) {#image fit=cover}

@video media/clip.mp4 {#video poster=media/poster.jpg controls=true muted=true loop=false}
'''
    source_path.write_text(source, encoding="utf-8")
    project = compile_project([SourceUnit(str(source_path), source)], [])

    output = tmp_path / "dist" / "deck.html"
    export_html(project, output)
    html = output.read_text(encoding="utf-8")

    exported = sorted((output.parent / "assets").iterdir())
    assert len(exported) == 3
    assert all(path.name.split("-", 1)[0].isalnum() for path in exported)
    assert "media/image.png" not in html
    assert "media/clip.mp4" not in html
    assert "media/poster.jpg" not in html
    assert "assets/" in html
    assert "<video" in html
    assert "controls" in html
    assert "muted" in html
    assert " loop " not in html
    assert "data-fit='cover'" in html


def test_https_assets_are_preserved_without_export(tmp_path: Path):
    source = '''# Remote {#remote}
![Remote](https://example.com/image.png) {#image}

@video "https://cdn.example.com/video.mp4?token=abc" {#video controls=false}
'''
    project = compile_project([SourceUnit(str(tmp_path / "deck.md"), source)], [])
    output = tmp_path / "deck.html"
    export_html(project, output)
    html = output.read_text(encoding="utf-8")
    assert "https://example.com/image.png" in html
    assert "https://cdn.example.com/video.mp4?token=abc" in html
    assert not (tmp_path / "assets").exists()
    video = html.split("<video", 1)[1].split("></video>", 1)[0]
    assert "controls" not in video


def test_video_is_a_typed_presentation_object_and_supports_motion():
    content = SourceUnit(
        "deck.md",
        '# Demo {#demo}\n@video https://example.com/demo.mp4 {#clip controls=true}\n',
    )
    motion = SourceUnit("motion.soda", "motion demo { clip.fade_in(duration = 200ms); }")
    project = compile_project([content], [motion])
    assert project.slides[0].root.children[1].kind == "video"
    assert 'data-kind="video"' in render_html(project)


def test_asset_reference_rejects_nonportable_schemes_and_absolute_paths(tmp_path: Path):
    with pytest.raises(ValueError, match="unsupported asset URL scheme"):
        resolve_asset_reference("http://example.com/a.png", str(tmp_path / "deck.md"))
    with pytest.raises(ValueError, match="absolute local asset paths"):
        resolve_asset_reference("/tmp/a.png", str(tmp_path / "deck.md"))


def test_boolean_media_attributes_are_parsed_as_booleans():
    project = compile_project(
        [SourceUnit("deck.md", '# Demo {#demo}\n@video https://example.com/a.mp4 {#clip controls=false autoplay=true muted=true}\n')],
        [],
    )
    video = project.slides[0].root.children[1]
    assert video.props["controls"] is False
    assert video.props["autoplay"] is True
    assert video.props["muted"] is True


def test_asset_manifest_reports_missing_and_remote(tmp_path: Path):
    from soda.html.assets import collect_asset_references, validate_asset_references

    source_path = tmp_path / "nested" / "deck.md"
    source_path.parent.mkdir()
    source = '''# Assets {#assets}
![Missing](media/missing.png) {#missing}

@video https://example.com/video.mp4 {#remote}
'''
    project = compile_project([SourceUnit(str(source_path), source)], [])
    entries = collect_asset_references(project)
    assert [(entry.object_id, entry.remote, entry.exists) for entry in entries] == [
        ("missing", False, False),
        ("remote", True, None),
    ]
    with pytest.raises(ValueError, match="missing local assets"):
        validate_asset_references(project)


def test_quoted_media_attribute_values_can_contain_spaces(tmp_path: Path):
    media = tmp_path / "media"
    media.mkdir()
    (media / "first frame.jpg").write_bytes(b"poster")
    (media / "demo clip.mp4").write_bytes(b"video")
    source_path = tmp_path / "deck.md"
    source = '''# Demo {#demo}
@video "media/demo clip.mp4" {#clip poster="media/first frame.jpg" label="Demo clip" controls=true}
'''
    project = compile_project([SourceUnit(str(source_path), source)], [])
    video = project.slides[0].root.children[1]
    assert video.props["src"] == "media/demo clip.mp4"
    assert video.props["poster"] == "media/first frame.jpg"
    assert video.props["label"] == "Demo clip"
    output = tmp_path / "out" / "deck.html"
    export_html(project, output)
    html = output.read_text(encoding="utf-8")
    assert "aria-label='Demo clip'" in html
