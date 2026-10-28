import unittest

from mathessible.editing.source_lines import line_at, line_step

ROWS = "a &= b \\\\\n  c &= d + 1 \\\\\n  e"


class SourceLinesTests(unittest.TestCase):
    def test_the_line_the_caret_is_on(self) -> None:
        self.assertEqual(line_at(ROWS, 0), "a &= b \\\\")
        self.assertEqual(line_at(ROWS, ROWS.index("c")), "  c &= d + 1 \\\\")
        self.assertEqual(line_at(ROWS, len(ROWS)), "  e")

    def test_up_and_down_keep_the_column_where_they_can(self) -> None:
        down = line_step(ROWS, 3, 1)
        self.assertEqual(down, ROWS.index("c") + 1)
        self.assertEqual(line_step(ROWS, down, -1), 3)
        self.assertEqual(line_step(ROWS, ROWS.index("+"), 1), len(ROWS))  # The short last line's end.

    def test_no_line_before_the_first_or_after_the_last(self) -> None:
        self.assertIsNone(line_step(ROWS, 2, -1))
        self.assertIsNone(line_step(ROWS, len(ROWS), 1))


if __name__ == "__main__":
    unittest.main()
