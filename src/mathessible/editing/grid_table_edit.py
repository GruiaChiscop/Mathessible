"""Edit Table's changes to a grid table (grid_tables): its cells' text, rows and columns, merging and splitting.

Each takes a table and gives a new one (tables are frozen), so the dialog keeps the one it shows and its
OK writes it back with `write_grid_table`. A change that would not leave a rectangle of cells raises
`TableEditError`; `can_merge_right` and the like let the dialog offer only what applies.
"""

from __future__ import annotations

from dataclasses import replace

from mathessible.documents.grid_tables import GridCell, GridTable, header_row_count
from mathessible.i18n import _, ngettext


class TableEditError(ValueError):
    pass


def cell_at(table: GridTable, row: int, column: int) -> GridCell:
    """The cell covering a position (a merged cell covers several)."""
    for cell in table.cells:
        if cell.row <= row < cell.row + cell.rowspan and cell.column <= column < cell.column + cell.colspan:
            return cell
    raise TableEditError(f"No cell at row {row}, column {column}")


def _table(rows: int, columns: int, cells: list[GridCell]) -> GridTable:
    """The table of those cells, a row (or column) that only lies inside merged cells left out: no cell
    starts or ends there, so a grid could not draw it (merging a one-column table's two rows makes one)."""
    row_lines = sorted({0, rows, *(edge for cell in cells for edge in (cell.row, cell.row + cell.rowspan))})
    column_lines = sorted({0, columns, *(edge for cell in cells for edge in (cell.column, cell.column + cell.colspan))})
    placed = []
    for cell in cells:
        row, column = row_lines.index(cell.row), column_lines.index(cell.column)
        rowspan = row_lines.index(cell.row + cell.rowspan) - row
        colspan = column_lines.index(cell.column + cell.colspan) - column
        placed.append(replace(cell, row=row, column=column, rowspan=rowspan, colspan=colspan))
    return GridTable(
        len(row_lines) - 1, len(column_lines) - 1, tuple(sorted(placed, key=lambda cell: (cell.row, cell.column)))
    )


def new_table(rows: int, columns: int, header: bool) -> GridTable:
    """An empty table; with `header`, its first row the header."""
    cells = [GridCell(row, column, 1, 1, header and row == 0, "") for row in range(rows) for column in range(columns)]
    return _table(rows, columns, cells)


def with_content(table: GridTable, cell: GridCell, content: str) -> GridTable:
    text = "\n".join(line.rstrip() for line in content.replace("\r\n", "\n").split("\n")).strip("\n")
    return _table(
        table.rows, table.columns, [replace(each, content=text) if each == cell else each for each in table.cells]
    )


def insert_row(table: GridTable, index: int) -> GridTable:
    """A row of empty cells before row `index` (`table.rows` for the end); a merged cell it passes through
    grows by a row."""
    header = index < header_row_count(table)  # Inside the header (or above it), a header row.
    cells: list[GridCell] = []
    for cell in table.cells:
        if cell.row >= index:
            cells.append(replace(cell, row=cell.row + 1))
        elif cell.row + cell.rowspan > index:
            cells.append(replace(cell, rowspan=cell.rowspan + 1))
        else:
            cells.append(cell)
    covered = {column for cell in cells if cell.row < index < cell.row + cell.rowspan for column in _columns(cell)}
    cells += [GridCell(index, column, 1, 1, header, "") for column in range(table.columns) if column not in covered]
    return _table(table.rows + 1, table.columns, cells)


def delete_row(table: GridTable, index: int) -> GridTable:
    """Row `index` without its cells; a merged cell across it loses a row, keeping its text."""
    if table.rows == 1:
        raise TableEditError("A table keeps at least one row")
    cells: list[GridCell] = []
    for cell in table.cells:
        if cell.row > index:
            cells.append(replace(cell, row=cell.row - 1))
        elif cell.row + cell.rowspan <= index:
            cells.append(cell)
        elif cell.rowspan > 1:
            cells.append(replace(cell, rowspan=cell.rowspan - 1))
    return _table(table.rows - 1, table.columns, cells)


def insert_column(table: GridTable, index: int) -> GridTable:
    """A column of empty cells before column `index` (`table.columns` for the end); a merged cell it passes
    through grows by a column."""
    cells: list[GridCell] = []
    for cell in table.cells:
        if cell.column >= index:
            cells.append(replace(cell, column=cell.column + 1))
        elif cell.column + cell.colspan > index:
            cells.append(replace(cell, colspan=cell.colspan + 1))
        else:
            cells.append(cell)
    covered = {row for cell in cells if cell.column < index < cell.column + cell.colspan for row in _rows(cell)}
    header_rows = header_row_count(table)
    cells += [GridCell(row, index, 1, 1, row < header_rows, "") for row in range(table.rows) if row not in covered]
    return _table(table.rows, table.columns + 1, cells)


def delete_column(table: GridTable, index: int) -> GridTable:
    """Column `index` without its cells; a merged cell across it loses a column, keeping its text."""
    if table.columns == 1:
        raise TableEditError("A table keeps at least one column")
    cells: list[GridCell] = []
    for cell in table.cells:
        if cell.column > index:
            cells.append(replace(cell, column=cell.column - 1))
        elif cell.column + cell.colspan <= index:
            cells.append(cell)
        elif cell.colspan > 1:
            cells.append(replace(cell, colspan=cell.colspan - 1))
    return _table(table.rows, table.columns - 1, cells)


def _right_neighbour(table: GridTable, cell: GridCell) -> GridCell | None:
    column = cell.column + cell.colspan
    if column >= table.columns:
        return None
    neighbour = cell_at(table, cell.row, column)
    same_rows = neighbour.row == cell.row and neighbour.rowspan == cell.rowspan and neighbour.header == cell.header
    return neighbour if same_rows else None


def _lower_neighbour(table: GridTable, cell: GridCell) -> GridCell | None:
    row = cell.row + cell.rowspan
    if row >= table.rows:
        return None
    neighbour = cell_at(table, row, cell.column)
    same_columns = neighbour.column == cell.column and neighbour.colspan == cell.colspan
    return neighbour if same_columns and neighbour.header == cell.header else None


def can_merge_right(table: GridTable, cell: GridCell) -> bool:
    return _right_neighbour(table, cell) is not None


def can_merge_down(table: GridTable, cell: GridCell) -> bool:
    return _lower_neighbour(table, cell) is not None


def merge_right(table: GridTable, cell: GridCell) -> tuple[GridTable, GridCell]:
    """The cell and the one to its right (as tall as it) as one, their texts as paragraphs; and that cell."""
    neighbour = _right_neighbour(table, cell)
    if neighbour is None:
        raise TableEditError("The cell to the right does not span the same rows")
    merged = replace(cell, colspan=cell.colspan + neighbour.colspan, content=_joined(cell, neighbour))
    return _merged(table, (cell, neighbour), merged), merged


def merge_down(table: GridTable, cell: GridCell) -> tuple[GridTable, GridCell]:
    """The cell and the one below it (as wide as it) as one, their texts as paragraphs; and that cell."""
    neighbour = _lower_neighbour(table, cell)
    if neighbour is None:
        raise TableEditError("The cell below does not span the same columns")
    merged = replace(cell, rowspan=cell.rowspan + neighbour.rowspan, content=_joined(cell, neighbour))
    return _merged(table, (cell, neighbour), merged), merged


def split(table: GridTable, cell: GridCell) -> GridTable:
    """A merged cell back into single cells, its text in the first."""
    cells = [each for each in table.cells if each != cell]
    for row in _rows(cell):
        for column in _columns(cell):
            first = row == cell.row and column == cell.column
            cells.append(GridCell(row, column, 1, 1, cell.header, cell.content if first else ""))
    return _table(table.rows, table.columns, cells)


def with_header_rows(table: GridTable, count: int) -> GridTable:
    """The first `count` rows as the header (0: none). A merged cell may not cross the header's end."""
    if any(cell.row < count < cell.row + cell.rowspan for cell in table.cells):
        raise TableEditError("A merged cell crosses the end of the header")
    return _table(table.rows, table.columns, [replace(cell, header=cell.row < count) for cell in table.cells])


def _joined(first: GridCell, second: GridCell) -> str:
    return "\n\n".join(text for text in (first.content, second.content) if text)


def _merged(table: GridTable, removed: tuple[GridCell, GridCell], merged: GridCell) -> GridTable:
    return _table(table.rows, table.columns, [cell for cell in table.cells if cell not in removed] + [merged])


def _rows(cell: GridCell) -> range:
    return range(cell.row, cell.row + cell.rowspan)


def _columns(cell: GridCell) -> range:
    return range(cell.column, cell.column + cell.colspan)


def neighbour(table: GridTable, cell: GridCell, direction: str) -> GridCell | None:
    """The cell next to `cell` ("up", "down", "left" or "right"), along its first row or column; None at the
    table's edge."""
    row, column = {
        "up": (cell.row - 1, cell.column),
        "down": (cell.row + cell.rowspan, cell.column),
        "left": (cell.row, cell.column - 1),
        "right": (cell.row, cell.column + cell.colspan),
    }[direction]
    if 0 <= row < table.rows and 0 <= column < table.columns:
        return cell_at(table, row, column)
    return None


def cell_position(cell: GridCell) -> str:
    """Where the cell is and what it spans, as Edit Table names its text field."""
    label = _("Row {row}, column {column}").format(row=cell.row + 1, column=cell.column + 1)
    if cell.header:
        label += ", " + _("header")
    if cell.rowspan > 1 or cell.colspan > 1:
        rows = ngettext("{count} row", "{count} rows", cell.rowspan).format(count=cell.rowspan)
        columns = ngettext("{count} column", "{count} columns", cell.colspan).format(count=cell.colspan)
        label += ", " + _("spans {rows} and {columns}").format(rows=rows, columns=columns)
    return label
