from __future__ import annotations

import random
import unittest
from dataclasses import replace

from mathessible.documents.grid_tables import header_row_count
from mathessible.documents.pipe_tables import editable_table_at, simplest_table
from mathessible.editing import document_insert
from mathessible.editing.grid_table_edit import (
    can_merge_down,
    can_merge_right,
    cell_at,
    delete_column,
    delete_row,
    insert_column,
    insert_row,
    merge_down,
    merge_right,
    split,
    with_content,
    with_header_rows,
)

PIPE = """Before.

| Name | Value |
| :--- | ---: |
| $|x|$ | a \\| b |
| `c|d` | 2 |

After."""

BLOCK = """```table
| Group | > | Value |
| --- | --- | --- |
| A | First | 1 |
| ^ | Second | \\> |
```"""


def _table(source: str, at: str):
    found = editable_table_at(source, source.index(at))
    assert found is not None
    return found


class ReadTests(unittest.TestCase):
    def test_a_pipe_table(self) -> None:
        start, end, table, kind = _table(PIPE, "Value")
        self.assertEqual(kind, "pipe")
        self.assertEqual(PIPE[start:end].splitlines()[0], "| Name | Value |")
        self.assertEqual(table.alignments, ("left", "right"))
        self.assertEqual(header_row_count(table), 1)
        # An equation's `|` stays in its cell, `\|` is a `|`; a code span is split as GitHub splits it.
        self.assertEqual(cell_at(table, 1, 0).content, "$|x|$")
        self.assertEqual(cell_at(table, 1, 1).content, "a | b")
        self.assertEqual((table.rows, table.columns), (3, 2))
        self.assertEqual(cell_at(table, 2, 1).content, "d`")
        self.assertIsNone(editable_table_at(PIPE, PIPE.index("Before")))

    def test_a_block_with_merged_cells(self) -> None:
        _, _, table, kind = _table(BLOCK, "Second")
        self.assertEqual(kind, "block")
        group, a = cell_at(table, 0, 0), cell_at(table, 1, 0)
        self.assertEqual((group.colspan, group.header, a.rowspan), (2, True, 2))
        self.assertEqual(cell_at(table, 2, 2).content, ">")  # `\>` is the character, not a join.
        bad = "```table\n| a | b |\n| --- | --- |\n| ^ | > |\n| x | ^ |\n```"
        self.assertIsNone(editable_table_at(bad, 3))  # "b" over two rows next to a join from "a": no rectangle.

    def test_an_empty_header_row_is_no_header(self) -> None:
        inserted = document_insert.table("", 0, 0, 2, 2, header=False, tex=False).source
        _, _, table, _ = _table(inserted, "|")
        self.assertEqual((header_row_count(table), table.rows), (0, 2))
        written = simplest_table(table)
        self.assertEqual(written.splitlines()[0], "|  |  |")  # The empty header row back.
        self.assertEqual(_table(written, "|")[2], table)

    def test_tables_in_code_are_not_tables(self) -> None:
        self.assertIsNone(editable_table_at("```\n| a |\n| --- |\n```", 6))
        self.assertIsNone(editable_table_at("A paragraph with a | in it.", 5))


class WriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipe = _table(PIPE, "Value")[2]

    def test_the_simplest_syntax(self) -> None:
        self.assertEqual(simplest_table(self.pipe).splitlines()[1], "| :--- | ---: |")
        self.assertIn("| $|x|$ | a \\| b |", simplest_table(self.pipe))  # Only the text's `|` escaped.
        simple = _table("| a | b |\n| --- | --- |\n| c |  |", "c")[2]
        merged, _ = merge_right(simple, cell_at(simple, 1, 0))
        self.assertEqual(simplest_table(merged), "```table\n| a | b |\n| --- | --- |\n| c | > |\n```")
        # A block splits every `|`: a merged table with `$|x|$` is a grid.
        merged, _ = merge_right(self.pipe, cell_at(self.pipe, 1, 0))
        self.assertTrue(simplest_table(merged).startswith("+"))
        two_lines = with_content(self.pipe, cell_at(self.pipe, 2, 1), "one\n\ntwo")
        self.assertTrue(simplest_table(two_lines).startswith("+"))
        two_headers = with_header_rows(self.pipe, 2)
        self.assertTrue(simplest_table(two_headers).startswith("+"))

    def test_alignments_follow_their_columns(self) -> None:
        wider = insert_column(self.pipe, 1)
        self.assertEqual(wider.alignments, ("left", "", "right"))
        self.assertEqual(delete_column(wider, 0).alignments, ("", "right"))
        self.assertIn("| :--- | --- | ---: |", simplest_table(wider))

    def test_any_sequence_of_changes_reads_back_as_written(self) -> None:
        generator = random.Random(29)
        source = "| h1 | h2 | h3 |\n| --- | :---: | --- |\n| a | b | c |\n| d | e | f |"
        table = _table(source, "a")[2]
        for step in range(300):
            cell = generator.choice(table.cells)
            choice = generator.randrange(9)
            if choice == 0:
                table = insert_row(table, generator.randrange(table.rows + 1))
            elif choice == 1 and table.rows > 1:
                table = delete_row(table, cell.row)
            elif choice == 2 and table.columns < 6:
                table = insert_column(table, generator.randrange(table.columns + 1))
            elif choice == 3 and table.columns > 1:
                table = delete_column(table, cell.column)
            elif choice == 4 and can_merge_right(table, cell):
                table, _ = merge_right(table, cell)
            elif choice == 5 and can_merge_down(table, cell):
                table, _ = merge_down(table, cell)
            elif choice == 6:
                table = split(table, cell)
            # Text in every cell (an empty header row reads as none), now and then a `|` or a join's sign.
            for each in table.cells:
                if not each.content:
                    table = with_content(table, each, generator.choice(["w", "x | y", ">", "^", "$|z|$"]) + str(step))
            written = simplest_table(table)
            found = editable_table_at(written, 0)
            self.assertIsNotNone(found, written)
            read, kind = found[2], found[3]
            expected = replace(table, alignments=()) if kind == "grid" else table
            self.assertEqual(read, expected, written)


if __name__ == "__main__":
    unittest.main()
