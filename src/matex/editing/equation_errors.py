"""What is wrong with a UnicodeMath source, and where: the equation editor's error list.

The converter only colors what it cannot use (`#F01` on a dangling token,
`#F00` around the whole source when nothing parses) and gives no
position. The source is scanned here instead, on the control-word view
(`source_view`, so `\\sqrt(` counts as `√(`), and every error gets a real
source span and a sentence, like a code editor's problem list.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from matex.editing.source_view import view_of

_OPENERS = "([{⟨〖├"
_CLOSERS = ")]}⟩〗┤"
# Any opener closes with any closer in UnicodeMath (`[0,1)`, `{■(...)┤`).
_NAMES = {
    "(": "parenthesis",
    ")": "parenthesis",
    "[": "bracket",
    "]": "bracket",
    "{": "brace",
    "}": "brace",
    "⟨": "angle bracket",
    "⟩": "angle bracket",
    "〖": "group",
    "〗": "group",
    "├": "bracket",
    "┤": "bracket",
}
# Operators that need something after them, and what is missing then.
_NEEDS_AFTER = {
    "/": "fraction without denominator",
    "^": "superscript without anything after ^",
    "_": "subscript without anything after _",
    "┴": "nothing above the operator",
    "┬": "nothing below the operator",
    "▒": "empty integrand or argument",
}
_ENDS_OPERAND = frozenset(_CLOSERS) | {"&", "@"}
# What the parser stopping on a character usually means.
_UNEXPECTED = {
    "&": "& outside a matrix or equation array",
    "@": "@ outside a matrix or equation array",
}


@dataclass(frozen=True, slots=True)
class EquationError:
    """`start`..`end` in real-source offsets (the span to highlight)."""

    start: int
    end: int
    message: str

    def describe(self, source: str) -> str:
        """The list text: "unclosed parenthesis, at character 3: (a+b"."""
        context = source[max(0, self.start - 6) : self.end + 6].strip() or source[self.start : self.end]
        return f"{self.message}, at character {self.start + 1}: {context}"


def find_errors(
    source: str,
    total_failure: bool = False,
    control_words: Mapping[str, str] | None = None,
    caret: int | None = None,
    stopped: tuple[int, str | None] | None = None,
) -> list[EquationError]:
    """Every error found, in source order.

    `total_failure`: the converter could not parse anything (`#F00`); then
    an odd `|` is reported too (on its own it may be a "given" bar), and if
    nothing explains the failure, the whole source is. `control_words` (the
    converter's table) finds unknown commands; one ending at `caret` is
    still being typed and is left alone. `stopped` is where the
    converter's parser gave up (source offset, what it found there, None
    at the end): reported when nothing found here already covers it, so
    no failure goes unexplained.
    """
    view = view_of(source)
    text = view.text
    errors: list[EquationError] = []

    def add(start: int, end: int, message: str) -> None:
        errors.append(EquationError(view.to_source(start), view.to_source(end), message))

    stack: list[int] = []
    quote: int | None = None
    for index, character in enumerate(text):
        if character == '"':
            quote = index if quote is None else None
            continue
        if quote is not None:
            continue
        if character in _OPENERS:
            stack.append(index)
        elif character in _CLOSERS:
            if stack:
                stack.pop()
            else:
                add(index, index + 1, f"closing {_NAMES[character]} without an opening one")
    for index in stack:
        add(index, index + 1, f"unclosed {_NAMES[text[index]]}")
    if quote is not None:
        add(quote, quote + 1, "text not closed: missing quote")

    for index, character in enumerate(text):
        if character not in _NEEDS_AFTER or _quoted(text, index):
            continue
        following = _next_visible(text, index + 1)
        if following is None or following in _ENDS_OPERAND:
            add(index, index + 1, _NEEDS_AFTER[character])
        if character == "/":
            previous = _previous_visible(text, index - 1)
            if previous is None or previous in _OPENERS or previous in "&@":
                add(index, index + 1, "fraction without numerator")
    for index in range(len(text) - 2):
        if text[index : index + 3] == "√(&":
            add(index, index + 3, "root without an index")

    if total_failure and text.count("|") % 2 == 1:
        last = text.rindex("|")
        add(last, last + 1, "absolute value bar without its pair")

    if control_words is not None:
        errors.extend(_unknown_control_words(source, control_words, caret))

    if total_failure and stopped is not None:
        position, found = stopped
        end = len(source.rstrip())
        if found is None or position >= len(source):
            # The source ended too early: unless an error at its end says why already.
            if not any(error.end >= end for error in errors):
                errors.append(EquationError(max(0, end - 1), end, "the equation ends too early"))
        elif not any(error.start <= position < max(error.end, error.start + 1) for error in errors):
            message = _UNEXPECTED.get(found, f"cannot continue with {found}")
            errors.append(EquationError(position, position + 1, message))
    if total_failure and not errors:
        errors.append(EquationError(0, len(source), "the equation cannot be read"))
    errors.sort(key=lambda error: (error.start, error.end))
    return errors


def _unknown_control_words(source: str, table: Mapping[str, str], caret: int | None) -> list[EquationError]:
    found: list[EquationError] = []
    index = 0
    while index < len(source):
        if source[index] != "\\":
            index += 1
            continue
        end = index + 1
        while end < len(source) and source[end].isascii() and source[end].isalnum():
            end += 1
        word = source[index + 1 : end]
        if word and word not in table and end != caret:
            found.append(EquationError(index, end, f"unknown command \\{word}"))
        index = max(end, index + 2)  # "\\" escapes the next character.
    return found


def _quoted(text: str, index: int) -> bool:
    return text[:index].count('"') % 2 == 1


def _next_visible(text: str, index: int) -> str | None:
    while index < len(text) and text[index] in " ​":
        index += 1
    return text[index] if index < len(text) else None


def _previous_visible(text: str, index: int) -> str | None:
    while index >= 0 and text[index] in " ​":
        index -= 1
    return text[index] if index >= 0 else None
