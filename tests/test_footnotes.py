import unittest

from mathessible.documents.footnotes import counterpart, insert_footnote, next_label, notes, references
from mathessible.documents.markdown_math import find_math_zones, with_marks

SOURCE = """Roots[^1] of $x^[^2]$ and `[^3]`, again[^1].

[^1]: The first note,
    which runs on.

[^long]: Another.
"""


class FootnoteTests(unittest.TestCase):
    def test_references_and_notes_but_not_in_code_or_equations(self) -> None:
        self.assertEqual([reference.label for reference in references(SOURCE)], ["1", "1"])
        found = notes(SOURCE)
        self.assertEqual([note.label for note in found], ["1", "long"])
        self.assertEqual(SOURCE[found[0].text_start : found[0].end], "The first note,\n    which runs on.")

    def test_the_next_label_follows_the_highest_number(self) -> None:
        self.assertEqual(next_label(SOURCE), "2")
        self.assertEqual(next_label("No notes."), "1")

    def test_insert_footnote_puts_the_reference_at_the_caret_and_the_note_at_the_end(self) -> None:
        source, caret, label = insert_footnote("Roots here.\n\n", 5)
        self.assertEqual(source, "Roots[^1] here.\n\n[^1]: ")
        self.assertEqual((caret, label), (len(source), "1"))
        self.assertEqual(insert_footnote("", 0)[0], "[^1]\n\n[^1]: ")

    def test_counterpart_goes_from_a_reference_to_its_note_and_back(self) -> None:
        note_text = SOURCE.index("The first")
        self.assertEqual(counterpart(SOURCE, SOURCE.index("[^1]") + 2), (note_text, "1", True))
        self.assertEqual(counterpart(SOURCE, note_text + 5), (SOURCE.index("[^1]") + 4, "1", False))
        self.assertIsNone(counterpart(SOURCE, SOURCE.index("[^long]")))  # No reference to it.
        self.assertIsNone(counterpart(SOURCE, 2))

    def test_a_display_equation_in_a_note_stays_in_the_note(self) -> None:
        source = "Text[^a].\n\n[^a]: See\n$$y$$\n\n$$z$$\n"
        marked = with_marks(source, find_math_zones(source), lambda index: f"<{index}>")
        self.assertEqual(marked, "Text[^a].\n\n[^a]: See\n<0>\n\n\n\n<1>\n\n\n")


if __name__ == "__main__":
    unittest.main()
