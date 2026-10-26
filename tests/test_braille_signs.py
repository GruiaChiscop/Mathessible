import tempfile
import unittest
from pathlib import Path

from mathessible.mathcat.navigator import MathCatNavigator
from mathessible.symbols.braille_signs import (
    cells_from_text,
    dots_of,
    format_signs,
    load_signs,
    parse_signs,
    save_signs,
    signs_yaml,
    symbol_from_text,
)


class SignTextTests(unittest.TestCase):
    def test_braille_is_typed_as_cells_or_dot_numbers(self) -> None:
        self.assertEqual(cells_from_text("⠈⠸⠣"), "⠈⠸⠣")
        self.assertEqual(cells_from_text("4-456-126"), "⠈⠸⠣")
        self.assertEqual(cells_from_text("4 456 126"), "⠈⠸⠣")
        self.assertEqual(cells_from_text("78"), "⣀")  # Eight-dot braille too.
        self.assertIsNone(cells_from_text("abc"))
        self.assertIsNone(cells_from_text("9"))

    def test_cells_read_back_as_dots(self) -> None:
        self.assertEqual(dots_of("⠈⠸⠣"), "4-456-126")

    def test_a_symbol_is_typed_as_itself_a_control_word_or_a_code(self) -> None:
        self.assertEqual(symbol_from_text("⊏"), "⊏")
        self.assertEqual(symbol_from_text("\\sqsubset", {"sqsubset": "⊏"}), "⊏")
        self.assertEqual(symbol_from_text("U+228F"), "⊏")
        self.assertIsNone(symbol_from_text("\\unknown", {}))
        self.assertIsNone(symbol_from_text("ab"))


class SignsFileTests(unittest.TestCase):
    def test_a_file_is_one_sign_per_line_with_comments(self) -> None:
        text = "# The class's signs.\n⊏ ⠈⠸⠣\n⊐ 4-456-28\nnot a sign\n"
        self.assertEqual(parse_signs(text), {"⊏": "⠈⠸⠣", "⊐": "⠈⠸⢂"})
        self.assertEqual(parse_signs(format_signs({"⊏": "⠈⠸⠣"})), {"⊏": "⠈⠸⠣"})

    def test_saved_per_code_and_removed_when_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            save_signs("Nemeth", {"⊏": "⠈⠸⠣"}, folder)
            self.assertEqual(load_signs("Nemeth", folder), {"⊏": "⠈⠸⠣"})
            self.assertEqual(load_signs("UEB", folder), {})
            save_signs("Nemeth", {}, folder)
            self.assertFalse((folder / "Nemeth.txt").exists())

    def test_mathcat_entries_quote_what_yaml_needs(self) -> None:
        self.assertEqual(signs_yaml({'"': "⠿", "⊏": "⠈⠸⠣"}), ' - "\\"": [t: "⠿"]\n - "⊏": [t: "⠈⠸⠣"]\n')
        self.assertEqual(signs_yaml({}), "")


class MathCatSignsTests(unittest.TestCase):
    """MathCAT patch 0008: the user's signs replace the code's, and clearing them brings the code's back."""

    def braille(self, signs: dict[str, str]) -> str:
        navigator = MathCatNavigator(language="en")
        navigator.braille_code = "Nemeth"
        navigator.braille_signs = signs_yaml(signs)
        navigator.load("<math><mi>a</mi><mo>⊏</mo><mi>b</mi></math>")
        cells = navigator._native.braille(navigator.structure.root.identifier)
        return "".join(chr(0x2800 + ((ord(cell) - 0x2800) & 0x3F)) for cell in cells)  # No dots 7-8.

    def test_a_users_sign_replaces_the_hex_code(self) -> None:
        self.assertIn("⠈⠸⠣", self.braille({"⊏": "⠈⠸⠣"}))
        self.assertNotIn("⠈⠸⠣", self.braille({}))


if __name__ == "__main__":
    unittest.main()
