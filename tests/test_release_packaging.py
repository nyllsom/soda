import json
from pathlib import Path

from soda.html.render import _esbuild_executable, _esbuild_names, _zanim_web_root


def test_release_contains_complete_vendored_zanim_web(monkeypatch):
    monkeypatch.delenv("ZANIM_WEB_ROOT", raising=False)
    root = _zanim_web_root()
    assert root.name == "zanim_web"
    assert (root / "src" / "zanim.js").is_file()
    assert (root / "dist" / "zanim_web_core.wasm").stat().st_size > 0
    metadata = json.loads((root / "package.json").read_text(encoding="utf-8"))
    assert metadata["name"] == "@zanim/web"
    assert metadata["version"] == "0.1.0-beta.1"


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
