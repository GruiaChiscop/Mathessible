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
    if any(name in mathml for name in _LARGE_FUNCTIONS) or "⏞" in mathml or "⏟" in mathml:
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
    changed = False
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        children = list(element)
        if tag in ("msub", "munder") and children and children[0].text in _LARGE_FUNCTIONS and "intent" not in element.attrib:
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
