from __future__ import annotations

import io
import unittest
import zipfile

from mathessible.documents.grid_tables import expand_grid_tables, parse_grid_table
from mathessible.documents.html_export import markdown_parser, render_markdown

# As Pandoc 3.13 writes a pasted table: a header over two columns, a cell over two rows, paragraphs and a
# list in cells.
MERGED = """\
+---------------------------------------------------+-----------------------+
| Group                                             | Value                 |
+=========================+=========================+=======================+
| A                       | First paragraph         | - x                   |
|                         |                         | - y                   |
|                         | Second                  |                       |
|                         +-------------------------+-----------------------+
|                         | b                       | 42                    |
+-------------------------+-------------------------+-----------------------+"""

# Pandoc does not escape `|` in a cell, and pads a wide character as two columns.
PLAIN = """\
+-----------------+-----------------+
| 中文            | x               |
+=================+=================+
| a | b           | $|x|$           |
+-----------------+-----------------+"""


def _html(source: str) -> str:
    return markdown_parser(native_lists=True).render(expand_grid_tables(source))


class GridTableTests(unittest.TestCase):
    def test_spans_header_and_blocks(self) -> None:
        table = parse_grid_table(MERGED.split("\n"))
        self.assertEqual((table.rows, table.columns), (3, 3))
        spans = {(cell.row, cell.column): (cell.rowspan, cell.colspan, cell.header) for cell in table.cells}
        self.assertEqual(spans[0, 0], (1, 2, True))
        self.assertEqual(spans[1, 0], (2, 1, False))
        self.assertEqual(
            next(cell for cell in table.cells if cell.row == 1 and cell.column == 1).content,
            "First paragraph\n\nSecond",
        )
        html = _html(MERGED)
        self.assertIn('<th colspan="2">Group</th>', html)
        self.assertIn('<td rowspan="2">A</td>', html)
        self.assertIn("<p>First paragraph</p>\n<p>Second</p>", html)
        self.assertIn("<li>x</li>", html)
        self.assertIn("<thead>", html)

    def test_pipes_and_wide_characters_by_columns(self) -> None:
        html = _html(PLAIN)
        self.assertIn("<th>中文</th>", html)
        self.assertIn("<td>a | b</td>", html)
        self.assertNotIn("rowspan", html)

    def test_equations_in_cells_are_found(self) -> None:
        html = render_markdown(PLAIN, lambda source: f"<math><mi>{source}</mi></math>")
        self.assertIn("<mi>|x|</mi>", html)

    def test_invalid_grids_and_code_stay_as_written(self) -> None:
        broken = MERGED.replace("| b                       |", "| b                        |")
        self.assertEqual(expand_grid_tables(broken), broken)
        fenced = "```\n" + PLAIN + "\n```"
        self.assertEqual(expand_grid_tables(fenced), fenced)
        self.assertIsNone(parse_grid_table(["+--+", "|a |"]))

    def test_word_pdf_and_braille_write_cell_blocks(self) -> None:
        import typst

        from mathessible.documents.brf_export import _blocks
        from mathessible.documents.docx_export import DocxOptions, docx_document
        from mathessible.documents.html_export import ExportPage
        from mathessible.documents.pdf_export import PdfOptions, pdf_inputs, typst_document

        pages = [ExportPage("Table", MERGED)]
        data = docx_document(pages, "Table", lambda _: None, DocxOptions())
        xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode()
        self.assertIn('w:gridSpan w:val="2"', xml)
        self.assertIn('w:vMerge w:val="restart"', xml)
        self.assertIn("Second", xml)
        self.assertIn('w:pStyle w:val="ListBullet"', xml)
        source = typst_document(pages, "Table", lambda _: (None, ""), PdfOptions())
        self.assertIn("table.header(table.cell(x: 0, y: 0, colspan: 2, rowspan: 1)[Group]", source)
        self.assertIn("First paragraph\n\nSecond", source)
        self.assertIn("- x\n\n- y", source)
        self.assertTrue(typst.compile(source.encode(), sys_inputs=pdf_inputs(pages)).startswith(b"%PDF"))
        rows = [block.cells for block in _blocks(MERGED, lambda text: text, lambda text: text)]
        self.assertIn("First paragraph; Second", rows[1])
        self.assertIn("• x; • y", rows[1])
        self.assertIn("spans 2 rows and 1 columns: A", rows[1])

    def test_a_cells_list_does_not_leak_into_the_document(self) -> None:
        from mathessible.documents.brf_export import _blocks

        blocks = _blocks(MERGED + "\n\nAfter the table.", lambda text: text, lambda text: text)
        self.assertEqual(blocks[-1].cells, "After the table.")
