from __future__ import annotations

import re

_WORD_CHAR = re.compile(r"\w")


def previous_word_boundary(source: str, position: int) -> int:
    """Return the caret position one "word" to the left of `position`.

    A word is a run of letters/digits/underscore; any other non-space
    character (an operator, a delimiter, ...) is its own word, matching how
    UnicodeMath packs meaning into single symbols.
    """
    index = max(0, min(position, len(source)))
    while index > 0 and source[index - 1].isspace():
        index -= 1
    if index == 0:
        return 0
    if _WORD_CHAR.match(source[index - 1]):
        while index > 0 and _WORD_CHAR.match(source[index - 1]):
            index -= 1
    else:
        index -= 1
    return index


def next_word_boundary(source: str, position: int) -> int:
    """Return the caret position one "word" to the right of `position`."""
    length = len(source)
    index = max(0, min(position, length))
    while index < length and source[index].isspace():
        index += 1
    if index == length:
        return length
    if _WORD_CHAR.match(source[index]):
        while index < length and _WORD_CHAR.match(source[index]):
            index += 1
    else:
        index += 1
    return index
