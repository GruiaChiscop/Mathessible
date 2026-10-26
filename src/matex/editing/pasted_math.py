"""What a paste into the equation editor holds: UnicodeMath text, or MathML to convert first.

Word copies its linear format (UnicodeMath) as plain text, or MathML with
its "Copy MathML to the clipboard as plain text" option; a web page puts
its `<math>` in the clipboard's HTML, with plain text that is only the
rendered characters. MateX's own copy has the UnicodeMath text and the
same source as the HTML `<math>`'s `alttext`, so its text is taken as it is.
"""

from __future__ import annotations

import re
import unicodedata
from html import unescape

# A whole MathML element, prefixed (`<mml:math>`, Word's) or not.
_MATH = re.compile(r"<((?:\w+:)?math)\b[^>]*>.*?</\1\s*>", re.DOTALL | re.IGNORECASE)
_ALTTEXT = re.compile(r'^<(?:\w+:)?math\b[^>]*?\salttext\s*=\s*"([^"]*)"', re.IGNORECASE)
_XML_DECLARATION = re.compile(r"^<\?xml[^>]*\?>\s*")


def pasted_mathml(text: str | None, html: str | None) -> str | None:
    """The MathML to convert for a paste, or None to paste the text as it is."""
    plain = _XML_DECLARATION.sub("", (text or "").strip())
    if plain.lower().startswith(("<math", "<mml:math", "<m:math")):
        found = _MATH.match(plain)
        return found.group(0) if found else None
    if not html:
        return None
    elements = _MATH.findall(html)
    if len(elements) != 1:
        return None  # No equation, or a page of text with several: the text.
    element = _MATH.search(html)
    assert element is not None
    alttext = _ALTTEXT.match(element.group(0))
    if alttext is not None and unescape(alttext.group(1)) == plain:
        return None  # MateX's own copy: its text is the source.
    return element.group(0)


def plain_letters(source: str) -> str:
    """The converter's maths-italic letters as typed (𝑥 → x, ℎ → h, 𝛼 → α), as the linear view shows them.

    Only italic letters, the converter's default for a variable: bold,
    script or double-struck letters mean something else and stay.
    """
    result: list[str] = []
    for character in source:
        if character == "ℎ":  # Planck constant: the converter's italic h.
            result.append("h")
            continue
        name = unicodedata.name(character, "")
        letter = None
        if name.startswith("MATHEMATICAL ITALIC SMALL "):
            letter = name.removeprefix("MATHEMATICAL ITALIC SMALL ")
            kind = "LATIN SMALL LETTER" if len(letter) == 1 else "GREEK SMALL LETTER"
        elif name.startswith("MATHEMATICAL ITALIC CAPITAL ") and len(name) == len("MATHEMATICAL ITALIC CAPITAL ") + 1:
            letter = name.removeprefix("MATHEMATICAL ITALIC CAPITAL ")
            kind = "LATIN CAPITAL LETTER"
        if letter is None:
            result.append(character)
            continue
        try:
            result.append(unicodedata.lookup(f"{kind} {letter}"))
        except KeyError:
            result.append(character)
    return "".join(result)
