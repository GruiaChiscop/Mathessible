"""Fraction styles (Word's stacked/skewed/linear/small) and finding fractions in the source."""

from __future__ import annotations

from dataclasses import dataclass

from mathessible.templates.template_source import TemplateEdit, matching_parens

# Fraction styles, as Word names them, and the UnicodeMath operator of each.
# Linear (U+2215) is an inline "a/b": the converter drops the parens around
# its operands, so `(a+b)∕c` keeps them only as `((a+b))∕c`. "¦" (no bar,
# binomials) is not offered but is still an `mfrac`, so it is counted.
FRACTION_STYLES = {"stacked": "/", "skewed": "⁄", "linear": "∕", "small": "⊘"}
_FRACTION_OPERATORS = {operator: style for style, operator in FRACTION_STYLES.items()} | {"¦": "no bar"}
_ROOT_SIGNS = "√∛∜"


@dataclass(frozen=True, slots=True)
class Fraction:
    """A fraction in the source: `start`..`end` spans both operands."""

    operator: int
    start: int
    end: int
    style: str


def fractions(source: str) -> list[Fraction]:
    """Every fraction, in reading order (an outer one before those inside it)."""
    pairs = matching_parens(source)
    closing_to_opening = {end: start for start, end in pairs.items()}
    found = [
        Fraction(
            index, _numerator_start(source, index, closing_to_opening), _denominator_end(source, index, pairs), style
        )
        for index, character in enumerate(source)
        if (style := _FRACTION_OPERATORS.get(character)) is not None
    ]
    return sorted(found, key=lambda fraction: (fraction.start, -fraction.end))


def fraction_at(source: str, caret: int) -> Fraction | None:
    """The innermost fraction whose operands contain the caret."""
    around = [fraction for fraction in fractions(source) if fraction.start <= caret <= fraction.end]
    return min(around, key=lambda fraction: fraction.end - fraction.start, default=None)


def built_fractions(source: str) -> list[Fraction]:
    """The fractions the converter builds as an `mfrac` (all but linear), in reading order."""
    return [fraction for fraction in fractions(source) if fraction.style != "linear"]


def restyle_fraction(source: str, caret: int, style: str) -> TemplateEdit | None:
    """Change the fraction around the caret to `style` (a FRACTION_STYLES key)."""
    fraction = fraction_at(source, caret)
    if fraction is None:
        return None
    operator = FRACTION_STYLES[style]
    numerator = (fraction.start, fraction.operator)
    denominator = (fraction.operator + 1, fraction.end)
    # (position, removed characters, inserted text), applied right to left.
    edits = [(fraction.operator, 1, operator)]
    for start, end in (numerator, denominator):
        if fraction.style == "linear" and style != "linear" and _double_parens(source, start, end):
            edits += [(start, 1, ""), (end - 1, 1, "")]
        elif style == "linear" and fraction.style != "linear" and _needs_linear_parens(source, start, end):
            edits += [(start, 0, "("), (end, 0, ")")]
    for position, removed, inserted in sorted(edits, reverse=True):
        source = source[:position] + inserted + source[position + removed :]
        if caret > position:
            caret = max(position, caret - removed) + len(inserted)
    return TemplateEdit(source, caret, f"{style} fraction")


def _numerator_start(source: str, operator: int, closing_to_opening: dict[int, int]) -> int:
    start = operator
    if start > 0 and source[start - 1] == ")" and start - 1 in closing_to_opening:
        start = closing_to_opening[start - 1]
    while start > 0 and (source[start - 1].isalnum() or source[start - 1] in _ROOT_SIGNS):
        start -= 1  # A token, a function name before "(x)", or a root sign.
    return start


def _denominator_end(source: str, operator: int, pairs: dict[int, int]) -> int:
    end = operator + 1
    while end < len(source) and source[end] in _ROOT_SIGNS:
        end += 1
    while end < len(source) and source[end].isalnum():
        end += 1
    if end < len(source) and source[end] == "(" and end in pairs:
        end = pairs[end] + 1
    return end


def _is_group(source: str, start: int, end: int) -> bool:
    return end - start >= 2 and source[start] == "(" and matching_parens(source).get(start) == end - 1


def _double_parens(source: str, start: int, end: int) -> bool:
    return _is_group(source, start, end) and _is_group(source, start + 1, end - 1)


def _needs_linear_parens(source: str, start: int, end: int) -> bool:
    """A "(...)" operand holding more than one token loses its visible parens when linear."""
    if not _is_group(source, start, end):
        return False
    content = source[start + 1 : end - 1]
    return bool(content) and not content.isalnum()
