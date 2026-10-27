"""Matrix templates and row/column editing, as pure source rewriting."""

from __future__ import annotations

from dataclasses import dataclass

from mathessible.i18n import spoken, spoken_n
from mathessible.templates.template_source import TemplateEdit, insert_template, matching_parens

MAX_MATRIX_SIZE = 10
# Fence name -> (opening, closing) characters wrapped around the bare `■(...)`.
# Only fences the real converter groups cleanly are offered: `(`/`[` give an
# `intent=":fenced"` mrow and `|` a `determinant($a)` one, but `‖` comes back
# as two loose `<mo>`s around the table, so it is deliberately left out.
MATRIX_FENCES = {
    "none": ("", ""),
    "parentheses": ("(", ")"),
    "brackets": ("[", "]"),
    "bars": ("|", "|"),
}
_CLOSING_FENCES = {"(": ")", "[": "]", "|": "|", "{": "┤"}
# Every source construct that becomes an `mtable`: matrices (cases are one,
# `{■(...)┤`) and equation arrays. In source order they are the MathML's
# tables in order, which is how professional view finds its cell's source.
MATRIX_SIGNS = "■"
TABLE_SIGNS = "■█"


@dataclass(frozen=True, slots=True)
class MatrixCell:
    start: int
    end: int
    row: int
    column: int
    matrix_open: int
    matrix_close: int


def insert_matrix_template(
    source: str, caret: int, rows: int, columns: int, fence: str = "parentheses"
) -> TemplateEdit:
    """Insert a rows x columns matrix with every cell empty, caret in the first.

    Cells are left genuinely empty (`■(&@&)`) rather than filled with "()"
    placeholders: the real converter keeps "()" inside an `mtd` as visible
    parens (an `intent=":fenced"` mrow), while an empty cell becomes a plain
    zero-width `mspace` and is not flagged as a parse error. Empty cells are
    found as Tab-able slots by `matrix_cells`, not by the "()" scan.
    """
    if not (1 <= rows <= MAX_MATRIX_SIZE and 1 <= columns <= MAX_MATRIX_SIZE):
        raise ValueError(f"matrix size must be between 1 and {MAX_MATRIX_SIZE} in each direction")
    try:
        opening, closing = MATRIX_FENCES[fence]
    except KeyError:
        raise ValueError(f"unknown matrix fence: {fence}") from None
    body = "@".join("&" * (columns - 1) for _row in range(rows))
    if fence == "bars":
        announcement = spoken("{rows} by {columns} determinant template, empty cell, row 1, column 1")
    else:
        announcement = spoken("{rows} by {columns} matrix template, empty cell, row 1, column 1")
    return insert_template(
        source,
        caret,
        f"{opening}■({body}){closing}",
        first_slot_offset=len(opening) + 2,
        announcement=announcement.format(rows=rows, columns=columns),
    )


@dataclass(frozen=True, slots=True)
class MatrixPosition:
    row: int
    column: int
    rows: int
    columns: int
    # Which table, counting every `signs` table in source order from 0 —
    # with TABLE_SIGNS, the same order as the `mtable`s in the MathML.
    index: int
    # "matrix", "determinant", "cases" or "equations" (an equation array).
    kind: str = "matrix"


def matrix_position_at(source: str, caret: int, signs: str = MATRIX_SIGNS) -> MatrixPosition | None:
    """Where the caret sits in the innermost matrix (or, with TABLE_SIGNS, any table) around it."""
    found = _matrix_at(source, caret, signs)
    if found is None:
        return None
    cell, grid = found
    index = _matrix_opens(source, signs).index(cell.matrix_open)
    columns = max(len(row) for row in grid)
    return MatrixPosition(cell.row, cell.column, len(grid), columns, index, table_kind(source, cell))


def table_position_at(source: str, caret: int) -> MatrixPosition | None:
    """`matrix_position_at` over every table: equation arrays too."""
    return matrix_position_at(source, caret, TABLE_SIGNS)


def matrix_count(source: str, signs: str = MATRIX_SIGNS) -> int:
    return len(_matrix_opens(source, signs))


def matrix_cell_caret(source: str, index: int, row: int, column: int, signs: str = MATRIX_SIGNS) -> int | None:
    """A caret inside a matrix cell given by matrix index and 1-based row/column.

    A row shorter than `column` (rows may be ragged) gives its last cell.
    """
    opens = _matrix_opens(source, signs)
    if not 0 <= index < len(opens):
        return None
    cells = matrix_cells(source, signs)
    in_row = [cell for cell in cells if cell.matrix_open == opens[index] and cell.row == row]
    if not in_row:
        return None
    return in_row[min(column, len(in_row)) - 1].start


def _matrix_opens(source: str, signs: str = MATRIX_SIGNS) -> list[int]:
    return sorted({cell.matrix_open for cell in matrix_cells(source, signs)})


def insert_matrix_row(source: str, caret: int, below: bool = True) -> TemplateEdit | None:
    found = _matrix_at(source, caret)
    if found is None:
        return None
    cell, grid = found
    index = cell.row if below else cell.row - 1
    grid.insert(index, [""] * max(len(row) for row in grid))
    return _rebuild_matrix(
        source, cell, grid, index, cell.column - 1, spoken("inserted row {row}").format(row=index + 1)
    )


def insert_matrix_column(source: str, caret: int, right: bool = True) -> TemplateEdit | None:
    found = _matrix_at(source, caret)
    if found is None:
        return None
    cell, grid = found
    index = cell.column if right else cell.column - 1
    for row in grid:
        # Rows may be ragged in UnicodeMath; pad a short one with empty cells
        # so the new column lands at the same position in every row.
        row.extend([""] * (index - len(row)))
        row.insert(index, "")
    return _rebuild_matrix(
        source, cell, grid, cell.row - 1, index, spoken("inserted column {column}").format(column=index + 1)
    )


def delete_matrix_row(source: str, caret: int) -> TemplateEdit | None:
    """Remove the caret's row; None if it is the only one (delete the matrix instead)."""
    found = _matrix_at(source, caret)
    if found is None or len(found[1]) < 2:
        return None
    cell, grid = found
    del grid[cell.row - 1]
    row = min(cell.row - 1, len(grid) - 1)
    return _rebuild_matrix(source, cell, grid, row, cell.column - 1, spoken("deleted row {row}").format(row=cell.row))


def delete_matrix_column(source: str, caret: int) -> TemplateEdit | None:
    """Remove the caret's column; None if it is the only one."""
    found = _matrix_at(source, caret)
    if found is None or max(len(row) for row in found[1]) < 2:
        return None
    cell, grid = found
    for row in grid:
        if len(row) >= cell.column:
            del row[cell.column - 1]
    # A ragged row that only had the deleted cell still needs one empty cell.
    grid = [row or [""] for row in grid]
    return _rebuild_matrix(
        source, cell, grid, cell.row - 1, cell.column - 1, spoken("deleted column {column}").format(column=cell.column)
    )


def insert_table_row(source: str, caret: int, below: bool = True) -> TemplateEdit | None:
    """A new row in the innermost table: an equation (equation array), a case, or a matrix row."""
    found = _matrix_at(source, caret, TABLE_SIGNS)
    if found is None:
        return None
    cell, grid = found
    kind = table_kind(source, cell)
    index = cell.row if below else cell.row - 1
    # An equation's "&" only aligns it: a new one starts as a single empty line.
    grid.insert(index, [""] if kind == "equations" else [""] * max(len(row) for row in grid))
    if kind not in _ROW_NAMES:
        return _rebuild_matrix(
            source, cell, grid, index, cell.column - 1, spoken("inserted row {row}").format(row=index + 1)
        )
    edit = _rebuild_matrix(source, cell, grid, index, 0, "")
    if kind == "cases":
        announcement = spoken("inserted case {number}, {count}, empty value, case {number}")
    else:
        announcement = spoken("inserted equation {number}, {count}, empty equation {number}")
    count = _count(len(grid), kind)
    return TemplateEdit(edit.source, edit.caret, announcement.format(number=index + 1, count=count))


def delete_table_row(source: str, caret: int) -> TemplateEdit | None:
    """Remove the caret's row of the innermost table; None if it is the only one."""
    found = _matrix_at(source, caret, TABLE_SIGNS)
    if found is None or len(found[1]) < 2:
        return None
    cell, grid = found
    kind = table_kind(source, cell)
    del grid[cell.row - 1]
    row = min(cell.row - 1, len(grid) - 1)
    if kind not in _ROW_NAMES:
        return _rebuild_matrix(
            source, cell, grid, row, cell.column - 1, spoken("deleted row {row}").format(row=cell.row)
        )
    edit = _rebuild_matrix(source, cell, grid, row, 0, "")
    if kind == "cases":
        announcement = spoken("deleted case {number}, {count}, case {current}")
    else:
        announcement = spoken("deleted equation {number}, {count}, equation {current}")
    count = _count(len(grid), kind)
    return TemplateEdit(edit.source, edit.caret, announcement.format(number=cell.row, count=count, current=row + 1))


_ROW_NAMES = {"equations": "equation", "cases": "case"}


def _count(count: int, kind: str) -> str:
    if kind == "cases":
        return spoken_n("{count} case", "{count} cases", count).format(count=count)
    return spoken_n("{count} equation", "{count} equations", count).format(count=count)


def table_kind(source: str, cell: MatrixCell) -> str:
    """ "equations" for an equation array `█(...)`, else `matrix_label`."""
    if cell.matrix_open > 0 and source[cell.matrix_open - 1] == "█":
        return "equations"
    return matrix_label(source, cell)


def _matrix_at(source: str, caret: int, signs: str = MATRIX_SIGNS) -> tuple[MatrixCell, list[list[str]]] | None:
    """The innermost cell around the caret, plus its matrix as a grid of cell texts."""
    caret = max(0, min(caret, len(source)))
    cells = matrix_cells(source, signs)
    around = [cell for cell in cells if cell.start <= caret <= cell.end]
    if not around:
        return None
    # A nested matrix opens after the outer one, so the innermost is the latest.
    cell = max(around, key=lambda candidate: candidate.matrix_open)
    grid: list[list[str]] = []
    for other in cells:
        if other.matrix_open != cell.matrix_open:
            continue
        if other.row > len(grid):
            grid.append([])
        grid[-1].append(source[other.start : other.end])
    return cell, grid


def _rebuild_matrix(
    source: str, cell: MatrixCell, grid: list[list[str]], row: int, column: int, action: str
) -> TemplateEdit:
    """Write the grid back as the matrix body, caret at the start of (row, column).

    The column is clamped to the target row's length, since rows may be ragged.
    """
    column = min(column, len(grid[row]) - 1)
    body = ""
    caret = cell.matrix_open + 1
    for row_index, cells in enumerate(grid):
        if row_index:
            body += "@"
        for column_index, text in enumerate(cells):
            if column_index:
                body += "&"
            if (row_index, column_index) == (row, column):
                caret = cell.matrix_open + 1 + len(body)
            body += text
    edited = source[: cell.matrix_open + 1] + body + source[cell.matrix_close :]
    label = matrix_label(source, cell)
    columns = max(len(cells) for cells in grid)
    parts = [action] if action else []
    parts.append(
        spoken("{rows} by {columns} {structure}").format(rows=len(grid), columns=columns, structure=spoken(label))
    )
    if not grid[row][column]:
        parts.append(spoken("empty cell"))
    parts.append(spoken("row {row}, column {column}").format(row=row + 1, column=column + 1))
    return TemplateEdit(edited, caret, ", ".join(parts))


def matrix_label(source: str, cell: MatrixCell) -> str:
    symbol, after_matrix = cell.matrix_open - 1, cell.matrix_close + 1
    is_determinant = symbol > 0 and after_matrix < len(source) and source[symbol - 1] == source[after_matrix] == "|"
    if symbol > 0 and source[symbol - 1] == "{" and source[after_matrix : after_matrix + 1] == "┤":
        return "cases"  # `{■(value&condition@...)┤`: a piecewise definition.
    return "determinant" if is_determinant else "matrix"


def past_fence(source: str, start: int, end: int) -> int:
    if start > 0 and end < len(source) and _CLOSING_FENCES.get(source[start - 1]) == source[end]:
        return end + 1
    return end


def matrix_cells(source: str, signs: str = MATRIX_SIGNS) -> list[MatrixCell]:
    """Every cell of every `■(...)` (or other `signs` table) in the source, nested ones included.

    `&`/`@` only separate cells at the matrix's own depth: anything inside a
    nested "(...)" (a fraction slot, an inner matrix) is skipped as a whole.
    """
    pairs = matching_parens(source)
    cells: list[MatrixCell] = []
    for matrix_open, matrix_close in sorted(pairs.items()):
        if matrix_open == 0 or source[matrix_open - 1] not in signs:
            continue
        row = column = 1
        start = index = matrix_open + 1
        while index < matrix_close:
            character = source[index]
            if character == "(" and index in pairs:
                index = pairs[index] + 1
                continue
            if character in "&@":
                cells.append(MatrixCell(start, index, row, column, matrix_open, matrix_close))
                if character == "&":
                    column += 1
                else:
                    row += 1
                    column = 1
                start = index + 1
            index += 1
        cells.append(MatrixCell(start, matrix_close, row, column, matrix_open, matrix_close))
    return cells
