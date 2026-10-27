"""A document's header and footer, kept in the Markdown as front matter.

Front matter is the block Pandoc, Jekyll and GitHub read at the very top of
a Markdown file, between two `---` lines:

    ---
    header: Calculus notes
    footer: Chapter 2
    ---

Only simple `key: value` lines are read (a value plain, or quoted as YAML
and JSON quote it); a block holding anything else is not front matter but
the document's own text (a rule, a heading). Keys other than the header and
footer are kept as they are.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

_FENCE = re.compile(r"^---[ \t]*$")
_CLOSE = re.compile(r"^(---|\.\.\.)[ \t]*$")
_FIELD = re.compile(r"^([A-Za-z][\w-]*):(?:[ \t]+(.*?))?[ \t]*$")
_PLAIN = re.compile(r"^[^\s\"'#&*!|>%@`\[\]{},:?-][^#]*$")


@dataclass(frozen=True, slots=True)
class HeaderFooter:
    header: str = ""
    footer: str = ""


@dataclass(frozen=True, slots=True)
class _FrontMatter:
    lines: tuple[str, ...]  # The lines between the fences.
    end: int  # Where the document's text starts.


def _value(text: str | None) -> str:
    text = (text or "").strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        try:
            value = json.loads(text)
        except ValueError:
            return text
        return value if isinstance(value, str) else text
    if len(text) >= 2 and text[0] == text[-1] == "'":
        return text[1:-1].replace("''", "'")
    return text


def _quoted(value: str) -> str:
    """The value as written: plain where YAML reads it back unchanged, else double-quoted."""
    if _PLAIN.match(value) and value == value.strip() and ": " not in value:
        return value
    return json.dumps(value, ensure_ascii=False)


def _front_matter(source: str) -> _FrontMatter | None:
    lines = source.split("\n")
    if not lines or not _FENCE.match(lines[0]):
        return None
    for number in range(1, len(lines)):
        line = lines[number]
        if _CLOSE.match(line):
            if number == 1:
                return None  # "---" twice: rules, not front matter.
            end = sum(len(text) + 1 for text in lines[: number + 1])
            return _FrontMatter(tuple(lines[1:number]), min(end, len(source)))
        if line.strip() and not line.lstrip().startswith("#") and not _FIELD.match(line):
            return None
    return None


def header_and_footer(source: str) -> HeaderFooter:
    front = _front_matter(source)
    if front is None:
        return HeaderFooter()
    fields: dict[str, str] = {}
    for line in front.lines:
        match = _FIELD.match(line)
        if match is not None:
            fields[match.group(1).lower()] = _value(match.group(2))
    return HeaderFooter(fields.get("header", ""), fields.get("footer", ""))


def body_start(source: str) -> int:
    """Where the document's text starts: after its front matter, if it has one."""
    front = _front_matter(source)
    return 0 if front is None else front.end


def body(source: str) -> str:
    """The document without its front matter, for rendering and export."""
    return source[body_start(source) :]


def with_header_and_footer(source: str, header: str, footer: str) -> str:
    """The document with this header and footer ("" removes one), its other front matter kept."""
    front = _front_matter(source)
    kept = [line for line in (front.lines if front else ()) if not _is_ours(line)]
    fields = [f"{key}: {_quoted(value)}" for key, value in (("header", header), ("footer", footer)) if value]
    text = source[front.end :] if front else source
    lines = fields + kept
    if not any(line.strip() for line in lines):
        return text
    return "---\n" + "\n".join(lines) + "\n---\n" + text


def _is_ours(line: str) -> bool:
    match = _FIELD.match(line)
    return match is not None and match.group(1).lower() in ("header", "footer")
