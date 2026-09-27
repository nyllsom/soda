from soda.compiler.project import SourceUnit, compile_project
from soda.compiler.timeline_ir import compile_timeline
from soda.html.code import render_code, tokenize
from soda.html.render import render_html


def test_code_tokenizer_supports_python_and_zig():
    py = tokenize("def f(x):\n    return x + 2 # value", "python")
    assert any(segment.kind == "keyword" and segment.text == "def" for segment in py[0])
    assert any(segment.kind == "function" and segment.text == "f" for segment in py[0])
    assert any(segment.kind == "number" and segment.text == "2" for segment in py[1])
    assert any(segment.kind == "comment" for segment in py[1])

    zig = tokenize("pub fn main() void { const x = 1; }", "zig")[0]
    assert any(segment.kind == "keyword" and segment.text == "pub" for segment in zig)
    assert any(segment.kind == "keyword" and segment.text == "fn" for segment in zig)


def test_code_html_has_addressable_lines_and_tokens():
    html = render_code("const x = 1;\n// note", "zig", line_numbers=True, max_lines=4)
    assert 'data-line="1"' in html
    assert 'class="code-ln"' in html
    assert 'tok-keyword' in html
    assert 'tok-comment' in html
    assert 'data-max-lines="4"' in html


def test_code_focus_range_is_preserved_in_timeline_and_runtime():
    content = SourceUnit("deck.md", """# Code {#code_slide}
```python {#code}
def add(a, b):
    value = a + b
    return value
```
""")
    motion = SourceUnit("motion.soda", """motion code_slide {
    step "focus" { code.focus(range = [2, 3], duration = 300ms); }
    step "pulse" { code.highlight(line = 3, duration = 200ms); }
}
""")
    project = compile_project([content], [motion])
    timeline = compile_timeline(project)
    assert timeline.clips[0].args["range"] == [2, 3]
    assert timeline.clips[1].args["line"] == 3
    html = render_html(project)
    assert 'data-line="2"' in html
    assert 'code-focus-band' in html
    assert 'code-pulse-band' in html
    assert 'selectionGeometry' in html
    assert 'focusFromSelection' in html
    assert 'focusProgress' in html
    assert 'pulseProgress' in html
    assert 'selectionLabel' in html
    assert '--code-focus-highlight' not in html
    assert '--code-pulse-highlight' not in html
    assert 'code-active' not in html
    assert 'transition:opacity .14s' not in html


def test_code_focus_options_are_type_checked():
    import pytest

    from soda.compiler.diagnostics import SemanticError

    content = SourceUnit("deck.md", """# Code {#s}
```python {#code}
print(1)
```
""")
    bad = SourceUnit("bad.soda", 'motion s { code.focus(range = [1, "two"]); }')
    with pytest.raises(SemanticError, match="array element type"):
        compile_project([content], [bad])


def test_code_focus_does_not_dim_lines_unless_requested():
    plain = render_code("a\nb", "python")
    dimmed = render_code("a\nb", "python", dim_inactive=True)
    assert 'data-dim-inactive="false"' in plain
    assert 'data-dim-inactive="true"' in dimmed
    assert 'code-focus-band' in plain
    assert 'code-pulse-band' in plain
