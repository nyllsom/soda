from pathlib import Path

import pytest

from soda.compiler.diagnostics import SemanticError
from soda.compiler.project import SourceUnit, compile_paths, compile_project
from soda.compiler.timeline_ir import compile_timeline
from soda.html.render import export_html


def _find(node, object_id):
    if node.id == object_id:
        return node
    for child in node.children:
        found = _find(child, object_id)
        if found is not None:
            return found
    return None


def test_zanim_scene_markdown_lowers_to_bound_scene_and_timeline_clip(tmp_path: Path):
    (tmp_path / "koch.js").write_text("export default function mount(){ return { render(){} }; }\n", encoding="utf-8")
    md = tmp_path / "deck.md"
    md.write_text("## Fractal {#fractal}\n@zanim ./koch.js {#koch iteration=0}\n", encoding="utf-8")
    soda = tmp_path / "deck.soda"
    soda.write_text('motion fractal { koch.animate(name = "iteration", from = 0, to = 4, duration = 500ms); }\n', encoding="utf-8")
    program = compile_paths([str(md), str(soda)])
    obj = _find(program.slides[0].root, "koch")
    assert obj is not None
    assert obj.kind == "zanim"
    clip = compile_timeline(program).clips[0]
    assert clip.op == "animate"
    assert clip.channel == "zanim"
    assert clip.args["name"] == "iteration"


def test_zanim_scene_exports_js_module_and_runtime_mount(tmp_path: Path):
    (tmp_path / "scene.js").write_text("export function mount(){ return { render(){} }; }\n", encoding="utf-8")
    md = tmp_path / "deck.md"
    md.write_text("## Scene {#scene}\n@zanim scene.js {#demo value=0}\n", encoding="utf-8")
    soda = tmp_path / "deck.soda"
    soda.write_text('motion scene { demo.set(name = "value", value = 1); }\n', encoding="utf-8")
    program = compile_paths([str(md), str(soda)])
    out = tmp_path / "out.html"
    export_html(program, out)
    html = out.read_text(encoding="utf-8")
    assert 'data-kind="zanim"' in html
    assert "mountZanimScenes" in html
    assert "soda-single-scene:" in html or "new URL(source, window.location.href).href" in html
    assert "renderZanimScene" in html
    assert "props: authoredProps" in html
    assert '"@zanim/web":"./assets/zanim-web/src/zanim.js"' in html
    assert any(path.name.endswith("-scene.js") for path in (tmp_path / "assets").iterdir())
    assert (tmp_path / "assets" / "zanim-web" / "src" / "zanim.js").is_file()
    assert (tmp_path / "assets" / "zanim-web" / "dist" / "zanim_web_core.wasm").is_file()


def test_zanim_set_and_animate_are_only_for_zanim_scenes():
    content = SourceUnit("deck.md", "## A {#a}\nText. {#text}\n")
    bad = SourceUnit("deck.soda", 'motion a { text.animate(name = "x", to = 1); }')
    with pytest.raises(SemanticError, match="has no temporal method 'animate'"):
        compile_project([content], [bad])


def test_zanim_single_file_export_inlines_shared_scene_bundle_and_wasm(tmp_path: Path):
    (tmp_path / "scene.js").write_text(
        "import { Scene } from '@zanim/web';\n"
        "export async function mount(container){ const c=document.createElement('canvas'); container.append(c); const s=await Scene.create(c); return { render(t){s.seek(t);} }; }\n",
        encoding="utf-8",
    )
    md = tmp_path / "deck.md"
    md.write_text("## Scene {#scene}\n@zanim scene.js {#demo value=0}\n", encoding="utf-8")
    soda = tmp_path / "deck.soda"
    soda.write_text('motion scene { demo.animate(name = "value", from = 0, to = 1, duration = 500ms); }\n', encoding="utf-8")
    program = compile_paths([str(md), str(soda)])
    out = tmp_path / "single.html"
    export_html(program, out, single_file=True)
    html = out.read_text(encoding="utf-8")
    assert html.count("data:text/javascript;base64,") == 1
    assert "soda-single-scene:" in html
    assert "data:application/wasm;base64," in html
    assert './assets/zanim-web/src/zanim.js' not in html
    assert not (tmp_path / "assets").exists()
