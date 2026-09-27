from __future__ import annotations

import base64
import hashlib
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from soda.adapters.typst import typst_executable

_CACHE_SCHEMA = "soda-math-svg-v2"


@dataclass(frozen=True, slots=True)
class MathSvgAsset:
    svg: str
    data_uri: str
    width_pt: float
    height_pt: float

    @property
    def aspect_ratio(self) -> float:
        return self.width_pt / self.height_pt if self.height_pt > 0 else 1.0


_SVG_SIZE_RE = re.compile(r'<svg[^>]*\bwidth="([0-9.]+)pt"[^>]*\bheight="([0-9.]+)pt"', re.I)


def _cache_dir() -> Path:
    root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    path = root / "soda" / "math"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _typst_source(source: str, *, font_size: float, color: str) -> str:
    if font_size <= 0:
        raise ValueError("math font_size must be positive")
    color = color.strip()
    if not color.startswith("#"):
        raise ValueError(f"math color must be a hex color, got {color!r}")
    return (
        "#set page(width: auto, height: auto, margin: 0pt, fill: none)\n"
        f'#set text(size: {font_size:g}pt, fill: rgb("{color}"))\n'
        "$ " + source.strip() + " $\n"
    )


@lru_cache(maxsize=256)
def compile_math_svg(source: str, font_size: float = 38.0, color: str = "#111111") -> str:
    typst_source = _typst_source(source, font_size=font_size, color=color)
    executable = typst_executable()
    try:
        version = subprocess.run(
            [str(executable), "--version"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f"failed to execute Typst at {executable}") from exc

    digest = hashlib.sha256(
        (_CACHE_SCHEMA + "\0" + version + "\0" + typst_source).encode("utf-8")
    ).hexdigest()
    output = _cache_dir() / f"{digest}.svg"
    if not output.is_file():
        with tempfile.TemporaryDirectory(prefix=".soda-math-", dir=_cache_dir()) as td:
            temp = Path(td)
            source_path = temp / "formula.typ"
            result_path = temp / "formula.svg"
            source_path.write_text(typst_source, encoding="utf-8")
            proc = subprocess.run(
                [str(executable), "compile", str(source_path), str(result_path)],
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                details = (proc.stderr or proc.stdout).strip()
                hint = (
                    "\nSODA math uses Typst math syntax. For multi-letter subscripts/superscripts, "
                    'write text explicitly, e.g. q_t^"target", or separate letters if you mean multiplication.'
                )
                raise ValueError(f"Typst math compilation failed for {source!r}:\n{details}{hint}")
            result_path.replace(output)
    return output.read_text(encoding="utf-8")


@lru_cache(maxsize=256)
def math_svg_asset(source: str, font_size: float = 38.0, color: str = "#111111") -> MathSvgAsset:
    svg = compile_math_svg(source, font_size, color)
    match = _SVG_SIZE_RE.search(svg)
    if not match:
        raise ValueError("Typst math SVG is missing point width/height metadata")
    width_pt, height_pt = map(float, match.groups())
    payload = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return MathSvgAsset(svg, f"data:image/svg+xml;base64,{payload}", width_pt, height_pt)


def math_svg_data_uri(source: str, *, font_size: float = 38.0, color: str = "#111111") -> str:
    return math_svg_asset(source, font_size, color).data_uri
