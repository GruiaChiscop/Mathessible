"""Pipe tables and ```table blocks (merged_tables) in the grid model (grid_tables.GridTable), for Edit Table,
and the simplest syntax a table is written back in.

A pipe table's first row is always its header, an empty one too (a Markdown table always has one, and
Insert Table writes it empty): it is a row to fill in. Cells are split at a `|` that is not escaped (`\\|`,
a `|` in the cell's text) and not in an equation: Mathessible finds equations before it reads a table, so
`$|x|$` stays whole, while code spans are split as GitHub splits them. The delimiter row's colons are the
columns' alignments. A ```table block is a pipe table whose `>` joins a cell to the one on its left and
`^` to the one above (`\\>` and `\\^` are those characters); its joins must make rectangles.

`simplest_table` writes a table as a pipe table; as a ```table block when cells are merged; as a grid
table when a cell holds more than one line, when the header is more than one row, or when a merged table
has an equation holding `|` (a block's rows are split at every `|`, equations or not).
"""

from __future__ import annotations

import re

from mathessible.documents.grid_tables import GridCell, GridTable, grid_table_at, header_row_count, write_grid_table
from mathessible.documents.markdown_math import find_math_zones, literal_ranges

_DELIMITER_CELL = re.compile(r"\s*(:?)-+(:?)\s*")
_BLOCK = re.compile(r"^```table[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
_ALIGNMENT = {("", ""): "", (":", ""): "left", (":", ":"): "center", ("", ":"): "right"}
_DELIMITER = {"": "---", "left": ":---", "center": ":---:", "right": "---:"}


def editable_table_at(source: str, position: int) -> tuple[int, int, GridTable, str] | None:
    """The table at `position` as (start, end, table, kind): a "grid" table, a ```table "block" or a "pipe"
    table; None when there is none, or it cannot be read as a grid (a block whose joins are not
    rectangles)."""
    found = grid_table_at(source, position)
    if found is not None:
        return (*found, "grid")
    for block in _BLOCK.finditer(source):
        if block.start() <= position <= block.end():
            table = _block_table(block.group(1).splitlines())
            return None if table is None else (block.start(), block.end(), table, "block")
    if any(start <= position < end for start, end in literal_ranges(source)):
        return None  # In code: a code block's lines are not a table.
    return _pipe_table_at(source, position)


def simplest_table(table: GridTable) -> str:
    """The table in the simplest syntax that holds it (see the module notes)."""
    merged = any(cell.rowspan > 1 or cell.colspan > 1 for cell in table.cells)
    if any("\n" in cell.content for cell in table.cells) or header_row_count(table) > 1:
        return write_grid_table(table)
    if merged and any("|" in _math_text(cell.content) for cell in table.cells):
        return write_grid_table(table)
    rows = [[""] * table.columns for _ in range(table.rows)]
    for cell in table.cells:
        for row in range(cell.row, cell.row + cell.rowspan):
            for column in range(cell.column, cell.column + cell.colspan):
                if (row, column) == (cell.row, cell.column):
                    rows[row][column] = _escaped(cell.content, merged)
                else:
                    rows[row][column] = "^" if row > cell.row else ">"
    if header_row_count(table) == 0 and any(rows[0]):
        rows.insert(0, [""] * table.columns)  # A Markdown table has a header row: an empty one stands for none.
    alignments = table.alignments or ("",) * table.columns
    lines = [_line(rows[0]), _line([_DELIMITER[alignment] for alignment in alignments])]
    lines += [_line(row) for row in rows[1:]]
    text = "\n".join(lines)
    return f"```table\n{text}\n```" if merged else text


def _line(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _escaped(content: str, merged: bool) -> str:
    """A cell's text for a pipe table: its `|` outside equations escaped, and in a block a lone `>` or `^`
    (a join) escaped too."""
    zones = [(zone.start, zone.end) for zone in find_math_zones(content)]
    text = "".join(
        "\\|" if character == "|" and not any(start <= index < end for start, end in zones) else character
        for index, character in enumerate(content)
    )
    if merged and text in (">", "^"):
        return "\\" + text
    return text


def _math_text(content: str) -> str:
    return "".join(content[zone.start : zone.end] for zone in find_math_zones(content))


def _cells(line: str) -> list[str]:
    """A table row's cells, split at a `|` not escaped and not in an equation, `\\|` read as `|`."""
    zones = [(zone.start, zone.end) for zone in find_math_zones(line)]
    cells: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(line):
        character = line[index]
        in_math = any(start <= index < end for start, end in zones)
        if character == "\\" and line[index + 1 : index + 2] == "|" and not in_math:
            current.append("|")
            index += 2
            continue
        if character == "|" and not in_math:
            cells.append("".join(current))
            current = []
        else:
            current.append(character)
        index += 1
    cells.append("".join(current))
    stripped = line.strip()
    if stripped.startswith("|"):
        cells.pop(0)
    if stripped.endswith("|") and not stripped.endswith("\\|") and cells:
        cells.pop()
    return [cell.strip() for cell in cells]


def _alignments(line: str) -> tuple[str, ...] | None:
    """The delimiter row's alignments; None when the line is not one."""
    cells = _cells(line)
    found = [_DELIMITER_CELL.fullmatch(cell) for cell in cells]
    if not cells or not all(found):
        return None
    return tuple(_ALIGNMENT[(match.group(1), match.group(2))] for match in found if match)


def _rows(lines: list[str]) -> tuple[list[list[str]], tuple[str, ...]] | None:
    """A pipe table's rows (the header first) and alignments; body rows padded or cut to the header's
    width, as GitHub reads them. None when the second line is no delimiter row matching the header."""
    if len(lines) < 2:
        return None
    header, alignments = _cells(lines[0]), _alignments(lines[1])
    if alignments is None or len(alignments) != len(header) or not header:
        return None
    width = len(header)
    rows = [header] + [(_cells(line) + [""] * width)[:width] for line in lines[2:]]
    return rows, alignments


def _grid(
    rows: list[list[str]], alignments: tuple[str, ...], spans: dict[tuple[int, int], tuple[int, int]]
) -> GridTable:
    """The grid of those rows, the first the header; `spans` gives a merged cell's (rowspan, colspan) by
    its first position."""
    covered = {
        (row + down, column + across)
        for (row, column), (rowspan, colspan) in spans.items()
        for down in range(rowspan)
        for across in range(colspan)
        if (down, across) != (0, 0)
    }
    cells = []
    for row, values in enumerate(rows):
        for column, value in enumerate(values):
            if (row, column) in covered:
                continue
            rowspan, colspan = spans.get((row, column), (1, 1))
            cells.append(GridCell(row, column, rowspan, colspan, row == 0, value))
    return GridTable(len(rows), len(rows[0]), tuple(cells), alignments if any(alignments) else ())


def _block_table(lines: list[str]) -> GridTable | None:
    """A ```table block's table, its `>`/`^` joins as merged cells; None when they are not rectangles."""
    read = _rows([line for line in lines if line.strip()])
    if read is None:
        return None
    rows, alignments = read
    owners: dict[tuple[int, int], tuple[int, int]] = {}
    for row, values in enumerate(rows):
        for column, value in enumerate(values):
            owner: tuple[int, int] | None = (row, column)
            if value == ">":
                owner = owners.get((row, column - 1))
            elif value == "^":
                owner = owners.get((row - 1, column))
            if owner is None:
                return None  # A join with nothing to join.
            owners[(row, column)] = owner
    regions: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for position, owner in owners.items():
        regions.setdefault(owner, []).append(position)
    spans = {}
    for owner, positions in regions.items():
        height = max(row for row, _ in positions) - owner[0] + 1
        width = max(column for _, column in positions) - owner[1] + 1
        if len(positions) != height * width:
            return None
        if (height, width) != (1, 1):
            spans[owner] = (height, width)
    unescaped = [[value[1:] if value in ("\\>", "\\^") else value for value in row] for row in rows]
    return _grid(unescaped, alignments, spans)


def _pipe_table_at(source: str, position: int) -> tuple[int, int, GridTable, str] | None:
    """The pipe table whose lines hold `position`: a header line, a delimiter row, then rows holding `|`."""
    lines = source.split("\n")
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line) + 1)
    here = next(index for index in range(len(lines)) if offsets[index + 1] > position or index == len(lines) - 1)
    if "|" not in lines[here]:
        return None
    first = here
    while first > 0 and "|" in lines[first - 1] and lines[first - 1].strip():
        first -= 1
    last = here
    while last + 1 < len(lines) and "|" in lines[last + 1] and lines[last + 1].strip():
        last += 1
    # The table starts at the header above its delimiter row; lines before it are a paragraph's.
    for start in range(first, last):
        if _alignments(lines[start + 1]) is not None and start <= here:
            read = _rows(lines[start : last + 1])
            if read is None:
                continue
            rows, alignments = read
            table = _grid(rows, alignments, {})
            return offsets[start], offsets[last] + len(lines[last]), table, "pipe"
    return None
