from __future__ import annotations

from dataclasses import dataclass

from .matrix_templates import matrix_cells, matrix_label, past_fence
from .settings import DEFAULT_RECOGNIZED_FUNCTIONS
from .template_source import TemplateEdit, insert_template, matching_parens, operand_end


# N-ary operators whose `_(...)`/`^(...)` groups are limits, not scripts.
NARY_LABELS = {"∫": "integral", "∬": "integral", "∭": "integral", "∮": "integral", "∑": "sum", "∏": "product"}
# Functions whose `_(...)` is part of the function: (template, slot role).
# The argument follows a space ("lim_(n→∞) a_n"): with no separator the
# converter folds it into the subscript, and "▒" is a parse error there.
FUNCTION_SCRIPTS = {"lim": ("limit", "limit condition"), "log": ("logarithm", "base")}
FUNCTION_TEMPLATES = frozenset(template for template, _role in FUNCTION_SCRIPTS.values())
# Word's operator structures: an operator with text above (`→┴(...)`) or
# below (`→┬(...)`); both stack as `→┬(below)┴(above)`. Like lim, a space
# must follow, or the converter folds the next operand into the text.
OPERATOR_TEXT_ROLES = {"┴": "text above", "┬": "text below"}
ARROWS = frozenset("→←↔⇒⇐⇔⟶⟵⟷⟹⟸⟺↦⇌")
# What Tab past a template's last slot lands in, after its "▒" or space
# (the n-ary names are the ones MathMLDocument uses too).
NARYAND_ROLES = {
    "integral": "integrand",
    "sum": "summand",
    "product": "factor",
    "limit": "argument",
    "logarithm": "argument",
}


def insert_fraction_template(source: str, caret: int) -> TemplateEdit:
    return insert_template(source, caret, "()/()", first_slot_offset=1, announcement="fraction template, empty numerator")


def insert_square_root_template(source: str, caret: int) -> TemplateEdit:
    return insert_template(source, caret, "√()", first_slot_offset=2, announcement="square root template, empty radicand")


def insert_limit_template(source: str, caret: int) -> TemplateEdit:
    """`lim_() 〖〗`: caret in the limit condition; Tab goes on to the argument.

    The argument is an invisible group: `/` takes everything glued before
    it as its numerator, so `lim_(x→∞) (a)/(b)` is a fraction with the limit
    on top, while `lim_(x→∞) 〖(a)/(b)〗` is the limit of the fraction.
    """
    return insert_template(
        source, caret, "lim_() 〖〗", first_slot_offset=5, announcement="limit template, empty limit condition"
    )


def group_function_argument(source: str, caret: int, functions: tuple[str, ...] = ()) -> TemplateEdit | None:
    """Space right after a function: open its argument box, as Word does.

    After `lim_(...)`, `log_(...)` or a named function (`ln`, `sin`, ... and
    any in `functions`), the argument becomes an invisible group `〖...〗`
    (`\\begin ... \\end`), the caret inside. Word's argument box is that
    group: `/` takes everything glued before it as its numerator, so
    without it `lim_(x→∞) (a)/(b)` or `ln (a)/(b)` is a fraction with the
    function in the numerator; `ln 〖(a)/(b)〗` is the log of the fraction.
    """
    if caret == 0 or source[caret : caret + 1] in ("〖", "(", " "):
        return None
    if source[caret - 1] == ")":
        pairs = matching_parens(source)
        opening = next((start for start, end in pairs.items() if end == caret - 1), None)
        if opening is None or _function_script(source, opening, caret - 1) is None:
            return None
        return TemplateEdit(source[:caret] + " 〖〗" + source[caret:], caret + 2, "empty argument")
    start = caret
    while start > 0 and source[start - 1].isalpha():
        start -= 1
    name = source[start:caret]
    if not name or name not in functions or (start > 0 and source[start - 1] == "\\"):
        return None
    return TemplateEdit(source[:caret] + " 〖〗" + source[caret:], caret + 2, f"{name}, empty argument")


def insert_logarithm_template(source: str, caret: int) -> TemplateEdit:
    """`log_() 〖〗`: caret in the base; Tab goes on to the argument, an invisible group as for lim."""
    return insert_template(source, caret, "log_() 〖〗", first_slot_offset=5, announcement="logarithm template, empty base")


def insert_operator_template(source: str, caret: int, operator: str = "→", above: bool = True) -> TemplateEdit:
    """`→┴() `/`→┬() `: an operator with text above/below, caret in the text."""
    mark = "┴" if above else "┬"
    label = _operator_label(operator)
    return insert_template(
        source,
        caret,
        f"{operator}{mark}() ",
        first_slot_offset=len(operator) + 2,
        announcement=f"{label} template, empty {OPERATOR_TEXT_ROLES[mark]}",
    )


def insert_root_template(source: str, caret: int) -> TemplateEdit:
    """`√(&)`: an n-th root, caret in the index; Tab goes on to the radicand.

    Unlike empty n-ary limits, an empty index is a parse error for the
    converter (`√(&x)` fails, `√(3&x)` is an mroot), the usual transient
    state of a template that has not been filled in yet.
    """
    return insert_template(source, caret, "√(&)", first_slot_offset=2, announcement="root template, empty index")


def insert_absolute_value_template(source: str, caret: int) -> TemplateEdit:
    return insert_template(source, caret, "|()|", first_slot_offset=2, announcement="absolute value template, empty value")


def insert_integral_template(source: str, caret: int, limits: bool = False) -> TemplateEdit:
    return _insert_nary_template(source, caret, symbol="∫", limits=limits)


def insert_sum_template(source: str, caret: int, limits: bool = False) -> TemplateEdit:
    return _insert_nary_template(source, caret, symbol="∑", limits=limits)


def insert_product_template(source: str, caret: int, limits: bool = False) -> TemplateEdit:
    return _insert_nary_template(source, caret, symbol="∏", limits=limits)


def _insert_nary_template(source: str, caret: int, symbol: str, limits: bool) -> TemplateEdit:
    """Insert an n-ary operator sign, caret ready to type the naryand or its limits.

    With `limits`, `∫_()^()▒`: the caret starts in the lower limit, Tab goes
    to the upper one and then past `▒` to the naryand. Empty limits are fine
    for the converter (zero-width `mspace`s, like empty matrix cells, and
    "()" around a limit is transparent), so they can simply be left empty.

    Unlike `/`, `√`, `_`, `^` and `|`, UnicodeMath's n-ary delimiter `▒`
    never makes a following "()" transparent (confirmed against the real
    converter: `∫▒(f(x))` keeps visible parens around the integrand, even
    though `∫▒f(x)` alone renders cleanly). So there is no empty-slot
    placeholder here — the caret is simply placed right after `▒`, and the
    user types the naryand directly, same as in Word once the structure
    exists. A bare "∫▒"/"∑▒"/"∏▒" with nothing typed after it is itself a
    total parse failure (confirmed empirically), same as any other
    freshly-inserted, not-yet-filled template — not a bug, just the
    expected transient state before typing.

    Without limits, the caret is placed right after `▒`.
    """
    label = NARY_LABELS[symbol]
    if limits:
        return insert_template(
            source, caret, f"{symbol}_()^()▒", first_slot_offset=3, announcement=f"{label} template, empty lower limit"
        )
    return insert_template(source, caret, f"{symbol}▒", first_slot_offset=2, announcement=f"{label} template")


def insert_subscript_template(source: str, caret: int) -> TemplateEdit:
    return _insert_script_template(source, caret, connector="_", label="subscript")


def insert_superscript_template(source: str, caret: int) -> TemplateEdit:
    return _insert_script_template(source, caret, connector="^", label="superscript")


def _insert_script_template(source: str, caret: int, connector: str, label: str) -> TemplateEdit:
    """Insert an empty subscript/superscript slot, reusing an existing base.

    Unlike `/` and `√`, UnicodeMath's `_`/`^` only make the *argument*'s
    parens transparent, not the base's: `x_(i)` renders as plain x-sub-i, but
    `(x)_(i)` keeps the parens around x visibly. So a base placeholder is
    only inserted when there is nothing usable immediately before the caret
    (a letter, digit, or closing bracket) to attach the script to instead.
    """
    caret = max(0, min(caret, len(source)))
    has_base = caret > 0 and (source[caret - 1].isalnum() or source[caret - 1] in ")]}")
    if has_base:
        # Offset 2: past the connector and the slot's opening "(".
        return insert_template(
            source, caret, f"{connector}()", first_slot_offset=2, announcement=f"{label} template, empty {label}"
        )
    return insert_template(
        source, caret, f"(){connector}()", first_slot_offset=1, announcement=f"{label} template, empty base"
    )


@dataclass(frozen=True, slots=True)
class _Slot:
    """A template argument the caret can Tab to, filled or empty.

    `start`/`end` bound its content (inside the "(...)" for a group);
    `exit` is where Tab lands when it leaves the template.
    """

    start: int
    end: int
    template: str
    role: str
    exit: int


def move_to_slot(
    source: str, caret: int, reverse: bool = False, functions: tuple[str, ...] = DEFAULT_RECOGNIZED_FUNCTIONS
) -> TemplateEdit | None:
    """Tab/Shift+Tab: the next/previous template argument in source order.

    Filled slots count too, so a slot stays reachable after typing in it.
    The caret lands at the end of a slot's content, ready to keep typing.
    Tab from the last slot leaves the template the caret is in.
    """
    slots = _slots(source, functions)
    caret = max(0, min(caret, len(source)))
    if reverse:
        # Slots around the caret are where it already is, not behind it.
        previous = [slot for slot in slots if slot.start < caret and not slot.start <= caret <= slot.end]
        if not previous:
            return None
        return _enter_slot(source, previous[-1])
    for slot in slots:
        if slot.start > caret:
            return _enter_slot(source, slot)
    around = [slot for slot in slots if slot.start <= caret <= slot.end]
    if not around:
        return None
    current = around[-1]
    return TemplateEdit(source, current.exit, f"end {current.template}")


def _enter_slot(source: str, slot: _Slot) -> TemplateEdit:
    content = source[slot.start : slot.end]
    announcement = f"{slot.role}, {content}" if content else f"empty {slot.role}"
    return TemplateEdit(source, slot.end, announcement)


def _slots(source: str, functions: tuple[str, ...] = DEFAULT_RECOGNIZED_FUNCTIONS) -> list[_Slot]:
    """Every template argument, sorted by where its content starts.

    An enclosing slot sorts before the ones nested in it (the numerator
    before a root inside it), which is the order Tab visits them in.
    """
    pairs = matching_parens(source)
    slots: list[_Slot] = []
    for cell in matrix_cells(source):
        slots.append(
            _Slot(
                cell.start,
                cell.end,
                matrix_label(source, cell),
                f"cell, row {cell.row}, column {cell.column}",
                past_fence(source, cell.matrix_open - 1, cell.matrix_close + 1),
            )
        )
    for opening, closing in pairs.items():
        separator = _root_index_separator(source, opening, closing, pairs)
        if separator is not None:
            slots.append(_Slot(opening + 1, separator, "root", "index", closing + 1))
            slots.append(_Slot(separator + 1, closing, "root", "radicand", closing + 1))
            continue
        detected = _detect_group(source, opening, closing)
        if detected is not None:
            slots.append(_Slot(opening + 1, closing, *detected))
    slots.extend(_naryand_slots(source, pairs, slots, functions))
    return sorted(slots, key=lambda slot: (slot.start, -slot.end))


def _naryand_slots(source: str, pairs: dict[int, int], slots: list[_Slot], functions: tuple[str, ...]) -> list[_Slot]:
    """The integrand/summand/factor after each n-ary `▒`, and a lim/log's argument.

    Not a "()" group (a "()" after `▒` stays visible), just the operand that
    follows, so it can be read back and re-entered after typing in it.
    """
    found: list[_Slot] = []
    for index, character in enumerate(source):
        if character != "▒":
            continue
        label = _nary_label_before(source, index, pairs)
        if label is not None:
            start = index + 1
            end = operand_end(source, start, pairs)
            found.append(_Slot(start, end, label, NARYAND_ROLES[label], end))
    starts = {slot.start for slot in found}
    for slot in slots:
        # lim_(...)/log_(...) exit past the space before their argument.
        if slot.template in FUNCTION_TEMPLATES and source[slot.exit - 1 : slot.exit] == " " and slot.exit not in starts:
            group_end = _invisible_group_end(source, slot.exit)
            if group_end is not None:
                # `lim_(...) 〖...〗`: the argument is the group's content; Tab leaves past "〗".
                found.append(_Slot(slot.exit + 1, group_end, slot.template, NARYAND_ROLES[slot.template], group_end + 1))
            else:
                end = operand_end(source, slot.exit, pairs)
                found.append(_Slot(slot.exit, end, slot.template, NARYAND_ROLES[slot.template], end))
            starts.add(slot.exit)
    for index, character in enumerate(source):
        # `ln 〖...〗`, `sin(...)`: a named function's group or parens hold its argument.
        closing = _invisible_group_end(source, index) if character == "〖" else pairs.get(index) if character == "(" else None
        if closing is None:
            continue
        name_end = index - 1 if index > 0 and source[index - 1] == " " and character == "〖" else index
        name_start = name_end
        while name_start > 0 and source[name_start - 1].isalpha():
            name_start -= 1
        name = source[name_start:name_end]
        if name in functions and (name_start == 0 or source[name_start - 1] != "\\") and index + 1 not in starts:
            found.append(_Slot(index + 1, closing, name, "argument", closing + 1))
            starts.add(index + 1)
    return found


def _invisible_group_end(source: str, start: int) -> int | None:
    """The index of the "〗" closing a "〖" at `start`, if there is one."""
    if source[start : start + 1] != "〖":
        return None
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "〖":
            depth += 1
        elif source[index] == "〗":
            depth -= 1
            if depth == 0:
                return index
    return None


def _nary_label_before(source: str, marker: int, pairs: dict[int, int]) -> str | None:
    """The n-ary operator a `▒` belongs to, stepping back over its `_`/`^` limits."""
    closing_to_opening = {end: start for start, end in pairs.items()}
    index = marker - 1
    while index >= 0:
        if source[index] == ")" and index in closing_to_opening:
            start = closing_to_opening[index]
        else:
            start = index
            while start > 0 and source[start].isalnum() and source[start - 1].isalnum():
                start -= 1
            if not source[start].isalnum():
                break
        if start > 0 and source[start - 1] in "_^":
            index = start - 2
            continue
        break
    return NARY_LABELS.get(source[index]) if index >= 0 else None


def _root_index_separator(source: str, opening: int, closing: int, pairs: dict[int, int]) -> int | None:
    """The `&` splitting `√(index&radicand)` at the root's own depth, if any."""
    if opening == 0 or source[opening - 1] != "√":
        return None
    index = opening + 1
    while index < closing:
        if source[index] == "(" and index in pairs:
            index = pairs[index] + 1
            continue
        if source[index] == "&":
            return index
        index += 1
    return None


def _nary_limit(source: str, opening: int, closing: int) -> tuple[str, str, int] | None:
    """A "(...)" that is the lower (`∑_(...)`) or upper (`∑_(...)^(...)`, `∑^(...)`) limit.

    Tab past the last limit lands after the `▒`, where the naryand goes.
    """
    if opening < 2 or source[opening - 1] not in "_^":
        return None
    base = opening - 2
    if source[opening - 1] == "^" and source[base] == ")":
        # Step back over the lower limit "_(...)" to the operator.
        lower_open = next((start for start, end in matching_parens(source).items() if end == base), None)
        if lower_open is None or lower_open < 2 or source[lower_open - 1] != "_":
            return None
        base = lower_open - 2
    label = NARY_LABELS.get(source[base])
    if label is None:
        return None
    role = "lower limit" if source[opening - 1] == "_" else "upper limit"
    exit = closing + 1
    if source[exit : exit + 2].startswith("^("):
        return label, role, exit  # An upper limit follows; it is the next slot.
    if source[exit : exit + 1] == "▒":
        exit += 1
    return label, role, exit


def _function_script(source: str, opening: int, closing: int) -> tuple[str, str, int] | None:
    """The `_(...)` of `lim_(...)`/`log_(...)`; Tab past it lands after the space before the argument."""
    if opening < 1 or source[opening - 1] != "_":
        return None
    for name, (template, role) in FUNCTION_SCRIPTS.items():
        start = opening - 1 - len(name)
        if start < 0 or source[start : opening - 1] != name:
            continue
        if start > 0 and source[start - 1].isalpha():
            continue  # Part of a longer word.
        exit = closing + 1
        if source[exit : exit + 1] == " ":
            exit += 1
        return template, role, exit
    return None


def _operator_label(operator: str) -> str:
    return "arrow" if operator in ARROWS else "operator"


def _operator_text(source: str, opening: int, closing: int) -> tuple[str, str, int] | None:
    """The `(...)` of `→┴(...)`/`→┬(...)`; Tab past it skips the space after it."""
    if opening < 2 or source[opening - 1] not in OPERATOR_TEXT_ROLES:
        return None
    base = opening - 2
    if source[base] == ")" and source[opening - 1] == "┴":
        # `→┬(below)┴(above)`: step back over the text below to the operator.
        below_open = next((start for start, end in matching_parens(source).items() if end == base), None)
        if below_open is None or below_open < 2 or source[below_open - 1] != "┬":
            return None
        base = below_open - 2
    if source[base].isspace() or source[base] in "()":
        return None
    exit = closing + 1
    if source[exit : exit + 2] == "┴(":
        return _operator_label(source[base]), OPERATOR_TEXT_ROLES[source[opening - 1]], exit
    if source[exit : exit + 1] == " ":
        exit += 1
    return _operator_label(source[base]), OPERATOR_TEXT_ROLES[source[opening - 1]], exit


def _detect_group(source: str, opening: int, closing: int) -> tuple[str, str, int] | None:
    """Classify a "(...)" group as a template argument: (template, role, exit).

    Decided by the delimiter directly outside the group's own "(" and ")" —
    never a fixed window of characters, so whatever precedes or follows the
    group (another template's closing "|", a filled numerator) cannot be
    misread as part of it. Backward-looking checks (what opens this group)
    win over forward-looking ones (what follows it): in "√()/()" the radicand
    is followed by "/", but the "/" belongs to an enclosing fraction whose
    numerator is the whole root. A group only counts as a numerator or base
    when it starts an operand, so the "(x)" of "f(x)/2" is not one.
    `exit` is where Tab lands after leaving the template.
    """
    before = source[opening - 1] if opening > 0 else ""
    after = source[closing + 1] if closing + 1 < len(source) else ""
    nary = (
        _nary_limit(source, opening, closing)
        or _function_script(source, opening, closing)
        or _operator_text(source, opening, closing)
    )
    if nary is not None:
        return nary
    if before == "/":
        return "fraction", "denominator", closing + 1
    if before == "_":
        return "scripts", "subscript", closing + 1
    if before == "^":
        return "scripts", "superscript", closing + 1
    if before == "√":
        return "square root", "radicand", closing + 1
    if before == "|" and after == "|":
        return "absolute value", "value", closing + 2
    if before and (before.isalnum() or before in ")]}"):
        return None
    if after in ("_", "^"):
        return "scripts", "base", closing + 1
    if after == "/":
        return "fraction", "numerator", closing + 1
    return None
