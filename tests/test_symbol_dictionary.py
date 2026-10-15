import tempfile
import unittest
from pathlib import Path
from unittest import mock

from matex import symbol_download
from matex.character_speech import character_name
from matex.symbol_dictionary import (
    BUILTIN_ID,
    SymbolDictionaryError,
    available_dictionaries,
    import_dictionary,
    load_dictionary,
    parse_symbols,
)

# A small file in NVDA's symbols.dic layout (written for this test).
SAMPLE = (
    "# comment\n"
    "complexSymbols:\n"
    "# identifier\tregexp\n"
    ". sentence ending\t(?<=[^\\s.])\\.\n"
    "\n"
    "symbols:\n"
    "# identifier\treplacement[[\tlevel][\tpreserve]][\t# display name]\n"
    ". sentence ending\tpunct\tall\talways\n"
    " \tspațiu\tchar\t# space\n"
    "\\#\tdiez\tmost\n"
    "\\t\ttab\tchar\n"
    "∑\tsumă\tnone\n"
    "∫\t-\tnone\n"
    "(\tparanteză stânga\tmost\talways\n"
)


class ParseSymbolsTests(unittest.TestCase):
    def test_only_the_symbols_section_is_read(self) -> None:
        names = parse_symbols(SAMPLE)
        self.assertEqual(names[" "], "spațiu")
        self.assertEqual(names["#"], "diez")
        self.assertEqual(names["\t"], "tab")
        self.assertEqual(names["∑"], "sumă")
        self.assertEqual(names["("], "paranteză stânga")
        self.assertNotIn("∫", names)  # "-": left to the base dictionary.
        self.assertEqual(names[". sentence ending"], "punct")

    def test_the_built_in_dictionary_names_math_symbols(self) -> None:
        dictionary = load_dictionary(BUILTIN_ID)
        self.assertEqual(dictionary.name("∫"), "integral")
        self.assertEqual(dictionary.name(" "), "space")
        self.assertEqual(dictionary.name("\\"), "backslash")
        self.assertIsNone(dictionary.name("x"))


class DictionaryFilesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self._temporary.name)

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def test_a_chosen_dictionary_falls_back_to_nvda_english_then_built_in(self) -> None:
        (self.directory / "nvda-ro.dic").write_text(SAMPLE, encoding="utf-8")
        (self.directory / "nvda-en.dic").write_text("symbols:\n∫\tintegral sign\tnone\n", encoding="utf-8")
        dictionary = load_dictionary("nvda-ro", self.directory)
        self.assertEqual(character_name("∑", dictionary), "sumă")
        self.assertEqual(character_name("∫", dictionary), "integral sign")
        self.assertEqual(character_name("≤", dictionary), "less than or equal to")
        self.assertEqual(character_name("x", dictionary), "x")

    def test_an_unknown_choice_is_the_built_in_dictionary(self) -> None:
        self.assertEqual(load_dictionary("missing", self.directory).name("∑"), "sum")

    def test_available_dictionaries_list_the_built_in_one_first(self) -> None:
        (self.directory / "nvda-de.dic").write_text(SAMPLE, encoding="utf-8")
        found = available_dictionaries(self.directory)
        self.assertEqual([info.identifier for info in found], [BUILTIN_ID, "nvda-de"])
        self.assertEqual(found[1].label, "NVDA (de)")

    def test_import_copies_a_valid_file_named_after_its_folder(self) -> None:
        source_folder = self.directory / "source" / "ro"
        source_folder.mkdir(parents=True)
        (source_folder / "symbols.dic").write_text(SAMPLE, encoding="utf-8")
        info = import_dictionary(source_folder / "symbols.dic", self.directory / "symbols")
        self.assertEqual(info.identifier, "ro")
        self.assertTrue(info.path.is_file())

    def test_import_rejects_a_file_without_symbols(self) -> None:
        bad = self.directory / "notes.dic"
        bad.write_text("hello\n", encoding="utf-8")
        with self.assertRaises(SymbolDictionaryError):
            import_dictionary(bad, self.directory / "symbols")


class SymbolDownloadTests(unittest.TestCase):
    def test_download_saves_each_language_as_nvda_language(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            symbol_download, "_get", return_value=SAMPLE.encode("utf-8")
        ) as get:
            path = symbol_download.download_language("ro", Path(directory))
            self.assertEqual(path.name, "nvda-ro.dic")
            self.assertIn("/source/locale/ro/symbols.dic", get.call_args.args[0])
            self.assertEqual(load_dictionary("nvda-ro", Path(directory)).name("∑"), "sumă")

    def test_a_language_without_symbols_is_skipped(self) -> None:
        missing = symbol_download.SymbolDownloadError("HTTP Error 404: Not Found")
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(symbol_download, "_get", side_effect=missing):
            self.assertIsNone(symbol_download.download_language("xx", Path(directory)))

    def test_locale_names_are_checked_before_building_a_url(self) -> None:
        with self.assertRaises(symbol_download.SymbolDownloadError):
            symbol_download.download_language("../../etc", Path("."))


if __name__ == "__main__":
    unittest.main()
