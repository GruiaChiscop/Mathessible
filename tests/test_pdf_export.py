import unittest

import typst

from mathessible.documents.html_export import ExportPage
from mathessible.documents.pdf_export import PdfOptions, escape_markup, pdf_inputs, typst_document
from mathessible.documents.typst_math import TypstEquation

DOCUMENT = """# Roots

The roots of $ax^2+bx+c=0$ are *given* by **this**, see [here](https://example.com) and `code`:

$$x=(-b±√(b^2-4ac))/(2a)$$

- one $a$
  1. nested <b> #1 $ @ = - + / ~ _ * " ' \\\\ [x]
- two

| a | b |
|---|---|
| 1 | $x$ |

> quoted
"""


def equation_of(source: str) -> tuple[TypstEquation | None, str]:
    if source == "x":
        return None, ""  # One that does not build.
    return TypstEquation("y", "(1)" if "2a" in source else None), f"said {source}"


class PdfExportTests(unittest.TestCase):
    pages = [ExportPage("Roots", DOCUMENT)]

    def source(self, **options: object) -> str:
        return typst_document(self.pages, "Roots", equation_of, PdfOptions(**options))

    def test_equations_carry_their_spoken_form_and_number(self) -> None:
        source = self.source()
        self.assertIn('#math.equation(alt: "said ax^2+bx+c=0", $y$)', source)
        self.assertIn(
            '#math.equation(block: true, alt: "said x=(-b±√(b^2-4ac))/(2a)", numbering: _ => "(1)", $y$)', source
        )
        self.assertIn('[#raw("x")]', source)  # Its source, as code, in the table.

    def test_markdown_structure(self) -> None:
        source = self.source()
        for expected in (
            "= Roots",
            "#emph[given]",
            "#strong[this]",
            '#link("https://example.com")[here]',
            '#raw("code")',
            "- one",
            "  + nested",
            "table.header([a], [b])",
            "#quote(block: true)[",
        ):
            self.assertIn(expected, source)

    def test_text_is_never_typst_code(self) -> None:
        self.assertEqual(escape_markup('#1 $ @ = <b> "'), '\\#1 \\$ \\@ \\= \\<b\\> \\"')
        self.assertIn("\\<b\\> \\#1 \\$ \\@", self.source())

    def test_settings_reach_the_preamble(self) -> None:
        source = self.source(
            paper="us-letter",
            landscape=True,
            margins_mm=(10, 20, 30, 40),
            font_size=12,
            justify=True,
            page_numbers=False,
            header="Draft",
            author="A. B.",
            keywords=("algebra",),
            language="ro",
            table_of_contents=True,
        )
        for expected in (
            'paper: "us-letter", flipped: true, margin: (top: 10mm, right: 20mm, bottom: 30mm, left: 40mm)',
            'lang: "ro"',
            "size: 12pt",
            "justify: true",
            'header: align(right, "Draft")',
            'author: "A. B."',
            'keywords: ("algebra", )',
            "#outline()",
        ):
            self.assertIn(expected, source)
        self.assertNotIn('numbering: "1"', source)

    def test_stage_2_options(self) -> None:
        source = self.source(
            watermark="DRAFT",
            equation_numbering="(1)",
            heading_numbering="1.1",
            heading_colour="#1F4E79",
            link_colour="not a colour",
            columns=2,
        )
        for expected in (
            'background: rotate(-45deg, text(64pt, fill: luma(88%), "DRAFT"))',
            "columns: 2",
            '#set math.equation(numbering: "(1)")',
            '#set heading(numbering: "1.1")',
            '#show heading: set text(fill: rgb("#1F4E79"))',
        ):
            self.assertIn(expected, source)
        self.assertNotIn("show link", source)  # Only a colour like #1F4E79 is written.
        typst.compile(source.encode(), sys_inputs=pdf_inputs(self.pages), pdf_standards=["ua-1"])

    def test_typst_compiles_it_as_pdf_ua_1_with_the_source_attached(self) -> None:
        pdf = typst.compile(
            self.source(standards=("ua-1",)).encode(), sys_inputs=pdf_inputs(self.pages), pdf_standards=["ua-1"]
        )
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn(b"Roots.md", pdf)

    def test_pdf_ua_1_with_pdf_a_3a_keeps_the_attachment(self) -> None:
        standards = ["ua-1", "a-3a"]
        pdf = typst.compile(self.source().encode(), sys_inputs=pdf_inputs(self.pages), pdf_standards=standards)
        self.assertIn(b"Roots.md", pdf)


if __name__ == "__main__":
    unittest.main()
