import base64
from html.parser import HTMLParser
from pathlib import Path

import pytest

from soda.cli import main
from soda.compiler.project import SourceUnit, compile_project
from soda.html.render import render_html
from soda.themes import resolve_theme


class BrandReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.labels = []
        self.body_classes = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "body":
            self.body_classes.update(attrs.get("class", "").split())
        if attrs.get("role") == "img" and "brand" in attrs.get("class", ""):
            self.labels.append(attrs["aria-label"])


@pytest.mark.parametrize("name,layout,labels", [
    ("academic", "academic", []),
        ("ipads", "academic", [
        "IPADS — Institute of Parallel and Distributed Systems", "Shanghai Jiao Tong University",
    ]),
])
def test_declarative_themes_render_their_own_brand_and_shared_layout(name, layout, labels):
    program = compile_project([SourceUnit("deck.md", f"---\ntheme: {name}\n---\n# Research\n")], [])
    reader = BrandReader()
    reader.feed(render_html(program))
    assert reader.body_classes == {f"theme-{name}", f"layout-{layout}"}
    assert reader.labels == labels


def test_ipads_logo_payloads_are_original_embedded_assets():
    assets = Path(__file__).resolve().parents[1] / "src/soda/themes/assets"
    theme = resolve_theme(" IPADS ")
    for payload, filename in [(theme.brand_logo, "ipads-logo.png"),
                              (theme.affiliation_logo, "sjtu-logo.png")]:
        assert payload.startswith("data:image/png;base64,")
        assert base64.b64decode(payload.split(",", 1)[1]) == (assets / filename).read_bytes()


def test_export_theme_override_keeps_source_and_timeline(tmp_path):
    source = tmp_path / "deck.md"
    original = "---\ntheme: academic\n---\n# Research {#cover}\nResult. {#result}\n"
    source.write_text(original)
    source.with_suffix(".soda").write_text("motion cover { result.fade_in(duration = 300ms); }")
    target = tmp_path / "demo.html"
    assert main(["html", str(source), "--theme", "ipads", "--target", "portable",
                 "-o", str(target)]) == 0
    html = target.read_text()
    assert 'class="theme-ipads layout-academic"' in html
    assert '"end": 0.3' in html
    assert "--soda-primary:#2d4198" in html
    assert source.read_text() == original


def test_unknown_theme_reports_available_definitions():
    with pytest.raises(ValueError, match="available themes: academic, ipads"):
        resolve_theme("missing")
