"""Which conversion a rich paste takes: the local one, Pandoc, or the clipboard's plain text.

Pandoc is optional and only needed for what the local conversion (pasted_html) cannot hold: paragraphs,
lists, code or line breaks inside a table's cells, and nested lists (paste_requirements). Equations
(Word's, or MathML) are converted by neither, so such a paste stays the clipboard's text, as before.
"""

from __future__ import annotations

from enum import StrEnum

from mathessible.documents.paste_requirements import inspect_html


class PasteRoute(StrEnum):
    LOCAL = "local"
    PANDOC = "pandoc"
    NEEDS_PANDOC = "needs_pandoc"  # Pandoc would keep more, and is not installed: the user chooses.
    PLAIN = "plain"


_PLAIN_TEXT = frozenset({"office_equations", "mathml", "size_limit"})


def paste_route(html: str, pandoc_available: bool) -> PasteRoute:
    requirements = inspect_html(html)
    if requirements.unsupported_features & _PLAIN_TEXT:
        return PasteRoute.PLAIN
    if requirements.pandoc_features:
        return PasteRoute.PANDOC if pandoc_available else PasteRoute.NEEDS_PANDOC
    return PasteRoute.LOCAL
