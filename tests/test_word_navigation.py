import unittest

from mathessible.editing.word_navigation import next_word_boundary, previous_word_boundary


class WordNavigationTests(unittest.TestCase):
    def test_next_boundary_stops_after_a_run_of_letters(self) -> None:
        self.assertEqual(next_word_boundary("alpha+beta", 0), 5)

    def test_next_boundary_treats_a_single_operator_as_its_own_word(self) -> None:
        self.assertEqual(next_word_boundary("alpha+beta", 5), 6)

    def test_next_boundary_skips_leading_space_then_consumes_the_next_word(self) -> None:
        self.assertEqual(next_word_boundary("a  bc", 1), 5)

    def test_next_boundary_saturates_at_the_end_of_the_source(self) -> None:
        self.assertEqual(next_word_boundary("abc", 3), 3)

    def test_previous_boundary_stops_before_a_run_of_letters(self) -> None:
        self.assertEqual(previous_word_boundary("alpha+beta", 10), 6)

    def test_previous_boundary_treats_a_single_operator_as_its_own_word(self) -> None:
        self.assertEqual(previous_word_boundary("alpha+beta", 6), 5)

    def test_previous_boundary_skips_trailing_space_before_the_previous_word(self) -> None:
        self.assertEqual(previous_word_boundary("ab  c", 4), 0)

    def test_previous_boundary_saturates_at_the_start_of_the_source(self) -> None:
        self.assertEqual(previous_word_boundary("abc", 0), 0)


if __name__ == "__main__":
    unittest.main()
