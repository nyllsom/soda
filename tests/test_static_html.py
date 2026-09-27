from soda.compiler.project import SourceUnit, compile_project
from soda.html.render import render_html


def test_static_html_embeds_absolute_timeline_and_scrubber():
    content = SourceUnit("deck.md", "# A {#a}\nHello. {#lead}\n")
    motion = SourceUnit(
        "motion.soda",
        "motion a { lead.fade_in(duration = 200ms, easing = LINEAR); }",
    )
    html = render_html(compile_project([content], [motion]))
    assert 'class="scrub"' in html
    assert "window.sodaTimeline" in html
    assert '"easing": "LINEAR"' in html
    assert '"start": 0.0' in html
    assert '"end": 0.2' in html


def test_dense_slide_variant_is_rendered_and_styled():
    content = SourceUnit("deck.md", "# Dense {#dense .dense .tight}\nMore content. {#body}\n")
    html = render_html(compile_project([content], []))
    assert "slide-dense" in html
    assert "slide-tight" in html
    assert ".slide-dense" in html
    assert ".slide-tight" in html


def test_lang_metadata_localizes_player_chrome():
    content = SourceUnit("deck.md", "---\nlang: zh\n---\n## A {#a}\n你好。 {#lead}\n")
    html = render_html(compile_project([content], []))
    assert '<html lang="zh-CN">' in html
    assert '空格 / → 下一步' in html
    assert '<span class="step">就绪</span>' in html


def test_every_visible_content_node_uses_slide_object_frame_runtime():
    content = SourceUnit(
        "deck.md",
        '''## Objects {#objects}\nLead. {#lead}\n```python {#code}\nprint(1)\n```\n@slide target {#preview}\n\n### {left|right #main_group}\n#### Left {#left}\n![Remote](https://example.com/image.png) {#image}\n#### Right {#right}\n@video https://example.com/demo.mp4 {#video controls=false}\n\n## Target {#target}\nDone.\n''',
    )
    motion = SourceUnit(
        "motion.soda",
        '''motion objects {\n    slide.scale(by = 0.98, duration = 100ms);\n    lead.move(by = vec2(1, 0), duration = 100ms);\n    main_group.rotate(by = 0.02, duration = 100ms);\n    image.scale(by = 1.05, duration = 100ms);\n    video.fade_in(duration = 100ms);\n    code.fade_out(duration = 100ms);\n    preview.scale(by = 1.03, duration = 100ms);\n}\n''',
    )
    html = render_html(compile_project([content], [motion]))
    for object_id in ("slide", "lead", "main_group", "left", "right", "image", "video", "code", "preview"):
        assert f'data-object="{object_id}"' in html
    assert html.count('data-slide-object="true"') >= 9
    assert "slide-object-frame" in html
    assert "function resetFrame(el)" in html
    assert "function applyFrame(el, state)" in html
    assert "--soda-frame-x" in html
    assert "window.sodaObjects" in html


def test_html_runtime_exposes_layout_diagnostics_and_shared_transition_support():
    content = SourceUnit("deck.md", "## A {#a}\n### {#hero .card}\nSame.\n## B {#b}\n### {#hero .card}\nSame again.\n")
    motion = SourceUnit("motion.soda", 'flow { a -> b using shared("hero"); }')
    html = render_html(compile_project([content], [motion]))
    assert "window.sodaDiagnostics" in html
    assert "collectLayoutDiagnostics" in html
    assert "applySharedTransition" in html
    assert "shared-transition-overlay" in html


def test_fit_target_is_hidden_by_default_and_shared_clone_is_visible():
    content = SourceUnit("deck.md", """## A {left|right #a layout_id=layout}
### Source {#source}
Source.
### Target {#target}
Target.
## B {#b}
### {#hero .card}
Hero.
## C {#c}
### {#hero .card}
Hero moved.
""")
    motion = SourceUnit("motion.soda", """motion a { source.fit_to(target = target, duration = 400ms); }
flow { a -> b using cut(); b -> c using shared("hero", duration = 500ms); }
""")
    html = render_html(compile_project([content], [motion]))
    assert "clip.op !== 'fit_to' || clip.args?.show_target === true" in html
    assert "targetEl.style.visibility = 'hidden'" in html
    assert "clone.style.visibility = 'visible'" in html
    assert "sourceEl.style.visibility = 'hidden'" in html
    assert "targetEl.style.visibility = 'hidden'" in html


def test_frame_morphs_resize_boxes_without_scaling_typography():
    content = SourceUnit("deck.md", """## A {left|right 1:2 #a layout_id=layout}
### Source {#source}
Source.
### Target {#target}
Target.
## B {#b}
### {#hero .card}
Shared.
## C {#c}
### {#hero .card}
Shared.
""")
    motion = SourceUnit("motion.soda", """motion a { source.fit_to(target = target, duration = 400ms); }
flow { a -> b using cut(); b -> c using shared("hero", duration = 500ms); }
""")
    html = render_html(compile_project([content], [motion]))
    assert "fit-motion-clone" in html
    assert "clone.style.width = `${lerp(sourceRect.width, targetRect.width) / stageScale}px`" in html
    assert "clone.style.transform = 'none'" in html
    assert "const sx = sourceRect.width ? targetRect.width / sourceRect.width : 1" not in html
    assert "renderSharedRegionSurface" in html
    assert "shared-surface-hidden" in html
    assert "renderSharedVisual" in html
    assert "addClone(sourceEl, sourceRect, 1 - p)" not in html
    assert "if (slide.classList.contains('visible')) continue" in html


def test_html_uses_fixed_1600x900_logical_canvas_with_outer_scaling():
    content = SourceUnit("deck.md", "## Fixed {#fixed}\nStable layout.\n")
    html = render_html(compile_project([content], []))
    assert ".stage{position:fixed;left:50%;top:50%;width:1600px;height:900px" in html
    assert ".slide{display:block;visibility:hidden;content-visibility:hidden;contain:layout style paint;pointer-events:none;grid-area:1/1;position:relative;width:1600px;height:900px" in html
    assert ".slide.visible{visibility:visible;content-visibility:visible;pointer-events:auto}" in html
    assert "function updateStageScale()" in html
    assert "LOGICAL_WIDTH = 1600" in html
    assert "LOGICAL_HEIGHT = 900" in html
    assert "width:min(95vw,168.9vh)" not in html
    assert "@media(max-width:900px)" not in html


def test_fixed_canvas_transitions_convert_screen_rects_back_to_logical_space():
    content = SourceUnit("deck.md", """## A {#a}
@slide b {#preview}
## B {#b}
Target.
""")
    motion = SourceUnit("motion.soda", "flow { a -> b using embed_zoom(duration = 500ms); }")
    html = render_html(compile_project([content], [motion]))
    # fit_to still converts measured screen rectangles back to logical stage pixels.
    assert "function currentStageScale()" in html
    assert "clone.style.width = `${lerp(sourceRect.width, targetRect.width) / stageScale}px`" in html
    assert "clone.style.height = `${lerp(sourceRect.height, targetRect.height) / stageScale}px`" in html
    # embed_zoom keeps the real target slide pristine and animates a disposable
    # full-resolution proxy in viewport coordinates. At transition end the proxy
    # disappears and the unscaled target becomes the static frame.
    assert "const proxy = target.cloneNode(true)" in html
    assert "proxy.classList.add('embed-zoom-proxy', 'visible')" in html
    assert "sourceRect.width / LOGICAL_WIDTH" in html
    assert "targetRect.width / LOGICAL_WIDTH" in html
    assert "sharedOverlay.appendChild(proxy)" in html
    assert "target.classList.remove('visible')" in html
    assert "target.style.transform=`translate(" not in html


def test_navigation_preempts_any_running_animation_but_first_request_still_plays():
    content = SourceUnit("deck.md", """## A {#a}
A.
## B {#b}
B.
""")
    motion = SourceUnit("motion.soda", """motion a {
    step "show" { title.fade_in(duration = 400ms); }
}
flow { a -> b using fade(duration = 500ms); }
""")
    html = render_html(compile_project([content], [motion]))
    assert "function completeActiveAnimation()" in html
    assert "function startAnimationTo(targetTime)" in html
    assert "function animateTo(targetTime)" in html
    assert "if (animationTargetTime != null) completeActiveAnimation();" in html
    assert "prepareCodeFocusNavigation(stop.time);" in html
    assert "startAnimationTo(stop.time);" in html
    # Starting playback must never complete itself; preemption happens only in
    # the caller when a newer request arrives.
    start_body = html.split("function startAnimationTo(targetTime)", 1)[1].split("function animateTo(targetTime)", 1)[0]
    assert "completeActiveAnimation()" not in start_body
    assert "animationIsSlideTransition" not in html
    assert "pendingNavigationDirection" not in html
    assert "e.preventDefault(); navigate(1);" in html
    assert "e.preventDefault(); navigate(-1);" in html


def test_nju_theme_has_consistent_academic_spacing_and_intrinsic_tables():
    content = SourceUnit("deck.md", """---
theme: nju
---
# Cover {#cover}
Subtitle.
## Content {#content}
### Left
Body.
""")
    html = render_html(compile_project([content], []))
    assert "--soda-page-x:96px" in html
    assert "--soda-page-top:64px" in html
    assert "--soda-prose-width:1000px" in html
    assert "padding:var(--soda-page-top) var(--soda-page-x) var(--soda-page-bottom)" in html
    assert "--soda-layout-gap:64px" in html
    assert "width:fit-content;max-width:100%" in html
    assert "font-variant-numeric:tabular-nums" in html
    assert "padding:72px 36px 24px" not in html


def test_layout_gap_distinguishes_theme_default_from_explicit_zero():
    from soda.html.render import _style_for_layout

    content = SourceUnit("deck.md", """## Default {columns 1:1 #default}
### A
Text.
### B
Text.
## Explicit {columns 1:1 #explicit gap=0}
### A
Text.
### B
Text.
""")
    html = render_html(compile_project([content], []))
    assert 'gap:var(--soda-layout-gap,0.70rem)' in html
    assert 'gap:0.00rem' in html
    assert 'gap:1.40rem' in _style_for_layout({"kind": "columns", "gap": 0.7})
    assert 'grid-template-rows:repeat(3,minmax(0,1fr))' in _style_for_layout(
        {"kind": "grid", "cols": 2, "rows": 3}
    )
