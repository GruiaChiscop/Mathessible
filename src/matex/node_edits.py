"""Copy, cut and delete a whole node of the built equation, in source terms.

A node's source is its leaves' spans joined, widened over its own parens
and sign (`source_map.anchor_offset(..., outside=True)`): the fraction
`(1)/(2)` is all of `(1)/(2)`, a square root `√〖x〗` includes `√〖〗`.
Removing a node that fills a required place (a numerator, a radicand, a
script, a limit, a matrix cell) leaves that place empty instead of taking
the structure around it apart: `()` or `〖〗` as it was written, nothing in
a cell. Deleting a structure is never one keystroke away from deleting a
character — see `EquationEditor` for the confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass

from .mathml_model import MathMLDocument
from .source_map import anchor_offset

# Roles whose node must be replaced by an empty slot, not removed.
_SLOT_ROLES = frozenset(
    {
        "numerator",
        "denominator",
        "radicand",
        "index",
        "base",
        "subscript",
        "superscript",
        "underscript",
        "overscript",
        "lower limit",
        "upper limit",
        "limit condition",
        "text above",
        "text below",
    }
)


@dataclass(frozen=True, slots=True)
class NodeSpan:
    start: int
    end: int


def node_span(source: str, document: MathMLDocument, node_id: str) -> NodeSpan:
    """The source of a node, with its own parens and sign; the whole source for the math itself."""
    node = document.node(node_id)
    if node is None or node is document.root:
        return NodeSpan(0, len(source))
    outside = bool(node.children)
    start = anchor_offset(source, document, node_id, "before", outside)
    end = anchor_offset(source, document, node_id, "after", outside)
    return NodeSpan(start, max(start, end))


def removal(source: str, document: MathMLDocument, node_id: str) -> tuple[NodeSpan, str]:
    """What removing a node replaces, and with what (an empty slot where one is required)."""
    span = node_span(source, document, node_id)
    node = document.node(node_id)
    if node is None or node is document.root:
        return span, ""
    parent = document.parent_by_id.get(node_id)
    text = source[span.start : span.end]
    if node.tag == "mtr":
        # A whole row goes with one of its "@" separators (the matrix menu's Delete Row).
        if source[span.end : span.end + 1] == "@":
            return NodeSpan(span.start, span.end + 1), ""
        if span.start > 0 and source[span.start - 1] == "@":
            return NodeSpan(span.start - 1, span.end), ""
        return span, ""
    if parent is not None and parent.tag == "mtd" or node.tag == "mtd":
        return span, ""  # An empty cell is just nothing between its separators.
    if text.startswith("〖") and text.endswith("〗"):
        return span, "〖〗"  # A function's argument box, a radicand: emptied, kept.
    if document.semantic_role(node_id) not in _SLOT_ROLES:
        return span, ""
    if text.startswith("(") and text.endswith(")"):
        return span, "()"
    # A bare token in a slot (`a/b`'s `a`): an empty "()" keeps the slot.
    widened = _with_parens(source, span)
    return (widened, "()") if widened != span else (span, "()")


def _with_parens(source: str, span: NodeSpan) -> NodeSpan:
    if span.start > 0 and span.end < len(source) and source[span.start - 1] == "(" and source[span.end] == ")":
        return NodeSpan(span.start - 1, span.end + 1)
    return span
