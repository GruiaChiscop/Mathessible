"""Pandoc's grid tables, read without Pandoc: merged cells and cells holding paragraphs, lists or code.

A grid table is drawn with its columns aligned, and Pandoc does not escape a `|` inside a cell, so it can
only be read by its characters' columns. The exporters replace equations with marks of another width
before parsing, which would break that alignment, so `expand_grid_tables` runs first, on the document as
written: it rewrites each grid table as ordinary Markdown between marker lines (each cell's content as
blocks of its own), and `grid_tables_plugin` turns the markers back into a table whose cells hold those
blocks. Equations in cells stay text until then, so every exporter finds them as anywhere else.

An invalid grid stays as it is written: nothing in it is lost.
"""

from __future__ import annotations

import re
import textwrap
import unicodedata
from dataclasses import dataclass

from markdown_it import MarkdownIt
from markdown_it.token import Token

# Private-use characters, which no one types: a marker line cannot be text of the document.
_OPEN, _CLOSE = "", ""
_TABLE = re.compile(f"^{_OPEN}table (\\d+) (\\d+){_CLOSE}$")
_CELL = re.compile(f"^{_OPEN}cell (\\d+) (\\d+) (\\d+) (\\d+) ([hd]){_CLOSE}$")
_END = f"{_OPEN}end{_CLOSE}"
_TOP = re.compile(r"^\+(?:[-:]+\+)+\s*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_LIMIT = 1000  # Rows or columns, as a pasted table's.


@dataclass(frozen=True, slots=True)
class GridCell:
    row: int
    column: int
    rowspan: int
    colspan: int
    header: bool
    content: str  # Markdown, dedented.


@dataclass(frozen=True, slots=True)
class GridTable:
    rows: int
    columns: int
    cells: tuple[GridCell, ...]


def _slots(line: str) -> list[str]:
    """The line as it shows, one entry per column: a wide (CJK) character takes two, its second empty, and
    a combining mark joins the character before it, as Pandoc measures a grid."""
    slots: list[str] = []
    for character in line:
        if unicodedata.combining(character) and slots:
            slots[-1] += character
        elif unicodedata.east_asian_width(character) in ("W", "F"):
            slots += [character, ""]
        else:
            slots.append(character)
    return slots


def parse_grid_table(lines: list[str]) -> GridTable | None:
    """The table those lines draw, or None when they are not a valid grid."""
    grid = [_slots(line.rstrip()) for line in lines]
    height, width = len(grid), max(map(len, grid), default=0)
    if height < 3 or width < 3 or any(len(row) != width for row in grid):
        return None

    def at(row: int, column: int) -> str:
        return grid[row][column] if 0 <= row < height and 0 <= column < width else ""

    found: list[tuple[int, int, int, int]] = []
    for top in range(height - 1):
        for left in range(width - 1):
            if at(top, left) != "+" or at(top, left + 1) not in ("-", "=", ":") or at(top + 1, left) not in ("|", "+"):
                continue
            right = next(
                (
                    column
                    for column in range(left + 1, width)
                    if at(top, column) == "+" and at(top + 1, column) in ("|", "+")
                ),
                None,
            )
            if right is None or any(at(top, column) not in "-=:+" for column in range(left, right + 1)):
                return None
            bottom = next(
                (
                    row
                    for row in range(top + 1, height)
                    if at(row, left) == "+"
                    and at(row, right) == "+"
                    and all(at(row, column) in "-=:+" for column in range(left, right + 1))
                ),
                None,
            )
            if bottom is None or any(
                at(row, column) not in "|+" for row in range(top, bottom + 1) for column in (left, right)
            ):
                return None
            found.append((top, left, bottom, right))
    if not found:
        return None
    row_lines = sorted({edge for top, _, bottom, _ in found for edge in (top, bottom)})
    column_lines = sorted({edge for _, left, _, right in found for edge in (left, right)})
    rows, columns = len(row_lines) - 1, len(column_lines) - 1
    if rows > _LIMIT or columns > _LIMIT or row_lines[0] != 0 or row_lines[-1] != height - 1:
        return None
    header_end = next((row for row in row_lines if "=" in "".join(grid[row])), None)
    occupied: set[tuple[int, int]] = set()
    cells: list[GridCell] = []
    for top, left, bottom, right in found:
        y, x = row_lines.index(top), column_lines.index(left)
        rowspan, colspan = row_lines.index(bottom) - y, column_lines.index(right) - x
        covered = {(y + down, x + across) for down in range(rowspan) for across in range(colspan)}
        if covered & occupied:
            return None
        occupied |= covered
        text = "\n".join("".join(grid[row][left + 1 : right]).rstrip() for row in range(top + 1, bottom))
        cells.append(GridCell(y, x, rowspan, colspan, header_end is not None and bottom <= header_end, _content(text)))
    if len(occupied) != rows * columns:
        return None
    return GridTable(rows, columns, tuple(sorted(cells, key=lambda cell: (cell.row, cell.column))))


def _content(text: str) -> str:
    """A cell's lines as Markdown: Pandoc's one-space padding and common indentation removed."""
    return textwrap.dedent(text).strip("\n")


def expand_grid_tables(source: str) -> str:
    """The Markdown with each grid table (outside code fences) rewritten for `grid_tables_plugin`."""
    if "+-" not in source:
        return source
    lines = source.split("\n")
    result: list[str] = []
    fence = ""
    index = 0
    while index < len(lines):
        line = lines[index]
        opening = _FENCE.match(line)
        if fence:
            if opening and opening.group(1)[0] == fence[0] and len(opening.group(1)) >= len(fence):
                fence = ""
        elif opening:
            fence = opening.group(1)
        elif _TOP.match(line):
            end = index + 1
            while end < len(lines) and lines[end][:1] in ("+", "|"):
                end += 1
            table = parse_grid_table(lines[index:end])
            if table is not None:
                result += ["", *_written(table), ""]
                index = end
                continue
        result.append(line)
        index += 1
    return "\n".join(result)


def _written(table: GridTable) -> list[str]:
    lines = [f"{_OPEN}table {table.rows} {table.columns}{_CLOSE}", ""]
    for cell in table.cells:
        kind = "h" if cell.header else "d"
        marker = f"{_OPEN}cell {cell.row} {cell.column} {cell.rowspan} {cell.colspan} {kind}{_CLOSE}"
        lines += [marker, ""]
        if cell.content:
            lines += [*cell.content.split("\n"), ""]
    lines.append(_END)
    return lines


def grid_tables_plugin(md: MarkdownIt) -> None:
    md.core.ruler.after("block", "grid_tables", _assemble)


def _marker(tokens: list[Token], index: int) -> str | None:
    """The marker a paragraph at the top level is, if it is one."""
    if (
        index + 2 < len(tokens)
        and tokens[index].type == "paragraph_open"
        and tokens[index].level == 0
        and tokens[index + 1].type == "inline"
        and tokens[index + 1].content.startswith(_OPEN)
        and tokens[index + 2].type == "paragraph_close"
    ):
        return tokens[index + 1].content.strip()
    return None


def _assemble(state: object) -> None:
    tokens: list[Token] = state.tokens
    result: list[Token] = []
    index = 0
    while index < len(tokens):
        marker = _marker(tokens, index)
        table = _TABLE.match(marker) if marker else None
        if table is None:
            result.append(tokens[index])
            index += 1
            continue
        cells: list[tuple[re.Match[str], list[Token]]] = []
        index += 3
        while index < len(tokens):
            marker = _marker(tokens, index)
            if marker == _END:
                index += 3
                break
            cell = _CELL.match(marker) if marker else None
            if cell is not None:
                cells.append((cell, []))
                index += 3
                continue
            if cells:
                cells[-1][1].append(tokens[index])
            index += 1
        result += _table_tokens(int(table.group(1)), int(table.group(2)), cells)
    state.tokens = result


def _table_tokens(rows: int, columns: int, cells: list[tuple[re.Match[str], list[Token]]]) -> list[Token]:
    by_row: dict[int, list[tuple[re.Match[str], list[Token]]]] = {}
    for cell in cells:
        by_row.setdefault(int(cell[0].group(1)), []).append(cell)
    header_rows = {row for row, row_cells in by_row.items() if all(cell[0].group(5) == "h" for cell in row_cells)}
    # Positions only in a table with merged cells, as merged_tables gives them: the exporters place such
    # cells by them, and write any other table row by row.
    merged = any(int(cell[0].group(3)) > 1 or int(cell[0].group(4)) > 1 for cell in cells)
    result = [Token("table_open", "table", 1)]
    section = ""
    for row in range(rows):
        wanted = "thead" if row in header_rows and section in ("", "thead") else "tbody"
        if wanted != section:
            if section:
                result.append(Token(f"{section}_close", section, -1))
            result.append(Token(f"{wanted}_open", wanted, 1))
            section = wanted
        result.append(Token("tr_open", "tr", 1))
        for match, content in sorted(by_row.get(row, []), key=lambda cell: int(cell[0].group(2))):
            y, x, rowspan, colspan = (int(match.group(number)) for number in range(1, 5))
            tag = "th" if match.group(5) == "h" else "td"
            opening = Token(f"{tag}_open", tag, 1)
            if colspan > 1:
                opening.attrSet("colspan", str(colspan))
            if rowspan > 1:
                opening.attrSet("rowspan", str(rowspan))
            if merged:
                opening.meta["table_cell"] = {
                    "x": x,
                    "y": y,
                    "colspan": colspan,
                    "rowspan": rowspan,
                    "columns": columns,
                }
            paragraphs = [token for token in content if token.type == "paragraph_open"]
            if len(paragraphs) == 1 and len(content) == 3:
                for token in content:  # One paragraph: written as the cell's text, as a pipe table's.
                    token.hidden = token.type != "inline"
            result += [opening, *content, Token(f"{tag}_close", tag, -1)]
        result.append(Token("tr_close", "tr", -1))
    if section:
        result.append(Token(f"{section}_close", section, -1))
    result.append(Token("table_close", "table", -1))
    return result
