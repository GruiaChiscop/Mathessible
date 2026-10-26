"""Changing an existing structure: a root's index, an n-ary operator's limits,
a script's subscript and superscript, a bracket pair, an accent or a bar.

Like the fraction styles, these rewrite the UnicodeMath source; in
professional mode the editor maps MathCAT's node back by order (the n-th
`msqrt`/`mroot` is the n-th root sign, the n-th `:nary` mrow the n-th n-ary
operator), so `roots` and `nary_operators` list them in reading order.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from mathessible.templates.math_templates import FUNCTION_SCRIPTS, NARY_LABELS
from mathessible.templates.template_source import TemplateEdit, matching_parens, operand_end

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
        if source[after : after + 1] == "〖":
            closing = _group_end(source, after)
            if closing is not None:
                found.append(Root(index, character, after + 1, closing, True, None))
                continue
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
    replacement = f"√〖{radicand}〗" if root.grouped else f"√{radicand}"
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


def _group_end(source: str, start: int) -> int | None:
    """The "〗" closing the "〖" at `start`."""
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "〖":
            depth += 1
        elif source[index] == "〗":
            depth -= 1
            if depth == 0:
                return index
    return None


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


@dataclass(frozen=True, slots=True)
class Script:
    """A base with a subscript and/or a superscript: `x_i`, `x^2`, `(a+b)^2`, `x_i^2`.

    `subscript`/`superscript` are (connector offset, argument end) or None;
    `end` is where the whole script ends.
    """

    base_start: int
    base_end: int
    subscript: tuple[int, int] | None
    superscript: tuple[int, int] | None
    end: int


def scripts(source: str) -> list[Script]:
    """Every script in reading order, not the limits of ∑/∫ or lim/log's own (their menus edit those)."""
    pairs = matching_parens(source)
    openings = {closing: opening for opening, closing in pairs.items()}
    found: list[Script] = []
    taken: set[int] = set()
    for index, character in enumerate(source):
        if character not in "_^" or index == 0 or index in taken:
            continue
        parts: dict[str, tuple[int, int]] = {}
        position = index
        while position < len(source) and source[position] in "_^" and source[position] not in parts:
            end = _argument_end(source, position + 1, pairs)
            parts[source[position]] = (position, end)
            taken.add(position)  # Also for ∑'s limits: `^n` of `∑_(i=1)^n` is not a script of its own.
            position = end
        base_start = _base_start(source, index, openings)
        if base_start is not None:
            found.append(Script(base_start, index, parts.get("_"), parts.get("^"), position))
    return found


def script_at(source: str, caret: int, end: int | None = None) -> Script | None:
    """The innermost script whose base or scripts hold the caret (or all of `caret`..`end`, a node's span)."""
    end = caret if end is None else end
    around = [script for script in scripts(source) if script.base_start <= caret and end <= script.end]
    return max(around, key=lambda script: script.base_start, default=None)


def add_subscript(source: str, caret: int) -> TemplateEdit | None:
    """`x^2` → `x_()^2`, caret in the empty subscript (an empty one converts cleanly)."""
    script = script_at(source, caret)
    if script is None or script.subscript is not None:
        return None
    at = script.base_end
    return TemplateEdit(source[:at] + "_()" + source[at:], at + 2, "subscript added, empty subscript")


def add_superscript(source: str, caret: int) -> TemplateEdit | None:
    """`x_i` → `x_i^()`, caret in the empty superscript."""
    script = script_at(source, caret)
    if script is None or script.superscript is not None:
        return None
    at = script.end
    return TemplateEdit(source[:at] + "^()" + source[at:], at + 2, "superscript added, empty superscript")


def remove_subscript(source: str, caret: int) -> TemplateEdit | None:
    script = script_at(source, caret)
    if script is None or script.subscript is None:
        return None
    start, end = script.subscript
    return TemplateEdit(source[:start] + source[end:], start, "subscript removed")


def remove_superscript(source: str, caret: int) -> TemplateEdit | None:
    script = script_at(source, caret)
    if script is None or script.superscript is None:
        return None
    start, end = script.superscript
    return TemplateEdit(source[:start] + source[end:], start, "superscript removed")


def _base_start(source: str, connector: int, openings: dict[int, int]) -> int | None:
    """Where the base of the `_`/`^` at `connector` starts; None for an n-ary sign, lim/log or no base."""
    index = connector - 1
    while index >= 0 and unicodedata.combining(source[index]):
        index -= 1  # An accented base: `x̂_i`.
    if index < 0:
        return None
    character = source[index]
    if character == ")":
        return openings.get(index)
    if character in NARY_LABELS:
        return None
    if character.isalpha():
        start = index
        while start > 0 and (source[start - 1].isalpha() or source[start - 1] == "\u00a0"):
            start -= 1
        word = source[start : index + 1]
        if word in FUNCTION_SCRIPTS:
            return None  # lim_(...), log_2, lim inf_(...): their own structures.
        # A multi-letter ASCII run is a name (`sin^2 x`); otherwise the base is one letter.
        return start if len(word) > 1 and word.isascii() and word.isalpha() else index
    if character.isdigit() or character in "∞′″":
        return index
    return None


def _argument_end(source: str, start: int, pairs: dict[int, int]) -> int:
    """The end of a script's argument: a "(...)" group, a run of letters and digits, or one other symbol."""
    end = _script_end(source, start, pairs)
    if end == start and start < len(source) and source[start] not in " +-−=<>,_^)":
        end = start + 1  # `x^∞`, `x_π`.
    while end < len(source) and unicodedata.combining(source[end]):
        end += 1
    return end


# Visible bracket pairs (opening -> closing); `├`/`┤` are UnicodeMath's invisible ones.
BRACKETS = {"(": ")", "[": "]", "{": "}", "⟨": "⟩", "⌊": "⌋", "⌈": "⌉", "|": "|", "‖": "‖", "├": "┤"}
BRACKET_NAMES = {
    "(": "parentheses",
    "[": "square brackets",
    "{": "braces",
    "⟨": "angle brackets",
    "⌊": "floor",
    "⌈": "ceiling",
    "|": "absolute value",
    "‖": "norm",
}
_OPENERS = "([{⟨⌊⌈├"
_CLOSERS = ")]}⟩⌋⌉┤"


@dataclass(frozen=True, slots=True)
class Bracket:
    """A visible bracket pair: `opening`/`closing` offsets (either may be hidden, `├`/`┤`)."""

    opening: int
    closing: int


def brackets(source: str) -> list[Bracket]:
    """Every visible bracket pair in reading order, not the parens UnicodeMath makes transparent.

    A "(...)" right after `_ ^ √ ▒ ┴ ┬` or a structure sign, or around a
    fraction's operand, is grouping that does not show (`x_(i)`, `(a)/(b)`).
    Any opener pairs with any closer, as in UnicodeMath (`[0,1)`, `(a+b┤`).
    """
    found: list[Bracket] = []
    stack: list[int] = []
    bars: list[int] = []
    for index, character in enumerate(source):
        if character in _OPENERS:
            stack.append(index)
        elif character in _CLOSERS and stack:
            opening = stack.pop()
            if _visible(source, opening, index):
                found.append(Bracket(opening, index))
        elif character in "|‖":
            if bars and source[bars[-1]] == character:
                found.append(Bracket(bars.pop(), index))
            else:
                bars.append(index)
    return sorted(found, key=lambda bracket: bracket.opening)


def bracket_at(source: str, caret: int, end: int | None = None) -> Bracket | None:
    """The innermost visible bracket pair holding the caret (on a bracket counts as inside), or `caret`..`end`."""
    end = caret if end is None else end
    around = [bracket for bracket in brackets(source) if bracket.opening <= caret and end <= bracket.closing + 1]
    return max(around, key=lambda bracket: bracket.opening, default=None)


def change_brackets(source: str, caret: int, opening: str) -> TemplateEdit | None:
    """The pair around the caret becomes `opening` and its closer (`(a+b)` → `[a+b]`)."""
    bracket = bracket_at(source, caret)
    if bracket is None:
        return None
    closing = BRACKETS[opening]
    edited = source[: bracket.opening] + opening + source[bracket.opening + 1 : bracket.closing] + closing
    edited += source[bracket.closing + 1 :]
    return TemplateEdit(edited, min(caret, bracket.closing), f"{BRACKET_NAMES.get(opening, 'brackets')}")


def encloses_matrix(source: str, bracket: Bracket) -> bool:
    """A matrix's own fence: hiding or removing it would leave a bare `■(...)`, read as lines."""
    return source[bracket.opening + 1 : bracket.opening + 2] == "■"


def remove_brackets(source: str, caret: int) -> TemplateEdit | None:
    """Word's "Remove enclosing characters": the content stays, the pair goes."""
    bracket = bracket_at(source, caret)
    if bracket is None or encloses_matrix(source, bracket):
        return None
    content = source[bracket.opening + 1 : bracket.closing]
    edited = source[: bracket.opening] + content + source[bracket.closing + 1 :]
    return TemplateEdit(edited, bracket.opening + len(content), "brackets removed")


def hide_bracket(source: str, caret: int, closing: bool) -> TemplateEdit | None:
    """Hide (or show again) one side: `(a+b)` → `(a+b┤`; a hidden side shows as "(" or ")"."""
    bracket = bracket_at(source, caret)
    if bracket is None or source[bracket.opening] in "|‖" or encloses_matrix(source, bracket):
        return None
    at = bracket.closing if closing else bracket.opening
    hidden = source[at] in "├┤"
    replacement = (")" if closing else "(") if hidden else ("┤" if closing else "├")
    side = "closing" if closing else "opening"
    edited = source[:at] + replacement + source[at + 1 :]
    return TemplateEdit(edited, min(caret, len(edited)), f"{side} bracket {'shown' if hidden else 'hidden'}")


def _visible(source: str, opening: int, closing: int) -> bool:
    if source[opening] != "(" or source[closing] != ")":
        return True
    before = source[opening - 1] if opening > 0 else " "
    after = source[closing + 1] if closing + 1 < len(source) else " "
    if before in "_^√∛∜▒┴┬▭#⏞⏟¯▁■█/⁄∕⊘¦":
        return False  # A script, radicand, label, table body or denominator: grouping only.
    if after in "/⁄∕⊘¦":
        return False  # A numerator. A script's base keeps its parens: `(a+b)^2` shows them.
    return not (before == "|" and after == "|")  # `|()|`'s parens are the bars' content.


# Accents Mathessible inserts (structure_gallery), by combining mark.
ACCENTS = {
    "\u20d7": "vector arrow",
    "\u0302": "hat",
    "\u0305": "bar",
    "\u0307": "dot",
    "\u0308": "double dot",
    "\u0303": "tilde",
    "\u030c": "check",
    "\u0301": "acute",
    "\u0300": "grave",
    "\u0306": "breve",
}


@dataclass(frozen=True, slots=True)
class Accent:
    """A combining accent at `mark` on the base `base_start`..`mark` (a character or a "(...)")."""

    base_start: int
    mark: int


def accents(source: str) -> list[Accent]:
    pairs = matching_parens(source)
    openings = {closing: opening for opening, closing in pairs.items()}
    found: list[Accent] = []
    for index, character in enumerate(source):
        if character not in ACCENTS or index == 0:
            continue
        base = index - 1
        while base > 0 and unicodedata.combining(source[base]):
            base -= 1
        if source[base] == ")" and base in openings:
            base = openings[base]
        found.append(Accent(base, index))
    return found


def accent_at(source: str, caret: int, end: int | None = None) -> Accent | None:
    end = caret if end is None else end
    around = [accent for accent in accents(source) if accent.base_start <= caret and end <= accent.mark + 1]
    return max(around, key=lambda accent: accent.base_start, default=None)


def change_accent(source: str, caret: int, mark: str) -> TemplateEdit | None:
    accent = accent_at(source, caret)
    if accent is None:
        return None
    edited = source[: accent.mark] + mark + source[accent.mark + 1 :]
    return TemplateEdit(edited, accent.mark + 1, ACCENTS[mark])


def remove_accent(source: str, caret: int) -> TemplateEdit | None:
    accent = accent_at(source, caret)
    if accent is None:
        return None
    edited = source[: accent.mark] + source[accent.mark + 1 :]
    return TemplateEdit(edited, accent.mark, f"{ACCENTS[source[accent.mark]]} removed")


# Bars over or under a group: `¯(x+y)`, `▁(x+y)` (CONTENT_SIGNS in math_templates).
BARS = {"¯": "overbar", "▁": "underbar"}


def bar_at(source: str, caret: int, end: int | None = None) -> tuple[int, int] | None:
    """(sign offset, closing paren offset) of the innermost bar around the caret (or `caret`..`end`)."""
    end = caret if end is None else end
    pairs = matching_parens(source)
    around = [
        (index, pairs[index + 1])
        for index, character in enumerate(source)
        if character in BARS and index + 1 in pairs and index <= caret and end <= pairs[index + 1] + 1
    ]
    return max(around, default=None)


def switch_bar(source: str, caret: int) -> TemplateEdit | None:
    """Overbar ↔ underbar."""
    bar = bar_at(source, caret)
    if bar is None:
        return None
    sign = "▁" if source[bar[0]] == "¯" else "¯"
    return TemplateEdit(source[: bar[0]] + sign + source[bar[0] + 1 :], caret, BARS[sign])


def remove_bar(source: str, caret: int) -> TemplateEdit | None:
    """`¯(x+y)` → `x+y`."""
    bar = bar_at(source, caret)
    if bar is None:
        return None
    sign, closing = bar
    content = source[sign + 2 : closing]
    edited = source[:sign] + content + source[closing + 1 :]
    return TemplateEdit(edited, sign + len(content), f"{BARS[source[sign]]} removed")
