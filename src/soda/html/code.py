from __future__ import annotations

import html
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Segment:
    text: str
    kind: str = "plain"


_PYTHON = set(
    "and as assert async await break class continue def del elif else except False finally for from global if import in is lambda None nonlocal not or pass raise return True try while with yield match case".split()
)
_JS = set(
    "async await break case catch class const continue default delete do else export extends false finally for from function if import in instanceof let new null of return static super switch this throw true try typeof undefined var while yield interface type enum implements".split()
)
_ZIG = set(
    "align allowzero and anyframe anytype asm async await break callconv catch comptime const continue defer else enum errdefer error export extern fn for if inline noalias nosuspend opaque or orelse packed pub resume return struct suspend switch test threadlocal try union unreachable usingnamespace var volatile while".split()
)
_RUST = set(
    "as async await break const continue crate dyn else enum extern false fn for if impl in let loop match mod move mut pub ref return self Self static struct super trait true type unsafe use where while".split()
)
_CLIKE = set(
    "auto bool break case char class const continue default do double else enum extern float for if inline int long namespace private protected public register return short signed sizeof static struct switch template this throw try typedef typename union unsigned using virtual void volatile while".split()
)


def _language(language: str):
    lang = language.lower()
    if lang in {"python", "py"}:
        return _PYTHON, "#", None
    if lang in {"javascript", "js", "typescript", "ts", "tsx", "jsx"}:
        return _JS, "//", "/*"
    if lang == "zig":
        return _ZIG, "//", None
    if lang in {"rust", "rs"}:
        return _RUST, "//", "/*"
    if lang in {"c", "cpp", "c++", "cc", "h", "hpp", "java"}:
        return _CLIKE, "//", "/*"
    if lang in {"sh", "shell", "bash", "zsh"}:
        return (
            set("if then else elif fi for while do done case esac function in".split()),
            "#",
            None,
        )
    return set(), "//", "/*"


def _ident_start(ch):
    return ch.isalpha() or ch in "_$@"


def _ident(ch):
    return ch.isalnum() or ch in "_$@"


def tokenize(source: str, language: str) -> list[list[Segment]]:
    keywords, line_comment, block_start = _language(language)
    block_end = "*/" if block_start else None
    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    result = []
    in_block = False
    for line in lines:
        out = []
        i = 0
        while i < len(line):
            if in_block and block_end:
                end = line.find(block_end, i)
                if end < 0:
                    out.append(Segment(line[i:], "comment"))
                    i = len(line)
                    continue
                out.append(Segment(line[i : end + len(block_end)], "comment"))
                i = end + len(block_end)
                in_block = False
                continue
            if line_comment and line.startswith(line_comment, i):
                out.append(Segment(line[i:], "comment"))
                break
            if block_start and line.startswith(block_start, i):
                end = line.find(block_end or "", i + len(block_start))
                if end < 0:
                    out.append(Segment(line[i:], "comment"))
                    in_block = True
                    break
                out.append(Segment(line[i : end + len(block_end or "")], "comment"))
                i = end + len(block_end or "")
                continue
            ch = line[i]
            if ch in {'"', "'", "`"}:
                triple = language.lower() in {"python", "py"} and line.startswith(ch * 3, i)
                marker = ch * 3 if triple else ch
                j = i + len(marker)
                while j < len(line):
                    if line[j] == "\\":
                        j += 2
                    elif line.startswith(marker, j):
                        j += len(marker)
                        break
                    else:
                        j += 1
                out.append(Segment(line[i:j], "string"))
                i = j
                continue
            if ch.isdigit() or (ch == "." and i + 1 < len(line) and line[i + 1].isdigit()):
                j = i + 1
                while j < len(line) and (line[j].isalnum() or line[j] in "._xX+-"):
                    if line[j] in "+-" and line[j - 1] not in "eE":
                        break
                    j += 1
                out.append(Segment(line[i:j], "number"))
                i = j
                continue
            if _ident_start(ch):
                j = i + 1
                while j < len(line) and _ident(line[j]):
                    j += 1
                word = line[i:j]
                k = j
                while k < len(line) and line[k].isspace():
                    k += 1
                kind = (
                    "keyword"
                    if word in keywords
                    else "function"
                    if k < len(line) and line[k] == "("
                    else "plain"
                )
                out.append(Segment(word, kind))
                i = j
                continue
            j = i + 1
            while j < len(line):
                if line_comment and line.startswith(line_comment, j):
                    break
                if block_start and line.startswith(block_start, j):
                    break
                if line[j] in {'"', "'", "`"} or line[j].isdigit() or _ident_start(line[j]):
                    break
                j += 1
            out.append(Segment(line[i:j]))
            i = j
        result.append(out)
    return result


def render_code(
    source: str,
    language: str,
    *,
    line_numbers: bool = True,
    max_lines: int | None = None,
    dim_inactive: bool = False,
) -> str:
    rows = tokenize(source.strip("\n"), language)
    if max_lines is not None:
        max_lines = max(1, max_lines)
    attrs = [
        f'data-language="{html.escape(language, quote=True)}"',
        f'data-line-count="{len(rows)}"',
        f'data-line-numbers="{str(line_numbers).lower()}"',
        f'data-dim-inactive="{str(dim_inactive).lower()}"',
    ]
    if max_lines is not None:
        attrs.append(f'data-max-lines="{max_lines}"')
    style = (
        f' style="max-height:calc({max_lines} * var(--soda-code-line-height,1.52em)'
        ' + var(--soda-code-padding-y,1.54rem))"'
        if max_lines is not None else ""
    )
    rendered = []
    for number, segments in enumerate(rows, 1):
        body = (
            "".join(
                f'<span class="tok tok-{seg.kind}">{html.escape(seg.text)}</span>'
                for seg in segments
            )
            or "&#8203;"
        )
        lineno = f'<span class="code-ln" aria-hidden="true">{number}</span>' if line_numbers else ""
        rendered.append(
            f'<span class="code-line" data-line="{number}">{lineno}<span class="code-text">{body}</span></span>'
        )
    bands = '<div class="code-focus-band" aria-hidden="true"></div><div class="code-pulse-band" aria-hidden="true"></div>'
    return f'<div class="code-render" {" ".join(attrs)}{style}>{bands}{"".join(rendered)}</div>'
