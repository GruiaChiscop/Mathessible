"""Normal text in an equation, as Word's Normal Text button: UnicodeMath's quoted text.

`"for all "x` is the text "for all " and then the variable x: the
converter gives the quoted part as `mtext`, upright, spaces kept, and
MathCAT reads it as words. `toggle_normal_text` is the one command that
starts, ends or splits it: it puts a quote at each end of the selection
(or a pair at the caret) and drops the empty pairs that leaves, so the
same key starts text in math, gets back to math at the end of a text,
or turns a selected part of a text back into math.
"""

from __future__ import annotations

from collections.abc import Collection

from matex.templates.template_source import TemplateEdit

Span = tuple[int, int]


def _escaped(source: str, index: int) -> bool:
    count = 0
    while index - count > 0 and source[index - count - 1] == "\\":
        count += 1
    return count % 2 == 1


def _quotes(source: str, ignored: Collection[Span] = ()) -> list[int]:
    """The quotes that delimit text: not escaped (`\\"` is a literal quote), not in `ignored` ranges."""
    return [
        index
        for index, character in enumerate(source)
        if character == '"' and not _escaped(source, index) and not any(start <= index < end for start, end in ignored)
    ]


def text_spans(source: str, ignored: Collection[Span] = ()) -> list[Span]:
    """The content of each quoted text, between its quotes; an unclosed one runs to the end.

    `ignored` are ranges whose quotes are not delimiters (linear runs: escaped there).
    """
    quotes = _quotes(source, ignored)
    spans = [(quotes[index] + 1, quotes[index + 1]) for index in range(0, len(quotes) - 1, 2)]
    if len(quotes) % 2:
        spans.append((quotes[-1] + 1, len(source)))
    return spans


def in_text(source: str, caret: int, ignored: Collection[Span] = ()) -> bool:
    """Whether typing at `caret` goes into a normal text (between its quotes)."""
    return any(start <= caret <= end for start, end in text_spans(source, ignored))


def toggle_normal_text(source: str, caret: int, selection: Span | None = None) -> TemplateEdit:
    """Normal Text on or off at the caret, or for a selection: a quote at each end, empty pairs dropped.

    Outside text: `""` with the caret inside, or the selection quoted. In a
    text: at its end the caret goes past the closing quote (math again), in
    its middle the text is split there, and a selection in it becomes math.
    """
    start, end = selection if selection is not None else (caret, caret)
    updated = source[:start] + '"' + source[start:end] + '"' + source[end:]
    # Right after what was selected (inside the new text, or after the part made math again).
    new_caret = end + 1
    updated, new_caret = _drop_empty_pairs(updated, new_caret, keep_at=None if selection else new_caret)
    mode = "normal text" if in_text(updated, new_caret) else "math"
    return TemplateEdit(updated, new_caret, f"{mode}, {source[start:end]}" if selection else mode)


def _drop_empty_pairs(source: str, caret: int, keep_at: int | None) -> tuple[str, int]:
    """Remove each empty `""` text, except the one the caret was just put in (`keep_at`),
    and join texts that touch (`"ab""x"` is `"abx"`)."""
    while True:
        quotes = _quotes(source)
        pairs = [(quotes[index], quotes[index + 1]) for index in range(0, len(quotes) - 1, 2)]
        empty = next(
            ((opening, closing) for opening, closing in pairs if closing == opening + 1 and keep_at != opening + 1),
            None,
        )
        touching = next(
            (
                (left[1], right[0])
                for left, right in zip(pairs, pairs[1:], strict=False)
                if right[0] == left[1] + 1 and keep_at != right[0]  # Not the split just made at the caret.
            ),
            None,
        )
        found = empty or touching
        if found is None:
            return source, caret
        first, second = found
        source = source[:first] + source[first + 1 : second] + source[second + 1 :]
        if caret > second:
            caret -= 2
        elif caret > first:
            caret = first if empty else caret - 1
        if keep_at is not None and keep_at > second:
            keep_at -= 2
