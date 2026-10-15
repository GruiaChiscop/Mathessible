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
    """The next empty argument: between "(" / "&" / "@" and ")" / "&" / "@" (a "()" or an empty cell)."""
    for index in range(max(position, 1), min(len(text), position + _LOOKAHEAD) + 1):
        if text[index - 1] in "(&@" and (index == len(text) or text[index] in ")&@"):
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
