import unittest

from mathessible.documents.brf_export import (
    BLANK,
    BrfLayout,
    ascii_braille,
    braille_lines,
    brf_pages,
    nemeth_in_ueb,
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
        self.assertEqual(brf_pages([["⠁", "⠃", "⠉" + BLANK]], layout), "A\r\nB\r\n\fC\r\n\f")

    def test_the_page_number_ends_the_last_line_three_blanks_after_the_text(self) -> None:
        layout = BrfLayout(cells_per_line=10, lines_per_page=3)
        number = letters  # "#" + digits, as a table writes them, in the stand-in.
        self.assertEqual(
            brf_pages([[letters("one"), letters("two"), letters("three"), letters("four")]], layout, number).split(
                "\f"
            ),
            ["ONE\r\nTWO\r\nTHREE    1\r\n", "FOUR\r\n\r\n         2\r\n", ""],
        )

    def test_a_last_line_with_no_room_for_the_number_moves_on(self) -> None:
        layout = BrfLayout(cells_per_line=10, lines_per_page=2)
        pages = brf_pages([[letters("one"), letters("seventeen")]], layout, letters).split("\f")
        self.assertEqual(pages[:2], ["ONE\r\n         1\r\n", "SEVENTEEN\r\n         2\r\n"])

    def test_each_notebook_page_starts_a_braille_page_and_numbers_go_on(self) -> None:
        layout = BrfLayout(cells_per_line=20, lines_per_page=4)
        brf = notebook_brf([ExportPage("One", "a"), ExportPage("Two", "b")], letters, math, layout)
        self.assertEqual(
            brf,
            "        ONE\r\n\r\n  A\r\n                   1\r\n\f        TWO\r\n\r\n  B\r\n                   2\r\n\f",
        )
        self.assertNotIn("1", notebook_brf([ExportPage("One", "a")], letters, math, layout, page_numbers=False))


class NemethInUebTests(unittest.TestCase):
    def test_the_switch_indicators_and_their_spaces(self) -> None:
        self.assertEqual(ascii_braille(nemeth_in_ueb(letters("x"))), "_% X _:")


if __name__ == "__main__":
    unittest.main()
