"""The lines of an equation's source written on several (a .tex align's rows), for Up and Down.

The linear view is a one-line field, where Up and Down read the whole
source; a source with line breaks moves line by line instead, as a
multi-line text field does, the caret keeping its column where it can.
"""

from __future__ import annotations


def line_at(source: str, caret: int) -> str:
    """The text of the line the caret is on, without its line break."""
    start = source.rfind("\n", 0, caret) + 1
    end = source.find("\n", caret)
    return source[start : len(source) if end < 0 else end]


def line_step(source: str, caret: int, direction: int) -> int | None:
    """The caret on the previous (`direction` -1) or next (1) line, in the same column or at that line's end;
    None on the first or the last line."""
    start = source.rfind("\n", 0, caret) + 1
    column = caret - start
    if direction < 0:
        if start == 0:
            return None
        previous_start = source.rfind("\n", 0, start - 1) + 1
        return min(previous_start + column, start - 1)
    end = source.find("\n", caret)
    if end < 0:
        return None
    following_end = source.find("\n", end + 1)
    following_end = len(source) if following_end < 0 else following_end
    return min(end + 1 + column, following_end)
