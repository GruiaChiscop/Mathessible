"""Word's equations (OMML) as MathML, for a paste from Word: the converter's lineariser then writes them as
UnicodeMath, as it does a pasted MathML equation.

The reverse of omml_math (the DOCX export), structure by structure: fractions (`m:f`), roots (`m:rad`),
scripts (`m:sSub`, `m:sSup`, `m:sSubSup`, `m:sPre`), sums and integrals (`m:nary`), functions
(`m:func`), limits (`m:limLow`, `m:limUpp`), accents (`m:acc`), bars (`m:bar`), braces (`m:groupChr`),
delimiters (`m:d`), matrices (`m:m`) and equation arrays (`m:eqArr`). An unknown element gives its
content. Word's clipboard HTML holds OMML as HTML, not XML (a run's text without `m:t`, styling spans
between the elements), so it is read with the paste's own tolerant parser. Text is escaped, never markup.
"""

from __future__ import annotations

import html as html_module
import re

from mathessible.documents.pasted_html import Node, Parser

_DEFAULT_NARY = "∫"
_DEFAULT_ACCENT = "̂"
_DEFAULT_GROUP = "⏟"
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_MATH = '<math xmlns="http://www.w3.org/1998/Math/MathML">'


def mathml_from_omml(omml: str) -> str:
    """The OMML of one equation (`m:oMathPara` or `m:oMath`) as a `math` element; several lines of an
    `m:oMathPara` as a one-column table."""
    parser = Parser()
    parser.feed(omml)
    lines = _find_all(parser.root, "m:omath")
    if not lines:
        return f"{_MATH}</math>"
    if len(lines) == 1:
        return f"{_MATH}{_row(lines[0])}</math>"
    rows = "".join(f"<mtr><mtd>{_row(line)}</mtd></mtr>" for line in lines)
    return f"{_MATH}<mtable>{rows}</mtable></math>"


def _find_all(node: Node, tag: str) -> list[Node]:
    found = []
    for child in node.children:
        if isinstance(child, Node):
            if child.tag == tag:
                found.append(child)
            else:
                found.extend(_find_all(child, tag))
    return found


def _elements(node: Node) -> list[Node]:
    """The node's OMML children, looking through Word's styling spans and HTML emphasis."""
    found = []
    for child in node.children:
        if not isinstance(child, Node):
            continue
        if child.tag.startswith("m:"):
            found.append(child)
        else:
            found.extend(_elements(child))
    return found


def _child(node: Node, tag: str) -> Node | None:
    return next((child for child in _elements(node) if child.tag == tag), None)


def _property(node: Node, properties: str, name: str) -> str | None:
    """`m:val` of a property (`m:chr` in `m:naryPr`); None when it is not given."""
    holder = _child(node, properties)
    found = _child(holder, name) if holder is not None else None
    return None if found is None else found.attrs.get("m:val", "")


def _row(node: Node | None, names: bool = False) -> str:
    """The node's content in an `mrow`; with `names`, a run's letters as one name (a function's)."""
    if node is None:
        return "<mrow></mrow>"
    return "<mrow>" + "".join(_element(child, names) for child in _elements(node)) + "</mrow>"


def _operator(text: str, **attributes: str) -> str:
    extra = "".join(f' {key}="{value}"' for key, value in attributes.items())
    return f"<mo{extra}>{html_module.escape(text)}</mo>"


def _element(node: Node, names: bool = False) -> str:
    tag = node.tag
    if tag.endswith("pr") or tag in ("m:ctrlpr", "m:rpr"):
        return ""  # Properties: read where they apply.
    if tag == "m:r":
        return _run(node, names)
    if tag in ("m:ssup", "m:ssub", "m:ssubsup"):
        base = _row(_child(node, "m:e"))
        sub, sup = _row(_child(node, "m:sub")), _row(_child(node, "m:sup"))
        if tag == "m:ssup":
            return f"<msup>{base}{sup}</msup>"
        if tag == "m:ssub":
            return f"<msub>{base}{sub}</msub>"
        return f"<msubsup>{base}{sub}{sup}</msubsup>"
    if tag == "m:spre":
        base = _row(_child(node, "m:e"))
        sub, sup = _row(_child(node, "m:sub")), _row(_child(node, "m:sup"))
        return f"<mmultiscripts>{base}<mprescripts/>{sub}{sup}</mmultiscripts>"
    if tag == "m:f":
        numerator, denominator = _row(_child(node, "m:num")), _row(_child(node, "m:den"))
        kind = _property(node, "m:fpr", "m:type")
        if kind in ("lin", "skw"):
            return f"<mrow>{numerator}{_operator('/')}{denominator}</mrow>"
        thickness = ' linethickness="0"' if kind == "noBar" else ""
        return f"<mfrac{thickness}>{numerator}{denominator}</mfrac>"
    if tag == "m:rad":
        base, degree = _row(_child(node, "m:e")), _child(node, "m:deg")
        hidden = _property(node, "m:radpr", "m:deghide") in ("1", "on", "true")
        if hidden or degree is None or not _elements(degree):
            return f"<msqrt>{base}</msqrt>"
        return f"<mroot>{base}{_row(degree)}</mroot>"
    if tag == "m:nary":
        sign = _property(node, "m:narypr", "m:chr") or _DEFAULT_NARY
        under = _property(node, "m:narypr", "m:limloc") == "undOvr"
        hide_sub = _property(node, "m:narypr", "m:subhide") in ("1", "on", "true")
        hide_sup = _property(node, "m:narypr", "m:suphide") in ("1", "on", "true")
        operator = _operator(sign, largeop="true")
        sub, sup = _row(_child(node, "m:sub")), _row(_child(node, "m:sup"))
        if hide_sub and hide_sup:
            scripted = operator
        elif hide_sup:
            scripted = f"<{'munder' if under else 'msub'}>{operator}{sub}</{'munder' if under else 'msub'}>"
        elif hide_sub:
            scripted = f"<{'mover' if under else 'msup'}>{operator}{sup}</{'mover' if under else 'msup'}>"
        else:
            both = "munderover" if under else "msubsup"
            scripted = f"<{both}>{operator}{sub}{sup}</{both}>"
        return f"<mrow>{scripted}{_row(_child(node, 'm:e'))}</mrow>"
    if tag == "m:d":
        opening = _property(node, "m:dpr", "m:begchr")
        closing = _property(node, "m:dpr", "m:endchr")
        separator = _property(node, "m:dpr", "m:sepchr")
        parts = [_row(child) for child in _elements(node) if child.tag == "m:e"]
        joined = _operator("|" if separator is None else separator).join(parts)
        opening = "(" if opening is None else opening
        closing = ")" if closing is None else closing
        fences = (
            _operator(opening, fence="true") if opening else "",
            _operator(closing, fence="true") if closing else "",
        )
        return f"<mrow>{fences[0]}{joined}{fences[1]}</mrow>"
    if tag == "m:acc":
        accent = _property(node, "m:accpr", "m:chr") or _DEFAULT_ACCENT
        return f'<mover accent="true">{_row(_child(node, "m:e"))}{_operator(accent)}</mover>'
    if tag == "m:bar":
        if _property(node, "m:barpr", "m:pos") == "top":
            return f'<mover accent="true">{_row(_child(node, "m:e"))}{_operator("¯")}</mover>'
        return f'<munder accentunder="true">{_row(_child(node, "m:e"))}{_operator("_")}</munder>'
    if tag == "m:groupchr":
        sign = _property(node, "m:groupchrpr", "m:chr") or _DEFAULT_GROUP
        above = _property(node, "m:groupchrpr", "m:pos") == "top"
        name = "mover" if above else "munder"
        return f"<{name}>{_row(_child(node, 'm:e'))}{_operator(sign, stretchy='true')}</{name}>"
    if tag == "m:func":
        name = _row(_child(node, "m:fname"), names=True)
        return f"<mrow>{name}{_operator(chr(0x2061))}{_row(_child(node, 'm:e'))}</mrow>"
    if tag in ("m:limlow", "m:limupp"):
        name = "munder" if tag == "m:limlow" else "mover"
        return f"<{name}>{_row(_child(node, 'm:e'), names=True)}{_row(_child(node, 'm:lim'))}</{name}>"
    if tag == "m:m":
        rows = [child for child in _elements(node) if child.tag == "m:mr"]
        cells = (
            "<mtr>" + "".join(f"<mtd>{_row(cell)}</mtd>" for cell in _elements(row) if cell.tag == "m:e") + "</mtr>"
            for row in rows
        )
        return "<mtable>" + "".join(cells) + "</mtable>"
    if tag == "m:eqarr":
        lines = [child for child in _elements(node) if child.tag == "m:e"]
        return "<mtable>" + "".join(f"<mtr><mtd>{_row(line)}</mtd></mtr>" for line in lines) + "</mtable>"
    if tag == "m:borderbox":
        return f'<menclose notation="box">{_row(_child(node, "m:e"))}</menclose>'
    return _row(node, names)  # m:e, m:box, m:phant and what is not known: the content.


def _run(node: Node, names: bool) -> str:
    """A run's text as tokens: numbers, letters (one name each, or the whole run as a name: a
    function's, or text Word sets upright, `m:sty p`), operators."""
    text = html_module.unescape(_text(node)).replace("\xa0", " ")
    properties = _child(node, "m:rpr")
    upright = (
        names
        or _property(node, "m:rpr", "m:sty") == "p"
        or (properties is not None and _child(properties, "m:nor") is not None)
    )
    tokens: list[str] = []
    index = 0
    while index < len(text):
        character = text[index]
        number = _NUMBER.match(text, index)
        if number:
            tokens.append(f"<mn>{html_module.escape(number.group())}</mn>")
            index = number.end()
            continue
        if character.isalpha():
            end = index + 1
            if upright:
                while end < len(text) and text[end].isalpha():
                    end += 1
            word = text[index:end]
            variant = ' mathvariant="normal"' if upright and len(word) == 1 and not names else ""
            tokens.append(f"<mi{variant}>{html_module.escape(word)}</mi>")
            index = end
            continue
        if not character.isspace():
            tokens.append(_operator(character))
        index += 1
    return "".join(tokens)


def _text(node: Node) -> str:
    """A run's text: `m:t`'s in a document, the run's own in clipboard HTML; never its properties'."""
    parts = []
    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
        elif not child.tag.endswith("pr"):
            parts.append(_text(child))
    return "".join(parts)
