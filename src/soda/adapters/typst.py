from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_SVG_SIZE_RE = re.compile(
    r'<svg[^>]*\bwidth="([0-9.]+)pt"[^>]*\bheight="([0-9.]+)pt"',
    re.I,
)


@dataclass(frozen=True, slots=True)
class TypstSvgAsset:
    svg: str
    width_pt: float
    height_pt: float

    @property
    def aspect_ratio(self) -> float:
        return self.width_pt / self.height_pt if self.height_pt > 0 else 1.0


def typst_executable() -> Path:
    for env_name in ("SODA_TYPST",):
        value = os.environ.get(env_name)
        if value:
            path = Path(value).expanduser()
            if path.is_file():
                return path
            raise ValueError(f"{env_name} does not point to a Typst executable: {path}")

    system = shutil.which("typst")
    if system:
        return Path(system)

    raise ValueError(
        "Typst is required for Typst-backed presentation objects. Install Typst "
        "on PATH, or set SODA_TYPST to the executable."
    )


def _parse_svg(svg: str, *, source: str) -> TypstSvgAsset:
    match = _SVG_SIZE_RE.search(svg)
    if not match:
        raise ValueError(f"Typst SVG for {source!r} is missing point width/height metadata")
    width_pt, height_pt = map(float, match.groups())
    return TypstSvgAsset(svg, width_pt, height_pt)


def compile_typst_file(
    path: Path, *, page: int = 1, inputs: Mapping[str, str] | None = None
) -> TypstSvgAsset:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Typst source does not exist: {path}")
    if page < 1:
        raise ValueError("Typst page must be positive")

    executable = typst_executable()
    input_args = [arg for key, value in (inputs or {}).items()
                  for arg in ("--input", f"{key}={value}")]
    with tempfile.TemporaryDirectory(prefix="soda-typst-") as td:
        output = Path(td) / "figure.svg"
        proc = subprocess.run(
            [
                str(executable),
                "compile",
                *input_args,
                "--pages",
                str(page),
                str(path),
                str(output),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            details = (proc.stderr or proc.stdout).strip()
            raise ValueError(f"Typst compilation failed for {path}:\n{details}")
        if not output.is_file():
            raise ValueError(f"Typst did not produce an SVG for page {page} of {path}")
        return _parse_svg(output.read_text(encoding="utf-8"), source=str(path))
