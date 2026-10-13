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
