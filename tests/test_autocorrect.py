import unittest

from converter_harness import convert, needs_node
from matex.editing.autocorrect import (
    AutoCorrectTable,
    default_entries,
    differences,
    is_symbol_shortcut,
    math_alphabet_character,
    math_alphabet_entries,
)
from matex.editing.build_repair import literal_repair, literal_text, repairs
from matex.editing.space_conversion import convert_shortcut_on_character

DEFAULTS = {
    typed: symbol
    for typed, symbol in default_entries({"alpha": "α", "infty": "∞"}, {"->": "→", "<=": "≤"}).items()
    if typed in ("\\alpha", "\\infty", "->", "<=")
}


class AutoCorrectTableTests(unittest.TestCase):
    def test_defaults_and_user_entries_are_one_list(self) -> None:
        self.assertEqual(DEFAULTS, {"\\alpha": "α", "\\infty": "∞", "->": "→", "<=": "≤"})
        table = AutoCorrectTable(DEFAULTS, overrides=(("\\R", "ℝ"), ("->", "⟶")), removed=("\\alpha", "<="))
        self.assertEqual(table.control_words(), {"infty": "∞", "R": "ℝ"})
        self.assertEqual(table.shortcuts(), {"->": "⟶"})
        self.assertEqual(table.removed_words(), ("alpha",))

    def test_greek_capitals_the_converter_lacks_are_defaults(self) -> None:
        defaults = default_entries({"alpha": "α", "Delta": "Δ"}, {})
        self.assertEqual(defaults["\\Alpha"], "\u0391")  # Greek capital alpha, not Latin A.
        self.assertEqual(defaults["\\omicron"], "ο")
        self.assertEqual(defaults["\\Delta"], "Δ")
        self.assertEqual(default_entries({"Alpha": "𝐀"}, {})["\\Alpha"], "𝐀")  # The converter's own wins.

    def test_only_the_differences_are_saved(self) -> None:
        entries = dict(DEFAULTS)
        entries["\\R"] = "ℝ"
        entries["->"] = "⟶"
        del entries["\\alpha"]
        self.assertEqual(differences(DEFAULTS, entries), ((("->", "⟶"), ("\\R", "ℝ")), ("\\alpha",)))
        self.assertEqual(differences(DEFAULTS, dict(DEFAULTS)), ((), ()))  # Reset to defaults.

    def test_a_deleted_word_added_back_is_not_text(self) -> None:
        table = AutoCorrectTable(DEFAULTS, overrides=(("\\alpha", "ɑ"),), removed=("\\alpha",))
        self.assertEqual(table.removed_words(), ())
        self.assertEqual(table.control_words()["alpha"], "ɑ")

    def test_symbol_shortcuts(self) -> None:
        self.assertTrue(is_symbol_shortcut("->"))
        self.assertFalse(is_symbol_shortcut("deg"))
        self.assertFalse(is_symbol_shortcut("\\R"))


class MathAlphabetTests(unittest.TestCase):
    def test_unicode_names_give_the_letterlike_exceptions_too(self) -> None:
        self.assertEqual(math_alphabet_character("DOUBLE-STRUCK", "R"), "ℝ")  # U+211D, not in the math block.
        self.assertEqual(math_alphabet_character("DOUBLE-STRUCK", "k"), "\U0001d55c")
        self.assertEqual(math_alphabet_character("SCRIPT", "H"), "ℋ")
        self.assertEqual(math_alphabet_character("SCRIPT", "e"), "ℯ")
        self.assertEqual(math_alphabet_character("FRAKTUR", "C"), "ℭ")
        self.assertEqual(math_alphabet_character("DOUBLE-STRUCK", "1"), "𝟙")
        self.assertIsNone(math_alphabet_character("DOUBLE-STRUCK", "α"))

    def test_words_math_alphabet_entries_are_defaults(self) -> None:
        entries = math_alphabet_entries()
        self.assertEqual(entries["\\doubleC"], "ℂ")
        self.assertEqual(entries["\\frakturg"], "𝔤")
        self.assertEqual(entries["\\mathbb{N}"], "ℕ")
        self.assertEqual(len([typed for typed in entries if typed.startswith("\\mathbb{")]), 62)
        self.assertEqual(default_entries({}, {})["\\mathbb{Z}"], "ℤ")

    def test_mathbb_converts_when_its_brace_closes(self) -> None:
        shortcuts = AutoCorrectTable(default_entries({}, {})).shortcuts()
        edit = convert_shortcut_on_character("x∈\\mathbb{R", 11, "}", shortcuts)
        self.assertEqual((edit.source, edit.caret), ("x∈ℝ", 3))
        self.assertTrue(is_symbol_shortcut("\\mathbb{R}"))


class LiteralWordTests(unittest.TestCase):
    def test_a_deleted_word_is_quoted_and_broken_for_the_converter(self) -> None:
        repair = literal_repair("x+\\alpha+\\infty", ("alpha",))
        self.assertEqual(repair.text, 'x+"\\‌alpha"+\\infty')
        self.assertEqual((repair.to_real(3), repair.to_real(repair.text.index("+", 3))), (2, 8))
        self.assertEqual(literal_text(repair.text, ("alpha",)), repair.text)  # Idempotent.
        self.assertEqual(literal_text("\\alphabet", ("alpha",)), "\\alphabet")  # Another word.

    def test_every_build_candidate_keeps_the_word_as_text(self) -> None:
        for candidate in repairs("√(&\\alpha", literal=("alpha",)):
            self.assertIn('"\\‌alpha"', candidate.text)

    @needs_node
    def test_the_converter_shows_the_text_typed(self) -> None:
        mathml = convert(literal_text("x+\\alpha", ("alpha",)))
        self.assertIn("<mtext>\\\u200calpha</mtext>", mathml)
        self.assertNotIn("α", mathml)
