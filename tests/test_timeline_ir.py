import pytest

from soda.compiler.project import SourceUnit, compile_project
from soda.compiler.timeline_ir import compile_timeline


def test_web_timeline_is_absolute_and_random_accessible():
    content = SourceUnit("deck.md", """# A {#a}\nHello. {#lead}\n@slide b {#preview}\n\n# B {#b}\nDone. {#done}\n""")
    motion = SourceUnit("motion.soda", """const D: Duration = 200ms;
motion a {
    step "show" {
        parallel(duration = D) {
            title.fade_in(duration = D);
            lead.fade_in(duration = D);
        }
    }
    step "grow" {
        preview.scale(by = 1.2, duration = 300ms);
    }
}
motion b {
    step "done" { done.fade_in(duration = 400ms); }
}
flow { a -> b using embed_zoom(duration = 500ms); }
""")
    timeline = compile_timeline(compile_project([content], [motion]))

    assert [(stop.time, stop.slide, stop.label) for stop in timeline.stops] == [
        (0.0, "a", "ready"),
        (0.2, "a", "show"),
        (0.5, "a", "grow"),
        (1.0, "b", "ready"),
        (1.4, "b", "done"),
    ]
    assert timeline.transitions[0].start == 0.5
    assert timeline.transitions[0].end == 1.0
    assert timeline.transitions[0].kind == "embed_zoom"
    assert timeline.clips[0].start == timeline.clips[1].start == 0.0
    assert timeline.total_duration == 1.4


def test_sequential_clips_have_stable_absolute_ranges():
    content = SourceUnit("deck.md", "# A {#a}\nText. {#text}\n")
    motion = SourceUnit("motion.soda", """motion a {
    step "sequence" {
        text.fade_in(duration = 100ms);
        text.move(by = vec2(1, 0), duration = 250ms);
    }
}
""")
    timeline = compile_timeline(compile_project([content], [motion]))
    assert [(clip.op, clip.start, clip.end) for clip in timeline.clips] == [
        ("fade_in", 0.0, 0.1),
        ("move", 0.1, 0.35),
    ]
    assert timeline.stops[-1].time == 0.35


def test_default_duration_and_parallel_default_match_zanim():
    content = SourceUnit("deck.md", "# A {#a}\nText. {#text}\n")
    motion = SourceUnit("motion.soda", """motion a {
    step "plain" { text.fade_in(); }
    step "parallel default" {
        parallel(duration = 250ms) {
            text.fade_out();
        }
    }
    step "parallel explicit" {
        parallel(duration = 2s) {
            text.fade_in(duration = 100ms);
        }
    }
}
""")
    timeline = compile_timeline(compile_project([content], [motion]))
    assert [(clip.op, clip.start, clip.end) for clip in timeline.clips] == [
        ("fade_in", 0.0, 1.0),
        ("fade_out", 1.0, 1.25),
        ("fade_in", 1.25, 1.35),
    ]
    assert timeline.stops[-1].time == 1.35


def test_clip_easing_is_preserved_in_backend_timeline():
    content = SourceUnit("deck.md", "# A {#a}\nText. {#text}\n")
    motion = SourceUnit(
        "motion.soda",
        "motion a { text.fade_in(duration = 1s, easing = LINEAR); }",
    )
    timeline = compile_timeline(compile_project([content], [motion]))
    assert timeline.clips[0].easing == "LINEAR"


def test_transform_channel_conflicts_match_zanim():
    content = SourceUnit("deck.md", "# A {#a}\nText. {#text}\n")
    motion = SourceUnit("motion.soda", """motion a {
    parallel {
        text.move(by = vec2(1, 0), duration = 1s);
        text.scale(by = 2, duration = 1s);
    }
}
""")
    with pytest.raises(ValueError, match="overlapping transform clips"):
        compile_timeline(compile_project([content], [motion]))


def test_flow_transition_kinds_have_absolute_reversible_spans():
    content = SourceUnit(
        "deck.md",
        "# A {#a}\nA.\n# B {#b}\nB.\n# C {#c}\nC.\n# D {#d}\nD.\n",
    )
    motion = SourceUnit("motion.soda", """flow {
    a -> b using fade();
    b -> c using push(RIGHT, duration = 100ms);
    c -> d using cut();
}
""")
    timeline = compile_timeline(compile_project([content], [motion]))
    assert [(tr.kind, tr.start, tr.end) for tr in timeline.transitions] == [
        ("fade", 0.0, 0.4),
        ("push", 0.4, 0.5),
        ("cut", 0.5, 0.501),
    ]
    assert timeline.transitions[1].args["_0"] == "RIGHT"
    assert timeline.total_duration == 0.501


def test_at_offset_uses_current_scheduler_base():
    content = SourceUnit("deck.md", "# A {#a}\nText. {#text}\n")
    motion = SourceUnit("motion.soda", """motion a {
    text.fade_in(duration = 100ms, at = 200ms);
    text.fade_out(duration = 150ms, at = 50ms);
}
""")
    timeline = compile_timeline(compile_project([content], [motion]))
    assert [(clip.start, clip.end) for clip in timeline.clips] == [
        pytest.approx((0.2, 0.3)),
        pytest.approx((0.35, 0.5)),
    ]


def test_parallel_at_offsets_share_one_scheduler_base():
    content = SourceUnit("deck.md", "# A {#a}\nOne. {#one}\n\nTwo. {#two}\n")
    motion = SourceUnit("motion.soda", """motion a {
    parallel(duration = 1s) {
        one.fade_in(at = 100ms);
        two.fade_in(duration = 200ms, at = 400ms);
    }
}
""")
    timeline = compile_timeline(compile_project([content], [motion]))
    values = [(clip.target, clip.start, clip.end) for clip in timeline.clips]
    assert values[0][0] == "one"
    assert values[0][1:] == pytest.approx((0.1, 1.1))
    assert values[1][0] == "two"
    assert values[1][1:] == pytest.approx((0.4, 0.6))
    assert timeline.total_duration == 1.1


def test_shared_transition_preserves_object_ids_in_transition_args():
    content = SourceUnit(
        "deck.md",
        "## A {#a}\n### {#hero .card}\nSame.\n## B {#b}\n### {#hero .card}\nSame again.\n",
    )
    motion = SourceUnit("motion.soda", 'flow { a -> b using shared("hero", duration = 600ms); }')
    timeline = compile_timeline(compile_project([content], [motion]))
    tr = timeline.transitions[0]
    assert tr.kind == "shared"
    assert tr.args["_0"] == "hero"
    assert tr.end - tr.start == pytest.approx(0.6)


def test_shared_transition_rejects_missing_object_on_either_slide():
    content = SourceUnit("deck.md", "# A {#a}\nSame. {#hero}\n# B {#b}\nOther. {#other}\n")
    motion = SourceUnit("motion.soda", 'flow { a -> b using shared("hero"); }')
    from soda.compiler.diagnostics import SemanticError
    with pytest.raises(SemanticError, match="does not exist on slide 'b'"):
        compile_project([content], [motion])
