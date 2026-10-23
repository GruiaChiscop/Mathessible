"""Tables: cell navigation (Command+Option+arrows), rows as lines (Up/Down), cells read alone."""

from __future__ import annotations

from matex.editing.source_map import leaf_nodes
from matex.mathcat.common import _CELL_STEPS, _clean_speech, _table_names
from matex.mathcat.mathml_model import MathMLDocument, MathMLNode


class TableNavigationMixin:
    """Methods of `MathCatNavigator` (mathcat.py); relies on its state."""

    __slots__ = ()

    def matrix_location(self) -> tuple[int, int, int] | None:
        """(matrix index in reading order, row, column) of the current cell."""
        position = self.current_table_position
        if position is None or position.table_id is None or self.structure is None:
            return None
        index = self.structure.table_index(position.table_id)
        return None if index is None else (index, position.row, position.column)

    def move_to_cell(self, index: int, row: int, column: int) -> bool:
        if self.structure is None:
            return False
        target = self.structure.cell_target(index, row, column)
        if target is None:
            return False
        self._boundary_stop = None
        self._linear_index = None
        self._go_to(target)
        return True

    def read_line(self, step: int) -> str:
        """Up/Down as in a text field: the previous (-1) or next (1) row of the table the cursor is in, read whole.

        A row is a matrix row, an equation of an equation array, a case.
        The cursor goes to the end of the same column in it. At the first or
        last row, and outside any table (one line), the current line is read
        again without moving.
        """
        if self.structure is None:
            return ""
        position = self.current_table_position
        table = self.structure.node(position.table_id) if position is not None and position.table_id else None
        if position is None or table is None:
            return _clean_speech(self._native.speak_expression())
        rows = [child for child in table.children if child.tag == "mtr"]
        target = position.row + step if 1 <= position.row + step <= len(rows) else position.row
        row = rows[target - 1]
        cells = [child for child in row.children if child.tag == "mtd"]
        if row.identifier is None or not cells:
            return _clean_speech(self._native.speak_expression())
        self._go_to(row.identifier)
        speech = self._navigate("ReadCurrent")
        self._move_to_cell_end(cells[min(position.column, len(cells)) - 1])
        return speech

    def _move_to_cell_end(self, cell: MathMLNode) -> None:
        """Put the cursor on a cell's last leaf: typing goes on at the end of its content.

        Not on the cell's content as a whole (an `mrow` such as `x>0`):
        that is no linear stop, so neither stepping nor typing knew where
        they were.
        """
        assert self.structure is not None
        inside = [
            leaf
            for leaf in leaf_nodes(self.structure)
            if any(ancestor is cell for ancestor in self.structure.ancestors(leaf.identifier or ""))
        ]
        target = inside[-1].identifier if inside else MathMLDocument._cell_target(cell)
        if target:
            self.move_to(target)

    def table_command(self, command: str) -> str:
        """Command+Option+arrows (Ctrl+Alt elsewhere): the cells of the innermost table.

        Matrices, cases (Left/Right between value and condition, Up/Down
        between cases) and equation arrays alike, from MateX's own
        structure: MathCAT's cell commands took the cases for one column,
        and left the cursor on the cell's content as a whole. The cursor
        lands at the end of the cell (`_move_to_cell_end`); MathCAT reads
        the cell. `MoveColumnStart`/`MoveColumnEnd` go to the first/last
        row, `ReadCellCurrent` reads where it is without moving.
        """
        if self.structure is None:
            return ""
        position = self.current_table_position
        table = self.structure.node(position.table_id) if position is not None and position.table_id else None
        if position is None or table is None:
            # Outside every table: into the nearest one's first cell.
            target = self.structure.nearest_first_cell(self.current_id)
            entered = self.structure.table_position(target) if target is not None else None
            table = self.structure.node(entered.table_id) if entered is not None and entered.table_id else None
            if table is None:
                return "not in a table"
            return self._go_to_cell(table, 1, 1, vertical=True)
        rows = [child for child in table.children if child.tag == "mtr"]
        row, column = position.row, position.column
        if command == "ReadCellCurrent":
            return self._cell_speech(table, row, column, vertical=True, move=False)
        if command in ("MoveColumnStart", "MoveColumnEnd"):
            return self._go_to_cell(table, 1 if command == "MoveColumnStart" else len(rows), column, vertical=True)
        row_step, column_step = _CELL_STEPS.get(command, (0, 0))
        boundary = self._boundary_stop
        if command == "MoveCellNext" and boundary is not None and boundary.speech.startswith("start"):
            # On "start of math"/"start matrix" the cursor is before this cell: enter it first.
            return self._go_to_cell(table, row, column, vertical=True)
        names = _table_names(self.structure.table_kind(table))
        if row_step:
            if not 1 <= row + row_step <= len(rows):
                return f"no {'next' if row_step > 0 else 'previous'} {names[0]}"
            return self._go_to_cell(table, row + row_step, column, vertical=True)
        cells = [child for child in rows[row - 1].children if child.tag == "mtd"]
        if not 1 <= column + column_step <= len(cells):
            return f"no {'next' if column_step > 0 else 'previous'} {names[1]}"
        return self._go_to_cell(table, row, column + column_step, vertical=False)

    def _go_to_cell(self, table: MathMLNode, row: int, column: int, vertical: bool) -> str:
        return self._cell_speech(table, row, column, vertical, move=True)

    def _cell_speech(self, table: MathMLNode, row: int, column: int, vertical: bool, move: bool) -> str:
        """Read a cell ("row 2, column 1; 3", "case 1, condition; x > 0") and, with `move`, go to its end."""
        assert self.structure is not None
        rows = [child for child in table.children if child.tag == "mtr"]
        cells = [child for child in rows[row - 1].children if child.tag == "mtd"]
        column = min(column, len(cells))
        cell = cells[column - 1]
        kind = self.structure.table_kind(table)
        row_name, _column_name = _table_names(kind)
        column_label = ("value", "condition")[column - 1] if kind == "cases" and len(cells) == 2 else f"column {column}"
        previous = self.current_id
        content_id = MathMLDocument._cell_target(cell)
        content_node = self.structure.node(content_id) if content_id else None
        content = ""
        if content_node is not None and (content_node.children or content_node.text.strip("\u00a0 ")):
            # Never on an empty cell: in cases MathCAT fails on one ("no speech generated").
            self._go_to(content_id)
            content = self._navigate("ReadCurrent").strip()
        if move:
            self._move_to_cell_end(cell)
        else:
            self._go_to(previous)
        content = content or "empty"
        if not vertical:
            return f"{column_label}; {content}"
        if len(cells) == 1:
            return f"{row_name} {row}; {content}"
        return f"{row_name} {row}, {column_label}; {content}"
