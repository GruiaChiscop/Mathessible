import unittest

from converter_harness import convert_all, needs_node
from mathessible.editing.space_tidy import caret_after_tidy, tidy_spaces


@needs_node
class TidySpacesTests(unittest.TestCase):
    def tidy(self, source: str) -> str:
        cache: dict[str, str] = {}

        def convert(text: str) -> str:
            if text not in cache:
                cache[text] = convert_all([text])[0]["mathml"]
            return cache[text]

        return tidy_spaces(source, convert)[0]

    def test_spaces_that_change_nothing_go(self) -> None:
        self.assertEqual(self.tidy("a^b^c  "), "a^b^c")  # The two that built the chain.
        self.assertEqual(self.tidy("x + y = 1"), "x+y=1")
        self.assertEqual(self.tidy(" x"), "x")

    def test_a_space_that_ends_an_operand_or_a_control_word_stays(self) -> None:
        self.assertEqual(self.tidy("a_1 b"), "a_1 b")  # Else b joins the subscript.
        self.assertEqual(self.tidy("(1)/(2) x"), "(1)/(2) x")  # Else x joins the denominator.
        self.assertEqual(self.tidy("\\alpha b"), "\\alpha b")

    def test_a_space_after_a_word_stays_for_reading(self) -> None:
        # The converter reads `sinx` the same; the linear view would read one word.
        self.assertEqual(self.tidy("sin x"), "sin x")
        self.assertEqual(self.tidy("sin  x"), "sin x")
        self.assertEqual(self.tidy("x\\cdot ln \\begin x\\end "), "x\\cdot ln \\begin x\\end")

    def test_a_normal_text_keeps_its_spaces(self) -> None:
        self.assertEqual(self.tidy('"for all "x > 0'), '"for all "x>0')


class CaretTests(unittest.TestCase):
    def test_the_caret_moves_back_over_removed_spaces(self) -> None:
        self.assertEqual(caret_after_tidy(9, (1, 3, 9)), 7)
        self.assertEqual(caret_after_tidy(2, (1, 3, 9)), 1)


if __name__ == "__main__":
    unittest.main()
