import unittest

import typst

from mathessible.documents.html_export import ExportPage
from mathessible.documents.pdf_export import PdfOptions, pdf_inputs, typst_document
from mathessible.documents.pdf_security import PdfSecurity, protect
from mathessible.documents.pdf_source import AttachedPage, PdfSourceError, attached_markdown
from mathessible.documents.typst_math import TypstEquation


def equation_of(source: str) -> tuple[TypstEquation | None, str]:
    return TypstEquation("x"), source


def exported(pages: list[ExportPage], **options: object) -> bytes:
    source = typst_document(pages, "Notebook", equation_of, PdfOptions(**options))
    return typst.compile(source.encode(), sys_inputs=pdf_inputs(pages))


class PdfSourceTests(unittest.TestCase):
    def test_a_document_comes_back_as_it_was_written(self) -> None:
        markdown = "---\nheader: Notes\n---\n# Roots\n\n$x$ and é[^1].\n\n[^1]: A note.\n"
        title, pages = attached_markdown(exported([ExportPage("Roots", markdown)], title="My roots"))
        self.assertEqual((title, pages), ("My roots", [AttachedPage("Notebook", markdown)]))

    def test_a_notebooks_pages_come_back_in_order_with_their_own_names(self) -> None:
        pages = [ExportPage("Zeta", "z"), ExportPage("Alpha", "a"), ExportPage("Zeta", "z again")]
        _title, found = attached_markdown(exported(pages))
        self.assertEqual(
            found, [AttachedPage("Zeta", "z"), AttachedPage("Alpha", "a"), AttachedPage("Zeta (2)", "z again")]
        )

    def test_a_permissions_password_is_no_obstacle_but_an_open_password_is(self) -> None:
        pdf = exported([ExportPage("A", "a")])
        restricted = protect(pdf, PdfSecurity("", "permissions", allow_copying=False))
        self.assertEqual(attached_markdown(restricted)[1][0].source, "a")
        with self.assertRaises(PdfSourceError):
            attached_markdown(protect(pdf, PdfSecurity("open")))

    def test_a_pdf_without_its_source_or_no_pdf_at_all(self) -> None:
        with self.assertRaises(PdfSourceError):
            attached_markdown(exported([ExportPage("A", "a")], attach_source=False))
        with self.assertRaises(PdfSourceError):
            attached_markdown(b"not a PDF")


if __name__ == "__main__":
    unittest.main()
