import base64
import re

import pytest

from soda.compiler.diagnostics import SemanticError
from soda.compiler.project import SourceUnit, compile_paths, compile_project
from soda.compiler.timeline_ir import compile_timeline
from soda.html.render import export_html, render_html


def scene_project(tmp_path, suffix='tsx'):
    (tmp_path / 'part.tsx').write_text('export const label = "bundled-child";')
    (tmp_path / f'scene.{suffix}').write_text(
        "import {useCurrentFrame} from 'remotion';\n"
        "import {label} from './part';\n"
        "export const config = {width: 640, height: 360, fps: 30, durationInFrames: 90};\n"
        "export default function Scene({value = 0}) { return <div>{label}:{useCurrentFrame()}:{value}</div>; }\n"
    )
    md = tmp_path / 'deck.md'
    md.write_text(f'## Scene {{#scene}}\n@remotion scene.{suffix} {{#demo value=0}}\n')
    motion = tmp_path / 'deck.soda'
    motion.write_text('motion scene { demo.animate(name = "value", from = 0, to = 1, duration = 500ms); }')
    return compile_paths([str(md), str(motion)])


def test_remotion_timeline_channel(tmp_path):
    clip = compile_timeline(scene_project(tmp_path)).clips[0]
    assert clip.channel == 'remotion'
    assert clip.args['name'] == 'value'


@pytest.mark.parametrize('single_file', [True, False])
def test_remotion_bundles_react_tsx_and_relative_imports(tmp_path, single_file):
    out = export_html(scene_project(tmp_path), tmp_path / 'out.html', single_file=single_file)
    html = out.read_text()
    assert 'data-kind="remotion"' in html
    assert 'soda-single-scene:' in html
    urls = re.findall('data:text/javascript;base64,([A-Za-z0-9+/=]+)', html)
    assert len(urls) == 1
    bundle = base64.b64decode(urls[0]).decode()
    assert 'bundled-child' in bundle
    assert 'seekTo' in bundle
    assert '@zanim/web' not in html + bundle
    assert 'data:application/wasm' not in html
    assert not (tmp_path / 'assets' / 'zanim-web').exists()


def test_render_html_bundles_components(tmp_path):
    assert '__SODA_REMOTION_SCENE_BUNDLE_URL__=' in render_html(scene_project(tmp_path))


def test_remotion_motion_only_for_components():
    with pytest.raises(SemanticError, match="has no temporal method 'animate'"):
        compile_project([SourceUnit('deck.md', '## A {#a}\nText. {#text}\n')],
                        [SourceUnit('deck.soda', 'motion a { text.animate(name = "x", to = 1); }')])


def test_legacy_zanim_directive_rejected():
    with pytest.raises(Exception, match='@zanim is no longer supported'):
        compile_project([SourceUnit('deck.md', '## A {#a}\n@zanim old.js {#old}\n')], [])


def test_remote_remotion_rejected(tmp_path):
    program = compile_project([SourceUnit('deck.md', '## A {#a}\n@remotion https://example.com/scene.js {#scene}\n')], [])
    with pytest.raises(ValueError, match='local relative paths'):
        export_html(program, tmp_path / 'out.html', single_file=True)


def test_bundling_failure_is_actionable(tmp_path):
    program = scene_project(tmp_path)
    (tmp_path / 'part.tsx').unlink()
    with pytest.raises(ValueError, match='failed to bundle Remotion scenes'):
        export_html(program, tmp_path / 'out.html')
