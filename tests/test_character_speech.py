import unittest

from matex.editing.character_speech import (
    character_name,
    deleted_character,
    inserted_character,
    name_unknown_symbols,
)


class CharacterSpeechTests(unittest.TestCase):
    def test_space_and_punctuation_have_spoken_names(self) -> None:
        self.assertEqual(character_name(" "), "space")
        self.assertEqual(character_name("("), "left parenthesis")
        self.assertEqual(character_name(")"), "right parenthesis")
        self.assertEqual(character_name("/"), "slash")
        self.assertEqual(character_name("^"), "caret")

    def test_math_symbols_have_spoken_names(self) -> None:
        self.assertEqual(character_name("∞"), "infinity")
        self.assertEqual(character_name("≤"), "less than or equal to")
        self.assertEqual(character_name("⇒"), "implies")
        self.assertEqual(character_name("∫"), "integral")

    def test_letters_fall_back_to_themselves(self) -> None:
        self.assertEqual(character_name("x"), "x")
        self.assertEqual(inserted_character("x"), "x")

    def test_deleted_character_uses_spoken_name(self) -> None:
        self.assertEqual(deleted_character(" "), "deleted space")
        self.assertEqual(deleted_character("/"), "deleted slash")


class UnknownSymbolTests(unittest.TestCase):
    def test_a_symbol_nothing_named_is_said_by_its_unicode_name(self) -> None:
        self.assertEqual(name_unknown_symbols("x plus 🜁"), "x plus alchemical symbol for air")
        self.assertEqual(name_unknown_symbols("deleted ⟁"), "deleted white triangle containing small white triangle")

    def test_letters_punctuation_and_named_speech_stay_as_they_are(self) -> None:
        for speech in ("x plus ș", "x plus 中", "la . sa se", "x plus 1", "x plus \ue000"):
            self.assertEqual(name_unknown_symbols(speech), speech)


if __name__ == "__main__":
    unittest.main()
