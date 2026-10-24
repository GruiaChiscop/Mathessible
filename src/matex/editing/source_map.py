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

from matex.editing.source_view import view_of
from matex.mathcat.mathml_model import MathMLDocument, MathMLNode, is_equation_label, number_last

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
    MathML (base, index) but first in the source (`√(3&x)`, `∛x`), and in a
    numbered equation, whose number comes first in MathML but last in the
    source (`E=mc^2#(1)`, `number_last`).
    """
    leaves: list[MathMLNode] = []

    def walk(node: MathMLNode) -> None:
        if node.children:
            children = number_last(node)
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

    Only letters and digits: NFKC would also split operators (∬ → ∫∫). A
    no-break space is a space: the converter writes a normal text's spaces
    so (`"for all "` is the mtext "for\\u00a0all\\u00a0").
    """
    return "".join(
        " "
        if character == " "
        else unicodedata.normalize("NFKC", character)
        if unicodedata.category(character)[0] in "LN"
        else character
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
    if side == "after" and not node.children and scripted_operator(document, node):
        # Right after ∑, ∫ or lim, before its limits: nothing can be typed
        # there (`∑q_(i=1)` does not parse), so typing goes on at the next leaf.
        later = [
            spans[leaf.identifier].start
            for leaf in leaf_nodes(document)
            if leaf.identifier in spans
            and spans[leaf.identifier].start >= end
            and spans[leaf.identifier].end > spans[leaf.identifier].start
        ]
        if later:
            return min(later)
    if outside or node.children:
        visible = {
            spans[leaf.identifier].start
            for leaf in leaf_nodes(document)
            if leaf.identifier in spans and leaf.text.strip() in ("(", ")", "[", "]", "{", "}")
        }
        start, end = _with_own_parens(source, start, end, visible)
        if _fills_a_slot(document, node):
            # A numerator's, a radicand's, an argument's parens are the slot's,
            # not the structure filling it: "after the fraction" in
            # `(1/2)/(3/4)` stays inside the numerator.
            start, end = _without_slot_parens(source, start, end)
    return start if side == "before" else end


_SLOT_PARENTS = frozenset(
    {"mfrac", "msqrt", "mroot", "msub", "msup", "msubsup", "munder", "mover", "munderover", "mtd"}
)
_SCRIPTED = frozenset({"msub", "msup", "msubsup", "munder", "mover", "munderover"})


def _fills_a_slot(document: MathMLDocument, node: MathMLNode) -> bool:
    """Whether the node is the whole content of a structure's argument (or a role such as "argument")."""
    current = node
    while current.identifier:
        parent = document.parent_by_id.get(current.identifier)
        if parent is None:
            return False
        if parent.tag in _SLOT_PARENTS:
            return True
        if parent.tag != "mrow" or len(parent.children) != 1:
            break
        current = parent  # A lone wrapper mrow: the slot is around it.
    if not node.identifier:
        return False
    if is_equation_label(node):
        return True  # The number's `(...)` is its slot: typing on it goes inside.
    # An argument's or integrand's box `〖...〗` is a slot too: "end integrand" types inside it.
    boxed = node.attributes.get("intent", "").startswith(":fenced") and bool(document.regions(node.identifier))
    return boxed or bool(document.semantic_role(node.identifier))


def _without_slot_parens(source: str, start: int, end: int) -> tuple[int, int]:
    view = view_of(source)
    text = view.text
    low, high = view.to_view(start), view.to_view(end)
    if high - low >= 2 and text[low] in "(〖" and text[high - 1] in ")〗":
        depth = 0
        for index in range(low, high):
            if text[index] in "(〖":
                depth += 1
            elif text[index] in ")〗":
                depth -= 1
                if depth == 0 and index != high - 1:
                    return start, end  # The first "(" closes before the end: not one pair.
        return view.to_source(low + 1), view.to_source(high - 1)
    return start, end


def scripted_operator(document: MathMLDocument, node: MathMLNode) -> bool:
    """∑, ∫, lim, log...: an operator or function name that is the base of its limits/scripts."""
    if document.is_large_operator(node):
        return True  # `∫▒f`: right after it comes ▒, nothing can be typed there either.
    parent = document.parent_by_id.get(node.identifier or "")
    if parent is None or parent.tag not in _SCRIPTED or not parent.children or parent.children[0] is not node:
        return False
    return node.tag == "mo" or len(node.text.strip()) > 1


def _with_own_parens(source: str, start: int, end: int, visible: set[int] = frozenset()) -> tuple[int, int]:
    """Widen `start`..`end` over the "(" / ")" whose partner is already inside it, and a structure's sign (√, ■).

    Not over parens that are leaves of their own (`visible`, source
    offsets): `((a+b)/c)^2` keeps its outer parens, they are not the fraction's.
    """
    view = view_of(source)
    text = view.text
    pairs = {}
    stack: list[int] = []
    for index, character in enumerate(text):
        if character in "(〖":
            stack.append(index)
        elif character in ")〗" and stack:
            opening = stack.pop()
            pairs[opening], pairs[index] = index, opening
    low, high = view.to_view(start), view.to_view(end)
    changed = True
    while changed:
        changed = False
        if (
            low > 0
            and text[low - 1] in "(〖"
            and low - 1 in pairs
            and pairs[low - 1] <= high
            and view.to_source(low - 1) not in visible
        ):
            low -= 1
            changed = True
        if low > 0 and text[low - 1] in _STRUCTURE_SIGNS and low < len(text) and text[low] in "(〖":
            low -= 1
            changed = True
        if (
            high < len(text)
            and text[high] in ")〗"
            and high in pairs
            and pairs[high] >= low
            and view.to_source(high) not in visible
        ):
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
    if caret <= 0:
        return None
    # After a space (no leaf of its own): the last leaf ending before the
    # caret, not the one right after it (`leaf_at` would give that one).
    before = [(span.end, identifier) for identifier, span in spans.items() if span.start < span.end <= caret]
    return max(before)[1] if before else leaf_at(spans, caret)


def leaf_characters(source: str, spans: dict[str, SourceSpan], document: MathMLDocument, leaf_id: str) -> str | None:
    """A leaf's characters, when the caret can step through them one by one (`12`, `sin`).

    Only for a leaf written as itself in the source: not one character, not
    a control word (`\\alpha` is one "α"), not a respelled symbol (`<=`).
    """
    span = spans.get(leaf_id)
    node = document.node(leaf_id)
    if span is None or node is None or node.children:
        return None
    text = source[span.start : span.end]
    if len(text) < 2 or "\\" in text or len(text) != len(node.text):
        return None
    return text


def inside_leaf(spans: dict[str, SourceSpan], caret: int) -> tuple[str, int] | None:
    """(leaf id, characters before the caret) when `caret` is strictly inside a leaf's span."""
    for identifier, span in spans.items():
        if span.start < caret < span.end:
            return identifier, caret - span.start
    return None
