import pytest

from soda.compiler.content import parse_content
from soda.compiler.diagnostics import ParseError


def test_markdown_heading_layout_becomes_object_tree():
    doc = parse_content('''---
deck: Demo
theme: academic
---
# Intro {#intro}
Lead paragraph. {#lead}

## Method {left|right 2:1 #method layout_id=main}
Intro before split. {#method_lead}

### Content {#left}
```python {#code}
print("hi")
```

### Demo {#right .card}
![hero](hero.png) {#hero}
''', path="deck.md")
    assert doc.metadata["deck"] == "Demo"
    assert len(doc.slides) == 2
    slide = doc.slides[1]
    assert slide.id == "method"
    assert slide.root.kind == "slide"
    assert slide.objects["title"].kind == "heading"
    assert slide.objects["method_lead"].kind == "paragraph"
    assert slide.objects["main"].kind == "columns"
    assert slide.objects["main"].props["ratio"] == [2.0, 1.0]
    assert slide.objects["left"].kind == "region"
    assert slide.objects["left_title"].props["text"] == "Content"
    assert slide.objects["code"].kind == "code"
    assert slide.objects["hero"].kind == "image"
    assert "card" in slide.objects["right"].props["classes"]


def test_slide_ids_are_automatic_but_explicit_ids_remain_available():
    doc = parse_content("# Intro\nhello\n\n## Residual RL\nworld\n\n## 中文标题\nend\n")
    assert [slide.id for slide in doc.slides] == ["intro", "residual_rl", "slide_3"]


def test_nested_heading_layout_is_recursive_and_sections_are_objects():
    doc = parse_content('''## Nested {#nested}
### Upper {top|bottom #upper layout_id=upper_layout}
#### A {#a}
A body.
#### B {left|right #b}
##### B1 {#b1}
left
##### B2 {#b2}
right
''')
    slide = doc.slides[0]
    assert slide.objects["upper"].kind == "region"
    assert slide.objects["upper_layout"].kind == "rows"
    assert slide.objects["a"].kind == "region"
    assert slide.objects["b_layout"].kind == "columns"
    assert slide.objects["b1_title"].props["text"] == "B1"


def test_duplicate_explicit_object_id_is_rejected():
    with pytest.raises(ParseError, match="duplicate object id"):
        parse_content("## Intro {#intro}\nA. {#x}\n\nB. {#x}\n")


def test_layout_requires_matching_heading_children():
    with pytest.raises(ParseError, match="ratio defines 2 regions"):
        parse_content("## Intro {left|right #intro}\n### Only one\ntext\n")


def test_old_container_dsl_is_not_special_syntax_anymore():
    doc = parse_content("## Intro\n::: columns\ntext\n:::\n")
    paragraph = doc.slides[0].root.children[1]
    assert paragraph.kind == "paragraph"
    assert "::: columns" in paragraph.props["text"]


def test_frontmatter_markdown_comment_is_not_a_slide():
    doc = parse_content('''---
# this is metadata commentary
deck: Demo
---
## Real slide {#real}
body
''')
    assert [slide.id for slide in doc.slides] == ["real"]
