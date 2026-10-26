"""The converter's MathML as Typst math, for the PDF export.

Typst typesets the equations; their spoken form (MathCAT's) goes in each
equation's `alt`, so the tagged PDF reads them. Every token is written
apart from the next (Typst reads `ab` as one name) and every Typst syntax
character is escaped, so only the structure is Typst's: fractions,
roots, scripts, limits, accents, braces, matrices, cases and equation
arrays. The converter's maths-italic letters go back to plain ones, which
Typst sets in italic itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree

from mathessible.documents.mathml_sanitize import local_name
from mathessible.editing.pasted_math import plain_letters

# Characters Typst math gives a meaning to: written escaped.
_SYNTAX = set("\\$#\"_^/&()[]{},;'@<>*~`")
# Nothing to show: invisible operators, the converter's empty fences.
_INVISIBLE = {"", "\u2061", "\u2062", "\u2063", "\u2064", "\u200b"}
_LARGE_OPERATORS = set("∑∏∐⋀⋁⋂⋃⨀⨁⨂⨄⨆∫∬∭∮∯∰∱∲∳⨌")
_MATRIX_DELIMITERS = {"(": '"("', "[": '"["', "{": '"{"', "|": '"|"', "‖": '"||"'}
_ERROR_COLOURS = ("#F00", "#F01")


@dataclass(frozen=True, slots=True)
class TypstEquation:
    math: str  # What goes between `$` and `$`.
    number: str | None = None  # "(1)" for `E=mc^2#(1)`.


def typst_math(mathml: str) -> TypstEquation:
    """An equation as Typst math, its number apart (the converter puts it in a labelled table row)."""
    # Not sanitised as for HTML: every text is escaped for Typst, and the attributes only steer
    # the conversion (the allow-list would drop `bevelled`).
    root = ElementTree.fromstring(mathml.strip())
    children = list(root)
    if len(children) == 1 and local_name(children[0].tag) == "mtable":
        number, body = _numbered(children[0])
        if number is not None:
            return TypstEquation(body, number)
    return TypstEquation(_join(root))


def _numbered(table: ElementTree.Element) -> tuple[str | None, str]:
    rows = [row for row in table if local_name(row.tag) in ("mtr", "mlabeledtr")]
    if len(rows) != 1:
        return None, ""
    cells = list(rows[0])
    labels = [cell for cell in cells if cell.get("intent") == ":equation-label"]
    if not labels:
        return None, ""
    body = " ".join(_node(cell) for cell in cells if cell is not labels[0])
    return "".join(labels[0].itertext()).strip(), body


def _escape(text: str) -> str:
    return " ".join("\\" + character if character in _SYNTAX else character for character in text)


def _string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _join(element: ElementTree.Element) -> str:
    return " ".join(part for part in (_node(child) for child in element) if part)


def _text(element: ElementTree.Element) -> str:
    return "".join(element.itertext())


def _node(element: ElementTree.Element) -> str:
    tag = local_name(element.tag)
    children = list(element)
    if tag in ("mstyle", "mpadded") and element.get("mathcolor") in _ERROR_COLOURS:
        return _string(_text(element))  # What did not build: its source, as text.
    if tag == "mi":
        return _identifier(element)
    if tag == "mn":
        text = _text(element)
        return text if text.isdigit() else _string(text)
    if tag == "mo":
        text = _text(element).strip()
        return "" if text in _INVISIBLE else _escape(text)
    if tag == "mtext":
        return _string(_text(element))
    if tag == "mspace":
        return ""
    if tag == "mfrac":
        return _fraction(element, children)
    if tag == "msqrt":
        return f"sqrt({_join(element)})"
    if tag == "mroot" and len(children) == 2:
        return f"root({_node(children[1])}, {_node(children[0])})"
    if tag in ("msub", "msup", "msubsup", "munder", "mover", "munderover") and children:
        return _scripts(tag, element, children)
    if tag == "mrow" and len(children) >= 2 and (element.get("intent") == ":fenced" or _bars(children)):
        return _fenced(children)
    if tag == "mtable":
        return _table(element, None)
    if tag == "menclose" and "box" in (element.get("notation") or "box"):
        return f"#box(stroke: 0.5pt, inset: 2pt, ${_join(element)}$)"
    if tag == "mphantom":
        return f"#hide(${_join(element)}$)"
    if tag == "semantics":
        return _node(children[0]) if children else ""
    if tag in ("annotation", "annotation-xml"):
        return ""
    return _join(element)


def _identifier(element: ElementTree.Element) -> str:
    text = plain_letters(_text(element).strip())
    if not text:
        return ""
    if len(text) > 1:
        return f"op({_string(text)})"  # A function's name: sin, lim, log.
    if element.get("mathvariant") == "normal" and text.isalpha():
        return f"upright({text})"
    return _escape(text)


def _fraction(element: ElementTree.Element, children: list[ElementTree.Element]) -> str:
    if len(children) != 2:
        return _join(element)
    top, bottom = (_node(child) for child in children)
    if element.get("linethickness") in ("0", "0pt", "0px"):
        return f"mat(delim: #none, {top}; {bottom})"  # A binomial's stack (¦).
    if element.get("bevelled") == "true":
        return f"{top} \\/ {bottom}"
    return f"frac({top}, {bottom})"


def _is_operator(element: ElementTree.Element) -> bool:
    text = _text(element).strip()
    return local_name(element.tag) == "mo" and (text in _LARGE_OPERATORS or element.get("largeop") == "true")


def _scripts(tag: str, element: ElementTree.Element, children: list[ElementTree.Element]) -> str:
    base, scripts = children[0], children[1:]
    if tag == "mover" and len(scripts) == 1:
        mark = _text(scripts[0]).strip()
        if mark == "⏞":
            return f"overbrace({_node(base)})"
        if mark in ("¯", "‾", "̅"):
            return f"overline({_node(base)})"
        if element.get("accent") == "true" and len(mark) == 1:
            return f"accent({_node(base)}, {_string(mark)})"
        if local_name(base.tag) == "mover" and len(base) == 2 and _text(list(base)[1]).strip() == "⏞":
            return f"overbrace({_node(list(base)[0])}, {_node(scripts[0])})"
    if tag == "munder" and len(scripts) == 1:
        mark = _text(scripts[0]).strip()
        if mark == "⏟":
            return f"underbrace({_node(base)})"
        if mark in ("_", "̲"):
            return f"underline({_node(base)})"
        if local_name(base.tag) == "munder" and len(base) == 2 and _text(list(base)[1]).strip() == "⏟":
            return f"underbrace({_node(list(base)[0])}, {_node(scripts[0])})"
    under = tag.startswith("mu")
    base_text = _node(base)
    if under and (_is_operator(base) or local_name(base.tag) == "mi"):
        base_text = f"limits({base_text})"
    bottom = top = None
    if tag in ("msub", "munder"):
        bottom = scripts[0]
    elif tag in ("msup", "mover"):
        top = scripts[0]
    elif len(scripts) == 2:
        bottom, top = scripts
    parts = [base_text or "zws"]
    if bottom is not None:
        parts.append(f"b: {_node(bottom) or 'zws'}")
    if top is not None:
        parts.append(f"t: {_node(top) or 'zws'}")
    return f"attach({', '.join(parts)})"


def _bars(children: list[ElementTree.Element]) -> bool:
    """`|x|`, `‖v‖`: a row between two bars of the same kind (an absolute value or a norm)."""
    first, last = children[0], children[-1]
    return (
        local_name(first.tag) == local_name(last.tag) == "mo"
        and _text(first).strip() == _text(last).strip()
        and _text(first).strip() in ("|", "‖")
    )


def _fenced(children: list[ElementTree.Element]) -> str:
    opening, closing = _text(children[0]).strip(), _text(children[-1]).strip()
    inner = children[1:-1]
    if len(inner) == 1 and local_name(inner[0].tag) == "mtable":
        if opening == "{" and closing in _INVISIBLE:
            return _table(inner[0], "cases")
        if opening in _MATRIX_DELIMITERS and closing not in _INVISIBLE:
            return _table(inner[0], _MATRIX_DELIMITERS[opening])
    stacked = len(inner) == 1 and local_name(inner[0].tag) == "mfrac" and inner[0].get("linethickness") in ("0", "0pt")
    if stacked and (opening, closing) == ("(", ")"):
        top, bottom = (_node(child) for child in inner[0])
        return f"binom({top}, {bottom})"  # (n¦k)
    content = " ".join(part for part in (_node(child) for child in inner) if part)
    if opening in _INVISIBLE and closing in _INVISIBLE:
        return content
    left = "" if opening in _INVISIBLE else _escape(opening)
    right = "" if closing in _INVISIBLE else _escape(closing)
    return f"lr({left} {content} {right})"


def _table(table: ElementTree.Element, kind: str | None) -> str:
    rows = [[_node(cell) or "zws" for cell in row] for row in table if local_name(row.tag) in ("mtr", "mlabeledtr")]
    if kind == "cases":
        return "cases(" + ", ".join(" & ".join(row) for row in rows) + ")"
    if table.get("intent") == ":equations":
        return " \\ ".join(" & ".join(row) for row in rows)  # An equation array, aligned at its `&`.
    delimiter = kind or "#none"
    return f"mat(delim: {delimiter}, " + "; ".join(", ".join(row) for row in rows) + ")"
