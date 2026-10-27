"""The equation editor's own words about an equation, in the speech language, when they are said.

Navigation builds its stops and descriptions in English ("start fraction",
"end of math", "row 1, column 2", "after a, end of numerator") and uses them
as identifiers. `translate` turns one into the speech language at the last
moment: the whole text if the catalog has it, else each piece between
commas and semicolons, by its own translation or by a pattern ("start
{region}") with its words translated. What MathCAT itself said is in the
speech language already and is left as it is.
"""

from __future__ import annotations

import re

from mathessible.i18n import N_, spoken

# The words navigation names regions and structures with (mathml_model, structural, insertion_point),
# and the pieces the editor's announcements are made of (built, assist).
WORDS = (
    N_("absolute value"),
    N_("after space"),
    N_("angle bracket"),
    N_("argument"),
    N_("arrow"),
    N_("at equation"),
    N_("base"),
    N_("blank"),
    N_("brace"),
    N_("bracket"),
    N_("built"),
    N_("case"),
    N_("cases"),
    N_("cell"),
    N_("condition"),
    N_("denominator"),
    N_("determinant"),
    N_("empty"),
    N_("empty slot"),
    N_("end of math"),
    N_("equation"),
    N_("equation number"),
    N_("equations"),
    N_("factor"),
    N_("fraction"),
    N_("function name"),
    N_("group"),
    N_("in an empty slot"),
    N_("index"),
    N_("integral"),
    N_("integrand"),
    N_("label"),
    N_("limit"),
    N_("limit condition"),
    N_("limits"),
    N_("linear"),
    N_("linear mode"),
    N_("logarithm"),
    N_("lower limit"),
    N_("matrix"),
    N_("no slot"),
    N_("norm"),
    N_("not in a table"),
    N_("nothing selected"),
    N_("numbered equation"),
    N_("numerator"),
    N_("operator"),
    N_("overscript"),
    N_("parentheses"),
    N_("parenthesis"),
    N_("press again to delete it"),
    N_("radicand"),
    N_("root"),
    N_("row"),
    N_("script"),
    N_("scripts"),
    N_("selected"),
    N_("selection cleared"),
    N_("square root"),
    N_("start of math"),
    N_("subscript"),
    N_("sum"),
    N_("summand"),
    N_("superscript"),
    N_("text above"),
    N_("text below"),
    N_("underscript"),
    N_("unselected"),
    N_("upper limit"),
    N_("value"),
)

# Forms the navigation composes, most specific first: (pattern, msgid with its placeholders).
_PATTERNS = (
    (re.compile(r"^row (\d+), column (\d+)$"), N_("row {row}, column {column}")),
    (re.compile(r"^cell row (\d+), column (\d+), (.+)$"), N_("cell row {row}, column {column}, {content}")),
    (re.compile(r"^equation number (.+)$"), N_("equation number {number}")),
    (re.compile(r"^equation (\d+)$"), N_("equation {number}")),
    (re.compile(r"^case (\d+)$"), N_("case {number}")),
    (re.compile(r"^row (\d+)$"), N_("row {row}")),
    (re.compile(r"^column (\d+)$"), N_("column {column}")),
    (re.compile(r"^start of (.+)$"), N_("start of {region}")),
    (re.compile(r"^end of (.+)$"), N_("end of {region}")),
    (re.compile(r"^start (.+)$"), N_("start {region}")),
    (re.compile(r"^end (.+)$"), N_("end {region}")),
    (re.compile(r"^inside (.+)$"), N_("inside {region}")),
    (re.compile(r"^in empty (.+)$"), N_("in empty {region}")),
    (re.compile(r"^after (.+)$"), N_("after {item}")),
    (re.compile(r"^before (.+)$"), N_("before {item}")),
    (re.compile(r"^the (.+)$"), N_("the {structure}")),
    (re.compile(r"^deleted (.+)$"), N_("deleted {item}")),
    (re.compile(r"^cut (.+)$"), N_("cut {item}")),
    (re.compile(r"^selected (.+)$"), N_("selected {item}")),
    (re.compile(r"^built (.+)$"), N_("built {structure}")),
)
_PLACEHOLDERS = re.compile(r"\{(\w+)\}")


def _piece(text: str) -> str:
    translated = spoken(text)
    if translated != text:
        return translated
    for pattern, message in _PATTERNS:
        match = pattern.match(text)
        if match is None:
            continue
        names = _PLACEHOLDERS.findall(message)
        values = {name: spoken(value) for name, value in zip(names, match.groups(), strict=True)}
        return spoken(message).format(**values)
    return text


def translate(text: str) -> str:
    """Navigation's English, said in the speech language; anything else unchanged."""
    whole = spoken(text)
    if whole != text:
        return whole
    return "; ".join(", ".join(_piece(part) for part in clause.split(", ")) for clause in text.split("; "))
