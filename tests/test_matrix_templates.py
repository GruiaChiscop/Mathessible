import unittest

from matex.matrix_templates import (
    MatrixPosition,
    delete_matrix_column,
    delete_matrix_row,
    insert_matrix_column,
    insert_matrix_row,
    insert_matrix_template,
    matrix_cell_caret,
    matrix_count,
    matrix_position_at,
)


class MatrixTemplateTests(unittest.TestCase):
    def test_matrix_template_has_empty_cells_and_caret_in_the_first(self) -> None:
        edit = insert_matrix_template("A=", 2, rows=2, columns=3)
        self.assertEqual(edit.source, "A=(■(&&@&&))")
        self.assertEqual(edit.caret, 5)
        self.assertEqual(edit.announcement, "2 by 3 matrix template, empty cell, row 1, column 1")

    def test_matrix_template_fences(self) -> None:
        self.assertEqual(insert_matrix_template("", 0, 2, 2, fence="none").source, "■(&@&)")
        self.assertEqual(insert_matrix_template("", 0, 2, 2, fence="brackets").source, "[■(&@&)]")
        determinant = insert_matrix_template("", 0, 2, 2, fence="bars")
        self.assertEqual(determinant.source, "|■(&@&)|")
        self.assertEqual(determinant.announcement, "2 by 2 determinant template, empty cell, row 1, column 1")

    def test_matrix_template_rejects_bad_sizes_and_fences(self) -> None:
        with self.assertRaises(ValueError):
            insert_matrix_template("", 0, 0, 2)
        with self.assertRaises(ValueError):
            insert_matrix_template("", 0, 2, 11)
        with self.assertRaises(ValueError):
            insert_matrix_template("", 0, 2, 2, fence="double bars")

    def test_matrix_position_reports_the_caret_cell_and_shape(self) -> None:
        # "(■(a&b@c&d))": "d" is at index 9.
        self.assertEqual(matrix_position_at("(■(a&b@c&d))", 9), MatrixPosition(2, 2, 2, 2, 0))
        self.assertIsNone(matrix_position_at("x+(■(a&b))", 1))

    def test_matrix_position_uses_the_innermost_matrix(self) -> None:
        source = "■(■(x&y@z&w)&b)"
        self.assertEqual(matrix_position_at(source, 4), MatrixPosition(1, 1, 2, 2, 1))
        self.assertEqual(matrix_position_at(source, 14), MatrixPosition(1, 2, 1, 2, 0))

    def test_insert_row_below_and_above(self) -> None:
        below = insert_matrix_row("(■(a&b@c&d))", 3, below=True)
        self.assertIsNotNone(below)
        self.assertEqual(below.source, "(■(a&b@&@c&d))")
        self.assertEqual(below.caret, 7)
        self.assertEqual(below.announcement, "inserted row 2, 3 by 2 matrix, empty cell, row 2, column 1")
        above = insert_matrix_row("(■(a&b@c&d))", 3, below=False)
        self.assertIsNotNone(above)
        self.assertEqual(above.source, "(■(&@a&b@c&d))")
        self.assertEqual(above.caret, 3)

    def test_insert_column_right_and_left_keeps_the_caret_row(self) -> None:
        right = insert_matrix_column("[■(a&b@c&d)]", 7, right=True)
        self.assertIsNotNone(right)
        self.assertEqual(right.source, "[■(a&&b@c&&d)]")
        self.assertEqual(right.caret, 10)
        self.assertEqual(right.announcement, "inserted column 2, 2 by 3 matrix, empty cell, row 2, column 2")
        left = insert_matrix_column("[■(a&b@c&d)]", 7, right=False)
        self.assertIsNotNone(left)
        self.assertEqual(left.source, "[■(&a&b@&c&d)]")

    def test_insert_column_pads_a_ragged_row(self) -> None:
        edit = insert_matrix_column("■(a&b&c@d)", 6, right=True)
        self.assertIsNotNone(edit)
        self.assertEqual(edit.source, "■(a&b&c&@d&&&)")

    def test_delete_row_and_column(self) -> None:
        row = delete_matrix_row("(■(a&b@c&d))", 9)
        self.assertIsNotNone(row)
        self.assertEqual(row.source, "(■(a&b))")
        self.assertEqual(row.caret, 5)
        self.assertEqual(row.announcement, "deleted row 2, 1 by 2 matrix, row 1, column 2")
        column = delete_matrix_column("|■(a&b@c&d)|", 3)
        self.assertIsNotNone(column)
        self.assertEqual(column.source, "|■(b@d)|")
        self.assertEqual(column.caret, 3)
        self.assertEqual(column.announcement, "deleted column 1, 2 by 1 determinant, row 1, column 1")

    def test_the_last_row_or_column_cannot_be_deleted(self) -> None:
        self.assertIsNone(delete_matrix_row("■(a&b)", 2))
        self.assertIsNone(delete_matrix_column("■(a@b)", 2))
        self.assertIsNone(insert_matrix_row("a+b", 1))

    def test_editing_a_nested_matrix_leaves_the_outer_one_alone(self) -> None:
        edit = insert_matrix_row("■(■(x&y)&b)", 4)
        self.assertIsNotNone(edit)
        self.assertEqual(edit.source, "■(■(x&y@&)&b)")

    def test_cells_with_nested_groups_are_kept_whole(self) -> None:
        edit = delete_matrix_column("■((a)/(b)&c)", 10)
        self.assertIsNotNone(edit)
        self.assertEqual(edit.source, "■((a)/(b))")

    def test_matrix_cells_are_found_by_matrix_index_row_and_column(self) -> None:
        source = "[■(1&2@3&4)]+■(■(x&y@z)&b)"
        self.assertEqual(matrix_count(source), 3)
        self.assertEqual(matrix_cell_caret(source, 0, 2, 2), 9)
        self.assertEqual(matrix_cell_caret(source, 2, 2, 1), 21)
        # A short row gives its last cell; a missing matrix or row gives None.
        self.assertEqual(matrix_cell_caret(source, 2, 2, 2), 21)
        self.assertIsNone(matrix_cell_caret(source, 3, 1, 1))
        self.assertIsNone(matrix_cell_caret(source, 0, 3, 1))
        self.assertEqual(matrix_position_at(source, 21), MatrixPosition(2, 1, 2, 2, 2))


if __name__ == "__main__":
    unittest.main()
