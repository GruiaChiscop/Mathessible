import unittest

from mathessible.editing.space_conversion import convert_in_text

WORDS = {"alpha": "α", "infty": "∞", "rightarrow": "→"}
SHORTCUTS = {"->": "→", "\\mathbb{R}": "ℝ", "deg": "°"}


def typed(source: str, character: str) -> str | None:
    result = convert_in_text(source, len(source), character, WORDS, SHORTCUTS)
    return None if result is None else result.source


class ConvertInTextTests(unittest.TestCase):
    """Word's Math AutoCorrect outside math regions: the delimiter converts and is kept."""

    def test_a_control_word_converts_on_space_punctuation_or_enter(self) -> None:
        self.assertEqual(typed("angle \\alpha", " "), "angle α ")
        self.assertEqual(typed("to \\infty", "."), "to ∞.")
        self.assertEqual(typed("(\\alpha", ")"), "(α)")
        self.assertEqual(typed("\\alpha", "\n"), "α\n")

    def test_shortcuts_too_and_letters_only_as_a_whole_word(self) -> None:
        self.assertEqual(typed("a ->", " "), "a → ")
        self.assertEqual(typed("in \\mathbb{R}", ","), "in ℝ,")
        self.assertEqual(typed("90deg", " "), None)
        self.assertEqual(typed("90 deg", " "), "90 ° ")

    def test_letters_digits_and_unknown_words_do_not_convert(self) -> None:
        self.assertIsNone(typed("\\alpha", "b"))
        self.assertIsNone(typed("\\alpha", "2"))
        self.assertIsNone(typed("\\alph", " "))
        self.assertIsNone(typed("\\alpha", "\\"))


if __name__ == "__main__":
    unittest.main()
