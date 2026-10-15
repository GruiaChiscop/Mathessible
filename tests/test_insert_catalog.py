import unittest

from matex.insert_catalog import all_items, item_for_key


class InsertCatalogTests(unittest.TestCase):
    def test_every_shortcut_is_unique(self) -> None:
        shortcuts = [(item.key, item.modifier, item.shift) for item in all_items() if item.key]
        self.assertEqual(len(shortcuts), len(set(shortcuts)))

    def test_keys_find_their_entries(self) -> None:
        self.assertEqual(item_for_key("/", "command", False).label, "&Fraction")
        self.assertEqual(item_for_key("=", "command", False).label, "&Subscript")
        self.assertEqual(item_for_key("+", "command", True).label, "Su&perscript")
        self.assertEqual(item_for_key("r", "variant", False).label, "&Root with Index")
        self.assertEqual(item_for_key("|", "command", True).label, "&Absolute Value")

    def test_shift_is_required_where_the_plain_key_belongs_to_the_frame(self) -> None:
        # Command+O is File > Open, Command+M is Minimize.
        self.assertIsNone(item_for_key("O", "command", False))
        self.assertIsNone(item_for_key("M", "command", False))
        self.assertIsNone(item_for_key("M", "command", True).insert)

    def test_accelerators_name_the_platform_modifier(self) -> None:
        root = item_for_key("R", "variant", False)
        self.assertEqual(root.accelerator(mac=True), "RawCtrl+R")
        self.assertEqual(root.accelerator(mac=False), "Alt+R")
        self.assertEqual(item_for_key("O", "command", True).accelerator(mac=True), "Ctrl+Shift+O")

    def test_entries_insert_their_template(self) -> None:
        edit = item_for_key("L", "command", False).insert("", 0)
        self.assertEqual(edit.source, "lim_() ")
        equals = next(item for item in all_items() if "Equals" in item.label)
        self.assertEqual(equals.insert("", 0).source, "=┴() ")


if __name__ == "__main__":
    unittest.main()
