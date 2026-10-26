"""The converter's MathML as Office Math (OMML), Word's own equations, for the DOCX export.

Each structure becomes Word's: fractions (`m:f`), roots (`m:rad`), scripts
(`m:sSub`/`m:sSup`/`m:sSubSup`), sums and integrals with their limits
(`m:nary`), functions (`m:func`), limits under and over (`m:limLow`/
`m:limUpp`), accents (`m:acc`), bars (`m:bar`), braces (`m:groupChr`),
delimiters (`m:d`), matrices (`m:m`) and equation arrays (`m:eqArr`). So
the equation in Word is an equation Word edits and reads aloud. Text is
XML-escaped, never markup; the converter's maths-italic letters go back
to plain ones, which Word sets in italic itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr

from mathessible.documents.mathml_sanitize import local_name
from mathessible.editing.pasted_math import plain_letters

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_INVISIBLE = {"", "⁡", "⁢", "⁣", "⁤", "​"}
_LARGE_OPERATORS = set("∑∏∐⋀⋁⋂⋃⨀⨁⨂⨄⨆∫∬∭∮∯∰∱∲∳⨌")
_ERROR_COLOURS = ("#F00", "#F01")


@dataclass(frozen=True, slots=True)
class OmmlEquation:
    body: str  # The equation's elements, inside `m:oMath`.
    number: str | None = None  # "(1)", for `E=mc^2#(1)`.

    @property
    def xml(self) -> str:
        """An `m:oMath` element, its namespace declared."""
        return f'<m:oMath xmlns:m="{M}">{self.body}</m:oMath>'


def omml_math(mathml: str) -> OmmlEquation:
    """An equation as Office Math, its number apart (the converter puts it in a labelled table row)."""
    root = ElementTree.fromstring(mathml.strip())
    children = list(root)
    number = None
    body = _join(root)
    if len(children) == 1 and local_name(children[0].tag) == "mtable":
        numbered = _numbered(children[0])
        if numbered is not None:
            number, body = numbered
    return OmmlEquation(body, number)


def _numbered(table: ElementTree.Element) -> tuple[str, str] | None:
    rows = [row for row in table if local_name(row.tag) in ("mtr", "mlabeledtr")]
    if len(rows) != 1:
        return None
    cells = list(rows[0])
    labels = [cell for cell in cells if cell.get("intent") == ":equation-label"]
    if not labels:
        return None
    body = "".join(_node(cell) for cell in cells if cell is not labels[0])
    return "".join(labels[0].itertext()).strip(), body


def _run(text: str, style: str = "") -> str:
    """A run of maths text: `style` "p" upright (names, numbers), "nor" ordinary text."""
    if not text:
        return ""
    properties = {"p": '<m:rPr><m:sty m:val="p"/></m:rPr>', "nor": "<m:rPr><m:nor/></m:rPr>"}.get(style, "")
    return f'<m:r>{properties}<m:t xml:space="preserve">{escape(text)}</m:t></m:r>'


def _wrap(tag: str, content: str) -> str:
    return f"<m:{tag}>{content}</m:{tag}>"


def _value(tag: str, value: str) -> str:
    return f"<m:{tag} m:val={quoteattr(value)}/>"


def _text(element: ElementTree.Element) -> str:
    return "".join(element.itertext())


def _join(element: ElementTree.Element) -> str:
    return "".join(_node(child) for child in element)


def _node(element: ElementTree.Element) -> str:
    tag = local_name(element.tag)
    children = list(element)
    if tag in ("mstyle", "mpadded") and element.get("mathcolor") in _ERROR_COLOURS:
        return _run(_text(element), "nor")  # What did not build: its source, as text.
    if tag == "mi":
        text = plain_letters(_text(element).strip())
        upright = len(text) > 1 or element.get("mathvariant") == "normal"
        return _run(text, "p" if upright else "")
    if tag == "mn":
        return _run(_text(element))
    if tag == "mo":
        text = _text(element).strip()
        return "" if text in _INVISIBLE else _run(text)
    if tag == "mtext":
        return _run(_text(element), "nor")
    if tag == "mspace" or tag in ("annotation", "annotation-xml"):
        return ""
    if tag == "mfrac" and len(children) == 2:
        kind = ""
        if element.get("linethickness") in ("0", "0pt", "0px"):
            kind = _wrap("fPr", _value("type", "noBar"))
        elif element.get("bevelled") == "true":
            kind = _wrap("fPr", _value("type", "skw"))
        return _wrap("f", kind + _wrap("num", _node(children[0])) + _wrap("den", _node(children[1])))
    if tag == "msqrt":
        return _wrap("rad", _wrap("radPr", _value("degHide", "on")) + "<m:deg/>" + _wrap("e", _join(element)))
    if tag == "mroot" and len(children) == 2:
        return _wrap("rad", _wrap("deg", _node(children[1])) + _wrap("e", _node(children[0])))
    if tag in ("msub", "msup", "msubsup") and children:
        return _scripts(tag, children)
    if tag in ("munder", "mover", "munderover") and children:
        return _under_over(tag, element, children)
    if tag == "mrow" and (element.get("intent") or "").startswith(":nary") and children:
        return _nary(children)
    if tag == "mrow" and element.get("intent") == ":function" and children:
        return _function(children)
    if tag == "mrow" and len(children) >= 2 and (element.get("intent") == ":fenced" or _bars(children)):
        return _fenced(children)
    if tag == "mtable":
        return _table(element)
    if tag == "menclose":
        return _wrap("borderBox", _wrap("e", _join(element)))
    if tag == "mphantom":
        return _wrap("phant", _wrap("e", _join(element)))
    if tag == "semantics":
        return _node(children[0]) if children else ""
    return _join(element)


def _scripts(tag: str, children: list[ElementTree.Element]) -> str:
    base = _wrap("e", _node(children[0]))
    if tag == "msub" and len(children) == 2:
        return _wrap("sSub", base + _wrap("sub", _node(children[1])))
    if tag == "msup" and len(children) == 2:
        return _wrap("sSup", base + _wrap("sup", _node(children[1])))
    if len(children) == 3:
        return _wrap("sSubSup", base + _wrap("sub", _node(children[1])) + _wrap("sup", _node(children[2])))
    return "".join(_node(child) for child in children)


def _under_over(tag: str, element: ElementTree.Element, children: list[ElementTree.Element]) -> str:
    base, scripts = children[0], children[1:]
    mark = _text(scripts[0]).strip() if scripts else ""
    if tag == "mover" and len(scripts) == 1:
        if mark in ("⏞", "⏟"):
            return _brace(_node(base), mark)
        if mark in ("¯", "‾", "̅"):
            return _wrap("bar", _wrap("barPr", _value("pos", "top")) + _wrap("e", _node(base)))
        if element.get("accent") == "true" and len(mark) == 1:
            return _wrap("acc", _wrap("accPr", _value("chr", mark)) + _wrap("e", _node(base)))
        if local_name(base.tag) == "mover" and len(base) == 2 and _text(list(base)[1]).strip() == "⏞":
            braced = _brace(_node(list(base)[0]), "⏞")
            return _wrap("limUpp", _wrap("e", braced) + _wrap("lim", _node(scripts[0])))
    if tag == "munder" and len(scripts) == 1:
        if mark == "⏟":
            return _brace(_node(base), mark)
        if mark in ("_", "̲"):
            return _wrap("bar", _wrap("barPr", _value("pos", "bot")) + _wrap("e", _node(base)))
        if local_name(base.tag) == "munder" and len(base) == 2 and _text(list(base)[1]).strip() == "⏟":
            braced = _brace(_node(list(base)[0]), "⏟")
            return _wrap("limLow", _wrap("e", braced) + _wrap("lim", _node(scripts[0])))
    if _is_operator(base):
        return _nary([element])  # A sum with limits but no operand of its own.
    result = _node(base)
    if tag in ("munder", "munderover"):
        result = _wrap("limLow", _wrap("e", result) + _wrap("lim", _node(scripts[0])))
    if tag in ("mover", "munderover"):
        result = _wrap("limUpp", _wrap("e", result) + _wrap("lim", _node(scripts[-1])))
    return result


def _brace(content: str, mark: str) -> str:
    position = "top" if mark == "⏞" else "bot"
    properties = _value("chr", mark) + _value("pos", position) + _value("vertJc", "bot" if position == "top" else "top")
    return _wrap("groupChr", _wrap("groupChrPr", properties) + _wrap("e", content))


def _is_operator(element: ElementTree.Element) -> bool:
    return local_name(element.tag) == "mo" and (
        _text(element).strip() in _LARGE_OPERATORS or element.get("largeop") == "true"
    )


def _nary(children: list[ElementTree.Element]) -> str:
    """`:nary`: the operator with its limits, then its operand (the converter's `naryand`)."""
    scripted, operand = children[0], children[1:]
    tag = local_name(scripted.tag)
    parts = list(scripted)
    if tag in ("munderover", "msubsup", "munder", "msub", "mover", "msup") and parts:
        sign = _text(parts[0]).strip()
        lower = parts[1] if tag in ("munderover", "msubsup", "munder", "msub") and len(parts) > 1 else None
        upper = parts[-1] if tag in ("munderover", "msubsup", "mover", "msup") and len(parts) > 1 else None
        location = "undOvr" if tag.startswith("mu") else "subSup"
    else:
        sign, lower, upper, location = _text(scripted).strip(), None, None, "undOvr"
    properties = _value("chr", sign) + _value("limLoc", location) + _value("grow", "1")  # As Word's own.
    if lower is None:
        properties += _value("subHide", "1")
    if upper is None:
        properties += _value("supHide", "1")
    body = "".join(_node(child) for child in operand)
    return _wrap(
        "nary",
        _wrap("naryPr", properties)
        + _wrap("sub", _node(lower) if lower is not None else "")
        + _wrap("sup", _node(upper) if upper is not None else "")
        + _wrap("e", body),
    )


def _function(children: list[ElementTree.Element]) -> str:
    """`:function`: the name (a script or a limit included), then its argument after U+2061."""
    split = next(
        (index for index, child in enumerate(children) if local_name(child.tag) == "mo" and _text(child) == "⁡"),
        None,
    )
    if split is None:
        return "".join(_node(child) for child in children)
    name = "".join(_node(child) for child in children[:split])
    argument = "".join(_node(child) for child in children[split + 1 :])
    return _wrap("func", _wrap("fName", name) + _wrap("e", argument))


def _bars(children: list[ElementTree.Element]) -> bool:
    first, last = children[0], children[-1]
    return (
        local_name(first.tag) == local_name(last.tag) == "mo"
        and _text(first).strip() == _text(last).strip()
        and _text(first).strip() in ("|", "‖")
    )


def _fenced(children: list[ElementTree.Element]) -> str:
    opening, closing = _text(children[0]).strip(), _text(children[-1]).strip()
    inner = "".join(_node(child) for child in children[1:-1])
    if opening in _INVISIBLE and closing in _INVISIBLE:
        return inner  # The argument box 〖〗: Word writes its content alone (checked with its mathml2omml.xsl).
    properties = _value("begChr", "" if opening in _INVISIBLE else opening)
    properties += _value("endChr", "" if closing in _INVISIBLE else closing)
    return _wrap("d", _wrap("dPr", properties) + _wrap("e", inner))


def _table(table: ElementTree.Element) -> str:
    """A matrix (`■`, cases included: a matrix in a brace, as Word builds it), or an equation array
    (`█`) whose cells are aligned at an `&`, as Word writes it."""
    rows = [list(row) for row in table if local_name(row.tag) in ("mtr", "mlabeledtr")]
    if table.get("intent") == ":equations":
        return _wrap("eqArr", "".join(_wrap("e", _run("&").join(_node(cell) for cell in row)) for row in rows))
    columns = max((len(row) for row in rows), default=1)
    matrix = "".join(
        _wrap("mr", "".join(_wrap("e", _node(cell)) for cell in row) + "<m:e/>" * (columns - len(row))) for row in rows
    )
    return _wrap("m", matrix)
