from __future__ import annotations

import base64
import html
import re
from pathlib import Path
from typing import Callable

from soda.html.assets import resolve_asset_reference
from soda.themes import Theme, theme_tokens

# Reserved SODA variables are an explicit opt-in. Literal colors and unrelated
# CSS variables in imported artwork keep their original meaning.
_SVG_TOKEN = re.compile(r"var\(\s*--soda-([a-z][a-z0-9-]*)\s*(?:,[^()]*)?\)")
_SVG_TOKEN_START = re.compile(r"var\(\s*--soda-")


def themed_asset_resolver(
    theme: Theme, fallback: Callable[[str, str], str]
) -> Callable[[str, str], str]:
    tokens = theme_tokens(theme)
    cache: dict[Path, str | None] = {}

    def resolve(authored: str, source_path: str) -> str:
        ref = resolve_asset_reference(authored, source_path)
        path = ref.resolved_path
        if ref.remote or path is None or path.suffix.lower() != ".svg" or not path.is_file():
            return fallback(authored, source_path)
        if path not in cache:
            try:
                svg = path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                # Preserve existing artwork in other encodings unchanged.
                cache[path] = None
                return fallback(authored, source_path)
            if not _SVG_TOKEN_START.search(svg):
                cache[path] = None
            else:
                def substitute(match: re.Match[str]) -> str:
                    name = match.group(1)
                    if name not in tokens:
                        raise ValueError(f"unknown SVG theme token --soda-{name} in {path}")
                    return html.escape(tokens[name], quote=True)

                rendered = _SVG_TOKEN.sub(substitute, svg)
                if _SVG_TOKEN_START.search(rendered):
                    raise ValueError(
                        f"unsupported SVG theme expression in {path}; use var(--soda-<token>) "
                        "with an optional literal fallback"
                    )
                payload = base64.b64encode(rendered.encode("utf-8")).decode("ascii")
                # Resolve at build time for both web and portable targets. An
                # <img> document cannot inherit the parent page's CSS variables.
                cache[path] = f"data:image/svg+xml;base64,{payload}"
        return cache[path] or fallback(authored, source_path)

    return resolve
