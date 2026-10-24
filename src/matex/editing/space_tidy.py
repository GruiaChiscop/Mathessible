"""Spaces that change nothing, removed as Word's linear format has none.

A space in UnicodeMath may end an operand (`a_1 b`: b is not in the
subscript), end a control word (`\\alpha b`) or be no more than typing
(`a^b^c  `, two spaces that built the chain). Python does not decide which:
a space is extra when the converter gives the same MathML without it.
Spaces in a normal text (`"for all "`) are the text's own and stay, and
so does a space after a word (`sin x`, `ln \\begin`): the converter reads
`sinx` the same, but the linear view would then read "sinx" as one word,
where Word writes an invisible function application.
"""

from __future__ import annotations

from collections.abc import Callable

from matex.editing.normal_text import text_spans


def tidy_spaces(source: str, convert: Callable[[str], str | None]) -> tuple[str, tuple[int, ...]]:
    """`source` without the spaces that change nothing, and where they were (offsets in `source`).

    `convert` gives the MathML for a source (None when it cannot); each
    space is tried from the last to the first, against the MathML of the
    whole original, so a removal never changes what the equation is.
    """
    original = convert(source)
    if original is None:
        return source, ()
    texts = text_spans(source)
    current = source
    removed: list[int] = []
    for index in range(len(source) - 1, -1, -1):
        if source[index] != " " or (index > 0 and source[index - 1] == "\\"):
            continue  # Not a space, or an escaped one (`\ `), which is a visible space.
        if any(start <= index < end for start, end in texts):
            continue
        followed = current[index + 1 : index + 2] not in ("", " ")
        if followed and index > 1 and source[index - 1].isalpha() and source[index - 2].isalpha():
            continue  # After a word, before something: kept for reading (`sin x`, not `sinx`).
        candidate = current[:index] + current[index + 1 :]
        if convert(candidate) == original:
            current = candidate
            removed.append(index)
    return current, tuple(sorted(removed))


def caret_after_tidy(caret: int, removed: tuple[int, ...]) -> int:
    """The caret in the tidied source: one less for each space removed before it."""
    return caret - sum(1 for index in removed if index < caret)
