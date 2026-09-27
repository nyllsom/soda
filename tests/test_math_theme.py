from types import SimpleNamespace

import soda.html.render as static_html
from soda.compiler.project import SourceUnit, compile_project


def test_ipads_theme_renders_brand_cover_and_vector_math(monkeypatch):
    monkeypatch.setattr(
        static_html,
        "math_svg_asset",
        lambda source, **kwargs: SimpleNamespace(
            data_uri="data:image/svg+xml;base64,PHN2Zy8+",
            svg='<svg width="10pt" height="5pt"><g></g></svg>',
            width_pt=10.0,
            height_pt=5.0,
            aspect_ratio=2.0,
        ),
    )
    content = SourceUnit(
        "deck.md",
        '''---
theme: ipads
---
# IPADS Math {#cover}
Inline $x^2$ formula.

## Detail {#detail}
$$
integral_0^1 x^2 dif x = 1/3
$$ {#equation font_size=40 color=primary}
''',
    )
    project = compile_project([content], [])
    html = static_html.render_html(project)

    assert 'class="theme-ipads layout-academic"' in html
    assert "soda-cover" in html
    assert "brand-logo" in html
    assert "data:image/png;base64," in html
    assert "math-svg" in html
    assert "inline-math" in html
    assert "--soda-primary:#2d4198" in html


def test_math_attributes_are_numeric_content_properties():
    content = SourceUnit(
        "deck.md",
        '''# Math {#math}
$$
x^2
$$ {#equation font_size=42 size=38}
''',
    )
    project = compile_project([content], [])
    equation = project.slides[0].root.children[1]
    assert equation.props["font_size"] == 42.0
    assert equation.props["size"] == 38.0


def test_math_create_keeps_fraction_rules_with_glyphs_and_highlight_is_typed(monkeypatch):
    monkeypatch.setattr(
        static_html,
        "math_svg_asset",
        lambda source, **kwargs: SimpleNamespace(
            data_uri="data:image/svg+xml;base64,PHN2Zy8+",
            svg='<svg width="20pt" height="10pt"><g id="glyph"><use xlink:href="#shape"/></g><path id="fraction-rule" d="M0 5H20"/><defs><symbol id="shape"/></defs></svg>',
            width_pt=20.0,
            height_pt=10.0,
            aspect_ratio=2.0,
        ),
    )
    content = SourceUnit("deck.md", """# Formula {#formula}
$$
x^2 + y^2
$$ {#eq align=left}
""")
    motion = SourceUnit("motion.soda", """motion formula {
    eq.create(duration = 500ms);
    eq.highlight(duration = 300ms);
}
""")
    html = static_html.render_html(compile_project([content], [motion]))
    assert '<svg class="math-svg"' in html
    assert 'formula-eq-glyph' in html
    assert 'formula-eq-fraction-rule' in html
    assert 'svg.style.opacity = String(mathReveal)' in html
    assert 'svg.math-svg > g' not in html
    assert 'math-align-left' in html
    assert 'motion-focus' in html


def test_math_focus_is_rejected_but_whole_formula_highlight_is_allowed():
    import pytest

    from soda.compiler.diagnostics import SemanticError

    content = SourceUnit("deck.md", """# Math {#s}
$$
x^2
$$ {#eq}
""")
    compile_project([content], [SourceUnit("ok.soda", "motion s { eq.highlight(duration = 100ms); }")])
    with pytest.raises(SemanticError, match=r"has no temporal method 'focus'"):
        compile_project([content], [SourceUnit("bad.soda", "motion s { eq.focus(duration = 100ms); }")])
    with pytest.raises(SemanticError, match=r"unknown highlight\(\) option 'line'"):
        compile_project([content], [SourceUnit("bad2.soda", "motion s { eq.highlight(line = 1); }")])
