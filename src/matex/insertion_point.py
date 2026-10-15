"""Speech for where typing goes in the built (professional) equation.

Typing in professional mode lands before or after a node
(`MathCatNavigator.edit_anchor`); this says where that is, from that same
anchor: "after a, before plus", "after 1, end of numerator", "start of
denominator, before 2", "in empty denominator", "start of math, before x".
A source offset alone could not tell "after the numerator's 1" from
"before the denominator's 2": typing at one joins the numerator, at the
other the denominator.
"""

from __future__ import annotations

import unicodedata

from .character_speech import character_name
from .mathml_model import MathMLDocument, MathMLNode
from .source_map import leaf_nodes
from .symbol_dictionary import SymbolDictionary

_INVISIBLE = frozenset("⁡⁢⁣⁤")
_STRUCTURE_NAMES = {
    "mfrac": "fraction",
    "msqrt": "square root",
    "mroot": "root",
    "msub": "subscript",
    "msup": "superscript",
    "msubsup": "scripts",
    "munder": "underscript",
    "mover": "overscript",
    "munderover": "limits",
    "mtable": "matrix",
}


def describe_insertion_point(
    document: MathMLDocument, node_id: str, side: str, outside: bool = False, symbols: SymbolDictionary | None = None
) -> str:
    """Where typing goes, for an edit anchor (`MathCatNavigator.edit_anchor`)."""
    leaves = [leaf for leaf in leaf_nodes(document) if leaf.text not in _INVISIBLE]
    node = document.node(node_id)
    if node is None or node is document.root or not leaves:
        return "start of math" if side == "before" else "end of math"
    inside = [leaf for leaf in leaves if leaf is node or _contains(document, node, leaf)]
    if len(inside) == 1 and _is_empty(inside[0]):
        regions = document.regions(inside[0].identifier or "")
        return f"in empty {regions[0]}" if regions else "in an empty slot"
    if not inside:
        return "start of math" if side == "before" else "end of math"
    if side == "after":
        edge = inside[-1]
        index = leaves.index(edge)
        neighbor = leaves[index + 1] if index + 1 < len(leaves) else None
        pieces = [f"after {_name(node if outside or not node.children else edge, symbols)}"]
        pieces += [f"end of {label}" for label in _left(document, node if outside else edge, neighbor, node)]
        pieces.append(f"before {_name(neighbor, symbols)}" if neighbor is not None else "end of math")
        return ", ".join(pieces)
    edge = inside[0]
    index = leaves.index(edge)
    neighbor = leaves[index - 1] if index > 0 else None
    pieces = [f"after {_name(neighbor, symbols)}" if neighbor is not None else "start of math"]
    pieces += [f"start of {label}" for label in reversed(_left(document, node if outside else edge, neighbor, node))]
    pieces.append(f"before {_name(node if outside or not node.children else edge, symbols)}")
    return ", ".join(pieces)


def _left(
    document: MathMLDocument, inner: MathMLNode, neighbor: MathMLNode | None, anchor: MathMLNode
) -> list[str]:
    """`inner`'s regions (innermost first) that `neighbor` is not in: the edges between them.

    Inside a role (typing at the end of the numerator), only the regions up
    to that role are edges the caret is at; the fraction around it is not.
    """
    own = document.region_entries(inner.identifier or "")
    other = set(document.region_entries(neighbor.identifier or "")) if neighbor is not None else set()
    edges = _cell_edges(document, inner, neighbor) if inner is not anchor or not anchor.children else []
    for key, label in own:
        if (key, label) in other:
            break
        edges.append(label)
        if key == id(anchor) and inner is not anchor:
            break
    return edges


def _cell_edges(document: MathMLDocument, inner: MathMLNode, neighbor: MathMLNode | None) -> list[str]:
    """In a matrix: "column C" (and "row R") when the neighbor is in another cell (row), innermost first."""
    here = document.table_position(inner.identifier or "")
    if here is None:
        return []
    there = document.table_position(neighbor.identifier or "") if neighbor is not None else None
    if there is not None and there.cell_id == here.cell_id:
        return []
    same_row = there is not None and there.table_id == here.table_id and there.row == here.row
    return [f"column {here.column}"] if same_row else [f"column {here.column}", f"row {here.row}"]


def _contains(document: MathMLDocument, node: MathMLNode, leaf: MathMLNode) -> bool:
    return leaf.identifier is not None and any(ancestor is node for ancestor in document.ancestors(leaf.identifier))


def _is_empty(leaf: MathMLNode) -> bool:
    return leaf.text.strip("  ") == ""


def _name(node: MathMLNode, symbols: SymbolDictionary | None) -> str:
    """A node as spoken: a plain letter for 𝑥, a symbol's dictionary name, a structure by its kind."""
    if node.children:
        return f"the {_STRUCTURE_NAMES.get(node.tag, 'group')}"
    if _is_empty(node):
        return "empty slot"
    text = "".join(
        unicodedata.normalize("NFKC", character) if unicodedata.category(character)[0] in "LN" else character
        for character in node.text
    )
    return character_name(text, symbols) if len(text) == 1 else text
