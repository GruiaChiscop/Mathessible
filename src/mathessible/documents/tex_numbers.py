"""A LaTeX document's numbers, as LaTeX would give them, for `\\ref`, `\\eqref` and `\\cite` in its preview.

LaTeX numbers its sections, equations, figures and tables as it reads the
file, and `\\label{key}` names the number before it; `\\ref{key}` then reads
it back. `tex_markdown` writes a .tex file as Markdown, so it numbers them
here first, in one pass: unstarred sections (1, 1.1; 1.1 under a
chapter), equations (`equation` and `multline` one number, `align`,
`gather`, `eqnarray` and the like one per row unless `\\nonumber`/`\\notag`,
or a row's own `\\tag{...}`), and figures and tables by their `\\caption`.
`\\bibitem{key}` numbers the `thebibliography` entries, in their order.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_COMMENT = re.compile(r"(?<!\\)%.*$", re.MULTILINE)
_LEVELS = ("chapter", "section", "subsection", "subsubsection")
_ONE_NUMBER = {"equation", "multline"}
_ROW_NUMBERS = {"align", "gather", "eqnarray", "flalign", "alignat"}
_FLOATS = {"figure": "figure", "table": "table"}
_TOKEN = re.compile(
    r"\\(?P<heading>chapter|section|subsection|subsubsection)(?P<star>\*?)(?![A-Za-z])"
    r"|\\begin\s*\{(?P<begin>[^}]*)\}"
    r"|\\end\s*\{(?P<end>[^}]*)\}"
    r"|\\caption(?![A-Za-z])"
    r"|\\label\s*\{(?P<label>[^}]*)\}"
    r"|\\tag\*?\s*\{(?P<tag>[^}]*)\}"
    r"|\\(?P<nonumber>nonumber|notag)(?![A-Za-z])"
    r"|\\bibitem(?:\[[^\]]*\])?\s*\{(?P<bibitem>[^}]*)\}"
    r"|(?P<row>\\\\)"
)


@dataclass
class TexNumbers:
    """Each label's number, the numbered headings' and captions' numbers in order, each numbered
    `equation`'s number by where it begins, and each bibliography entry's number by its key."""

    labels: dict[str, str] = field(default_factory=dict)
    headings: list[str] = field(default_factory=list)
    captions: list[str] = field(default_factory=list)
    equations: dict[int, str] = field(default_factory=dict)
    citations: dict[str, int] = field(default_factory=dict)


@dataclass
class _Row:
    labels: list[str] = field(default_factory=list)
    tag: str | None = None
    numbered: bool = True


def tex_numbers(source: str) -> TexNumbers:
    """The document's numbers. Comments are left out (their length kept, so that positions hold)."""
    text = _COMMENT.sub(lambda found: " " * len(found.group(0)), source)
    begin = text.find("\\begin{document}")
    numbers = TexNumbers()
    sections = [0] * len(_LEVELS)
    has_chapters = "\\chapter" in text
    counters = {"equation": 0, "figure": 0, "table": 0}
    environments: list[str] = []  # The environments open, innermost last.
    row: _Row | None = None  # The equation row being read, in a numbered environment.
    row_start = 0
    last = ""  # What a \label names: the last number given.

    def finish_row() -> None:
        nonlocal row, last
        if row is None:
            return
        if row.tag is not None:
            number = row.tag
        elif row.numbered:
            counters["equation"] += 1
            number = str(counters["equation"])
        else:
            number = ""
        if number and environments and environments[-1].rstrip("*") in _ONE_NUMBER:
            numbers.equations[row_start] = number
        for label in row.labels:
            numbers.labels[label] = number
        last = number or last
        row = None

    for found in _TOKEN.finditer(text, max(begin, 0)):
        if found.group("heading"):
            if found.group("star"):
                continue
            level = _LEVELS.index(found.group("heading"))
            sections[level] += 1
            sections[level + 1 :] = [0] * (len(_LEVELS) - level - 1)
            first = 0 if has_chapters else 1
            last = ".".join(str(count) for count in sections[first : level + 1]) if level >= first else ""
            numbers.headings.append(last)
        elif found.group("begin") is not None:
            name = found.group("begin").strip()
            environments.append(name)
            base = name.rstrip("*")
            if base in _ONE_NUMBER | _ROW_NUMBERS:
                row = _Row(numbered=not name.endswith("*"))
                row_start = found.start()
        elif found.group("end") is not None:
            name = found.group("end").strip()
            if name.rstrip("*") in _ONE_NUMBER | _ROW_NUMBERS:
                finish_row()
            if name in environments:
                del environments[len(environments) - 1 - environments[::-1].index(name)]
        elif found.group(0) == "\\caption":
            kind = next(
                (_FLOATS[name.rstrip("*")] for name in reversed(environments) if name.rstrip("*") in _FLOATS), None
            )
            if kind is not None:
                counters[kind] += 1
                last = str(counters[kind])
                numbers.captions.append(last)
        elif found.group("label") is not None:
            if row is not None:
                row.labels.append(found.group("label").strip())
            else:
                numbers.labels[found.group("label").strip()] = last
        elif found.group("tag") is not None and row is not None:
            row.tag = found.group("tag").strip()
        elif found.group("nonumber") and row is not None:
            row.numbered = False
        elif found.group("bibitem") is not None:
            numbers.citations.setdefault(found.group("bibitem").strip(), len(numbers.citations) + 1)
        elif found.group("row") and row is not None and environments[-1].rstrip("*") in _ROW_NUMBERS:
            finish_row()  # A row of align and its kind ends: the next has a number of its own.
            row = _Row(numbered=not environments[-1].endswith("*"))
    return numbers
