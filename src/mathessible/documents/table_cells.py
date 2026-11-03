"""A table cell's content as the exporters write it: its paragraphs, list items and code, in order.

A pipe table's cell is one line of text; a grid table's (grid_tables) holds blocks. Each exporter
collects a cell's tokens (from `td_open` to `td_close`) and writes `cell_blocks` of them, so a cell of
either kind is written the same way.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from markdown_it.token import Token


@dataclass(frozen=True, slots=True)
class CellBlock:
    kind: str  # "paragraph", "bullet", "ordered" (a list item's first paragraph) or "code".
    inline: Token | None = None  # The text, for every kind but code.
    code: str = ""
    level: int = 0  # Lists it is in: 1 for a top-level item and its later paragraphs.
    number: int = 0  # An ordered item's number.


@dataclass(frozen=True, slots=True)
class Cell:
    header: bool
    span: dict  # x, y, colspan, rowspan, columns when it is known (a merged or grid table's cell).
    blocks: tuple[CellBlock, ...]


def collect_cell(opening: Token, tokens: Sequence[Token]) -> Cell:
    """The cell `opening` (th_open or td_open) starts, its tokens up to its closing one."""
    span = dict(opening.meta.get("table_cell", {}))
    if not span:  # A merged table's cell (merged_tables) gives its span on its text.
        span = next((dict(token.meta["table_cell"]) for token in tokens if "table_cell" in token.meta), {})
    return Cell(opening.type == "th_open", span, tuple(cell_blocks(tokens)))


def cell_blocks(tokens: Sequence[Token]) -> list[CellBlock]:
    blocks: list[CellBlock] = []
    lists: list[list[int]] = []  # Per open list: [ordered (0/1), next number].
    marker: tuple[str, int] | None = None  # The open item's kind and number, until its first text.
    for token in tokens:
        kind = token.type
        if kind in ("bullet_list_open", "ordered_list_open"):
            lists.append([1 if kind == "ordered_list_open" else 0, int(token.attrGet("start") or 1)])
        elif kind in ("bullet_list_close", "ordered_list_close"):
            lists.pop()
        elif kind == "list_item_open" and lists:
            ordered, number = lists[-1]
            marker = ("ordered", number) if ordered else ("bullet", 0)
            lists[-1][1] += 1
        elif kind in ("fence", "code_block"):
            blocks.append(CellBlock("code", code=token.content.rstrip("\n"), level=len(lists)))
        elif kind == "inline":
            if marker is not None:
                blocks.append(CellBlock(marker[0], token, level=len(lists), number=marker[1]))
                marker = None
            else:
                blocks.append(CellBlock("paragraph", token, level=len(lists)))
    return blocks
