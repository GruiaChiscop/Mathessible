"""Conservative clipboard feature inspection, independent of Pandoc availability.

Candidate features describe where Pandoc may help, not a promise that the
editor already supports all of Pandoc's output. Losses still need confirmation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from mathessible.documents.pasted_html import Node, Parser


@dataclass(frozen=True, slots=True)
class PasteRequirements:
    pandoc_features: frozenset[str] = frozenset()
    unsupported_features: frozenset[str] = frozenset()


def inspect_html(html: str) -> PasteRequirements:
    if len(html.encode("utf-8")) > 2_000_000:
        return PasteRequirements(unsupported_features=frozenset({"size_limit"}))
    candidates: set[str] = set()
    unsupported: set[str] = set()
    # Conditional comments may hide Word equations from HTMLParser.
    if re.search(r"<(?:\w+:)?oMath\b", html, re.IGNORECASE):
        unsupported.add("office_equations")
    parser = Parser()
    parser.feed(html)
    pending = [(parser.root, False, 0)]
    while pending:
        node, in_cell, list_depth = pending.pop()
        if node.tag in {"script", "style", "head", "xml"}:
            continue
        if node.tag in {"math", "mml:math"}:
            unsupported.add("mathml")
        if node.tag in {"img", "object", "iframe", "svg"}:
            unsupported.add("embedded_content")
        if node.tag in {"td", "th"}:
            in_cell = True
            # A normal Office cell often wraps its text in one paragraph.
            paragraphs = 0
            descendants = list(node.children)
            while descendants:
                descendant = descendants.pop()
                if isinstance(descendant, Node):
                    paragraphs += descendant.tag == "p"
                    descendants.extend(descendant.children)
            if paragraphs > 1:
                candidates.add("cell_paragraphs")
        if in_cell and node.tag in {"ul", "ol", "pre", "blockquote", "br", "table"}:
            candidates.add("cell_blocks")
        if node.tag in {"ul", "ol"}:
            if list_depth:
                candidates.add("nested_lists")
            list_depth += 1
        pending.extend((child, in_cell, list_depth) for child in node.children if isinstance(child, Node))
    return PasteRequirements(frozenset(candidates), frozenset(unsupported))
