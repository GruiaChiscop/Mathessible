"""HTML for the clipboard, beside the plain text, so equations paste built.

Word builds an equation from MathML in the clipboard's HTML (checked with
Word for Mac), and browsers show it. The same sanitised MathML as export;
the root carries the MathML namespace, which a pasted fragment needs, and
the UnicodeMath source as its `alttext`.
"""

from __future__ import annotations

import re
from html import escape

from mathessible.documents.html_export import MathConverter, render_markdown
from mathessible.documents.markdown_math import find_math_zones
from mathessible.documents.mathml_sanitize import sanitize_mathml

MATHML_NAMESPACE = "http://www.w3.org/1998/Math/MathML"

_ROOT = re.compile(r"^<math\b([^>]*)>")
_DISPLAY = re.compile(r'\s+display="[^"]*"')
# The converter's own marks for what it could not build (see prepare_for_mathcat).
_ERROR_MARKS = ('mathcolor="#F00"', 'mathcolor="#F01"')


def _html(body: str) -> str:
    return f'<html><head><meta charset="utf-8"></head><body>{body}</body></html>'


def equation_html(mathml: str, source: str, display: bool) -> str | None:
    """One equation as clipboard HTML; None when it does not build cleanly."""
    if any(mark in mathml for mark in _ERROR_MARKS):
        return None
    try:
        clean = sanitize_mathml(mathml)
    except ValueError:
        return None
    root = _ROOT.match(clean)
    if root is None:
        return None
    attributes = _DISPLAY.sub("", root.group(1))
    kind = "block" if display else "inline"
    tag = f'<math xmlns="{MATHML_NAMESPACE}" display="{kind}" alttext="{escape(source)}"{attributes}>'
    return _html(tag + clean[root.end() :])


def document_html(markdown: str, convert_math: MathConverter) -> str | None:
    """Copied Markdown as clipboard HTML, its equations as MathML; None without any equation."""
    if not find_math_zones(markdown):
        return None

    def built(source: str) -> str:
        mathml = convert_math(source)
        if any(mark in mathml for mark in _ERROR_MARKS):
            raise ValueError("the equation does not build")  # Kept as its source, in code.
        return mathml

    rendered = render_markdown(markdown, built)
    rendered = rendered.replace("<math", f'<math xmlns="{MATHML_NAMESPACE}"')
    return _html(rendered)
