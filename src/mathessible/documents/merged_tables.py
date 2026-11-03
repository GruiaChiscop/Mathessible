"""Opt-in fenced tables with explicit left (>) and above (^) continuation cells.

Ordinary Markdown tables are unchanged. Invalid merge rectangles remain code.
"""

from __future__ import annotations

from markdown_it import MarkdownIt
from markdown_it.rules_block.table import escapedSplit
from markdown_it.token import Token


def merged_tables_plugin(md: MarkdownIt) -> None:
    md.core.ruler.after("block", "merged_tables", _expand)


def _table(source: str) -> list[Token]:
    lines = source.strip().splitlines()
    if len(lines) > 1001 or len(source) > 2_000_000:
        raise ValueError("Table exceeds limits")
    widths = []
    for line in lines:
        cells = escapedSplit(line.strip())
        if cells and cells[0] == "":
            cells.pop(0)
        if cells and cells[-1] == "":
            cells.pop()
        widths.append(len(cells))
    if not widths or not 1 <= widths[0] <= 100 or any(width != widths[0] for width in widths):
        raise ValueError("Every row must explicitly contain the same number of cells")
    parsed = MarkdownIt("commonmark").enable("table").parse(source)
    if (
        not parsed
        or parsed[0].type != "table_open"
        or parsed[-1].type != "table_close"
        or sum(token.type == "table_open" for token in parsed) != 1
    ):
        raise ValueError("Expected one table")
    rows: list[list[Token]] = []
    attributes = {}
    for token in parsed:
        if token.type == "tr_open":
            rows.append([])
        elif token.type in {"th_open", "td_open"}:
            attributes = dict(token.attrs)
        elif token.type == "inline":
            token.meta["cell_attributes"] = attributes
            rows[-1].append(token)
    if not rows or len(rows) > 1000 or len(rows[0]) > 100:
        raise ValueError("Table exceeds limits")
    owners: dict[tuple[int, int], tuple[int, int]] = {}
    regions: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for y, row in enumerate(rows):
        for x, token in enumerate(row):
            marker = token.content.strip()
            owner = (y, x)
            if marker == ">":
                owner = owners.get((y, x - 1))
            elif marker == "^":
                owner = owners.get((y - 1, x))
            if owner is None:
                raise ValueError("Continuation without a cell")
            owners[y, x] = owner
            regions.setdefault(owner, []).append((y, x))
    spans = {}
    for (y, x), cells in regions.items():
        height = max(row for row, _ in cells) - y + 1
        width = max(column for _, column in cells) - x + 1
        if len(cells) != height * width:
            raise ValueError("Nonrectangular merge")
        spans[y, x] = (height, width)
    result = [Token("table_open", "table", 1), Token("tbody_open", "tbody", 1)]
    for y, row in enumerate(rows):
        result.append(Token("tr_open", "tr", 1))
        for x, inline in enumerate(row):
            if (y, x) not in spans:
                continue
            height, width = spans[y, x]
            inline.children = []
            opening = Token("th_open" if y == 0 else "td_open", "th" if y == 0 else "td", 1)
            opening.attrs = inline.meta.pop("cell_attributes", {})
            if width > 1:
                opening.attrSet("colspan", str(width))
            if height > 1:
                opening.attrSet("rowspan", str(height))
            span = {"x": x, "y": y, "colspan": width, "rowspan": height, "columns": len(rows[0])}
            opening.meta["table_cell"] = inline.meta["table_cell"] = span
            result.extend([opening, inline, Token("th_close" if y == 0 else "td_close", opening.tag, -1)])
        result.append(Token("tr_close", "tr", -1))
    result.extend([Token("tbody_close", "tbody", -1), Token("table_close", "table", -1)])
    return result


def _expand(state: object) -> None:
    result = []
    for token in state.tokens:
        if token.type == "fence" and token.info.strip() == "table":
            try:
                result.extend(_table(token.content))
                continue
            except ValueError:
                pass
        result.append(token)
    state.tokens = result
