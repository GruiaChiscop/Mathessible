"""The allow-list gate for converter MathML embedded in exported HTML.

A security boundary: adding a tag or attribute here is a security decision
(script/foreignObject/event-handler smuggling), not a routine change.
"""

from __future__ import annotations

from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr


class MathMLModelError(ValueError):
    pass


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


# Presentation MathML 3 elements. Anything else (script, foreignObject, svg,
# annotation-xml with embedded markup, ...) is rejected rather than passed
# through, since converted equations end up embedded verbatim in exported
# HTML documents.
ALLOWED_MATHML_TAGS = frozenset(
    {
        "math",
        "mrow",
        "mfrac",
        "msqrt",
        "mroot",
        "mstyle",
        "merror",
        "mpadded",
        "mphantom",
        "mfenced",
        "menclose",
        "msub",
        "msup",
        "msubsup",
        "munder",
        "mover",
        "munderover",
        "mmultiscripts",
        "mprescripts",
        "none",
        "mtable",
        "mtr",
        "mlabeledtr",
        "mtd",
        "maction",
        "mi",
        "mn",
        "mo",
        "mtext",
        "ms",
        "mglyph",
        "mspace",
        "semantics",
    }
)

# Presentation attributes plus the accessibility-only "intent"/"arg" pair
# MathCAT relies on. Deliberately excludes anything a browser treats as a
# behavior or resource hook (href, src, style, on*, xlink:*).
ALLOWED_MATHML_ATTRIBUTES = frozenset(
    {
        "id",
        "class",
        "dir",
        "intent",
        "arg",
        "mathvariant",
        "mathsize",
        "mathcolor",
        "mathbackground",
        "displaystyle",
        "scriptlevel",
        "display",
        "fence",
        "separator",
        "separators",
        "stretchy",
        "symmetric",
        "largeop",
        "movablelimits",
        "accent",
        "accentunder",
        "lspace",
        "rspace",
        "minsize",
        "maxsize",
        "form",
        "open",
        "close",
        "notation",
        "actiontype",
        "selection",
        "linethickness",
        "align",
        "rowalign",
        "columnalign",
        "columnlines",
        "rowlines",
        "rowspacing",
        "columnspacing",
        "columnspan",
        "rowspan",
        "frame",
        "framespacing",
        "equalrows",
        "equalcolumns",
        "side",
        "width",
        "height",
        "depth",
        "voffset",
        "subscriptshift",
        "superscriptshift",
    }
)


def sanitize_mathml(source: str) -> str:
    """Validate converter output against a MathML allow-list and re-serialize it.

    Exported HTML embeds this string directly, so it must never be trusted
    as-is: a bug in the third-party UnicodeMath-to-MathML converter (or a
    crafted equation) could otherwise smuggle script/foreignObject/annotation
    content into a document users open in a browser.
    """
    try:
        root = ElementTree.fromstring(source.strip())
    except ElementTree.ParseError as error:
        raise MathMLModelError(f"Invalid MathML: {error}") from error
    if local_name(root.tag) != "math":
        raise MathMLModelError("Expected a MathML document with a <math> root element")
    return _serialize_safe(root)


def _serialize_safe(element: ElementTree.Element) -> str:
    tag = local_name(element.tag)
    if tag not in ALLOWED_MATHML_TAGS:
        raise MathMLModelError(f"Disallowed MathML element: {tag}")
    attributes = "".join(
        f" {name}={quoteattr(value)}" for name, value in element.attrib.items() if name in ALLOWED_MATHML_ATTRIBUTES
    )
    # Only the first child of <semantics> is the visible presentation form;
    # annotation/annotation-xml siblings are dropped rather than validated.
    children = list(element)[:1] if tag == "semantics" else list(element)
    parts = [escape(element.text)] if element.text else []
    for child in children:
        parts.append(_serialize_safe(child))
        if child.tail:
            parts.append(escape(child.tail))
    return f"<{tag}{attributes}>{''.join(parts)}</{tag}>"
