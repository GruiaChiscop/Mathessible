import unittest

from mathessible.documents.find_text import FindOptions, find, is_match, replace_all

TEXT = "The roots of $x^2=1$ are x=1 and x=-1. Roots, rooted."


class FindTests(unittest.TestCase):
    def test_the_next_match_wraps_around(self) -> None:
        self.assertEqual(find(TEXT, "roots", 0), (4, 9))
        self.assertEqual(find(TEXT, "roots", 5), (39, 44))
        self.assertEqual(find(TEXT, "roots", 45), (4, 9))  # Wrapped to the start.
        self.assertIsNone(find(TEXT, "cube", 0))
        self.assertIsNone(find(TEXT, "", 0))

    def test_the_previous_match_wraps_around(self) -> None:
        self.assertEqual(find(TEXT, "roots", 39, forward=False), (4, 9))
        self.assertEqual(find(TEXT, "roots", 4, forward=False), (39, 44))

    def test_case_and_whole_words(self) -> None:
        self.assertEqual(find(TEXT, "Roots", 0, options=FindOptions(match_case=True)), (39, 44))
        self.assertEqual(find(TEXT, "root", 0, options=FindOptions(whole_word=True)), None)
        self.assertEqual(find(TEXT, "x", 15, options=FindOptions(whole_word=True)), (25, 26))

    def test_equations_are_searched_as_their_source(self) -> None:
        self.assertEqual(find(TEXT, "x^2", 0), (14, 17))


class ReplaceTests(unittest.TestCase):
    def test_replace_needs_the_selection_to_be_a_match(self) -> None:
        self.assertTrue(is_match("Roots", "roots"))
        self.assertFalse(is_match("Roots", "roots", FindOptions(match_case=True)))
        self.assertFalse(is_match("Roots,", "roots"))
        self.assertFalse(is_match("", ""))

    def test_every_match_is_replaced_and_counted(self) -> None:
        self.assertEqual(replace_all("a+b, A+B", "a", "c"), ("c+b, c+B", 2))
        self.assertEqual(replace_all("a+b, A+B", "a", "c", FindOptions(match_case=True)), ("c+b, A+B", 1))
        self.assertEqual(replace_all(r"x\y", "x", r"\1"), (r"\1\y", 1))  # The replacement is literal.
        self.assertEqual(replace_all("abc", "", "z"), ("abc", 0))


if __name__ == "__main__":
    unittest.main()
