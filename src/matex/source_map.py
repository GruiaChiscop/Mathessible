"""Which part of the UnicodeMath source each MathML leaf came from.

The converter keeps no source positions (and its Ⓐ/Ⓕ selection markers
attach to the next node, vanish at the end and break parsing inside
parens), so the map is rebuilt by alignment: MathCAT's canonical MathML
keeps the source's reading order, so its leaves are matched one by one
against the source, left to right. What the source has and the MathML
does not (parens the converter made transparent, `_`, `^`, `/`, `▒`, `&`,
quotes, spaces) is skipped; what the MathML has and the source does not
(invisible times and function application) gets an empty span where it
sits. Control words are matched through `source_view`, so `\\sum` maps to
the `∑` leaf. It is a best effort: a leaf that cannot be matched gets an
empty span at the current position rather than derailing the rest.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from .mathml_model import MathMLDocument, MathMLNode
from .source_view import view_of

_INVISIBLE = frozenset("⁡⁢⁣⁤")
# Empty template slots ("()") come back as a non-breaking space or nothing.
_EMPTY_SLOT = frozenset({"", "\u00a0"})
# Source spellings the converter rewrites into another leaf text.
_SPELLINGS = {
    "≤": ("<=",),
    "≥": (">=",),
    "≠": ("/=",),
    "≔": (":=",),
    "…": ("...",),
    "∗": ("*",),
    "′": ("'",),
    "∼": ("~",),
    "−": ("-",),
    "/": ("∕",),  # A linear fraction's operator.
    # MathCAT canonicalizes three combining accents to spacing ones.
    "^": ("\u0302",),
    "˙": ("\u0307",),
    "¨": ("\u0308",),
    # The index of a cube or fourth root is its sign.
    "3": ("∛",),
    "4": ("∜",),
}
# Signs that open a structure: "before the square root" is before its "√".
_STRUCTURE_SIGNS = frozenset("√∛∜■█")
# How far ahead a leaf is looked for before giving up on it.
_LOOKAHEAD = 12


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """A leaf's source range; `start == end` for one with no characters (invisible, empty slot)."""

    start: int
    end: int


def leaf_nodes(document: MathMLDocument) -> list[MathMLNode]:
    """The leaves MathCAT can stand on, in source order.

    That is MathML order except in an `mroot`, whose index comes last in
    MathML (base, index) but first in the source (`√(3&x)`, `∛x`).
    """
    leaves: list[MathMLNode] = []

    def walk(node: MathMLNode) -> None:
        if node.children:
            children = node.children
            if node.tag == "mroot" and len(children) == 2:
                children = (children[1], children[0])
            for child in children:
                walk(child)
        elif node.identifier:
            leaves.append(node)

    walk(document.root)
    return leaves


def map_leaves(source: str, document: MathMLDocument) -> dict[str, SourceSpan]:
    """Leaf id -> the span of `source` it came from (see the module notes)."""
    view = view_of(source)
    text = view.text
    position = 0
    spans: dict[str, SourceSpan] = {}
    for leaf in leaf_nodes(document):
        assert leaf.identifier is not None
        content = leaf.text
        if content in _INVISIBLE:
            spans[leaf.identifier] = _span(view, position, position)
            continue
        if content in _EMPTY_SLOT or not content.strip("\u00a0 "):
            slot = _empty_slot(text, position)
            spans[leaf.identifier] = _span(view, slot, slot)
            position = slot + 1 if slot < len(text) else slot
            continue
        found = _find(text, position, content)
        if found is None:
            spans[leaf.identifier] = _span(view, position, position)
            continue
        start, end = found
        spans[leaf.identifier] = _span(view, start, end)
        position = end
    return spans


def _empty_slot(text: str, position: int) -> int:
    """The next empty argument: between "(" / "&" / "@" and ")" / "&" / "@" (a "()" or an empty cell),
    or a zero-width space standing in for one."""
    for index in range(max(position, 0), min(len(text), position + _LOOKAHEAD) + 1):
        if index < len(text) and text[index] == "\u200b":
            return index  # A placeholder for a missing argument (build_repair).
        if index > 0 and text[index - 1] in "(&@〖" and (index == len(text) or text[index] in ")&@〗"):
            return index
    return position


def _span(view, start: int, end: int) -> SourceSpan:
    return SourceSpan(view.to_source(start), view.to_source(end))


def _find(text: str, position: int, content: str) -> tuple[int, int] | None:
    """The first place at or after `position` where the leaf's text is spelled."""
    target = _normalize(content)
    spellings = (target,) + _SPELLINGS.get(content, ())
    for start in range(position, min(len(text), position + _LOOKAHEAD)):
        for spelling in spellings:
            end = _match(text, start, spelling)
            if end is not None:
                return start, end
    return None


def _match(text: str, start: int, spelling: str) -> int | None:
    index = start
    for character in spelling:
        if index >= len(text) or _normalize(text[index]) != character:
            return None
        index += 1
    return index


def _normalize(text: str) -> str:
    """Math italic and other styled letters and digits to plain ones (𝑥 → x), as typed in the source.

    Only letters and digits: NFKC would also split operators (∬ → ∫∫).
    """
    return "".join(
        unicodedata.normalize("NFKC", character) if unicodedata.category(character)[0] in "LN" else character
        for character in text
    )


def leaf_at(spans: dict[str, SourceSpan], offset: int) -> str | None:
    """The leaf whose characters contain `offset`, else the last one ending at or before it."""
    best: tuple[int, str] | None = None
    for identifier, span in spans.items():
        if span.start <= offset < span.end:
            return identifier
        if span.end <= offset and span.end > span.start and (best is None or span.end >= best[0]):
            best = (span.end, identifier)
    return None if best is None else best[1]


def anchor_offset(source: str, document: MathMLDocument, node_id: str, side: str, outside: bool = False) -> int:
    """The source offset just before or after a node (any node: its leaves' spans are joined).

    With `outside`, a whole structure's own parens are stepped over too, so
    "after the fraction" `(1)/(2)` is past its last ")", not inside "(2)".
    """
    spans = map_leaves(source, document)
    node = document.node(node_id)
    if node is None or node is document.root:
        return 0 if side == "before" else len(source)
    leaves = [leaf for leaf in leaf_nodes(document) if leaf is node or _inside(document, leaf, node)]
    found = [spans[leaf.identifier] for leaf in leaves if leaf.identifier in spans]
    if not found:
        return 0 if side == "before" else len(source)
    start, end = min(span.start for span in found), max(span.end for span in found)
    if outside:
        start, end = _with_own_parens(source, start, end)
    return start if side == "before" else end


def _with_own_parens(source: str, start: int, end: int) -> tuple[int, int]:
    """Widen `start`..`end` over the "(" / ")" whose partner is already inside it, and a structure's sign (√, ■)."""
    view = view_of(source)
    text = view.text
    pairs = {}
    stack: list[int] = []
    for index, character in enumerate(text):
        if character == "(":
            stack.append(index)
        elif character == ")" and stack:
            opening = stack.pop()
            pairs[opening], pairs[index] = index, opening
    low, high = view.to_view(start), view.to_view(end)
    changed = True
    while changed:
        changed = False
        if low > 0 and text[low - 1] == "(" and low - 1 in pairs and pairs[low - 1] <= high:
            low -= 1
            changed = True
        if low > 0 and text[low - 1] in _STRUCTURE_SIGNS and low < len(text) and text[low] == "(":
            low -= 1
            changed = True
        if high < len(text) and text[high] == ")" and high in pairs and pairs[high] >= low:
            high += 1
            changed = True
    return view.to_source(low), view.to_source(high)


def _inside(document: MathMLDocument, leaf: MathMLNode, node: MathMLNode) -> bool:
    return leaf.identifier is not None and any(ancestor is node for ancestor in document.ancestors(leaf.identifier))


def leaf_before(spans: dict[str, SourceSpan], caret: int, document: MathMLDocument) -> str | None:
    """The leaf to stand on with the caret at `caret`: the one holding the character before it.

    Else an empty slot right at the caret (a "()" just emptied), else the
    last leaf ending before it; None at the very start.
    """
    if caret > 0:
        for identifier, span in spans.items():
            if span.start <= caret - 1 < span.end:
                return identifier
    for identifier, span in spans.items():
        node = document.node(identifier)
        if span.start == span.end == caret and node is not None and node.text not in _INVISIBLE:
            return identifier
    return leaf_at(spans, caret) if caret > 0 else None
