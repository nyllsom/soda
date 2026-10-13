import json
from pathlib import Path

from soda.html.render import _esbuild_executable, _esbuild_names, _remotion_node_modules


def test_release_contains_remotion_dependencies():
    root = _remotion_node_modules()
    player = json.loads((root / "@remotion/player/package.json").read_text())
    remotion = json.loads((root / "remotion/package.json").read_text())
    assert player["version"] == remotion["version"]
    assert not Path("src/soda/vendor/zanim_web").exists()


def test_esbuild_finds_project_local_node_modules(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("SODA_ESBUILD", raising=False)
    monkeypatch.setenv("PATH", "")
    scene = tmp_path / "slides" / "scene.js"
    scene.parent.mkdir()
    scene.write_text("export default {};\n", encoding="utf-8")
    executable = tmp_path / "node_modules" / ".bin" / _esbuild_names()[0]
    executable.parent.mkdir(parents=True)
    executable.write_text("", encoding="utf-8")
    assert _esbuild_executable(scene) == executable
