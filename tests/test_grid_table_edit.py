from __future__ import annotations

import unittest

from mathessible.documents.grid_tables import grid_table_at, header_row_count, parse_grid_table, write_grid_table
from mathessible.editing import document_insert
from mathessible.editing.grid_table_edit import (
    TableEditError,
    can_merge_down,
    can_merge_right,
    cell_at,
    cell_position,
    delete_column,
    delete_row,
    insert_column,
    insert_row,
    merge_down,
    merge_right,
    neighbour,
    new_table,
    split,
    with_content,
    with_header_rows,
)
from tests.test_grid_tables import MERGED, PLAIN


def _round_trip(table) -> None:
    """Every change must give a table that is written and read back the same."""
    assert parse_grid_table(write_grid_table(table).split("\n")) == table, write_grid_table(table)


class WriterTests(unittest.TestCase):
    def test_tables_are_read_back_as_written(self) -> None:
        for source in (MERGED, PLAIN):
            table = parse_grid_table(source.split("\n"))
            self.assertEqual(parse_grid_table(write_grid_table(table).split("\n")), table)
        empty = new_table(2, 3, header=True)
        self.assertEqual(parse_grid_table(write_grid_table(empty).split("\n")), empty)
        self.assertIn("+===+===+===+", write_grid_table(empty))

    def test_the_table_at_the_caret(self) -> None:
        source = "Before\n\n" + MERGED + "\n\nAfter"
        start, end, table = grid_table_at(source, source.index("Second"))
        self.assertEqual(source[start:end], MERGED)
        self.assertEqual(table.rows, 3)
        self.assertIsNone(grid_table_at(source, 2))
        self.assertIsNone(grid_table_at("```\n" + MERGED + "\n```", 10))

    def test_insert_table_can_write_a_grid(self) -> None:
        edit = document_insert.table("", 0, 0, 2, 2, True, False, grid=True)
        self.assertIsNotNone(grid_table_at(edit.source, edit.caret))
        self.assertEqual(edit.source[edit.caret - 2 : edit.caret], "| ")


class EditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.table = parse_grid_table(MERGED.split("\n"))

    def test_rows_and_columns_through_merged_cells(self) -> None:
        # Row 2 passes through the cell "A" (rows 1 and 2): it grows instead of being cut.
        grown = insert_row(self.table, 2)
        self.assertEqual((grown.rows, cell_at(grown, 1, 0).rowspan), (4, 3))
        self.assertEqual(cell_at(grown, 2, 1).content, "")
        shrunk = delete_row(self.table, 2)
        self.assertEqual((shrunk.rows, cell_at(shrunk, 1, 0).rowspan, cell_at(shrunk, 1, 0).content), (2, 1, "A"))
        wider = insert_column(self.table, 1)  # Through "Group" (columns 0 and 1).
        self.assertEqual((wider.columns, cell_at(wider, 0, 0).colspan), (4, 3))
        narrower = delete_column(self.table, 0)
        self.assertEqual((narrower.columns, cell_at(narrower, 0, 0).colspan), (2, 1))
        for table in (grown, shrunk, wider, narrower):
            _round_trip(table)
        with self.assertRaises(TableEditError):
            delete_row(new_table(1, 2, False), 0)

    def test_merge_and_split(self) -> None:
        b = cell_at(self.table, 2, 1)
        self.assertTrue(can_merge_right(self.table, b))
        self.assertFalse(can_merge_down(self.table, b))  # The last row.
        merged, cell = merge_right(self.table, b)
        self.assertEqual((cell.colspan, cell.content), (2, "b\n\n42"))
        _round_trip(merged)
        apart = split(merged, cell)
        self.assertEqual((cell_at(apart, 2, 1).content, cell_at(apart, 2, 2).content), ("b\n\n42", ""))
        _round_trip(apart)
        # "First paragraph" is one row tall; the cell to its right too, but "A" to its left spans two rows.
        self.assertFalse(can_merge_right(self.table, cell_at(self.table, 1, 0)))
        down, cell = merge_down(self.table, cell_at(self.table, 1, 1))
        self.assertEqual(cell.rowspan, 2)
        _round_trip(down)

    def test_header_and_content(self) -> None:
        self.assertEqual(header_row_count(self.table), 1)
        none = with_header_rows(self.table, 0)
        self.assertEqual(header_row_count(none), 0)
        self.assertNotIn("=", write_grid_table(none))
        with self.assertRaises(TableEditError):
            with_header_rows(self.table, 2)  # "A" spans rows 1 and 2.
        edited = with_content(self.table, cell_at(self.table, 2, 2), "x  \r\n\r\n- one\n")
        self.assertEqual(cell_at(edited, 2, 2).content, "x\n\n- one")
        _round_trip(edited)

    def test_labels(self) -> None:
        self.assertEqual(cell_position(cell_at(self.table, 0, 0)), "Row 1, column 1, header, spans 1 row and 2 columns")
        self.assertEqual(cell_position(cell_at(new_table(1, 1, False), 0, 0)), "Row 1, column 1")

    def test_neighbours(self) -> None:
        group = cell_at(self.table, 0, 0)  # Columns 0 and 1 of the header.
        self.assertEqual(neighbour(self.table, group, "right"), cell_at(self.table, 0, 2))
        self.assertIsNone(neighbour(self.table, group, "up"))
        self.assertIsNone(neighbour(self.table, group, "left"))
        a = cell_at(self.table, 1, 0)  # Rows 1 and 2.
        self.assertEqual(neighbour(self.table, a, "up"), group)
        self.assertIsNone(neighbour(self.table, a, "down"))
        self.assertEqual(neighbour(self.table, cell_at(self.table, 2, 1), "left"), a)

    def test_any_sequence_of_changes_stays_a_valid_grid(self) -> None:
        import random

        chooser = random.Random(28)
        table = self.table
        for _step in range(400):
            cell = chooser.choice(table.cells)
            operation = chooser.randrange(8)
            try:
                if operation == 0:
                    table = insert_row(table, chooser.randrange(table.rows + 1))
                elif operation == 1:
                    table = delete_row(table, chooser.randrange(table.rows))
                elif operation == 2:
                    table = insert_column(table, chooser.randrange(table.columns + 1))
                elif operation == 3:
                    table = delete_column(table, chooser.randrange(table.columns))
                elif operation == 4 and can_merge_right(table, cell):
                    table = merge_right(table, cell)[0]
                elif operation == 5 and can_merge_down(table, cell):
                    table = merge_down(table, cell)[0]
                elif operation == 6:
                    table = split(table, cell)
                else:
                    table = with_content(table, cell, chooser.choice(["", "x", "two\n\nparas", "- a\n- b", "中文 é"]))
            except TableEditError:
                continue
            if table.rows > 8 or table.columns > 8:
                table = self.table
            _round_trip(table)
            covered = sum(each.rowspan * each.colspan for each in table.cells)
            self.assertEqual(covered, table.rows * table.columns)
