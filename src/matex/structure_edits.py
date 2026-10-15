"""Changing an existing root or n-ary operator: its index, its limits.

Like the fraction styles, these rewrite the UnicodeMath source; in
professional mode the editor maps MathCAT's node back by order (the n-th
`msqrt`/`mroot` is the n-th root sign, the n-th `:nary` mrow the n-th n-ary
operator), so `roots` and `nary_operators` list them in reading order.
"""

from __future__ import annotations

from dataclasses import dataclass

from .math_templates import NARY_LABELS
from .template_source import TemplateEdit, matching_parens, operand_end

ROOT_SIGNS = "√∛∜"


@dataclass(frozen=True, slots=True)
class Root:
    """A root sign (`character` at offset `sign`) and its radicand, `start`..`end`.

    `grouped` when the radicand is a "(...)" (then `start`/`end` are inside
    the parens); `separator` is the offset of the index's `&`, if any.
    """

    sign: int
    character: str
    start: int
    end: int
    grouped: bool
    separator: int | None

    @property
    def has_index(self) -> bool:
        return self.separator is not None or self.character != "√"

    @property
    def outer_end(self) -> int:
        return self.end + 1 if self.grouped else self.end


def roots(source: str) -> list[Root]:
    """Every root, in reading order (an outer one before those inside it)."""
    pairs = matching_parens(source)
    found: list[Root] = []
    for index, character in enumerate(source):
        if character not in ROOT_SIGNS:
            continue
        after = index + 1
        if after < len(source) and source[after] == "(" and after in pairs:
            closing = pairs[after]
            separator = _top_level_ampersand(source, after + 1, closing, pairs) if character == "√" else None
            found.append(Root(index, character, after + 1, closing, True, separator))
            continue
        end = after
        while end < len(source) and source[end].isalnum():
            end += 1
        found.append(Root(index, character, after, end, False, None))
    return found


def root_at(source: str, caret: int) -> Root | None:
    """The innermost root whose sign or radicand holds the caret."""
    around = [root for root in roots(source) if root.sign <= caret <= root.outer_end]
    return max(around, key=lambda root: root.sign, default=None)


def add_root_index(source: str, caret: int) -> TemplateEdit | None:
    """`√(x)`/`√x` → `√(&x)`, caret in the (empty) index. An empty index is a parse error until typed."""
    root = root_at(source, caret)
    if root is None or root.has_index:
        return None
    radicand = source[root.start : root.end]
    edited = source[: root.sign] + f"√(&{radicand})" + source[root.outer_end :]
    return TemplateEdit(edited, root.sign + 2, "root with index, empty index")


def remove_root_index(source: str, caret: int) -> TemplateEdit | None:
    """`√(n&x)`, `∛(x)`, `∜x` → a square root of the same radicand, caret at its end."""
    root = root_at(source, caret)
    if root is None or not root.has_index:
        return None
    radicand_start = root.separator + 1 if root.separator is not None else root.start
    radicand = source[radicand_start : root.end]
    replacement = f"√({radicand})" if root.grouped else f"√{radicand}"
    edited = source[: root.sign] + replacement + source[root.outer_end :]
    caret = root.sign + len(replacement) - (1 if root.grouped else 0)
    return TemplateEdit(edited, caret, "square root, index removed")


@dataclass(frozen=True, slots=True)
class NaryOperator:
    """`symbol` is the operator's offset; its limits run to `limits_end` (the `▒`, if any, follows)."""

    symbol: int
    limits_end: int
    end: int

    @property
    def has_limits(self) -> bool:
        return self.limits_end > self.symbol + 1


def nary_operators(source: str) -> list[NaryOperator]:
    """Every n-ary operator the converter builds as one (limits or a `▒`), in reading order."""
    pairs = matching_parens(source)
    found: list[NaryOperator] = []
    for index, character in enumerate(source):
        if character not in NARY_LABELS:
            continue
        limits_end = index + 1
        for connector in "_^":
            if limits_end < len(source) and source[limits_end] == connector:
                limits_end = _script_end(source, limits_end + 1, pairs)
        has_marker = source[limits_end : limits_end + 1] == "▒"
        if limits_end == index + 1 and not has_marker:
            continue  # A bare "∑x" is just an operator sign to the converter.
        naryand = limits_end + 1 if has_marker else limits_end
        while not has_marker and naryand < len(source) and source[naryand] == " ":
            naryand += 1  # "∑_i x_i": the space separates the limit from the naryand.
        found.append(NaryOperator(index, limits_end, operand_end(source, naryand, pairs)))
    return found


def nary_at(source: str, caret: int) -> NaryOperator | None:
    """The innermost n-ary operator whose sign, limits or naryand holds the caret."""
    around = [nary for nary in nary_operators(source) if nary.symbol <= caret <= nary.end]
    return max(around, key=lambda nary: nary.symbol, default=None)


def add_nary_limits(source: str, caret: int) -> TemplateEdit | None:
    """`∫▒x` → `∫_()^()▒x`, caret in the lower limit (empty limits convert cleanly)."""
    nary = nary_at(source, caret)
    if nary is None or nary.has_limits:
        return None
    label = NARY_LABELS[source[nary.symbol]]
    at = nary.symbol + 1
    return TemplateEdit(source[:at] + "_()^()" + source[at:], at + 2, f"{label} with limits, empty lower limit")


def remove_nary_limits(source: str, caret: int) -> TemplateEdit | None:
    """`∫_(0)^(1)▒x` → `∫▒x`, caret after the `▒`."""
    nary = nary_at(source, caret)
    if nary is None or not nary.has_limits:
        return None
    label = NARY_LABELS[source[nary.symbol]]
    at = nary.symbol + 1
    rest = source[nary.limits_end :]
    if not rest.startswith("▒"):
        rest = "▒" + rest.lstrip(" ")
    edited = source[:at] + rest
    return TemplateEdit(edited, at + 1, f"{label}, limits removed")


def _top_level_ampersand(source: str, start: int, end: int, pairs: dict[int, int]) -> int | None:
    index = start
    while index < end:
        if source[index] == "(" and index in pairs:
            index = pairs[index] + 1
            continue
        if source[index] == "&":
            return index
        index += 1
    return None


def _script_end(source: str, start: int, pairs: dict[int, int]) -> int:
    """The end of a limit: a "(...)" group, or a run of letters and digits."""
    if start < len(source) and source[start] == "(" and start in pairs:
        return pairs[start] + 1
    end = start
    while end < len(source) and source[end].isalnum():
        end += 1
    return end
