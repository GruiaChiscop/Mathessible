"""Converter output rewritten before MathCAT reads it (what MathCAT would misread)."""

from __future__ import annotations

import re
from xml.etree import ElementTree

_DETERMINANT_INTENT = re.compile(r'intent="determinant\(\$([\w-]+)\)"')


def prepare_for_mathcat(mathml: str) -> str:
    """Rewrite converter output MathCAT misreads, before it reaches MathCAT.

    UnicodeMathML marks `|■(...)|` as `intent="determinant($a)"` with
    `arg="a"` on the mtable. MathCAT then speaks the table as "2 lines" and
    its cell navigation reads the wrong cell ("row 1, column 1, b"). As a
    plain `:fenced` mrow with no arg, MathCAT infers the determinant itself
    ("the 2 by 2 determinant") and navigates cells correctly.
    """
    for match in list(_DETERMINANT_INTENT.finditer(mathml)):
        argument = re.escape(match.group(1))
        mathml = re.sub(rf'(<mtable\b[^>]*?)\s+arg="{argument}"', r"\1", mathml, count=1)
    mathml = _DETERMINANT_INTENT.sub('intent=":fenced"', mathml)
    # `{■(...)┤` (cases): the converter's ":fenced"/":array" intents hide the
    # piecewise layout; without them MathCAT says "2 cases; case 1; ...".
    mathml = _CASES_INTENTS.sub(r"<mrow><mo>{</mo><mtable", mathml)
    # ...and so does the invisible closing fence `┤` leaves (an `<mo>` holding U+200B).
    mathml = mathml.replace("</mtable><mo>\u200b</mo></mrow>", "</mtable></mrow>")
    # `|x|` carries intent="absolute-value(𝑥)" with the content written into it, so
    # navigating onto x reads the whole thing; MathCAT infers the absolute value itself.
    mathml = _ABSOLUTE_VALUE_INTENT.sub("", mathml)
    # `[0,1)`, `(a,b]` likewise carry intent="closed-open-interval(0,1)": every
    # stop in them read the whole interval. MathCAT infers the interval itself.
    mathml = _INTERVAL_INTENT.sub("", mathml)
    # The converter's italic h is ℎ (U+210E: Unicode has no math italic h of its own), which MathCAT
    # names "planck constant": every h was read so ("x plus planck constant"). It is an h.
    mathml = _ITALIC_H.sub(r"\1h\2", mathml)
    # `ⅆ` (\dd) carries intent="ⅆ", read "double-struck italic d"; "d" is what is meant.
    mathml = mathml.replace('intent="ⅆ"', 'intent="d"')
    if any(name in mathml for name in _LARGE_FUNCTIONS) or "⏞" in mathml or "⏟" in mathml or "\u00a0" in mathml:
        mathml = _intent_fixups(mathml)
    if 'intent=":equations"' in mathml and "<mtext>(" in mathml:
        mathml = _row_labels(mathml)
    # Accents: the converter writes `x\vec` with the combining arrow (U+20D7) as its `<mo>`, which MathCAT
    # reads "x with right arrow above embellishment above"; MathCAT knows the spacing characters.
    mathml = _COMBINING_ACCENT.sub(_spacing_accent, mathml)
    if "<mover" in mathml or "<munder" in mathml or 'notation="top"' in mathml or 'notation="bottom"' in mathml:
        mathml = _accents(mathml)
    return mathml


# Combining accents the converter writes in an `<mo>`, and the spacing characters MathCAT names (the source
# map finds them by these: source_map._SPELLINGS).
SPACING_ACCENTS = {
    "\u0300": "`",
    "\u0301": "\u00b4",
    "\u0302": "\u02c6",
    "\u0303": "\u02dc",
    "\u0304": "\u00af",
    "\u0305": "\u00af",
    "\u0306": "\u02d8",
    "\u0307": "\u02d9",
    "\u0308": "\u00a8",
    "\u030c": "\u02c7",
    "\u20d0": "\u21bc",
    "\u20d1": "\u21c0",
    "\u20d6": "\u2190",
    "\u20d7": "\u2192",
    "\u20e1": "\u2194",
}
_COMBINING_ACCENT = re.compile(r"(<mo\b[^>]*>)(&#x[0-9a-fA-F]+;|[\u0300-\u036f\u20d0-\u20ff])</mo>")


def _spacing_accent(match: re.Match[str]) -> str:
    text = match.group(2)
    character = chr(int(text[3:-1], 16)) if text.startswith("&#x") else text
    return match.group(1) + SPACING_ACCENTS[character] + "</mo>" if character in SPACING_ACCENTS else match.group(0)


# An accent's name for its intent (`_accents`): MathCAT says it with "start" and "end" (MathCAT patch 0010).
_ACCENT_NAMES = {
    "\u00af": "bar",
    "\u203e": "bar",
    "^": "hat",
    "\u02c6": "hat",
    "~": "tilde",
    "\u02dc": "tilde",
    "\u02d9": "dot",
    "\u00a8": "double-dot",
    "\u20db": "triple-dot",
    "\u20dc": "quadruple-dot",
    "\u02c7": "check",
    "\u02d8": "breve",
    "\u00b4": "acute",
    "`": "grave",
    "\u2192": "vector",
    "\u21c0": "vector",
    "\u2190": "left-arrow",
    "\u2194": "left-right-arrow",
    "\u21bc": "left-harpoon",
}
_UNDERLINES = frozenset("_\u00af\u203e")


def _accents(mathml: str) -> str:
    """Accents MathCAT reads with what they cover: "start bar, x y z t, end bar", not "x y z t bar" (the bar
    over t, or over all four?). Leaves the MathML as is if it does not parse.

    `x\bar` comes as a frame with only its top side (`menclose notation="top"`, "line on top, enclosing x"):
    it becomes the accent it is; a ▭ with only its top side (the same MathML) is drawn as one. An accent gets
    intent="bar:accent($base)" (the name, `_ACCENT_NAMES`); letters under it are kept apart by invisible
    times, as MathCAT puts between them elsewhere: alone in a row, MathCAT reads them as one word ("𝑥𝑦𝑧𝑡").
    """
    try:
        root = ElementTree.fromstring(mathml)
    except ElementTree.ParseError:
        return mathml
    changed = False
    namespace = root.tag[: -len(_local(root))]
    for element in list(root.iter()):
        tag = _local(element)
        if tag == "menclose" and element.get("notation") in ("top", "bottom"):
            children = list(element)
            base = children[0] if len(children) == 1 else _row(namespace, children)
            line = ElementTree.Element(namespace + "mo")
            line.text = "\u00af" if element.get("notation") == "top" else "_"
            tail = element.tail
            element.clear()
            element.tail = tail
            element.tag = namespace + ("mover" if line.text == "\u00af" else "munder")
            element.extend([base, line])
            tag = _local(element)
        children = list(element)
        if tag not in ("mover", "munder") or len(children) != 2 or "intent" in element.attrib:
            continue
        base, mark = children
        name = _ACCENT_NAMES.get((mark.text or "").strip()) if _local(mark) == "mo" else None
        if name is None or _local(base) == "mo":
            continue  # Not an accent, or text over an operator (`→┴(x)`).
        if tag == "munder":
            if (mark.text or "").strip() not in _UNDERLINES:
                continue
            name = "underline"
        if _local(base) == "mrow":
            _apart(namespace, base)
        base.set("arg", "base")
        element.set("intent", f"{name}:accent($base)")
        changed = True
    return ElementTree.tostring(root, encoding="unicode") if changed else mathml


def _row(namespace: str, children: list[ElementTree.Element]) -> ElementTree.Element:
    row = ElementTree.Element(namespace + "mrow")
    row.extend(children)
    return row


def _apart(namespace: str, row: ElementTree.Element) -> None:
    """Invisible times between letters next to each other in a row."""
    children = list(row)
    for index in range(len(children) - 1, 0, -1):
        if _local(children[index]) == "mi" and _local(children[index - 1]) == "mi":
            times = ElementTree.Element(namespace + "mo")
            times.text = "\u2062"
            row.insert(index, times)


# max/min/sup/inf with a condition under them read like ∑ ("the max over x of f").
_LARGE_FUNCTIONS = ("max", "min", "sup", "inf", "argmax", "argmin")
_ITALIC_H = re.compile(r"(<mi\b[^>]*>)\u210e(</mi>)")
_ABSOLUTE_VALUE_INTENT = re.compile(r'\s+intent="absolute-value\([^"$]*\)"')
_INTERVAL_INTENT = re.compile(r'\s+intent="(?:open|closed|open-closed|closed-open)-interval\([^"$]*\)"')
_CASES_INTENTS = re.compile(r'<mrow intent=":fenced">\s*<mo>\{</mo>\s*<mtable intent=":array\([^)]*\)"')


def _intent_fixups(mathml: str) -> str:
    """Intents the converter does not give (see prepare_for_mathcat); leaves the MathML as is if it does not parse."""
    try:
        root = ElementTree.fromstring(mathml)
    except ElementTree.ParseError:
        return mathml
    changed = _join_limit_names(root)
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        children = list(element)
        if (
            tag in ("msub", "munder")
            and children
            and children[0].text in _LARGE_FUNCTIONS
            and "intent" not in element.attrib
        ):
            element.set("intent", ":largeop")
            changed = True
        if tag in ("mover", "munder") and len(children) == 2 and "intent" not in element.attrib:
            inner = children[0]
            inner_children = list(inner)
            brace = "⏞" if tag == "mover" else "⏟"
            if inner.tag.rsplit("}", 1)[-1] == tag and len(inner_children) == 2 and inner_children[1].text == brace:
                # `⏞(a+b)┴n`: "a plus b, with brace above, labeled n" (MathCAT patch 0003).
                name = "overbrace" if brace == "⏞" else "underbrace"
                element.set("intent", f"{name}($content,$label)")
                inner_children[0].set("arg", "content")
                children[1].set("arg", "label")
                changed = True
    return ElementTree.tostring(root, encoding="unicode") if changed else mathml


def _join_limit_names(root: ElementTree.Element) -> bool:
    """`lim inf_(n→∞) a`: one name, applied to what follows.

    The converter writes "lim inf" (no-break space, its own spelling) as an
    mrow of lim, a space and inf under the condition, with no function
    application after it. Every part was a stop reading the whole, and
    MathCAT said no "of" before the argument; as one `<mi>` followed by
    U+2061, it reads "the limit inferior as n approaches infinity, of a".
    """
    changed = False
    for parent in list(root.iter()):
        children = list(parent)
        for index, element in enumerate(children):
            if _join_unscripted_limit(parent, element, children[index + 1] if index + 1 < len(children) else None):
                changed = True
                continue
            if _local(element) not in ("msub", "munder") or not len(element):
                continue
            base = element[0]
            parts = list(base)
            if not (
                _local(base) == "mrow"
                and len(parts) == 3
                and [_local(part) for part in parts] == ["mi", "mo", "mi"]
                and parts[0].text == "lim"
                and parts[1].text == "\u00a0"
                and parts[2].text in ("inf", "sup")
            ):
                continue
            name = ElementTree.Element(parts[0].tag)
            name.text = f"lim\u00a0{parts[2].text}"
            element.remove(base)
            element.insert(0, name)
            following = children[index + 1] if index + 1 < len(children) else None
            if following is not None and not (_local(following) == "mo" and following.text == "\u2061"):
                apply = ElementTree.Element(parts[1].tag)
                apply.text = "\u2061"
                parent.insert(list(parent).index(element) + 1, apply)
            changed = True
    return changed


def _join_unscripted_limit(
    parent: ElementTree.Element, element: ElementTree.Element, following: ElementTree.Element | None
) -> bool:
    """`lim sup 〖a〗` with no condition: the converter applies lim to " sup" and leaves the argument outside."""
    parts = list(element)
    if not (
        _local(element) == "mrow"
        and element.get("intent") == ":function"
        and len(parts) == 4
        and [_local(part) for part in parts] == ["mi", "mo", "mo", "mi"]
        and parts[0].text == "lim"
        and parts[1].text == "\u2061"
        and parts[2].text == "\u00a0"
        and parts[3].text in ("inf", "sup")
    ):
        return False
    word = parts[3].text
    parts[0].text = f"lim\u00a0{word}"
    # With no condition MathCAT's limit rule does not apply, and the name alone read "limsup".
    parts[0].set("intent", "limit-inferior" if word == "inf" else "limit-superior")
    element.remove(parts[2])
    element.remove(parts[3])
    if following is not None:
        parent.remove(following)
        element.append(following)
    return True


def _local(element: ElementTree.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


_ROW_LABEL = re.compile(r"^\(.+\)$")


def _row_label(cells: list[ElementTree.Element]) -> str | None:
    """A row's number, when its last cell holds only it (`&&\\qquad\\text{(1)}`, as a .tex file's numbered
    align is written for its preview) after an empty cell; else None."""
    if len(cells) < 3:
        return None
    spacer, last = cells[-2], cells[-1]
    if any(_local(child) != "mspace" or child.get("width", "0") != "0" for child in spacer):
        return None
    texts = [child for child in last if _local(child) != "mspace"]
    if len(texts) != 1 or _local(texts[0]) != "mtext" or not _ROW_LABEL.match(texts[0].text or ""):
        return None
    return texts[0].text


def _row_labels(mathml: str) -> str:
    """A numbered align's rows as MathCAT reads labelled rows ("line 1 with label 1"): each number in a first
    cell of its own, with the converter's `:equation-label` intent (its #(1)), as it is for one equation."""
    try:
        root = ElementTree.fromstring(mathml)
    except ElementTree.ParseError:
        return mathml
    changed = False
    for table in root.iter():
        if _local(table) != "mtable" or "equations" not in table.get("intent", ""):
            continue
        rows = [row for row in table if _local(row) == "mtr"]
        labels = [_row_label(list(row)) for row in rows]
        if not any(labels):
            continue
        changed = True
        for row, label in zip(rows, labels, strict=True):
            cell = ElementTree.Element("mtd")
            if label is not None:
                for spare in list(row)[-2:]:
                    row.remove(spare)
                cell.set("intent", ":equation-label")
                ElementTree.SubElement(cell, "mtext").text = label
            row.insert(0, cell)
    return ElementTree.tostring(root, encoding="unicode") if changed else mathml
