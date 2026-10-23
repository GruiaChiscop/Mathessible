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
    # `ⅆ` (\dd) carries intent="ⅆ", read "double-struck italic d"; "d" is what is meant.
    mathml = mathml.replace('intent="ⅆ"', 'intent="d"')
    if any(name in mathml for name in _LARGE_FUNCTIONS) or "⏞" in mathml or "⏟" in mathml or "\u00a0" in mathml:
        mathml = _intent_fixups(mathml)
    return mathml


# max/min/sup/inf with a condition under them read like ∑ ("the max over x of f").
_LARGE_FUNCTIONS = ("max", "min", "sup", "inf", "argmax", "argmin")
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
