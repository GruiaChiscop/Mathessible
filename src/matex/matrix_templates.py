"""Matrix templates and row/column editing, as pure source rewriting."""

from __future__ import annotations

from dataclasses import dataclass

from .template_source import TemplateEdit, insert_template, matching_parens


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
_CLOSING_FENCES = {"(": ")", "[": "]", "|": "|"}


@dataclass(frozen=True, slots=True)
class MatrixCell:
    start: int
    end: int
    row: int
    column: int
    matrix_open: int
    matrix_close: int


def insert_matrix_template(source: str, caret: int, rows: int, columns: int, fence: str = "parentheses") -> TemplateEdit:
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
    label = "determinant" if fence == "bars" else "matrix"
    return insert_template(
        source,
        caret,
        f"{opening}■({body}){closing}",
        first_slot_offset=len(opening) + 2,
        announcement=f"{rows} by {columns} {label} template, empty cell, row 1, column 1",
    )


@dataclass(frozen=True, slots=True)
class MatrixPosition:
    row: int
    column: int
    rows: int
    columns: int
    # Which matrix, counting every `■(` in source order from 0 — the same
    # order as the `mtable`s in the converter's MathML.
    index: int


def matrix_position_at(source: str, caret: int) -> MatrixPosition | None:
    """Where the caret sits in the innermost matrix around it, if any."""
    found = _matrix_at(source, caret)
    if found is None:
        return None
    cell, grid = found
    index = _matrix_opens(source).index(cell.matrix_open)
    return MatrixPosition(cell.row, cell.column, len(grid), max(len(row) for row in grid), index)


def matrix_count(source: str) -> int:
    return len(_matrix_opens(source))


def matrix_cell_caret(source: str, index: int, row: int, column: int) -> int | None:
    """A caret inside a matrix cell given by matrix index and 1-based row/column.

    A row shorter than `column` (rows may be ragged) gives its last cell.
    """
    opens = _matrix_opens(source)
    if not 0 <= index < len(opens):
        return None
    in_row = [cell for cell in matrix_cells(source) if cell.matrix_open == opens[index] and cell.row == row]
    if not in_row:
        return None
    return in_row[min(column, len(in_row)) - 1].start


def _matrix_opens(source: str) -> list[int]:
    return sorted({cell.matrix_open for cell in matrix_cells(source)})


def insert_matrix_row(source: str, caret: int, below: bool = True) -> TemplateEdit | None:
    found = _matrix_at(source, caret)
    if found is None:
        return None
    cell, grid = found
    index = cell.row if below else cell.row - 1
    grid.insert(index, [""] * max(len(row) for row in grid))
    return _rebuild_matrix(source, cell, grid, index, cell.column - 1, f"inserted row {index + 1}")


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
    return _rebuild_matrix(source, cell, grid, cell.row - 1, index, f"inserted column {index + 1}")


def delete_matrix_row(source: str, caret: int) -> TemplateEdit | None:
    """Remove the caret's row; None if it is the only one (delete the matrix instead)."""
    found = _matrix_at(source, caret)
    if found is None or len(found[1]) < 2:
        return None
    cell, grid = found
    del grid[cell.row - 1]
    row = min(cell.row - 1, len(grid) - 1)
    return _rebuild_matrix(source, cell, grid, row, cell.column - 1, f"deleted row {cell.row}")


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
    return _rebuild_matrix(source, cell, grid, cell.row - 1, cell.column - 1, f"deleted column {cell.column}")


def _matrix_at(source: str, caret: int) -> tuple[MatrixCell, list[list[str]]] | None:
    """The innermost cell around the caret, plus its matrix as a grid of cell texts."""
    caret = max(0, min(caret, len(source)))
    cells = matrix_cells(source)
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
    content = "" if grid[row][column] else "empty cell, "
    return TemplateEdit(
        edited,
        caret,
        f"{action}, {len(grid)} by {columns} {label}, {content}row {row + 1}, column {column + 1}",
    )


def matrix_label(source: str, cell: MatrixCell) -> str:
    symbol, after_matrix = cell.matrix_open - 1, cell.matrix_close + 1
    is_determinant = symbol > 0 and after_matrix < len(source) and source[symbol - 1] == source[after_matrix] == "|"
    return "determinant" if is_determinant else "matrix"


def past_fence(source: str, start: int, end: int) -> int:
    if start > 0 and end < len(source) and _CLOSING_FENCES.get(source[start - 1]) == source[end]:
        return end + 1
    return end


def matrix_cells(source: str) -> list[MatrixCell]:
    """Every cell of every `■(...)` in the source, nested matrices included.

    `&`/`@` only separate cells at the matrix's own depth: anything inside a
    nested "(...)" (a fraction slot, an inner matrix) is skipped as a whole.
    """
    pairs = matching_parens(source)
    cells: list[MatrixCell] = []
    for matrix_open, matrix_close in sorted(pairs.items()):
        if matrix_open == 0 or source[matrix_open - 1] != "■":
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
