"""Templates and structure edits on a source that may spell symbols as control words.

The template and structure modules scan UnicodeMath symbols (`√`, `▒`,
`■`, ...). The source may instead hold control words (`\\sqrt`, `\\of`,
`\\matrix`): typed by the user, or inserted that way when the
`template_control_words` setting is on. `SourceView` resolves them the way
the converter does (`resolveCW` in UnicodeMathML: `\\[A-Za-z0-9]+` plus one
optional space), so the scanners see symbols, and `edit_in_view` maps an
edit made on that view back onto the real source, written with control
words or symbols.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from .template_source import TemplateEdit

# The control word each template/structure symbol is written as.
CONTROL_WORDS = {
    "√": "sqrt",
    "∛": "cbrt",
    "∜": "qdrt",
    "∫": "int",
    "∬": "iint",
    "∭": "iiint",
    "∮": "oint",
    "∑": "sum",
    "∏": "prod",
    "▒": "of",
    "■": "matrix",
    "┴": "above",
    "┬": "below",
    "→": "rightarrow",
    "⁄": "sdiv",
    "∕": "ldiv",
    "⊘": "ndiv",
    "〖": "begin",
    "〗": "end",
    "█": "eqarray",
    "▭": "boxed",
    "⏞": "overbrace",
    "⏟": "underbrace",
    "‖": "norm",
    "⌊": "lfloor",
    "⌋": "rfloor",
    "⌈": "lceil",
    "⌉": "rceil",
    "⟨": "langle",
    "⟩": "rangle",
    "¦": "atop",
    "┤": "close",
    "⋃": "bigcup",
    "⋂": "bigcap",
}
# Words always followed by a space: what comes next is typed right there
# (`\begin x\end`), and a letter would run into the word (`\beginx`).
_SPACED_WORDS = frozenset({"begin"})
_CONTROL_WORD = re.compile(r"\\([A-Za-z0-9]+) ?")
_WORD_CHARACTER = re.compile(r"[A-Za-z0-9]")
_ENDS_WITH_CONTROL_WORD = re.compile(r"\\[A-Za-z0-9]+$")


@lru_cache(maxsize=1)
def _symbol_table() -> dict[str, str]:
    """Control word -> its single-character symbol, from the converter's own table."""
    table = {word: symbol for symbol, word in CONTROL_WORDS.items()}
    try:
        from .unicodemath import control_words

        converter = control_words()
    except (OSError, ValueError):
        return table
    return {word: symbol for word, symbol in converter.items() if len(symbol) == 1} | table


@dataclass(frozen=True, slots=True)
class SourceView:
    """`text` is `source` with control words resolved; `starts[i]` is the source offset of `text[i]`."""

    source: str
    text: str
    starts: tuple[int, ...]

    def to_source(self, index: int) -> int:
        """The source offset of a view position (before the control word it stands for)."""
        index = max(0, min(index, len(self.text)))
        return self.starts[index] if index < len(self.text) else len(self.source)

    def to_view(self, offset: int) -> int:
        """The view position of a source offset; inside a control word counts as before its symbol."""
        offset = max(0, min(offset, len(self.source)))
        index = 0
        while index < len(self.starts) and self.starts[index] < offset:
            index += 1
        if index > 0 and index <= len(self.text) and self._inside(index - 1, offset):
            return index - 1
        return index

    def _inside(self, index: int, offset: int) -> bool:
        end = self.to_source(index + 1)
        return self.starts[index] < offset < end and end - self.starts[index] > 1


def view_of(source: str) -> SourceView:
    table = _symbol_table()
    text: list[str] = []
    starts: list[int] = []
    position = 0
    for match in _CONTROL_WORD.finditer(source):
        symbol = table.get(match.group(1))
        if symbol is None:
            continue
        for offset in range(position, match.start()):
            text.append(source[offset])
            starts.append(offset)
        text.append(symbol)
        starts.append(match.start())
        position = match.end()
    for offset in range(position, len(source)):
        text.append(source[offset])
        starts.append(offset)
    return SourceView(source, "".join(text), tuple(starts))


def edit_in_view(
    source: str,
    caret: int,
    build: Callable[[str, int], TemplateEdit | None],
    control_words: bool,
) -> TemplateEdit | None:
    """Run a symbol-based edit on the resolved view and apply its change to `source`.

    Only the span the edit changed is rewritten (with control words when
    `control_words`, else symbols); the rest of the source keeps its spelling.
    """
    view = view_of(source)
    edit = build(view.text, view.to_view(caret))
    if edit is None:
        return None
    old, new = view.text, edit.source
    prefix = 0
    while prefix < min(len(old), len(new)) and old[prefix] == new[prefix]:
        prefix += 1
    suffix = 0
    while suffix < min(len(old), len(new)) - prefix and old[-1 - suffix] == new[-1 - suffix]:
        suffix += 1
    start, end = view.to_source(prefix), view.to_source(len(old) - suffix)
    replacement = new[prefix : len(new) - suffix]
    if edit.caret <= prefix:
        caret_in = None
        new_caret = view.to_source(edit.caret)
    elif edit.caret >= len(new) - suffix:
        caret_in = None
        new_caret = view.to_source(edit.caret - len(new) + len(old))
    else:
        caret_in = edit.caret - prefix
        new_caret = 0
    following = source[end:]
    if control_words:
        replacement, caret_in = spell_with_control_words(replacement, caret_in, following)
    if _ENDS_WITH_CONTROL_WORD.search(source[:start]) and _WORD_CHARACTER.match(replacement[:1]):
        # "\alpha" right before an inserted "lim": keep the word from swallowing it.
        replacement = " " + replacement
        caret_in = None if caret_in is None else caret_in + 1
    edited = source[:start] + replacement + following
    if caret_in is not None:
        new_caret = start + caret_in
    elif edit.caret > prefix:
        new_caret += len(edited) - len(source)
    return TemplateEdit(edited, new_caret, edit.announcement)


def spell_with_control_words(text: str, caret: int | None, following: str = "") -> tuple[str, int | None]:
    """Write `text`'s template symbols as control words; `caret` (an offset in `text`) moves along.

    A control word needs a space after it when a letter or digit follows
    (`\\of x`, `\\sdiv b`) or nothing does (the user types there next).
    """
    parts: list[str] = []
    new_caret = caret
    for index, character in enumerate(text):
        word = CONTROL_WORDS.get(character)
        if word is None:
            parts.append(character)
            continue
        after = text[index + 1 : index + 2] or following[:1]
        spaced = not after or _WORD_CHARACTER.match(after) or (word in _SPACED_WORDS and after != " ")
        spelled = f"\\{word}" + (" " if spaced else "")
        if caret is not None and caret > index:
            new_caret += len(spelled) - 1
        parts.append(spelled)
    return "".join(parts), new_caret


def in_view(source: str, caret: int, query: Callable[[str, int], object]) -> object:
    """Run a symbol-based query (e.g. `fraction_at`) on the resolved view."""
    view = view_of(source)
    return query(view.text, view.to_view(caret))
