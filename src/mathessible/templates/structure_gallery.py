"""Word's structure gallery (Insert > Structures…): every template by category, with variants.

Word shows a ribbon of pictures; here each category is a list of named
variants, inserted through the same path as the Insert menu (`InsertItem`),
so Tab slots, control-word spelling and building work the same. Only
variants the converter builds are listed (checked against the real
UnicodeMathML output, as docs/engineering-notes.md describes); `()⃗` does
not parse, so accents go on the base already typed, as in Word's linear
format.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from mathessible.editing.source_view import spell_with_control_words
from mathessible.i18n import N_, spoken
from mathessible.templates.insert_catalog import Inserter, InsertItem, all_items
from mathessible.templates.math_templates import (
    insert_nary_operator_template,
    insert_operator_template,
)
from mathessible.templates.matrix_templates import insert_matrix_template
from mathessible.templates.saved_equations import SavedEquation
from mathessible.templates.template_source import TemplateEdit, insert_template


@dataclass(frozen=True, slots=True)
class GalleryCategory:
    name: str
    items: tuple[InsertItem, ...]


def _template(text: str, caret: int, announcement: str) -> Inserter:
    """Insert `text` with the caret `caret` characters into it."""
    return lambda source, at: insert_template(source, at, text, first_slot_offset=caret, announcement=announcement)


def _example(text: str, name: str) -> Inserter:
    """A ready-made expression (Word's "common" entries), caret after it."""
    return _template(text, len(text), name)


def _accent(mark: str, name: str) -> Inserter:
    """An accent on the base right before the caret (`x` → `x⃗`, `(a+b)` → `(a+b)⃗`)."""

    def insert(source: str, caret: int) -> TemplateEdit:
        caret = max(0, min(caret, len(source)))
        before = source[caret - 1] if caret else ""
        if not (before.isalnum() or before == ")"):
            return TemplateEdit(
                source, caret, spoken("{accent}: type the base first, then the accent").format(accent=spoken(name))
            )
        announcement = spoken("{accent} on {base}").format(accent=spoken(name), base=before)
        return insert_template(source, caret, mark, first_slot_offset=len(mark), announcement=announcement)

    return insert


def _matrix(rows: int, columns: int, fence: str, name: str) -> Inserter:
    def insert(source: str, caret: int) -> TemplateEdit:
        edit = insert_matrix_template(source, caret, rows, columns, fence)
        return TemplateEdit(
            edit.source, edit.caret, spoken("{matrix}, empty cell, row 1, column 1").format(matrix=spoken(name))
        )

    return insert


# The dialog entries' labels as the gallery shows them, without the menu's "…".
_DIALOG_LABELS = (N_("Matrix"), N_("Symbol"))


def _menu_item(label: str) -> InsertItem:
    """An Insert-menu entry by its label (mnemonic "&" ignored), so both lists stay one."""
    for item in all_items():
        if item.label.replace("&", "") == label:
            return InsertItem(label.rstrip("…"), item.insert, dialog=item.dialog)
    raise KeyError(label)


def _function(name: str) -> InsertItem:
    announcement = spoken("{function} template, empty argument").format(function=name)
    return InsertItem(name, _template(f"{name} 〖〗", len(name) + 2, announcement))


CATEGORIES: tuple[GalleryCategory, ...] = (
    GalleryCategory(
        N_("Fraction"),
        (
            _menu_item(N_("Fraction")),
            InsertItem(N_("Skewed fraction"), _template("()⁄()", 1, N_("skewed fraction template, empty numerator"))),
            InsertItem(N_("Linear fraction"), _template("()∕()", 1, N_("linear fraction template, empty numerator"))),
            InsertItem(N_("Small fraction"), _template("()⊘()", 1, N_("small fraction template, empty numerator"))),
            InsertItem(N_("dy over dx"), _example("ⅆy/ⅆx", N_("d y over d x"))),
            InsertItem(N_("Partial y over partial x"), _example("∂y/∂x", N_("partial y over partial x"))),
            InsertItem(N_("Delta y over delta x"), _example("Δy/Δx", N_("delta y over delta x"))),
            InsertItem(N_("Pi over 2"), _example("π/2", N_("pi over 2"))),
        ),
    ),
    GalleryCategory(
        N_("Script"),
        (
            _menu_item(N_("Subscript")),
            _menu_item(N_("Superscript")),
            InsertItem(N_("Subscript and superscript"), lambda source, caret: _scripts_template(source, caret)),
            InsertItem(N_("x squared"), _example("x^2", N_("x squared"))),
            InsertItem(N_("e to the minus i omega t"), _example("e^(-iωt)", N_("e to the minus i omega t"))),
            InsertItem(N_("x sub y squared"), _example("x_y^2", N_("x sub y squared"))),
        ),
    ),
    GalleryCategory(
        N_("Radical"),
        (
            _menu_item(N_("Square Root")),
            _menu_item(N_("Root with Index")),
            InsertItem(N_("Cube root"), _template("∛〖〗", 2, N_("cube root template, empty radicand"))),
            InsertItem(N_("Fourth root"), _template("∜〖〗", 2, N_("fourth root template, empty radicand"))),
            InsertItem(N_("Quadratic formula"), _example("x=(-b±√(b^2-4ac))/2a", N_("quadratic formula"))),
        ),
    ),
    GalleryCategory(
        N_("Integral"),
        (
            _menu_item(N_("Integral")),
            _menu_item(N_("Integral with Limits")),
            _menu_item(N_("Double Integral")),
            InsertItem(
                N_("Double integral with limits"),
                lambda source, caret: insert_nary_operator_template(source, caret, "∬", limits=True),
            ),
            _menu_item(N_("Triple Integral")),
            InsertItem(
                N_("Triple integral with limits"),
                lambda source, caret: insert_nary_operator_template(source, caret, "∭", limits=True),
            ),
            _menu_item(N_("Contour Integral")),
            InsertItem(
                N_("Contour integral with limits"),
                lambda source, caret: insert_nary_operator_template(source, caret, "∮", limits=True),
            ),
            InsertItem(N_("Surface integral"), lambda source, caret: insert_nary_operator_template(source, caret, "∯")),
            InsertItem(N_("Volume integral"), lambda source, caret: insert_nary_operator_template(source, caret, "∰")),
            InsertItem(N_("Differential dx"), _example("ⅆx", N_("d x"))),
            InsertItem(N_("Differential dy"), _example("ⅆy", N_("d y"))),
            InsertItem(N_("Differential d theta"), _example("ⅆθ", N_("d theta"))),
        ),
    ),
    GalleryCategory(
        N_("Large Operator"),
        (
            _menu_item(N_("Sum")),
            _menu_item(N_("Sum with Limits")),
            _menu_item(N_("Product")),
            _menu_item(N_("Product with Limits")),
            InsertItem(N_("Coproduct"), lambda source, caret: insert_nary_operator_template(source, caret, "∐")),
            InsertItem(
                N_("Coproduct with limits"),
                lambda source, caret: insert_nary_operator_template(source, caret, "∐", limits=True),
            ),
            _menu_item(N_("Union")),
            _menu_item(N_("Intersection")),
        ),
    ),
    GalleryCategory(
        N_("Bracket"),
        (
            InsertItem(N_("Parentheses"), _template("()", 1, N_("parentheses, empty"))),
            InsertItem(N_("Square brackets"), _template("[]", 1, N_("square brackets, empty"))),
            InsertItem(N_("Braces"), _template("{}", 1, N_("braces, empty"))),
            _menu_item(N_("Angle Brackets")),
            _menu_item(N_("Absolute Value")),
            _menu_item(N_("Norm")),
            _menu_item(N_("Floor")),
            _menu_item(N_("Ceiling")),
            _menu_item(N_("Binomial")),
            _menu_item(N_("Cases")),
        ),
    ),
    GalleryCategory(
        N_("Function"),
        tuple(
            _function(name)
            for name in ("sin", "cos", "tan", "cot", "sec", "csc", "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh")
        ),
    ),
    GalleryCategory(
        N_("Accent"),
        (
            InsertItem(N_("Vector arrow"), _accent("⃗", N_("vector arrow"))),
            InsertItem(N_("Hat"), _accent("̂", N_("hat"))),
            InsertItem(N_("Bar"), _accent("̅", N_("bar"))),
            InsertItem(N_("Dot"), _accent("̇", N_("dot"))),
            InsertItem(N_("Double dot"), _accent("̈", N_("double dot"))),
            InsertItem(N_("Tilde"), _accent("̃", N_("tilde"))),
            InsertItem(N_("Check"), _accent("̌", N_("check"))),
            InsertItem(N_("Acute"), _accent("́", N_("acute"))),
            InsertItem(N_("Grave"), _accent("̀", N_("grave"))),
            InsertItem(N_("Breve"), _accent("̆", N_("breve"))),
            InsertItem(N_("Overbar"), _template("¯()", 2, N_("overbar template, empty content"))),
            InsertItem(N_("Underbar"), _template("▁()", 2, N_("underbar template, empty content"))),
            _menu_item(N_("Overbrace")),
            _menu_item(N_("Underbrace")),
            _menu_item(N_("Box")),
        ),
    ),
    GalleryCategory(
        N_("Limit and Log"),
        (
            _menu_item(N_("Limit")),
            InsertItem(
                N_("Limit as n goes to infinity"),
                _template("lim_(n→∞) 〖〗", 11, N_("limit as n goes to infinity, empty argument")),
            ),
            InsertItem(
                N_("Limit inferior"),
                _template("lim\u00a0inf_() 〖〗", 9, N_("limit inferior template, empty limit condition")),
            ),
            InsertItem(
                N_("Limit superior"),
                _template("lim\u00a0sup_() 〖〗", 9, N_("limit superior template, empty limit condition")),
            ),
            _menu_item(N_("Logarithm")),
            _function("ln"),
            _function("log"),
        ),
    ),
    GalleryCategory(
        N_("Operator"),
        (
            _menu_item(N_("Arrow with Text Above")),
            _menu_item(N_("Arrow with Text Below")),
            _menu_item(N_("Equals with Text Above")),
            InsertItem(
                N_("Left arrow with text above"),
                lambda source, caret: insert_operator_template(source, caret, operator="←"),
            ),
            InsertItem(
                N_("Double arrow with text above"),
                lambda source, caret: insert_operator_template(source, caret, operator="⇒"),
            ),
            InsertItem(N_("Colon equals"), _example("≔", N_("colon equals"))),
            InsertItem(N_("Equal by definition"), _example("≝", N_("equal by definition"))),
            InsertItem(N_("Delta equals"), _example("≜", N_("delta equals"))),
        ),
    ),
    GalleryCategory(
        N_("Matrix"),
        (
            _menu_item("Matrix…"),
            InsertItem(N_("1 by 2 matrix"), _matrix(1, 2, "parentheses", N_("1 by 2 matrix"))),
            InsertItem(N_("2 by 1 matrix"), _matrix(2, 1, "parentheses", N_("2 by 1 matrix"))),
            InsertItem(N_("2 by 2 matrix"), _matrix(2, 2, "parentheses", N_("2 by 2 matrix"))),
            InsertItem(N_("2 by 2 matrix in brackets"), _matrix(2, 2, "brackets", N_("2 by 2 matrix in brackets"))),
            InsertItem(N_("2 by 2 determinant"), _matrix(2, 2, "bars", N_("2 by 2 determinant"))),
            InsertItem(N_("3 by 3 matrix"), _matrix(3, 3, "parentheses", N_("3 by 3 matrix"))),
            InsertItem(N_("2 by 2 identity matrix"), _example("(■(1&0@0&1))", N_("2 by 2 identity matrix"))),
            _menu_item(N_("Equation Array")),
        ),
    ),
    GalleryCategory(
        N_("Other"),
        (
            _menu_item(N_("Equation Number")),
            _menu_item("Symbol…"),
        ),
    ),
)


# The user's own equations (Save as New Equation), first when there are any.
MY_EQUATIONS = N_("My Equations")


def gallery_categories(saved: Sequence[SavedEquation]) -> tuple[GalleryCategory, ...]:
    """The gallery's categories: My Equations (when any are saved), then Word's."""
    if not saved:
        return CATEGORIES
    mine = tuple(InsertItem(equation.name, _example(equation.source, equation.name)) for equation in saved)
    return (GalleryCategory(MY_EQUATIONS, mine), *CATEGORIES)


def _scripts_template(source: str, caret: int) -> TemplateEdit:
    """`x_()^()` on the base before the caret, like the subscript template; `()_()^()` with none."""
    caret = max(0, min(caret, len(source)))
    before = source[caret - 1] if caret else ""
    if before.isalnum() or before in ")]}":
        return insert_template(
            source, caret, "_()^()", first_slot_offset=2, announcement=spoken("scripts template, empty subscript")
        )
    return insert_template(
        source, caret, "()_()^()", first_slot_offset=1, announcement=spoken("scripts template, empty base")
    )


def written_form(item: InsertItem, control_words: bool) -> str:
    """How the variant is typed in the linear view (`()\\sdiv()`, `x\\vec`), or "" for a dialog."""
    if item.insert is None or item.dialog:
        return ""
    edit = item.insert("x", 1)
    if edit.source == "x":
        return ""
    text = edit.source[1:]
    if unicodedata.combining(text[0]):
        text = edit.source  # An accent, shown on its base.
    if control_words:
        text, _caret = spell_with_control_words(text, None)
    return text.strip()
