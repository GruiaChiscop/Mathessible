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
from dataclasses import dataclass

from .insert_catalog import InsertItem, Inserter, all_items
from .math_templates import (
    insert_nary_operator_template,
    insert_operator_template,
)
from .matrix_templates import insert_matrix_template
from .source_view import spell_with_control_words
from .template_source import TemplateEdit, insert_template


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
            return TemplateEdit(source, caret, f"{name}: type the base first, then the accent")
        return insert_template(source, caret, mark, first_slot_offset=len(mark), announcement=f"{name} on {before}")

    return insert


def _matrix(rows: int, columns: int, fence: str, name: str) -> Inserter:
    def insert(source: str, caret: int) -> TemplateEdit:
        edit = insert_matrix_template(source, caret, rows, columns, fence)
        return TemplateEdit(edit.source, edit.caret, f"{name}, empty cell, row 1, column 1")

    return insert


def _menu_item(label: str) -> InsertItem:
    """An Insert-menu entry by its label (mnemonic "&" ignored), so both lists stay one."""
    for item in all_items():
        if item.label.replace("&", "") == label:
            return InsertItem(label.rstrip("…"), item.insert, dialog=item.dialog)
    raise KeyError(label)


def _function(name: str) -> InsertItem:
    return InsertItem(name, _template(f"{name} 〖〗", len(name) + 2, f"{name} template, empty argument"))


CATEGORIES: tuple[GalleryCategory, ...] = (
    GalleryCategory(
        "Fraction",
        (
            _menu_item("Fraction"),
            InsertItem("Skewed fraction", _template("()⁄()", 1, "skewed fraction template, empty numerator")),
            InsertItem("Linear fraction", _template("()∕()", 1, "linear fraction template, empty numerator")),
            InsertItem("Small fraction", _template("()⊘()", 1, "small fraction template, empty numerator")),
            InsertItem("dy over dx", _example("ⅆy/ⅆx", "d y over d x")),
            InsertItem("Partial y over partial x", _example("∂y/∂x", "partial y over partial x")),
            InsertItem("Delta y over delta x", _example("Δy/Δx", "delta y over delta x")),
            InsertItem("Pi over 2", _example("π/2", "pi over 2")),
        ),
    ),
    GalleryCategory(
        "Script",
        (
            _menu_item("Subscript"),
            _menu_item("Superscript"),
            InsertItem("Subscript and superscript", lambda source, caret: _scripts_template(source, caret)),
            InsertItem("x squared", _example("x^2", "x squared")),
            InsertItem("e to the minus i omega t", _example("e^(-iωt)", "e to the minus i omega t")),
            InsertItem("x sub y squared", _example("x_y^2", "x sub y squared")),
        ),
    ),
    GalleryCategory(
        "Radical",
        (
            _menu_item("Square Root"),
            _menu_item("Root with Index"),
            InsertItem("Cube root", _template("∛〖〗", 2, "cube root template, empty radicand")),
            InsertItem("Fourth root", _template("∜〖〗", 2, "fourth root template, empty radicand")),
            InsertItem("Quadratic formula", _example("x=(-b±√(b^2-4ac))/2a", "quadratic formula")),
        ),
    ),
    GalleryCategory(
        "Integral",
        (
            _menu_item("Integral"),
            _menu_item("Integral with Limits"),
            _menu_item("Double Integral"),
            InsertItem(
                "Double integral with limits",
                lambda source, caret: insert_nary_operator_template(source, caret, "∬", limits=True),
            ),
            _menu_item("Triple Integral"),
            InsertItem(
                "Triple integral with limits",
                lambda source, caret: insert_nary_operator_template(source, caret, "∭", limits=True),
            ),
            _menu_item("Contour Integral"),
            InsertItem(
                "Contour integral with limits",
                lambda source, caret: insert_nary_operator_template(source, caret, "∮", limits=True),
            ),
            InsertItem("Surface integral", lambda source, caret: insert_nary_operator_template(source, caret, "∯")),
            InsertItem("Volume integral", lambda source, caret: insert_nary_operator_template(source, caret, "∰")),
            InsertItem("Differential dx", _example("ⅆx", "d x")),
            InsertItem("Differential dy", _example("ⅆy", "d y")),
            InsertItem("Differential d theta", _example("ⅆθ", "d theta")),
        ),
    ),
    GalleryCategory(
        "Large Operator",
        (
            _menu_item("Sum"),
            _menu_item("Sum with Limits"),
            _menu_item("Product"),
            _menu_item("Product with Limits"),
            InsertItem("Coproduct", lambda source, caret: insert_nary_operator_template(source, caret, "∐")),
            InsertItem(
                "Coproduct with limits",
                lambda source, caret: insert_nary_operator_template(source, caret, "∐", limits=True),
            ),
            _menu_item("Union"),
            _menu_item("Intersection"),
        ),
    ),
    GalleryCategory(
        "Bracket",
        (
            InsertItem("Parentheses", _template("()", 1, "parentheses, empty")),
            InsertItem("Square brackets", _template("[]", 1, "square brackets, empty")),
            InsertItem("Braces", _template("{}", 1, "braces, empty")),
            _menu_item("Angle Brackets"),
            _menu_item("Absolute Value"),
            _menu_item("Norm"),
            _menu_item("Floor"),
            _menu_item("Ceiling"),
            _menu_item("Binomial"),
            _menu_item("Cases"),
        ),
    ),
    GalleryCategory(
        "Function",
        tuple(
            _function(name)
            for name in ("sin", "cos", "tan", "cot", "sec", "csc", "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh")
        ),
    ),
    GalleryCategory(
        "Accent",
        (
            InsertItem("Vector arrow", _accent("⃗", "vector arrow")),
            InsertItem("Hat", _accent("̂", "hat")),
            InsertItem("Bar", _accent("̅", "bar")),
            InsertItem("Dot", _accent("̇", "dot")),
            InsertItem("Double dot", _accent("̈", "double dot")),
            InsertItem("Tilde", _accent("̃", "tilde")),
            InsertItem("Check", _accent("̌", "check")),
            InsertItem("Acute", _accent("́", "acute")),
            InsertItem("Grave", _accent("̀", "grave")),
            InsertItem("Breve", _accent("̆", "breve")),
            InsertItem("Overbar", _template("¯()", 2, "overbar template, empty content")),
            InsertItem("Underbar", _template("▁()", 2, "underbar template, empty content")),
            _menu_item("Overbrace"),
            _menu_item("Underbrace"),
            _menu_item("Box"),
        ),
    ),
    GalleryCategory(
        "Limit and Log",
        (
            _menu_item("Limit"),
            InsertItem("Limit as n goes to infinity", _template("lim_(n→∞) 〖〗", 11, "limit as n goes to infinity, empty argument")),
            InsertItem(
                "Limit inferior", _template("lim\u00a0inf_() 〖〗", 9, "limit inferior template, empty limit condition")
            ),
            InsertItem(
                "Limit superior", _template("lim\u00a0sup_() 〖〗", 9, "limit superior template, empty limit condition")
            ),
            _menu_item("Logarithm"),
            _function("ln"),
            _function("log"),
        ),
    ),
    GalleryCategory(
        "Operator",
        (
            _menu_item("Arrow with Text Above"),
            _menu_item("Arrow with Text Below"),
            _menu_item("Equals with Text Above"),
            InsertItem(
                "Left arrow with text above",
                lambda source, caret: insert_operator_template(source, caret, operator="←"),
            ),
            InsertItem(
                "Double arrow with text above",
                lambda source, caret: insert_operator_template(source, caret, operator="⇒"),
            ),
            InsertItem("Colon equals", _example("≔", "colon equals")),
            InsertItem("Equal by definition", _example("≝", "equal by definition")),
            InsertItem("Delta equals", _example("≜", "delta equals")),
        ),
    ),
    GalleryCategory(
        "Matrix",
        (
            _menu_item("Matrix…"),
            InsertItem("1 by 2 matrix", _matrix(1, 2, "parentheses", "1 by 2 matrix")),
            InsertItem("2 by 1 matrix", _matrix(2, 1, "parentheses", "2 by 1 matrix")),
            InsertItem("2 by 2 matrix", _matrix(2, 2, "parentheses", "2 by 2 matrix")),
            InsertItem("2 by 2 matrix in brackets", _matrix(2, 2, "brackets", "2 by 2 matrix in brackets")),
            InsertItem("2 by 2 determinant", _matrix(2, 2, "bars", "2 by 2 determinant")),
            InsertItem("3 by 3 matrix", _matrix(3, 3, "parentheses", "3 by 3 matrix")),
            InsertItem("2 by 2 identity matrix", _example("(■(1&0@0&1))", "2 by 2 identity matrix")),
            _menu_item("Equation Array"),
        ),
    ),
    GalleryCategory(
        "Other",
        (
            _menu_item("Equation Number"),
            _menu_item("Symbol…"),
        ),
    ),
)


def _scripts_template(source: str, caret: int) -> TemplateEdit:
    """`x_()^()` on the base before the caret, like the subscript template; `()_()^()` with none."""
    caret = max(0, min(caret, len(source)))
    before = source[caret - 1] if caret else ""
    if before.isalnum() or before in ")]}":
        return insert_template(source, caret, "_()^()", first_slot_offset=2, announcement="scripts template, empty subscript")
    return insert_template(source, caret, "()_()^()", first_slot_offset=1, announcement="scripts template, empty base")


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
