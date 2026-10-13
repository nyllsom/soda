import pytest

from soda.compiler.content import parse_content
from soda.compiler.project import SourceUnit, compile_project
from soda.html.render import render_html


def test_notes_do_not_create_slides_or_visible_objects():
    text = '## A {#a}\nVisible.\n::: notes\n## Not a slide\n<script>unsafe</script>\n::: \n## B {#b}\nBody.\n'
    doc = parse_content(text, path='deck.md')
    assert len(doc.slides) == 2
    assert '## Not a slide' in doc.slides[0].root.props['speaker_notes']
    assert all('unsafe' not in str(o.props) for o in doc.slides[0].root.children)
    html = render_html(compile_project([SourceUnit('deck.md', text)], []))
    assert '<script>unsafe</script>' not in html
    assert '<script>unsafe<\\/script>' in html
    assert '"notes": "## Not a slide' in html


def test_notes_markers_in_code_are_literal():
    doc = parse_content('## A\n```text\n::: notes\n## example\n```\n', path='deck.md')
    assert 'speaker_notes' not in doc.slides[0].root.props


def test_unterminated_notes_are_an_error():
    with pytest.raises(Exception, match='unterminated ::: notes'):
        parse_content('## A\n::: notes\nforgot close\n', path='deck.md')


def test_multiple_notes_blocks_and_internal_headings():
    doc = parse_content('## A\n::: notes\nFirst\n:::\n### Region\nBody\n::: notes\nSecond\n:::\n', path='deck.md')
    assert doc.slides[0].root.props['speaker_notes'] == 'First\n\nSecond'
