from __future__ import annotations

import unittest

from mathessible.documents.html_export import markdown_parser
from mathessible.documents.pasted_html import markdown_from_html


class MergedTableTests(unittest.TestCase):
    def test_braille_describes_the_merge(self) -> None:
        from mathessible.documents.brf_export import _blocks

        blocks = _blocks("```table\n| Group | > |\n|---|---|\n```", lambda text: text, lambda text: text)
        self.assertIn("spans 1 rows and 2 columns: Group", blocks[0].cells)

    def test_paste_preserves_a_rectangle(self) -> None:
        source = markdown_from_html(
            '<table><tr><td rowspan="2" colspan="2">Group</td><td>A</td></tr><tr><td>B</td></tr></table>'
        )
        html = markdown_parser().render(source)
        self.assertIn('colspan="2"', html)
        self.assertIn('rowspan="2"', html)
        self.assertEqual(html.count("Group"), 1)
        cells = [token.meta["table_cell"] for token in markdown_parser().parse(source) if "table_cell" in token.meta]
        self.assertEqual(cells[-1]["x"], 2)
        self.assertEqual(cells[-1]["y"], 1)

    def test_ordinary_tables_and_literal_markers_are_unchanged(self) -> None:
        html = markdown_parser().render("| A | B |\n|---|---|\n| ^ | |")
        self.assertNotIn("rowspan", html)
        self.assertIn("^", html)

    def test_invalid_merge_remains_visible_source(self) -> None:
        html = markdown_parser().render("```table\n| > | A |\n|---|---|\n```")
        self.assertIn("<code", html)

    def test_extra_cells_are_not_silently_discarded(self) -> None:
        html = markdown_parser().render("```table\n| A | B |\n|---|---|\n| C | D | IMPORTANT |\n```")
        self.assertIn("<code", html)
        self.assertIn("IMPORTANT", html)

    def test_nonrectangular_merge_remains_source(self) -> None:
        html = markdown_parser().render("```table\n| A | > |\n|---|---|\n| ^ | B |\n```")
        self.assertIn("<code", html)

    def test_literal_markers_survive_rich_paste(self) -> None:
        source = markdown_from_html(
            '<table><tr><td colspan="2">Group</td></tr><tr><td>^</td><td>&gt;</td></tr></table>'
        )
        html = markdown_parser().render(source)
        self.assertIn("<td>^</td>", html)
        self.assertIn("<td>&gt;</td>", html)
        self.assertNotIn("rowspan", html)

    def test_column_alignment_survives_parsing(self) -> None:
        html = markdown_parser().render("```table\n| A | > |\n|:---|---:|\n| B | C |\n```")
        self.assertIn("text-align:right", html)

    def test_word_and_pdf_preserve_spans(self) -> None:
        import io
        import zipfile

        import typst

        from mathessible.documents.docx_export import DocxOptions, docx_document
        from mathessible.documents.html_export import ExportPage
        from mathessible.documents.pdf_export import PdfOptions, pdf_inputs, typst_document

        source = "```table\n| Group | > | A |\n|---|---|---|\n| ^ | ^ | B |\n```"
        pages = [ExportPage("Table", source)]
        data = docx_document(pages, "Table", lambda _: None, DocxOptions())
        xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode()
        self.assertIn('w:gridSpan w:val="2"', xml)
        self.assertIn('w:vMerge w:val="restart"', xml)
        pdf_source = typst_document(pages, "Table", lambda _: (None, ""), PdfOptions())
        self.assertIn("colspan: 2, rowspan: 2", pdf_source)
        self.assertTrue(typst.compile(pdf_source.encode(), sys_inputs=pdf_inputs(pages)).startswith(b"%PDF"))
