import unittest

from matex.completion import Suggestion, accept_completion, completion_at, search_symbols, symbol_insertion

TABLE = {
    "alpha": "α",
    "aleph": "ℵ",
    "in": "∈",
    "inf": "∞",
    "infty": "∞",
    "int": "∫",
    "le": "≤",
    "leq": "≤",
    "rightarrow": "→",
}
NAMES = {"α": "alpha", "≤": "less than or equal to", "→": "right arrow", "∞": "infinity"}.get


class CompletionTests(unittest.TestCase):
    def test_offers_words_beginning_with_what_was_typed(self) -> None:
        completion = completion_at(r"x+\al", 5, TABLE)
        assert completion is not None
        self.assertEqual([s.word for s in completion.suggestions], ["aleph", "alpha"])
        self.assertEqual((completion.start, completion.end), (2, 5))

    def test_the_word_typed_so_far_comes_first(self) -> None:
        completion = completion_at(r"\in", 3, TABLE)
        assert completion is not None
        self.assertEqual([s.word for s in completion.suggestions], ["in", "inf", "infty", "int"])

    def test_nothing_without_a_letter_or_a_backslash(self) -> None:
        self.assertIsNone(completion_at("\\", 1, TABLE))
        self.assertIsNone(completion_at("al", 2, TABLE))
        self.assertIsNone(completion_at(r"\\al", 4, TABLE))

    def test_nothing_when_no_word_matches_or_it_is_complete(self) -> None:
        self.assertIsNone(completion_at(r"\xyz", 4, TABLE))
        self.assertIsNone(completion_at(r"\alpha", 6, TABLE))

    def test_browsing_wraps_and_speaks_the_position(self) -> None:
        completion = completion_at(r"\le", 3, TABLE)
        assert completion is not None
        self.assertEqual(completion.speech(NAMES), "le, less than or equal to, 1 of 2")
        self.assertEqual(completion.moved(1).current.word, "leq")
        self.assertEqual(completion.moved(-1).current.word, "leq")
        self.assertEqual(completion.moved(2).current.word, "le")

    def test_a_name_equal_to_the_word_is_not_repeated(self) -> None:
        self.assertEqual(Suggestion("alpha", "α").speech(NAMES), "alpha")

    def test_accepting_writes_the_symbol_or_the_word(self) -> None:
        completion = completion_at(r"2\al+1", 4, TABLE)
        assert completion is not None
        chosen = completion.moved(1)
        edit = accept_completion(r"2\al+1", chosen, convert=True)
        self.assertEqual((edit.source, edit.caret, edit.announcement), ("2α+1", 2, "alpha"))
        edit = accept_completion(r"2\al+1", chosen, convert=False)
        self.assertEqual((edit.source, edit.caret), (r"2\alpha+1", 7))


class SymbolSearchTests(unittest.TestCase):
    def test_word_start_before_inside_before_spoken_name(self) -> None:
        words = [s.word for s in search_symbols("in", TABLE, NAMES)]
        self.assertEqual(words[:4], ["in", "inf", "int", "infty"])
        self.assertIn("rightarrow", [s.word for s in search_symbols("arrow", TABLE, NAMES)])
        self.assertEqual([s.word for s in search_symbols("less", TABLE, NAMES)], ["le", "leq"])

    def test_by_symbol_and_with_a_backslash(self) -> None:
        self.assertEqual([s.word for s in search_symbols("≤", TABLE, NAMES)], ["le", "leq"])
        self.assertEqual([s.word for s in search_symbols(r"\alp", TABLE, NAMES)], ["alpha"])

    def test_empty_query_lists_everything(self) -> None:
        self.assertEqual(len(search_symbols("", TABLE)), len(TABLE))

    def test_label(self) -> None:
        self.assertEqual(Suggestion("le", "≤").label(NAMES), "\\le   ≤   less than or equal to")

    def test_inserting_a_symbol_or_its_control_word(self) -> None:
        alpha = Suggestion("alpha", "α")
        self.assertEqual(symbol_insertion("x+", 2, alpha, control_words=False).source, "x+α")
        edit = symbol_insertion("x+", 2, alpha, control_words=True)
        self.assertEqual((edit.source, edit.caret), ("x+\\alpha ", 9))
        self.assertEqual(symbol_insertion("x+y", 2, alpha, control_words=True).source, "x+\\alpha y")
        self.assertEqual(symbol_insertion("x+)", 2, alpha, control_words=True).source, "x+\\alpha)")


if __name__ == "__main__":
    unittest.main()
