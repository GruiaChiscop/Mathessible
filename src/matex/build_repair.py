"""Keep a half-typed equation buildable: fill in what is missing, only for building.

Some sources the converter cannot build at all (a total failure,
`mathcolor="#F00"` around the whole input) while the user is in the middle
of typing them: an n-ary `▒` with nothing after it yet, an empty root
index or radicand (`√(&x)`), an open quote, `|` or matrix. Professional
mode builds a *repaired* text instead, never shown as source: a zero-width
space (U+200B, a clean empty argument to the converter) where an argument
is missing, closing characters at the end. The real source is not
changed; `BuildRepair` maps offsets between the two, so the source map and
editing keep working in real-source terms.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from .source_view import view_of

PLACEHOLDER = "​"


@dataclass(frozen=True, slots=True)
class BuildRepair:
    """`text` is `source` with `insertions` ((real offset, inserted text), sorted) applied."""

    source: str
    text: str
    insertions: tuple[tuple[int, str], ...] = ()

    def to_real(self, offset: int) -> int:
        """A repaired offset in real-source terms (inside an insertion: where it was inserted)."""
        shift = 0
        for position, inserted in self.insertions:
            start = position + shift
            if offset <= start:
                break
            if offset < start + len(inserted):
                return position
            shift += len(inserted)
        return max(0, min(len(self.source), offset - shift))

    def to_repaired(self, offset: int) -> int:
        """A real offset in repaired terms; at an insertion point, before what was inserted."""
        shift = sum(len(inserted) for position, inserted in self.insertions if position < offset)
        return offset + shift


def _apply(source: str, insertions: list[tuple[int, str]]) -> BuildRepair:
    ordered = tuple(sorted(insertions, key=lambda insertion: insertion[0]))
    parts: list[str] = []
    previous = 0
    for position, inserted in ordered:
        parts.append(source[previous:position])
        parts.append(inserted)
        previous = position
    parts.append(source[previous:])
    return BuildRepair(source, "".join(parts), ordered)


def _missing_arguments(source: str) -> list[tuple[int, str]]:
    """Placeholders where an argument is still empty: after a bare `▒`, in `√(&x)`/`√(x&)`."""
    view = view_of(source)
    text = view.text
    insertions: list[tuple[int, str]] = []
    for index, character in enumerate(text):
        following = text[index + 1 : index + 2]
        if character == "▒" and following in ("", " ", ")", "&", "@"):
            insertions.append((view.to_source(index + 1), PLACEHOLDER))
        if character == "(" and following == "&" and index > 0 and text[index - 1] == "√":
            insertions.append((view.to_source(index + 1), PLACEHOLDER))
        if character == "&" and following in ("", ")") and _in_root(text, index):
            insertions.append((view.to_source(index + 1), PLACEHOLDER))
    return insertions


def _in_root(text: str, index: int) -> bool:
    depth = 0
    for position in range(index - 1, -1, -1):
        if text[position] == ")":
            depth += 1
        elif text[position] == "(":
            if depth == 0:
                return position > 0 and text[position - 1] == "√"
            depth -= 1
    return False


def _closers(source: str) -> str:
    """What closes everything left open at the end: a quote, then ")" per open "(", then "|"."""
    quoted = source.count('"') % 2 == 1
    depth = 0
    inside_quote = False
    for character in source:
        if character == '"':
            inside_quote = not inside_quote
        elif not inside_quote and character == "(":
            depth += 1
        elif not inside_quote and character == ")" and depth:
            depth -= 1
    bars = source.count("|") % 2 == 1
    return ('"' if quoted else "") + ")" * depth + ("|" if bars else "")


def repairs(source: str) -> Iterator[BuildRepair]:
    """Candidate repairs, least invasive first: none, missing arguments, then closing what is open."""
    yield BuildRepair(source, source)
    arguments = _missing_arguments(source)
    if arguments:
        yield _apply(source, arguments)
    closers = _closers(source)
    if closers:
        yield _apply(source, arguments + [(len(source), closers)])


def repair_for_build(source: str, builds: Callable[[str], bool]) -> BuildRepair | None:
    """The first candidate `builds` accepts (no total failure), or None if none does."""
    for candidate in repairs(source):
        if builds(candidate.text):
            return candidate
    return None
