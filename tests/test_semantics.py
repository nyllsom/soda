import pytest

from soda.compiler.diagnostics import ParseError, SemanticError
from soda.compiler.project import SourceUnit, compile_project
from soda.compiler.timeline_ir import compile_timeline


def project(motion: str, markdown: str = "# Demo {#demo}\nText. {#text}\n"):
    return compile_project(
        [SourceUnit("deck.md", markdown)],
        [SourceUnit("motion.soda", motion)],
    )


def test_duration_arithmetic_is_typed():
    compiled = project(
        """
const T: Duration = 1s + 500ms;
motion demo { text.fade_in(duration = T); }
"""
    )
    assert compile_timeline(compiled).clips[0].end == pytest.approx(1.5)


def test_parallel_duration_must_be_duration():
    with pytest.raises(SemanticError, match="expected Duration, got Float"):
        project("motion demo { parallel(duration = 1.0) { text.fade_in(); } }")


def test_relative_move_uses_logical_canvas_pixels_and_has_no_frame_option():
    compiled = project("motion demo { text.move(by = vec2(80, -20), duration = 300ms); }")
    clip = compile_timeline(compiled).clips[0]
    assert clip.args["by"] == [80, -20]
    with pytest.raises(SemanticError, match=r"unknown move\(\) option 'frame'"):
        project(
            "motion demo { text.move(by = vec2(80, 0), frame = LOCAL, duration = 300ms); }"
        )


def test_absolute_move_is_not_part_of_presentation_frame_api():
    with pytest.raises(SemanticError, match=r"unknown move\(\) option 'to'"):
        project("motion demo { text.move(to = vec2(80, 0), duration = 300ms); }")


def test_unsupported_temporal_methods_are_rejected():
    with pytest.raises(SemanticError, match="has no temporal method 'morph'"):
        project("motion demo { text.morph(duration = 300ms); }")


def test_timeline_rejects_non_object_call_statements():
    with pytest.raises(SemanticError, match="timeline statements must call"):
        project("motion demo { vec2(1, 2); }")


def test_fit_to_requires_an_object_target_and_lowers_as_transform():
    markdown = """## Fit {left|right #fit layout_id=row}
### A {#a}
A.
### B {#b}
B.
"""
    compiled = compile_project(
        [SourceUnit("fit.md", markdown)],
        [SourceUnit("fit.soda", "motion fit { a.fit_to(target = b, duration = 400ms); }")],
    )
    clip = compile_timeline(compiled).clips[0]
    assert clip.op == "fit_to"
    assert clip.channel == "transform"
    assert clip.args["target"] == "b"


def test_fit_to_show_target_must_be_bool():
    markdown = """## Fit {left|right #fit layout_id=row}
### A {#a}
A.
### B {#b}
B.
"""
    with pytest.raises(SemanticError, match="expected Bool"):
        compile_project(
            [SourceUnit("fit.md", markdown)],
            [
                SourceUnit(
                    "fit.soda",
                    'motion fit { a.fit_to(target = b, show_target = "yes"); }',
                )
            ],
        )


def test_zanim_set_is_instant_and_does_not_accept_duration():
    markdown = "# Demo {#demo}\n@zanim scene.js {#scene value=0}\n"
    compiled = compile_project(
        [SourceUnit("deck.md", markdown)],
        [SourceUnit("motion.soda", 'motion demo { scene.set(name = "value", value = 2); }')],
    )
    clip = compile_timeline(compiled).clips[0]
    assert clip.end - clip.start == pytest.approx(0.001)
    with pytest.raises(SemanticError, match=r"unknown set\(\) option 'duration'"):
        compile_project(
            [SourceUnit("deck.md", markdown)],
            [
                SourceUnit(
                    "motion.soda",
                    'motion demo { scene.set(name = "value", value = 2, duration = 1s); }',
                )
            ],
        )


def test_legacy_code_first_soda_is_rejected_at_parse_time():
    with pytest.raises(ParseError):
        compile_project(
            [SourceUnit("deck.md", "# Demo {#demo}\n")],
            [SourceUnit("legacy.soda", "slide Demo {}")],
        )
