import pytest

from soda.compiler.diagnostics import ParseError, SemanticError
from soda.compiler.project import SourceUnit, compile_project

CONTENT = SourceUnit("deck.md", '''# Intro {#intro}
Hello. {#lead}
```python {#code}
print(1)
```
''')


def test_content_and_motion_are_linked_but_separate():
    motion = SourceUnit("motion.soda", '''motion intro {
    step "show" {
        lead.fade_in(duration = 400ms);
        code.focus(line = 1, duration = 200ms);
    }
}
''')
    project = compile_project([CONTENT], [motion])
    assert project.slides[0].root.children[1].id == "lead"
    assert project.slides[0].root.layout == {"kind": "slide-flow"}
    assert project.motions[0].slide == "intro"


def test_motion_cannot_reference_unknown_content_object():
    motion = SourceUnit("motion.soda", "motion intro { missing.fade_in(duration = 1s); }")
    with pytest.raises(SemanticError, match="unknown name 'missing'"):
        compile_project([CONTENT], [motion])


def test_motion_cannot_use_layout_mutation():
    motion = SourceUnit("motion.soda", "motion intro { lead.place(anchor = CENTER); }")
    with pytest.raises(SemanticError, match="has no temporal method 'place'"):
        compile_project([CONTENT], [motion])


def test_multiple_content_files_link_slide_references():
    first = SourceUnit("a.md", "# A {#a}\n@slide b {#preview}\n")
    second = SourceUnit("b.md", "# B {#b}\nEnd.\n")
    project = compile_project([first, second], [])
    preview = project.slides[0].root.children[1]
    assert preview.kind == "slide-ref"
    assert preview.props["slide"] == "b"


def test_motion_cannot_add_new_content_objects():
    motion = SourceUnit("motion.soda", '''motion intro {
        let extra = Text("late");
        let extra_h = add(extra);
    }
''')
    with pytest.raises(ParseError):
        compile_project([CONTENT], [motion])


def test_layout_shape_is_checked_before_motion():
    broken = SourceUnit("broken.md", """## Intro {left|right #intro}
### Only one child
Text.
""")
    from soda.compiler.diagnostics import ParseError
    with pytest.raises(ParseError, match="ratio defines 2 regions"):
        compile_project([broken], [])


def test_code_specific_motion_is_typed():
    motion = SourceUnit("motion.soda", "motion intro { lead.focus(duration = 1s); }")
    with pytest.raises(SemanticError, match="has no temporal method 'focus'"):
        compile_project([CONTENT], [motion])


def test_motion_module_keeps_constants_for_lowering():
    motion = SourceUnit("motion.soda", '''const D: Duration = 400ms;
motion intro {
    lead.fade_in(duration = D);
}
''')
    project = compile_project([CONTENT], [motion])
    assert project.modules[0].source == "motion.soda"
    assert project.modules[0].constants[0].name == "D"


def test_parallel_rejects_wait_to_match_zanim():
    motion = SourceUnit("motion.soda", """motion intro {
    parallel(duration = 1s) {
        wait 100ms;
    }
}
""")
    with pytest.raises(SemanticError, match=r"wait is not allowed inside parallel"):
        compile_project([CONTENT], [motion])


def test_parallel_rejects_nesting_to_match_zanim():
    motion = SourceUnit("motion.soda", """motion intro {
    parallel {
        parallel { lead.fade_in(duration = 100ms); }
    }
}
""")
    with pytest.raises(SemanticError, match=r"nested parallel\(\) blocks are not supported"):
        compile_project([CONTENT], [motion])


def test_temporal_at_requires_duration():
    motion = SourceUnit("motion.soda", "motion intro { lead.fade_in(at = 1); }")
    with pytest.raises(SemanticError, match="expected Duration"):
        compile_project([CONTENT], [motion])


def test_shared_rejects_text_leaf_instead_of_cross_fading_it():
    import pytest

    from soda.compiler.diagnostics import SemanticError
    from soda.compiler.project import SourceUnit, compile_project

    content = SourceUnit("deck.md", "# A {#a}\nSame. {#hero}\n# B {#b}\nSame. {#hero}\n")
    motion = SourceUnit("motion.soda", 'flow { a -> b using shared("hero"); }')
    with pytest.raises(SemanticError, match="unsupported kind 'paragraph'"):
        compile_project([content], [motion])


def test_shared_visual_leaf_requires_same_visual_content():
    import pytest

    from soda.compiler.diagnostics import SemanticError
    from soda.compiler.project import SourceUnit, compile_project

    content = SourceUnit("deck.md", """# A {#a}
$$
x^2
$$ {#formula}
# B {#b}
$$
y^2
$$ {#formula}
""")
    motion = SourceUnit("motion.soda", 'flow { a -> b using shared("formula"); }')
    with pytest.raises(SemanticError, match="changes visual content"):
        compile_project([content], [motion])


def test_shared_stable_math_leaf_is_allowed():
    from soda.compiler.project import SourceUnit, compile_project

    content = SourceUnit("deck.md", """# A {#a}
$$
x^2
$$ {#formula}
# B {#b}
$$
x^2
$$ {#formula}
""")
    motion = SourceUnit("motion.soda", 'flow { a -> b using shared("formula"); }')
    program = compile_project([content], [motion])
    assert len(program.flow) == 1


def test_compile_paths_accepts_md_and_rejects_legacy_zmd(tmp_path):
    from soda.compiler.project import compile_paths

    good = tmp_path / "deck.md"
    good.write_text("## Demo {#demo}\nbody\n", encoding="utf-8")
    assert compile_paths([str(good)]).slides[0].id == "demo"

    old = tmp_path / "deck.zmd"
    old.write_text("## Demo {#demo}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="use .md for content"):
        compile_paths([str(old)])


def test_flow_rejects_non_adjacent_edges_instead_of_silently_ignoring_them():
    content = SourceUnit(
        "deck.md",
        "# A {#a}\nA.\n# B {#b}\nB.\n# C {#c}\nC.\n",
    )
    motion = SourceUnit("motion.soda", "flow { a -> c using fade(); }")
    with pytest.raises(SemanticError, match="must transition to 'b', not 'c'"):
        compile_project([content], [motion])


def test_flow_rejects_duplicate_transition_definitions():
    content = SourceUnit("deck.md", "# A {#a}\nA.\n# B {#b}\nB.\n")
    first = SourceUnit("one.soda", "flow { a -> b using fade(); }")
    second = SourceUnit("two.soda", "flow { a -> b using cut(); }")
    with pytest.raises(SemanticError, match="already defined in one.soda"):
        compile_project([content], [first, second])


def test_flow_direction_is_a_typed_enum_not_an_arbitrary_string():
    content = SourceUnit("deck.md", "# A {#a}\nA.\n# B {#b}\nB.\n")
    bad = SourceUnit("motion.soda", 'flow { a -> b using push("LEFT"); }')
    with pytest.raises(SemanticError, match="expected Direction, got String"):
        compile_project([content], [bad])
