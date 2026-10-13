import json
from pathlib import Path

import pytest

from soda.compiler.content import parse_content
from soda.compiler.diagnostics import ParseError
from soda.compiler.project import SourceUnit, compile_project
from soda.html.assets import collect_asset_references, validate_asset_references
from soda.html.render import export_html, render_html


def _notes_html(output: str, index: int = 0) -> str:
    marker = '<script type="application/json" id="soda-runtime">'
    payload = output.split(marker, 1)[1].split('</script>', 1)[0]
    return json.loads(payload)['pages'][index]['notes_html']


def test_notes_are_separate_from_slides_and_html_is_escaped():
    text = ('## A {#a}\nVisible.\n::: notes\n**Not a slide**\n'
            '<script>unsafe</script>\n::: \n## B {#b}\nBody.\n')
    doc = parse_content(text, path='deck.md')
    assert len(doc.slides) == 2
    assert '**Not a slide**' in doc.slides[0].root.props['speaker_notes']
    assert all('unsafe' not in str(o.props) for o in doc.slides[0].root.children)
    output = render_html(compile_project([SourceUnit('deck.md', text)], []))
    assert '<script>unsafe</script>' not in output
    assert '<script>unsafe<\\/script>' in output  # raw notes stored in runtime JSON
    assert '&lt;script&gt;unsafe&lt;/script&gt;' in output  # displayed as text
    assert '<strong>Not a slide</strong>' in _notes_html(output)


def test_notes_render_full_common_markdown_without_soda_extensions():
    source = '''## Demo
::: notes
Text **bold** and *italic*, ~~old~~ and `code`, [link](https://example.com).

- first
- second

1. one
2. two

> quoted

| Method | Score |
| :--- | ---: |
| **A** | 42 |

```python
# this is code, not a heading
@chart demo.csv
```
---
:::
'''
    output = render_html(compile_project([SourceUnit('deck.md', source)], []))
    rendered = _notes_html(output)
    for fragment in ('<strong>bold</strong>', '<em>italic</em>', '<s>old</s>',
                     '<code>code</code>', '<ul>', '<ol>', '<blockquote>',
                     '<table>', '<strong>A</strong>', '<pre><code class="language-python">', '<hr'):
        assert fragment in rendered, fragment
    assert 'rel="noopener noreferrer"' in rendered
    assert 'target="_blank"' in rendered
    assert '@chart demo.csv' in output


def test_markdown_notes_images_follow_export_asset_pipeline(tmp_path: Path):
    (tmp_path / 'picture.png').write_bytes(b'example image')
    source_path = tmp_path / 'deck.md'
    source = '## A\n::: notes\n![experiment](picture.png)\n:::\n'
    project = compile_project([SourceUnit(str(source_path), source)], [])
    references = collect_asset_references(project)
    assert len(references) == 1 and references[0].object_id == 'notes'
    assert references[0].role == 'image'
    validate_asset_references(project)
    output = tmp_path / 'dist' / 'deck.html'
    export_html(project, output)
    rendered = output.read_text(encoding='utf8')
    notes = _notes_html(rendered)
    assert '<img src="assets/' in notes
    assert 'alt="experiment"' in notes
    assert len(list((output.parent / 'assets').glob('*.png'))) == 1


@pytest.mark.parametrize('body, fragment', [
    ('# Title', 'Markdown headings'),
    ('## Title', 'Markdown headings'),
    ('Title\n-----', 'Markdown headings'),
    ('@chart data.csv', 'SODA directives'),
    ('@embed file.pdf', 'SODA directives'),
    ('something {#key cols=2}', 'SODA directives'),
    ('::: columns', 'nested ::: containers'),
])
def test_notes_forbid_heading_and_soda_syntax(body: str, fragment: str):
    with pytest.raises(ParseError, match=fragment) as caught:
        parse_content(f'## A\n::: notes\n{body}\n:::\n', path='deck.md')
    assert caught.value.diagnostic.span.line == 3


def test_colon_delimiter_in_notes_code_fence_does_not_close_block():
    source = '## First\n::: notes\n```md\n:::\n## not a slide\n```\n:::\n## Second\nBody\n'
    doc = parse_content(source, path='deck.md')
    assert len(doc.slides) == 2
    assert '## not a slide' in doc.slides[0].root.props['speaker_notes']
    assert ':::\n## not a slide' in _notes_html(
        render_html(compile_project([SourceUnit('deck.md', source)], []))
    )


def test_notes_allow_directive_examples_as_code():
    source = '## A\n::: notes\n```soda\n@embed demo.js\n::: columns\n# heading\n```\n:::\n'
    doc = parse_content(source, path='deck.md')
    assert len(doc.slides) == 1
    assert '@embed demo.js' in _notes_html(render_html(compile_project([SourceUnit('deck.md', source)], [])))


def test_notes_markers_in_code_are_literal():
    doc = parse_content('## A\n```text\n::: notes\n## example\n```\n', path='deck.md')
    assert 'speaker_notes' not in doc.slides[0].root.props


def test_unterminated_notes_are_an_error():
    with pytest.raises(ParseError, match='unterminated ::: notes'):
        parse_content('## A\n::: notes\nforgot close\n', path='deck.md')


def test_multiple_notes_blocks_and_regular_slide_sections():
    doc = parse_content('## A\n::: notes\nFirst\n:::\n### Region\nBody\n'
                        '::: notes\nSecond\n:::\n', path='deck.md')
    assert doc.slides[0].root.props['speaker_notes'] == 'First\n\nSecond'
    assert doc.slides[0].root.children[-1].kind == 'region'


def test_missing_notes_image_is_reported_by_asset_validation(tmp_path: Path):
    project = compile_project([SourceUnit(str(tmp_path / 'deck.md'),
                                          '## A\n::: notes\n![no](missing.png)\n:::\n')], [])
    with pytest.raises(ValueError, match='notes:image'):
        validate_asset_references(project)
