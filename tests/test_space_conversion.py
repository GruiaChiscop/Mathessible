import unittest

from matex.space_conversion import convert_on_space


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


if __name__ == "__main__":
    unittest.main()
