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

import re
from collections.abc import Callable, Collection, Iterator
from dataclasses import dataclass

from matex.editing.linear_runs import Runs, escape_insertions, inside
from matex.editing.normal_text import text_spans
from matex.editing.source_view import view_of

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


def literal_repair(source: str, literal: Collection[str], runs: Runs = ()) -> BuildRepair:
    """No repair, only `literal` words and linear `runs` as text (what is built when no candidate builds)."""
    return _apply(source, literal_insertions(source, literal) + escape_insertions(source, runs))


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


def _missing_arguments(source: str, runs: Runs = ()) -> list[tuple[int, str]]:
    """Placeholders where an argument is still empty: after a bare `▒`, in `√(&x)`/`√(x&)`.

    Not in linear runs: their characters are escaped, never structures.
    """
    view = view_of(source)
    text = view.text
    insertions: list[tuple[int, str]] = []
    for index, character in enumerate(text):
        if inside(runs, view.to_source(index)):
            continue
        following = text[index + 1 : index + 2]
        if character == "▒" and following in ("", " ", ")", "&", "@"):
            insertions.append((view.to_source(index + 1), PLACEHOLDER))
        if character == "(" and following == "&" and index > 0 and text[index - 1] == "√":
            insertions.append((view.to_source(index + 1), PLACEHOLDER))
        if character == "&" and following in ("", ")") and _in_root(text, index):
            insertions.append((view.to_source(index + 1), PLACEHOLDER))
        if character == "¦":
            # A binomial with an empty top or bottom: `(¦k)`, `(n¦)`.
            if index == 0 or text[index - 1] in "(&@":
                insertions.append((view.to_source(index), PLACEHOLDER))
            if following in ("", ")", "&", "@"):
                insertions.append((view.to_source(index + 1), PLACEHOLDER))
    # An empty normal text `""` (Normal Text just turned on) is a total failure; `"​"` is clean.
    insertions += [(start, PLACEHOLDER) for start, end in text_spans(source, runs) if start == end]
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


def _closers(source: str, runs: Runs = ()) -> str:
    """What closes everything left open at the end: a quote, then ")" per open "(", then "|".

    Linear runs open nothing: their characters are escaped.
    """
    if runs:
        source = "".join(character for index, character in enumerate(source) if not inside(runs, index))
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


def _escape_insertions(source: str, caret: int | None) -> list[tuple[int, str]]:
    """A backslash just typed before a separator or bracket (`1&x \\@&`): build it as a literal one.

    UnicodeMath's `\\` escapes the next character, so the control word the
    user is starting would turn the case's `@`, a cell's `&` or a `)` into
    plain text until its first letter, and the structure fall apart
    meanwhile. Only right before the caret: `\\(` typed on purpose stays an
    escaped paren once the caret has moved past it.
    """
    if caret is None or not 0 < caret < len(source) or source[caret - 1] != "\\":
        return []
    run = 0
    while run < caret and source[caret - 1 - run] == "\\":
        run += 1
    following = source[caret]
    if run % 2 == 0 or (following.isascii() and following.isalnum()):
        return []
    return [(caret, "\\")]


# Breaks a control word for the converter, which resolves `\\word` before anything
# else, even escaped or quoted: `"\\<ZWNJ>alpha"` is the text "\\alpha".
_WORD_BREAK = "\u200c"
_CONTROL_WORD = re.compile(r"\\([A-Za-z0-9]+)")


def literal_insertions(source: str, words: Collection[str]) -> list[tuple[int, str]]:
    """Each `\\word` of `words` (deleted from Math AutoCorrect) as quoted text, as Word leaves it."""
    if not words:
        return []
    insertions: list[tuple[int, str]] = []
    for match in _CONTROL_WORD.finditer(source):
        if match.group(1) in words:
            insertions += [(match.start(), '"'), (match.start() + 1, _WORD_BREAK), (match.end(), '"')]
    return insertions


def literal_text(source: str, words: Collection[str]) -> str:
    """`source` with `words` written as text, for the converter (idempotent: a broken word stays broken)."""
    return _apply(source, literal_insertions(source, words)).text


def repairs(
    source: str, caret: int | None = None, literal: Collection[str] = (), runs: Runs = ()
) -> Iterator[BuildRepair]:
    """Candidate repairs, least invasive first: none, missing arguments, then closing what is open.

    With `caret`, a backslash just typed there is built as a literal one
    in every candidate (`_escape_insertions`); `literal` words are text in
    every candidate (`literal_insertions`), and so are the linear `runs`
    (`linear_runs.escape_insertions`).
    """
    escape = _escape_insertions(source, caret) + literal_insertions(source, literal) + escape_insertions(source, runs)
    yield _apply(source, escape) if escape else BuildRepair(source, source)
    arguments = escape + _missing_arguments(source, runs)
    if len(arguments) > len(escape):
        yield _apply(source, arguments)
    closers = _closers(source, runs)
    if closers:
        yield _apply(source, arguments + [(len(source), closers)])


def repair_for_build(
    source: str,
    builds: Callable[[str], bool],
    caret: int | None = None,
    literal: Collection[str] = (),
    runs: Runs = (),
) -> BuildRepair | None:
    """The first candidate `builds` accepts (no total failure), or None if none does."""
    for candidate in repairs(source, caret, literal, runs):
        if builds(candidate.text):
            return candidate
    return None
