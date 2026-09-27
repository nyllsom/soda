import re
from importlib.resources import files

from soda.compiler.motion_api import SUPPORTED_MOTION_METHODS


def test_browser_runtime_handles_exactly_the_compiler_motion_contract():
    source = files("soda.html").joinpath("runtime.js").read_text(encoding="utf-8")
    handled = set(re.findall(r"clip\.op === '([^']+)'", source))
    assert handled == set(SUPPORTED_MOTION_METHODS)
    assert "Unsupported SODA motion op" in source


def test_presentation_move_uses_fixed_canvas_pixels_without_hidden_frame_math():
    source = files("soda.html").joinpath("runtime.js").read_text(encoding="utf-8")
    move = source.split("clip.op === 'move'", 1)[1].split("clip.op === 'fit_to'", 1)[0]
    assert "const v = args.by" in move
    assert "args.to" not in move
    assert "* 42" not in move
    assert "tx += Number(v[0] || 0) * p" in move
    assert "ty += Number(v[1] || 0) * p" in move
