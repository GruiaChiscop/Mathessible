import tempfile
import unittest
from pathlib import Path

from mathessible.symbols.text_braille import default_table, tables_directory, text_tables


class TextTablesTests(unittest.TestCase):
    def test_only_named_literary_6_dot_tables(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "xx-g0.utb").write_text(
                "#+type: literary\n#+language: xx\n#+contraction: no\n#-index-name: X, uncontracted\ninclude a\n"
            )
            (folder / "xx-8.utb").write_text("#+type: literary\n#+dots: 8\n#-index-name: X, 8 dots\n")
            (folder / "xx.cti").write_text("#+type: computer\n#-index-name: Computer\n")
            (folder / "yy.ctb").write_text("# no metadata\n")
            self.assertEqual([table.file for table in text_tables(folder)], ["xx-g0.utb"])

    def test_the_submodules_tables(self) -> None:
        tables = text_tables(tables_directory())
        names = {table.file: table.name for table in tables}
        self.assertEqual(names.get("ro-g0.utb"), "Romanian, uncontracted")
        self.assertIn("en-ueb-g2.ctb", names)
        self.assertEqual(default_table("ro_RO", tables), "ro-g0.utb")
        self.assertEqual(default_table("en", tables), "en-ueb-g1.ctb")
        self.assertEqual(default_table("zz", tables), "en-ueb-g1.ctb")


try:
    import mathessible_mathcat
except ImportError:
    mathessible_mathcat = None


@unittest.skipIf(mathessible_mathcat is None, "the native extension (with liblouis) is not built")
class LiblouisTests(unittest.TestCase):
    """liblouis compiled into the native extension (build.rs)."""

    def test_text_in_romanian_and_english_braille(self) -> None:
        tables = tables_directory()
        self.assertEqual(
            mathessible_mathcat.text_braille(str(tables / "ro-g0.utb"), "Ecuația are 2 soluții."),
            "⠨⠑⠉⠥⠁⠪⠊⠁⠀⠁⠗⠑⠀⠼⠃⠀⠎⠕⠇⠥⠪⠊⠊⠲",
        )
        self.assertEqual(mathessible_mathcat.text_braille(str(tables / "en-ueb-g2.ctb"), "the roots"), "⠮⠀⠗⠕⠕⠞⠎")

    def test_a_missing_table_is_an_error(self) -> None:
        with self.assertRaises(RuntimeError):
            mathessible_mathcat.text_braille(str(tables_directory() / "missing.ctb"), "x")


if __name__ == "__main__":
    unittest.main()
