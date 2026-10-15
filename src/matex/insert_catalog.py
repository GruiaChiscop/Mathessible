"""Everything the Insert menu offers, with its shortcut: one list for the menu
bar, the context menu and the equation editor's own key handling.

Shortcut modifiers: "command" is Cmd on macOS / Ctrl elsewhere, "variant" is
the physical Control key on macOS / Alt elsewhere (Option types ß, π, ...).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .math_templates import (
    insert_binomial_template,
    insert_box_template,
    insert_brace_template,
    insert_bracket_template,
    insert_cases_template,
    insert_equation_array_template,
    insert_equation_number_template,
    insert_nary_operator_template,
    insert_absolute_value_template,
    insert_fraction_template,
    insert_integral_template,
    insert_limit_template,
    insert_logarithm_template,
    insert_operator_template,
    insert_product_template,
    insert_root_template,
    insert_square_root_template,
    insert_subscript_template,
    insert_sum_template,
    insert_superscript_template,
)
from .template_source import TemplateEdit

Inserter = Callable[[str, int], TemplateEdit]


@dataclass(frozen=True, slots=True)
class InsertItem:
    """One Insert entry. `insert` is None for the matrix, which asks for its shape first."""

    label: str
    insert: Inserter | None
    key: str = ""
    modifier: str = ""
    shift: bool = False

    def accelerator(self, mac: bool) -> str:
        """The shortcut as wx menu-label text ("Ctrl+Shift+O"), or "" without one."""
        if not self.key:
            return ""
        prefix = {"command": "Ctrl", "variant": "RawCtrl" if mac else "Alt"}[self.modifier]
        return f"{prefix}+{'Shift+' if self.shift else ''}{self.key}"


# The Insert menu, one tuple per section (separators between them).
INSERT_GROUPS = (
    (
        InsertItem("&Fraction", insert_fraction_template, "/", "command"),
        InsertItem("&Subscript", insert_subscript_template, "=", "command"),
        InsertItem("Su&perscript", insert_superscript_template, "=", "command", shift=True),
    ),
    (
        InsertItem("&Square Root", insert_square_root_template, "R", "command"),
        InsertItem("&Root with Index", insert_root_template, "R", "variant"),
    ),
    (
        InsertItem("&Integral", insert_integral_template, "I", "command"),
        InsertItem(
            "Integral with &Limits",
            lambda source, caret: insert_integral_template(source, caret, limits=True),
            "I",
            "variant",
        ),
        InsertItem("&Sum", insert_sum_template, "S", "command"),
        InsertItem(
            "Sum with Li&mits", lambda source, caret: insert_sum_template(source, caret, limits=True), "S", "variant"
        ),
        InsertItem("&Product", insert_product_template, "P", "command"),
        InsertItem(
            "Product with Limi&ts",
            lambda source, caret: insert_product_template(source, caret, limits=True),
            "P",
            "variant",
        ),
    ),
    (
        InsertItem("&Absolute Value", insert_absolute_value_template, "\\", "command"),
        InsertItem("&Limit", insert_limit_template, "L", "command"),
        InsertItem("L&ogarithm", insert_logarithm_template, "L", "variant"),
    ),
    (
        # Shift avoids the frame's File > Open (Command+O).
        InsertItem("Arrow with Text &Above", insert_operator_template, "O", "command", shift=True),
        InsertItem(
            "Arrow with Text &Below",
            lambda source, caret: insert_operator_template(source, caret, above=False),
            "O",
            "variant",
        ),
        InsertItem(
            "&Equals with Text Above", lambda source, caret: insert_operator_template(source, caret, operator="=")
        ),
    ),
    (
        InsertItem("&Norm", lambda source, caret: insert_bracket_template(source, caret, "‖")),
        InsertItem("Floo&r", lambda source, caret: insert_bracket_template(source, caret, "⌊")),
        InsertItem("Ceili&ng", lambda source, caret: insert_bracket_template(source, caret, "⌈")),
        InsertItem("Angle Brac&kets", lambda source, caret: insert_bracket_template(source, caret, "⟨")),
        InsertItem("Bino&mial", insert_binomial_template),
    ),
    (
        InsertItem("Double Inte&gral", lambda source, caret: insert_nary_operator_template(source, caret, "∬")),
        InsertItem("Triple Integral", lambda source, caret: insert_nary_operator_template(source, caret, "∭")),
        InsertItem("Contour Integral", lambda source, caret: insert_nary_operator_template(source, caret, "∮")),
        InsertItem("&Union", lambda source, caret: insert_nary_operator_template(source, caret, "⋃", limits=True)),
        InsertItem("Intersection", lambda source, caret: insert_nary_operator_template(source, caret, "⋂", limits=True)),
    ),
    (
        InsertItem("&Cases", insert_cases_template),
        InsertItem("E&quation Array", insert_equation_array_template),
        InsertItem("Bo&x", insert_box_template),
        InsertItem("Equation &Number", insert_equation_number_template),
        InsertItem("Overbrace", insert_brace_template),
        InsertItem("Underbrace", lambda source, caret: insert_brace_template(source, caret, above=False)),
    ),
    # Shift is required: plain Command+M is macOS's Minimize, which the
    # frame's Window menu claims before the editor sees it.
    (InsertItem("&Matrix…", None, "M", "command", shift=True),),
)

# Keys that arrive as another character with Shift held ("+" for Shift+=).
_SHIFTED_KEYS = {"+": "=", "|": "\\"}
# Where Shift does not matter: the variants, and Cmd+\ / Cmd+| alike.
_SHIFT_INSENSITIVE = {("variant", key) for key in "IRSPLO"} | {("command", "\\")}


def all_items() -> tuple[InsertItem, ...]:
    return tuple(item for group in INSERT_GROUPS for item in group)


def item_for_key(key: str, modifier: str, shift: bool) -> InsertItem | None:
    """The entry a key press inserts: `key` is the pressed character, `modifier` "command" or "variant"."""
    key = _SHIFTED_KEYS.get(key, key).upper()
    ignore_shift = (modifier, key) in _SHIFT_INSENSITIVE
    for item in all_items():
        if item.key == key and item.modifier == modifier and (ignore_shift or item.shift == shift):
            return item
    return None
