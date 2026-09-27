from __future__ import annotations

import base64
import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Theme:
    id: str
    name: str
    background: str
    stage: str
    surface: str
    foreground: str
    muted: str
    primary: str
    accent: str
    border: str
    code_background: str
    code_foreground: str
    code_keyword: str
    code_string: str
    code_comment: str
    code_number: str
    code_function: str
    code_highlight: str
    font_family: str
    title_rule_width: str = "7.2rem"
    title_rule_height: str = "3px"
    logo_width: str = "9.25rem"
    cover_rule_width: str = "5.2rem"
    brand_logo: str | None = None
    layout: str = "academic"
    brand_label: str = ""
    logo_height: str = "3.2rem"
    cover_logo_width: str | None = None
    cover_logo_height: str | None = None
    affiliation_logo: str | None = None
    affiliation_label: str = ""
    affiliation_width: str = "280px"
    affiliation_height: str = "92px"
    code_canvas: str | None = None
    table_divider: str | None = None


_THEME_ROOT = Path(__file__).parent
_ASSET_ROOT = _THEME_ROOT / "assets"


def resolve_theme(name: str | Path | None = None, *, base_dir: Path | None = None) -> Theme:
    """Load a built-in theme or a project JSON; custom files extend one built-in."""
    label = str(name or "nju").strip()
    definitions = {p.stem: p for p in _THEME_ROOT.glob("*.json")}
    custom = {}
    asset_root = _ASSET_ROOT
    key = label.lower()
    if key in definitions:
        definition = definitions[key]
    elif Path(label).suffix.lower() == ".json":
        path = Path(label).expanduser()
        if not path.is_absolute():
            path = (base_dir or Path.cwd()) / path
        custom = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(custom, dict):
            raise ValueError(f"theme {path} must contain a JSON object")
        parent = custom.pop("extends", "nju")
        if parent not in definitions:
            raise ValueError(f"theme {path} extends unknown built-in {parent!r}")
        definition = definitions[parent]
        asset_root = path.resolve().parent
        key = path.stem.lower()
    else:
        raise ValueError(f"unknown theme {name!r}; available themes: {', '.join(sorted(definitions))}")
    values = json.loads(definition.read_text(encoding="utf-8"))
    values.update(custom)

    def token_value(field: str, visiting: tuple[str, ...] = ()):
        if field not in values:
            raise ValueError(f"unknown token reference ${field} in theme {key!r}")
        if field in visiting:
            raise ValueError(f"cyclic token reference ${field} in theme {key!r}")
        value = values[field]
        if isinstance(value, str) and value.startswith("$"):
            value = token_value(value[1:], (*visiting, field))
            values[field] = value
        return value

    for field in values:
        token_value(field)
    for field in ("brand_logo", "affiliation_logo"):
        if filename := values.get(field):
            root = asset_root if field in custom else _ASSET_ROOT
            data = (root / filename).read_bytes()
            mime = mimetypes.guess_type(filename)[0] or "image/png"
            values[field] = f"data:{mime};base64," + base64.b64encode(data).decode("ascii")
    try:
        theme = Theme(id=key, **values)
    except TypeError as exc:
        raise ValueError(f"invalid theme {key!r}: {exc}") from exc
    if theme.layout != "academic":
        raise ValueError(f"unknown layout {theme.layout!r} in theme {key!r}")
    return theme


def theme_tokens(theme: Theme) -> dict[str, str]:
    """One semantic token map for CSS, authored SVG, and Typst inputs."""
    return {
        "stage": theme.stage,
        "background": theme.background,
        "surface": theme.surface,
        "foreground": theme.foreground,
        "muted": theme.muted,
        "primary": theme.primary,
        "accent": theme.accent,
        "border": theme.border,
        "code-bg": theme.code_background,
        "code-canvas": theme.code_canvas or theme.code_background,
        "code-fg": theme.code_foreground,
        "code-keyword": theme.code_keyword,
        "code-string": theme.code_string,
        "code-comment": theme.code_comment,
        "code-number": theme.code_number,
        "code-function": theme.code_function,
        "code-highlight": theme.code_highlight,
        "font": theme.font_family,
        "title-rule-width": theme.title_rule_width,
        "title-rule-height": theme.title_rule_height,
        "brand-logo-width": theme.logo_width,
        "brand-logo-height": theme.logo_height,
        "cover-logo-width": theme.cover_logo_width or theme.logo_width,
        "cover-logo-height": theme.cover_logo_height or theme.logo_height,
        "affiliation-width": theme.affiliation_width,
        "affiliation-height": theme.affiliation_height,
        "cover-rule-width": theme.cover_rule_width,
        "table-divider": theme.table_divider or theme.border,
    }


def typst_theme_inputs(theme: Theme) -> dict[str, str]:
    return {f"soda-{key}": value for key, value in theme_tokens(theme).items()}


def css_variables(theme: Theme) -> str:
    values = theme_tokens(theme)
    if theme.brand_logo:
        values["brand-logo"] = f"url({theme.brand_logo})"
    if theme.affiliation_logo:
        values["affiliation-logo"] = f"url({theme.affiliation_logo})"
    return ";".join(f"--soda-{key}:{value}" for key, value in values.items())
