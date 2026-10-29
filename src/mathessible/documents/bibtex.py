"""A LaTeX document's BibTeX bibliography (`refs.bib`), read for `\\cite` and the references in its preview.

LaTeX reads `\\bibliography{refs}` (BibTeX) or `\\addbibresource{refs.bib}`
(biblatex) from the .tex file's folder and lists the entries cited, or
all of them after `\\nocite{*}`. Their numbers follow the style: `unsrt`,
`ieeetr` and their kind (and biblatex's `sorting=none`) number them in
the order they are first cited; `plain` and the others sort them by their
first author's family name, then year and title. An entry is written as
its authors, title, where it appeared and its year, the way most numeric
styles show it; the text is still LaTeX, which `tex_markdown` reads.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_COMMENT = re.compile(r"(?<!\\)%.*$", re.MULTILINE)
_BIBLIOGRAPHY = re.compile(r"\\bibliography\s*\{([^}]*)\}")
_RESOURCE = re.compile(r"\\addbibresource\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")
_STYLE = re.compile(r"\\bibliographystyle\s*\{([^}]*)\}")
_BIBLATEX_UNSORTED = re.compile(r"\\usepackage\s*\[[^\]]*\bsorting\s*=\s*none\b[^\]]*\]\s*\{biblatex\}")
_CITE = re.compile(r"\\(?:no)?(?:cite|citep|citet|parencite|textcite|autocite)\*?\s*(?:\[[^\]]*\]\s*){0,2}\{([^}]*)\}")
_NOCITE_ALL = re.compile(r"\\nocite\s*\{\s*\*\s*\}")
_ENTRY_START = re.compile(r"@\s*([A-Za-z]+)\s*[{(]")
_UNSORTED_STYLES = {"unsrt", "unsrtnat", "ieeetr", "IEEEtran", "unsrturl", "plainnat-unsorted"}


@dataclass(frozen=True, slots=True)
class BibEntry:
    key: str
    kind: str
    fields: dict[str, str]


def _value(text: str, position: int, strings: dict[str, str]) -> tuple[str, int]:
    """A field's value at `position`: `{...}`, `"..."`, a number or an @string, joined by `#`."""
    parts: list[str] = []
    while position < len(text):
        while position < len(text) and text[position] in " \t\r\n":
            position += 1
        character = text[position : position + 1]
        if character == "{":
            depth, start = 0, position
            while position < len(text):
                if text[position] == "\\":
                    position += 2
                    continue
                depth += {"{": 1, "}": -1}.get(text[position], 0)
                position += 1
                if depth == 0:
                    break
            parts.append(text[start + 1 : position - 1])
        elif character == '"':
            end = position + 1
            depth = 0
            while end < len(text) and not (text[end] == '"' and depth == 0):
                depth += {"{": 1, "}": -1}.get(text[end], 0)
                end += 1
            parts.append(text[position + 1 : end])
            position = end + 1
        else:
            found = re.match(r"[A-Za-z0-9_:.\-+]+", text[position:])
            if not found:
                break
            word = found.group(0)
            parts.append(strings.get(word.lower(), word))
            position += len(word)
        while position < len(text) and text[position] in " \t\r\n":
            position += 1
        if text[position : position + 1] != "#":
            break
        position += 1
    return "".join(parts), position


def parse_bib(text: str) -> dict[str, BibEntry]:
    """The entries of a .bib file, by key; @string abbreviations are expanded, @comment and @preamble left out."""
    entries: dict[str, BibEntry] = {}
    strings = {
        month: month.capitalize()
        for month in ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
    }
    position = 0
    while (found := _ENTRY_START.search(text, position)) is not None:
        kind = found.group(1).lower()
        position = found.end()
        if kind in ("comment", "preamble"):
            continue
        if kind == "string":
            name = re.match(r"\s*([A-Za-z0-9_:.\-+]+)\s*=", text[position:])
            if name:
                value, position = _value(text, position + name.end(), strings)
                strings[name.group(1).lower()] = value
            continue
        key = re.match(r"\s*([^,\s]+)\s*,", text[position:])
        if not key:
            continue
        position += key.end()
        fields: dict[str, str] = {}
        while position < len(text):
            name = re.match(r"\s*([A-Za-z][A-Za-z0-9_\-]*)\s*=", text[position:])
            if not name:
                break
            value, position = _value(text, position + name.end(), strings)
            fields[name.group(1).lower()] = " ".join(value.split())
            comma = re.match(r"\s*,", text[position:])
            if not comma:
                break
            position += comma.end()
        entries[key.group(1)] = BibEntry(key.group(1), kind, fields)
    return entries


def _people(names: str) -> list[str]:
    """`Knuth, Donald E. and Lamport, Leslie` as Donald E. Knuth, Leslie Lamport."""
    people = []
    for name in re.split(r"\s+and\s+", names.strip()):
        if "," in name:
            family, _comma, given = name.partition(",")
            name = f"{given.strip()} {family.strip()}".strip()
        if name:
            people.append(name)
    return people


def _family(names: str) -> str:
    people = _people(names)
    return re.sub(r"[{}\\]", "", people[0].split()[-1]).lower() if people else ""


def entry_text(entry: BibEntry) -> str:
    """An entry as most numeric styles show it: authors, title, where it appeared, year (LaTeX text)."""
    fields = entry.fields
    people = _people(fields.get("author") or fields.get("editor", ""))
    authors = ", ".join(people[:-1]) + (" and " if len(people) > 1 else "") + (people[-1] if people else "")
    title = fields.get("title", "")
    if entry.kind in ("book", "phdthesis", "mastersthesis", "manual"):
        title = f"\\emph{{{title}}}" if title else ""
    where = (
        fields.get("journal")
        or fields.get("booktitle")
        or fields.get("publisher")
        or fields.get("school")
        or fields.get("institution", "")
    )
    if where and entry.kind not in ("book",):
        where = f"\\emph{{{where}}}"
    details = [part for part in (fields.get("volume"), fields.get("pages")) if part]
    year = fields.get("year", "")
    pieces = [
        piece
        for piece in (authors, title, ", ".join([where, *details]) if where else ", ".join(details), year)
        if piece
    ]
    return ". ".join(piece.rstrip(".") for piece in pieces) + "." if pieces else entry.key


@dataclass(frozen=True, slots=True)
class Bibliography:
    """The entries the document lists, in their numbered order."""

    entries: tuple[BibEntry, ...]

    @property
    def numbers(self) -> dict[str, int]:
        return {entry.key: number for number, entry in enumerate(self.entries, 1)}


def document_bibliography(source: str, folder: Path) -> Bibliography | None:
    """The bibliography a .tex document's \\bibliography or \\addbibresource names, read from its folder:
    the entries cited (all of them after \\nocite{*}), numbered as its style numbers them. None without one."""
    text = _COMMENT.sub("", source)
    names = [name.strip() for found in _BIBLIOGRAPHY.finditer(text) for name in found.group(1).split(",")]
    names += [found.group(1).strip() for found in _RESOURCE.finditer(text)]
    entries: dict[str, BibEntry] = {}
    for name in names:
        path = folder / (name if name.endswith(".bib") else f"{name}.bib")
        try:
            entries.update(parse_bib(path.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    if not names or not entries:
        return None
    cited: list[str] = []
    for found in _CITE.finditer(text):
        for key in found.group(1).split(","):
            key = key.strip()
            if key in entries and key not in cited:
                cited.append(key)
    if _NOCITE_ALL.search(text):
        cited += [key for key in entries if key not in cited]
    style = _STYLE.search(text)
    unsorted = (style is not None and style.group(1).strip() in _UNSORTED_STYLES) or bool(
        _BIBLATEX_UNSORTED.search(text)
    )
    chosen = [entries[key] for key in cited]
    if not unsorted:
        chosen.sort(
            key=lambda entry: (
                _family(entry.fields.get("author") or entry.fields.get("editor", "")),
                entry.fields.get("year", ""),
                entry.fields.get("title", "").lower(),
            )
        )
    return Bibliography(tuple(chosen))
