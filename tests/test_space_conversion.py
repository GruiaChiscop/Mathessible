import unittest

from matex.space_conversion import (
    convert_before_character,
    convert_on_space,
    convert_shortcut_on_character,
    convert_word_before,
    split_autocorrect,
)


class SpaceConversionTests(unittest.TestCase):
    def test_converts_arrow_alias_without_inserting_space(self) -> None:
        edit = convert_on_space("a=>", 3)
        self.assertEqual(edit.source, "a⇒")
        self.assertEqual(edit.caret, 2)
        self.assertEqual(edit.announcement, "⇒")
        self.assertTrue(edit.converted)

    def test_converts_backslash_command(self) -> None:
        edit = convert_on_space(r"\alpha+1", 6)
        self.assertEqual(edit.source, "α+1")
        self.assertEqual(edit.caret, 1)

    def test_converts_control_word_typed_after_other_text(self) -> None:
        edit = convert_on_space(r"2\pi", 4)
        self.assertEqual(edit.source, "2π")
        self.assertEqual(edit.caret, 2)

    def test_uses_the_converter_table_when_given(self) -> None:
        edit = convert_on_space(r"f\circ", 6, control_words={"circ": "∘"})
        self.assertEqual(edit.source, "f∘")
        self.assertTrue(edit.converted)

    def test_unknown_or_unfinished_control_word_inserts_space(self) -> None:
        edit = convert_on_space(r"\cir", 4, control_words={"circ": "∘"})
        self.assertEqual(edit.source, "\\cir ")
        self.assertFalse(edit.converted)

    def test_naryand_marker_drops_the_spaces_before_it(self) -> None:
        # The converter rejects "∫_-1^1 ▒x"; "∫_-1^1▒x" is the integral.
        edit = convert_on_space("∫_-1^1 \\of", 10, control_words={"of": "▒"})
        self.assertEqual(edit.source, "∫_-1^1▒")
        self.assertEqual(edit.caret, 7)

    def test_other_control_words_keep_the_spaces_before_them(self) -> None:
        edit = convert_on_space("a \\circ", 7, control_words={"circ": "∘"})
        self.assertEqual(edit.source, "a ∘")

    def test_punctuation_after_a_control_word_converts_and_is_kept(self) -> None:
        edit = convert_before_character("\\int", 4, "_", control_words={"int": "∫"})
        self.assertEqual(edit.source, "∫_")
        self.assertEqual(edit.caret, 2)
        self.assertEqual(edit.announcement, "∫")

    def test_letters_digits_and_spaces_do_not_trigger_on_typing(self) -> None:
        for character in ("a", "2", " "):
            with self.subTest(character=character):
                self.assertIsNone(convert_before_character("\\int", 4, character, control_words={"int": "∫"}))

    def test_typing_after_a_shortcut_or_unknown_word_does_not_convert(self) -> None:
        self.assertIsNone(convert_before_character("a->", 3, "(", control_words={}))
        self.assertIsNone(convert_before_character("\\cir", 4, "+", control_words={"circ": "∘"}))

    def test_typing_converts_in_the_middle_of_the_source(self) -> None:
        edit = convert_before_character("\\alpha=1", 6, "+", control_words={"alpha": "α"})
        self.assertEqual((edit.source, edit.caret), ("α+=1", 2))

    def test_shortcut_converts_when_its_last_character_is_typed(self) -> None:
        edit = convert_shortcut_on_character("a<", 2, "<")
        self.assertEqual((edit.source, edit.caret, edit.announcement), ("a≪", 2, "≪"))

    def test_a_longer_shortcut_extends_an_already_converted_one(self) -> None:
        self.assertEqual(convert_shortcut_on_character("x←", 2, ">").source, "x↔")
        self.assertEqual(convert_shortcut_on_character("≤", 1, ">").source, "⇔")

    def test_three_dots_become_an_ellipsis(self) -> None:
        self.assertIsNone(convert_shortcut_on_character("x.", 2, "."))
        self.assertEqual(convert_shortcut_on_character("x..", 3, ".").source, "x…")

    def test_a_character_that_completes_no_shortcut_is_left_alone(self) -> None:
        self.assertIsNone(convert_shortcut_on_character("a", 1, "<"))
        self.assertIsNone(convert_shortcut_on_character("x", 1, "-"))

    def test_inserts_space_when_no_conversion_matches(self) -> None:
        edit = convert_on_space("x+1", 3)
        self.assertEqual(edit.source, "x+1 ")
        self.assertEqual(edit.caret, 4)
        self.assertEqual(edit.announcement, "space")
        self.assertFalse(edit.converted)

    def test_setting_can_disable_conversion(self) -> None:
        edit = convert_on_space("=>", 2, enabled=False)
        self.assertEqual(edit.source, "=> ")
        self.assertEqual(edit.caret, 3)
        self.assertFalse(edit.converted)


    def test_liminf_and_limsup_take_the_converters_spelling(self) -> None:
        # "lim inf" with a no-break space is the converter's function name.
        edit = convert_before_character("x+liminf", 8, "_")
        self.assertEqual((edit.source, edit.caret), ("x+lim\u00a0inf_", 10))
        self.assertEqual(convert_before_character("limsup", 6, "_").source, "lim\u00a0sup_")
        self.assertIsNone(convert_before_character("xliminf", 7, "_"))  # Part of a longer word.
        self.assertIsNone(convert_before_character("\\liminf", 7, "_"))


    def test_a_control_word_before_the_caret_converts_with_nothing_typed(self) -> None:
        # Tab leaving "lim_(x→\\infty|)" converts the word first, as Space would.
        edit = convert_word_before("lim_(x→\\infty)", 13, control_words={"infty": "∞"})
        self.assertEqual((edit.source, edit.caret, edit.announcement), ("lim_(x→∞)", 8, "∞"))
        self.assertIsNone(convert_word_before("lim_(x→\\inf)", 11, control_words={"infty": "∞"}))
        self.assertIsNone(convert_word_before("x+1", 3, control_words={"infty": "∞"}))
        self.assertIsNone(convert_word_before("\\infty", 6, enabled=False, control_words={"infty": "∞"}))


    def test_user_entries_split_into_control_words_and_shortcuts(self) -> None:
        words, shortcuts = split_autocorrect((("\\R", "ℝ"), ("deg", "°"), ("+-", "±")))
        self.assertEqual(words, {"R": "ℝ"})
        self.assertEqual(shortcuts, {"deg": "°", "+-": "±"})
        edit = convert_before_character("x∈\\R", 4, ",", control_words={"R": "ℝ"})
        self.assertEqual(edit.source, "x∈ℝ,")

    def test_user_shortcuts_convert_on_space_as_whole_words(self) -> None:
        self.assertEqual(convert_on_space("90deg", 5, shortcuts={"deg": "°"}).source, "90deg ")  # Not after a letter or digit.
        self.assertEqual(convert_on_space("90 deg", 6, shortcuts={"deg": "°"}).source, "90 °")
        self.assertEqual(convert_on_space("x~~", 3, shortcuts={"~~": "≈"}).source, "x≈")


if __name__ == "__main__":
    unittest.main()
