"""Everything the Insert menu offers, with its shortcut: one list for the menu
bar, the context menu and the equation editor's own key handling.

Shortcut modifiers: "command" is Cmd on macOS / Ctrl elsewhere, "variant" is
the physical Control key on macOS / Alt elsewhere (Option types ß, π, ...).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from mathessible.i18n import N_
from mathessible.templates.math_templates import (
    insert_absolute_value_template,
    insert_binomial_template,
    insert_box_template,
    insert_brace_template,
    insert_bracket_template,
    insert_cases_template,
    insert_equation_array_template,
    insert_equation_number_template,
    insert_fraction_template,
    insert_integral_template,
    insert_limit_template,
    insert_logarithm_template,
    insert_nary_operator_template,
    insert_operator_template,
    insert_product_template,
    insert_root_template,
    insert_square_root_template,
    insert_subscript_template,
    insert_sum_template,
    insert_superscript_template,
)
from mathessible.templates.template_source import TemplateEdit

Inserter = Callable[[str, int], TemplateEdit]


@dataclass(frozen=True, slots=True)
class InsertItem:
    """One Insert entry. `insert` is None for the entries that open a `dialog` first ("matrix", "symbol", "gallery")."""

    label: str
    insert: Inserter | None
    key: str = ""
    modifier: str = ""
    shift: bool = False
    dialog: str = ""

    def accelerator(self, mac: bool) -> str:
        """The shortcut as wx menu-label text ("Ctrl+Shift+O"), or "" without one."""
        if not self.key:
            return ""
        prefix = {"command": "Ctrl", "variant": "RawCtrl" if mac else "Alt"}[self.modifier]
        return f"{prefix}+{'Shift+' if self.shift else ''}{self.key}"


# The Insert menu, one tuple per section (separators between them).
INSERT_GROUPS = (
    (
        InsertItem(N_("&Fraction"), insert_fraction_template, "/", "command"),
        InsertItem(N_("&Subscript"), insert_subscript_template, "=", "command"),
        InsertItem(N_("Su&perscript"), insert_superscript_template, "=", "command", shift=True),
    ),
    (
        InsertItem(N_("&Square Root"), insert_square_root_template, "R", "command"),
        InsertItem(N_("&Root with Index"), insert_root_template, "R", "variant"),
    ),
    (
        InsertItem(N_("&Integral"), insert_integral_template, "I", "command"),
        InsertItem(
            N_("Integral with &Limits"),
            lambda source, caret: insert_integral_template(source, caret, limits=True),
            "I",
            "variant",
        ),
        InsertItem(N_("&Sum"), insert_sum_template, "S", "command"),
        InsertItem(
            N_("Sum with Li&mits"),
            lambda source, caret: insert_sum_template(source, caret, limits=True),
            "S",
            "variant",
        ),
        InsertItem(N_("&Product"), insert_product_template, "P", "command"),
        InsertItem(
            N_("Product with Limi&ts"),
            lambda source, caret: insert_product_template(source, caret, limits=True),
            "P",
            "variant",
        ),
    ),
    (
        InsertItem(N_("&Absolute Value"), insert_absolute_value_template, "\\", "command"),
        InsertItem(N_("&Limit"), insert_limit_template, "L", "command"),
        InsertItem(N_("L&ogarithm"), insert_logarithm_template, "L", "variant"),
    ),
    (
        # Shift avoids the frame's File > Open (Command+O).
        InsertItem(N_("Arrow with Text &Above"), insert_operator_template, "O", "command", shift=True),
        InsertItem(
            N_("Arrow with Text &Below"),
            lambda source, caret: insert_operator_template(source, caret, above=False),
            "O",
            "variant",
        ),
        InsertItem(
            N_("&Equals with Text Above"), lambda source, caret: insert_operator_template(source, caret, operator="=")
        ),
    ),
    (
        InsertItem(N_("&Norm"), lambda source, caret: insert_bracket_template(source, caret, "‖")),
        InsertItem(N_("Floo&r"), lambda source, caret: insert_bracket_template(source, caret, "⌊")),
        InsertItem(N_("Ceili&ng"), lambda source, caret: insert_bracket_template(source, caret, "⌈")),
        InsertItem(N_("Angle Brac&kets"), lambda source, caret: insert_bracket_template(source, caret, "⟨")),
        InsertItem(N_("Bino&mial"), insert_binomial_template),
    ),
    (
        InsertItem(N_("Double Inte&gral"), lambda source, caret: insert_nary_operator_template(source, caret, "∬")),
        InsertItem(N_("Triple Integral"), lambda source, caret: insert_nary_operator_template(source, caret, "∭")),
        InsertItem(N_("Contour Integral"), lambda source, caret: insert_nary_operator_template(source, caret, "∮")),
        InsertItem(N_("&Union"), lambda source, caret: insert_nary_operator_template(source, caret, "⋃", limits=True)),
        InsertItem(
            N_("Intersection"), lambda source, caret: insert_nary_operator_template(source, caret, "⋂", limits=True)
        ),
    ),
    (
        InsertItem(N_("&Cases"), insert_cases_template),
        InsertItem(N_("E&quation Array"), insert_equation_array_template),
        InsertItem(N_("Bo&x"), insert_box_template),
        InsertItem(N_("Equation &Number"), insert_equation_number_template),
        InsertItem(N_("Overbrace"), insert_brace_template),
        InsertItem(N_("Underbrace"), lambda source, caret: insert_brace_template(source, caret, above=False)),
    ),
    # Shift is required: plain Command+M is macOS's Minimize, which the
    # frame's Window menu claims before the editor sees it.
    (
        InsertItem(N_("&Matrix…"), None, "M", "command", shift=True, dialog="matrix"),
        # Searches control words and symbols by name (completion.py).
        InsertItem(N_("S&ymbol…"), None, "S", "command", shift=True, dialog="symbol"),
        # Word's structure gallery: every template by category (structure_gallery.py).
        InsertItem(N_("Structure Gallery…"), None, "G", "command", shift=True, dialog="gallery"),
    ),
    (
        # Word's Normal Text: starts or ends quoted text, or quotes the selection (normal_text.py).
        InsertItem(N_("Normal &Text"), None, "T", "command", shift=True, dialog="normal_text"),
    ),
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
