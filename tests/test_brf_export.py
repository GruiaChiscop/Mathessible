import unittest

from mathessible.documents.brf_export import (
    BLANK,
    BrfLayout,
    ascii_braille,
    braille_lines,
    brf_pages,
    notebook_brf,
)
from mathessible.documents.html_export import ExportPage


def letters(text: str) -> str:
    """A stand-in for liblouis: each letter as the cell Braille ASCII writes it with, a space blank."""
    ascii_ = " A1B'K2L@CIF/MSP\"E3H9O6R^DJG>NTQ,*5<-U8V.%[$+X!&;:4\\0Z7(_?W]#Y)="
    return "".join(chr(0x2800 + ascii_.index(c.upper())) if c.upper() in ascii_ else "⠿" for c in text)


def math(source: str) -> str:
    return letters(f"[{source}]")


def shown(lines: list[str]) -> list[str]:
    return [ascii_braille(line) for line in lines]


class AsciiTests(unittest.TestCase):
    def test_cells_are_braille_ascii_without_dots_7_and_8(self) -> None:
        self.assertEqual(ascii_braille("⠁⠃⠉⠀⠼⠁"), "ABC #A")
        self.assertEqual(ascii_braille("⣁"), "A")  # Dots 7 and 8 dropped.


class LayoutTests(unittest.TestCase):
    layout = BrfLayout(cells_per_line=20, lines_per_page=4)

    def test_paragraphs_lists_headings_and_display_equations(self) -> None:
        source = "# Title\n\nSome words in a paragraph here.\n\n- one\n- two $x$\n\n$$a/b$$\n"
        bullet = ascii_braille(letters("•"))
        self.assertEqual(
            shown(braille_lines(source, letters, math, self.layout)),
            [
                "       TITLE",  # Centred.
                "",
                "  SOME WORDS IN A",  # Cell 3, runover to cell 1.
                "PARAGRAPH HERE.",
                "",
                f"{bullet} ONE",
                "",
                f"{bullet} TWO [X]",  # An inline equation in its line.
                "",
                "    [A/B]",  # A display equation in cell 5.
            ],
        )

    def test_a_word_longer_than_a_line_is_split_and_runs_over(self) -> None:
        lines = shown(braille_lines("x " + "a" * 25, letters, math, self.layout))
        self.assertEqual(lines, ["  X", "AAAAAAAAAAAAAAAAAAAA", "AAAAA"])
        self.assertTrue(all(len(line) <= 20 for line in lines))

    def test_code_keeps_its_lines(self) -> None:
        self.assertEqual(shown(braille_lines("```\na = 1\nb = 2\n```", letters, math, self.layout)), ["A = 1", "B = 2"])

    def test_a_table_row_is_one_block(self) -> None:
        lines = shown(braille_lines("| a | b |\n| - | - |\n| 1 | $x$ |", letters, math, self.layout))
        self.assertEqual(lines, ["A B", "", "1 [X]"])


class PageTests(unittest.TestCase):
    def test_pages_end_with_a_form_feed_and_lines_with_cr_lf(self) -> None:
        layout = BrfLayout(cells_per_line=10, lines_per_page=2)
        self.assertEqual(brf_pages(["⠁", "⠃", "⠉" + BLANK], layout), "A\r\nB\r\n\fC\r\n\f")

    def test_each_notebook_page_starts_a_braille_page(self) -> None:
        layout = BrfLayout(cells_per_line=20, lines_per_page=4)
        brf = notebook_brf([ExportPage("One", "a"), ExportPage("Two", "b")], letters, math, layout)
        self.assertEqual(brf, "        ONE\r\n\r\n  A\r\n\r\n\f        TWO\r\n\r\n  B\r\n\f")


if __name__ == "__main__":
    unittest.main()
