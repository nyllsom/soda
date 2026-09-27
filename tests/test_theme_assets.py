import base64
import json
import shutil
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

import pytest

import soda.themes as themes
from soda.cli import main
from soda.compiler.project import compile_paths
from soda.compiler.timeline_ir import compile_timeline
from soda.html.render import export_html

DEMO_ASSETS = Path(__file__).resolve().parents[1] / "examples/showcase/assets"
SVG = "{http://www.w3.org/2000/svg}"


class Images(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.sources = {}
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            attrs = dict(attrs)
            self.sources[attrs["alt"]] = attrs["src"]


def image_bytes(src, output):
    if src.startswith("data:"):
        return base64.b64decode(src.split(",", 1)[1])
    return (output.parent / src).read_bytes()


@pytest.mark.parametrize("theme_name", ["ipads", "academic"])
@pytest.mark.parametrize("portable", [False, True])
def test_real_demo_assets_follow_one_theme_in_both_export_targets(tmp_path, theme_name, portable):
    for filename in ("curve.svg", "axes.svg", "pipeline.typ"):
        shutil.copyfile(DEMO_ASSETS / filename, tmp_path / filename)
    imported = b'<svg xmlns="http://www.w3.org/2000/svg"><path fill="#6f145f"/></svg>'
    (tmp_path / "imported.svg").write_bytes(imported)
    md = tmp_path / "deck.md"
    md.write_text(f"""---
theme: {theme_name}
---
## Theme {{#slide}}
![Curve](curve.svg) {{#curve}}
![Axes](axes.svg)
![Imported](imported.svg)
@typst pipeline.typ
""")
    motion = tmp_path / "deck.soda"
    motion.write_text("motion slide { curve.fade_in(duration = 300ms); }")
    originals = {p: p.read_bytes() for p in tmp_path.iterdir()}
    program = compile_paths([str(md), str(motion)])
    timeline = compile_timeline(program)
    output = tmp_path / "out" / "demo.html"
    export_html(program, output, single_file=portable)
    html = output.read_text()
    images = Images(html).sources
    theme = themes.resolve_theme(theme_name)
    curve_bytes = image_bytes(images["Curve"], output)
    curve = ET.fromstring(curve_bytes)
    assert curve.find(f"{SVG}path").attrib["stroke"] == theme.primary
    assert curve.find(f"{SVG}circle").attrib["fill"] == theme.primary
    assert b"var(--soda-" not in curve_bytes
    axes = ET.fromstring(image_bytes(images["Axes"], output))
    assert [p.attrib["stroke"] for p in axes] == [
        theme.border, themes.theme_tokens(theme)["table-divider"],
    ]
    assert image_bytes(images["Imported"], output) == imported
    typst = html.split('class="typst-svg"', 1)[1].split("</svg>", 1)[0]
    assert f'fill="{theme.primary}"' in typst
    assert f'fill="{theme.surface}"' in typst
    assert compile_timeline(program) == timeline
    assert all(p.read_bytes() == content for p, content in originals.items())


def test_new_brand_only_needs_a_json_definition(tmp_path):
    theme_root = tmp_path / "themes"
    theme_root.mkdir()
    definition = {"extends": "ipads", "name": "Custom", "primary": "#123456"}
    (theme_root / "custom.json").write_text(json.dumps(definition))
    shutil.copyfile(DEMO_ASSETS / "curve.svg", tmp_path / "curve.svg")
    md = tmp_path / "deck.md"
    md.write_text("## Theme\n![Curve](curve.svg)\n")
    output = tmp_path / "demo.html"
    assert main(["html", str(md), "--theme", "themes/custom.json", "--target", "portable",
                 "-o", str(output)]) == 0
    html = output.read_text()
    curve = ET.fromstring(image_bytes(Images(html).sources["Curve"], output))
    assert curve.find(f"{SVG}path").attrib["stroke"] == "#123456"
    assert "--soda-primary:#123456" in html
    assert "--soda-code-keyword:#123456" in html
    assert "--soda-code-highlight:#123456" in html


@pytest.mark.parametrize("value,message", [
    ("$missing", "unknown token reference"),
    ("$code_keyword", "cyclic token reference"),
])
def test_invalid_theme_references_report_the_definition(tmp_path, monkeypatch, value, message):
    definition = json.loads((themes._THEME_ROOT / "ipads.json").read_text())
    definition["primary"] = value
    (tmp_path / "broken.json").write_text(json.dumps(definition))
    monkeypatch.setattr(themes, "_THEME_ROOT", tmp_path)
    with pytest.raises(ValueError, match=f"{message}.*broken"):
        themes.resolve_theme("broken")


def test_svg_token_typo_fails_export_with_asset_context(tmp_path):
    (tmp_path / "curve.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><path stroke="var(--soda-priamry)"/></svg>'
    )
    md = tmp_path / "deck.md"
    md.write_text("## Theme\n![Curve](curve.svg)\n")
    with pytest.raises(ValueError, match=r"unknown SVG theme token --soda-priamry.*curve.svg"):
        export_html(compile_paths([str(md)]), tmp_path / "demo.html", single_file=True)
