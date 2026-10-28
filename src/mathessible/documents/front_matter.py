"""A document's header, footer and equation language, kept in the Markdown as front matter.

Front matter is the block Pandoc, Jekyll and GitHub read at the very top of
a Markdown file, between two `---` lines:

    ---
    header: Calculus notes
    footer: Chapter 2
    math: latex
    ---

`math: latex` makes the document's equations LaTeX, stored as written;
without it they are UnicodeMath. Only simple `key: value` lines are read
(a value plain, or quoted as YAML and JSON quote it); a block holding
anything else is not front matter but the document's own text (a rule, a
heading). Other keys are kept as they are.
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


# A document's equation languages, as `math:` names them.
UNICODEMATH = "unicodemath"
LATEX = "latex"


def _fields(source: str) -> dict[str, str]:
    front = _front_matter(source)
    fields: dict[str, str] = {}
    for line in front.lines if front else ():
        match = _FIELD.match(line)
        if match is not None:
            fields[match.group(1).lower()] = _value(match.group(2))
    return fields


def header_and_footer(source: str) -> HeaderFooter:
    fields = _fields(source)
    return HeaderFooter(fields.get("header", ""), fields.get("footer", ""))


def equation_language(source: str) -> str:
    """LATEX when the front matter says `math: latex`, else UNICODEMATH."""
    return LATEX if _fields(source).get("math", "").strip().lower() == LATEX else UNICODEMATH


def body_start(source: str) -> int:
    """Where the document's text starts: after its front matter, if it has one."""
    front = _front_matter(source)
    return 0 if front is None else front.end


def body(source: str) -> str:
    """The document without its front matter, for rendering and export."""
    return source[body_start(source) :]


def _with_fields(source: str, values: dict[str, str]) -> str:
    """The document with these front matter fields ("" removes one), its other front matter kept."""
    front = _front_matter(source)

    def ours(line: str) -> bool:
        match = _FIELD.match(line)
        return match is not None and match.group(1).lower() in values

    kept = [line for line in (front.lines if front else ()) if not ours(line)]
    fields = [f"{key}: {_quoted(value)}" for key, value in values.items() if value]
    text = source[front.end :] if front else source
    lines = fields + kept
    if not any(line.strip() for line in lines):
        return text
    return "---\n" + "\n".join(lines) + "\n---\n" + text


def with_header_and_footer(source: str, header: str, footer: str) -> str:
    """The document with this header and footer ("" removes one), its other front matter kept."""
    return _with_fields(source, {"header": header, "footer": footer})


def with_equation_language(source: str, language: str) -> str:
    """The document marked as LaTeX (`math: latex`) or, for UNICODEMATH, unmarked; nothing else changed."""
    return _with_fields(source, {"math": LATEX if language == LATEX else ""})
