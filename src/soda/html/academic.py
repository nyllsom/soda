from __future__ import annotations

import csv
import re
from dataclasses import dataclass

from soda.html.assets import resolve_asset_reference


@dataclass(frozen=True, slots=True)
class BibEntry:
    key: str
    entry_type: str
    fields: dict[str, str]


def _local_text(authored: str, source_path: str, *, role: str) -> str:
    ref = resolve_asset_reference(authored, source_path)
    if ref.remote:
        raise ValueError(f"{role} must use a local relative path for deterministic HTML export")
    assert ref.resolved_path is not None
    if not ref.resolved_path.is_file():
        raise ValueError(f"{role} {authored!r} referenced from {source_path!r} does not exist at {ref.resolved_path}")
    return ref.resolved_path.read_text(encoding="utf-8")


def load_chart_rows(authored: str, source_path: str) -> list[dict[str, str]]:
    text = _local_text(authored, source_path, role="chart data")
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise ValueError(f"chart data {authored!r} has no CSV header")
    return [dict(row) for row in reader]


def parse_bibtex(text: str) -> dict[str, BibEntry]:
    entries: dict[str, BibEntry] = {}
    i = 0
    while True:
        match = re.search(r"@([A-Za-z]+)\s*\{\s*([^,\s]+)\s*,", text[i:])
        if not match:
            break
        entry_type = match.group(1).lower()
        key = match.group(2).strip()
        start = i + match.end()
        depth = 1
        j = start
        quote = False
        escaped = False
        while j < len(text) and depth:
            ch = text[j]
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quote = not quote
            elif not quote and ch == "{":
                depth += 1
            elif not quote and ch == "}":
                depth -= 1
            j += 1
        if depth:
            raise ValueError(f"unterminated BibTeX entry {key!r}")
        body = text[start:j - 1]
        fields: dict[str, str] = {}
        k = 0
        while k < len(body):
            while k < len(body) and (body[k].isspace() or body[k] == ","):
                k += 1
            field_match = re.match(r"([A-Za-z][A-Za-z0-9_-]*)\s*=\s*", body[k:])
            if not field_match:
                break
            name = field_match.group(1).lower()
            k += field_match.end()
            if k >= len(body):
                break
            if body[k] == "{":
                level = 1
                value_start = k + 1
                k += 1
                while k < len(body) and level:
                    if body[k] == "{":
                        level += 1
                    elif body[k] == "}":
                        level -= 1
                    k += 1
                value = body[value_start:k - 1]
            elif body[k] == '"':
                value_start = k + 1
                k += 1
                while k < len(body):
                    if body[k] == '"' and body[k - 1] != "\\":
                        break
                    k += 1
                value = body[value_start:k]
                k += 1
            else:
                value_start = k
                while k < len(body) and body[k] != ",":
                    k += 1
                value = body[value_start:k]
            fields[name] = re.sub(r"\s+", " ", value).strip()
        entries[key] = BibEntry(key, entry_type, fields)
        i = j
    return entries


def load_bibliography(authored: str, source_path: str) -> dict[str, BibEntry]:
    return parse_bibtex(_local_text(authored, source_path, role="bibliography"))


def _author_names(raw: str) -> list[str]:
    return [part.strip() for part in re.split(r"\s+and\s+", raw) if part.strip()]


def _family_name(author: str) -> str:
    author = author.strip()
    if "," in author:
        return author.split(",", 1)[0].strip()
    parts = author.split()
    return parts[-1] if parts else author


def short_citation(entry: BibEntry) -> str:
    authors = _author_names(entry.fields.get("author", ""))
    if not authors:
        name = entry.fields.get("organization") or entry.fields.get("title") or entry.key
    elif len(authors) == 1:
        name = _family_name(authors[0])
    elif len(authors) == 2:
        name = f"{_family_name(authors[0])} & {_family_name(authors[1])}"
    else:
        name = f"{_family_name(authors[0])} et al."
    year = entry.fields.get("year", "n.d.")
    return f"{name}, {year}"


def format_reference(entry: BibEntry) -> str:
    authors = entry.fields.get("author") or entry.fields.get("organization") or ""
    title = entry.fields.get("title", entry.key)
    venue = entry.fields.get("booktitle") or entry.fields.get("journal") or entry.fields.get("publisher") or ""
    year = entry.fields.get("year", "")
    parts = [part for part in (authors, title, venue, year) if part]
    return ". ".join(parts) + ("." if parts else "")
