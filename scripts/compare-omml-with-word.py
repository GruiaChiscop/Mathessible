"""Compare omml_math with Word's own MathML to OMML converter, on a Mac with Word installed.

Usage: uv run python scripts/compare-omml-with-word.py
Each source is UnicodeMath, converted by the real converter (tests/converter_harness.py, Node).
Word's mathml2omml.xsl is only read from the Word installation, never copied into Mathessible.
The structure is compared (not run properties), then the text. Expected differences: Word's
converter keeps maths-italic letters and writes some defaults (`sepChr`, `type=bar`, `mPr`);
a box 〖〗, `█` (an equation array), a labelled brace and an equation number are written as Word
builds them when they are typed, not as its converter does. See docs/engineering-notes.md.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from converter_harness import convert_all  # noqa: E402
from mathessible.documents.omml_math import M, omml_math  # noqa: E402

XSL = "/Applications/Microsoft Word.app/Contents/Resources/mathml2omml.xsl"
MML = "http://www.w3.org/1998/Math/MathML"
SKIP = {"rPr", "ctrlPr", "sty", "nor", "t", "r"}
SOURCES = [
    "x=(-b±√(b^2-4ac))/(2a)",
    "∑_(k=1)^n k^2",
    "∫_0^1▒〖x^2 dx〗",
    "lim_(x→∞) 〖1/x〗",
    "sin^2 x+cos^2 x=1",
    "(■(1&0@0&1))",
    "{■(x&x≥0@-x&x<0)┤",
    "√(3&x)",
    "E=mc^2#(1)",
    "█(x+y&=1@x-y&=3)",
    '"if "x>0',
    "x̂+ȳ",
    "(n¦k)",
    "1,5+2",
    "|x|",
    "⌊x⌋",
    "⏞(a+b)┴n",
    "x⁄y",
    "f(x)",
    "log_2 〖8〗",
]


def structure(element: etree._Element) -> list[str]:
    found = []
    for node in element.iter():
        if not isinstance(node.tag, str) or etree.QName(node).namespace != M:
            continue
        tag = etree.QName(node).localname
        if tag in SKIP:
            continue
        value = node.get(f"{{{M}}}val")
        found.append(f"{tag}={value}" if value is not None else tag)
    return found


def text(element: etree._Element) -> str:
    return "".join(node.text or "" for node in element.iter(f"{{{M}}}t"))


def main() -> None:
    word = etree.XSLT(etree.parse(XSL))
    same = 0
    for source, result in zip(SOURCES, convert_all(SOURCES), strict=True):
        mathml = re.sub(r"<math\b", f'<math xmlns="{MML}"', result["mathml"], count=1)
        theirs = word(etree.fromstring(mathml)).getroot()
        if etree.QName(theirs).localname != "oMath":
            theirs = theirs.find(f".//{{{M}}}oMath")
        ours = etree.fromstring(omml_math(result["mathml"]).xml)
        if structure(theirs) == structure(ours) and text(theirs) == text(ours):
            same += 1
            print("same ", source)
            continue
        print("diff ", source)
        if structure(theirs) != structure(ours):
            print("   Word:", " ".join(structure(theirs)))
            print("   ours:", " ".join(structure(ours)))
        if text(theirs) != text(ours):
            print(f"   text: Word {text(theirs)!r}, ours {text(ours)!r}")
    print(f"{same} of {len(SOURCES)} the same")


if __name__ == "__main__":
    main()
