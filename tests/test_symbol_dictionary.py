import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mathessible.editing.character_speech import character_name
from mathessible.symbols import download as symbol_download
from mathessible.symbols.dictionary import (
    BUILTIN_ID,
    SymbolDictionaryError,
    available_dictionaries,
    import_dictionary,
    load_dictionary,
    parse_symbols,
    provenance_header,
    read_provenance,
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
    ". sentence ending\tpoint\tall\talways\n"
    " \tespace\tchar\t# space\n"
    "\\#\tdièse\tmost\n"
    "\\t\ttab\tchar\n"
    "∑\tsomme\tnone\n"
    "∫\t-\tnone\n"
    "(\tparenthèse gauche\tmost\talways\n"
)


class ParseSymbolsTests(unittest.TestCase):
    def test_only_the_symbols_section_is_read(self) -> None:
        names = parse_symbols(SAMPLE)
        self.assertEqual(names[" "], "espace")
        self.assertEqual(names["#"], "dièse")
        self.assertEqual(names["\t"], "tab")
        self.assertEqual(names["∑"], "somme")
        self.assertEqual(names["("], "parenthèse gauche")
        self.assertNotIn("∫", names)  # "-": left to the base dictionary.
        self.assertEqual(names[". sentence ending"], "point")

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

    def nvda_file(self, name: str, language: str, text: str) -> None:
        header = provenance_header(source="NVDA", language=language, downloaded="2026-10-15")
        (self.directory / name).write_text(header + text, encoding="utf-8")

    def test_a_chosen_dictionary_falls_back_to_nvda_english_then_built_in(self) -> None:
        self.nvda_file("nvda-fr.dic", "fr", SAMPLE)
        # The NVDA English file is found by its header, whatever its name.
        self.nvda_file("english.dic", "en", "symbols:\n∫\tintegral sign\tnone\n")
        dictionary = load_dictionary("nvda-fr", self.directory)
        self.assertEqual(character_name("∑", dictionary), "somme")
        self.assertEqual(character_name("∫", dictionary), "integral sign")
        self.assertEqual(character_name("≤", dictionary), "less than or equal to")
        self.assertEqual(character_name("x", dictionary), "x")

    def test_an_unknown_choice_is_the_built_in_dictionary(self) -> None:
        self.assertEqual(load_dictionary("missing", self.directory).name("∑"), "sum")

    def test_available_dictionaries_list_the_built_in_one_first(self) -> None:
        self.nvda_file("nvda-de.dic", "de", SAMPLE)
        found = available_dictionaries(self.directory)
        self.assertEqual([info.identifier for info in found], [BUILTIN_ID, "nvda-de"])
        self.assertEqual(found[1].label, "de (NVDA, downloaded 2026-10-15)")

    def test_a_file_named_like_nvda_is_not_taken_for_nvda(self) -> None:
        (self.directory / "nvda-fr.dic").write_text(SAMPLE, encoding="utf-8")
        self.nvda_file("nvda-en.dic", "en", "symbols:\n∫\tintegral sign\tnone\n")
        info = next(info for info in available_dictionaries(self.directory) if info.identifier == "nvda-fr")
        self.assertEqual(info.label, "nvda-fr")
        self.assertFalse(info.from_nvda)
        # No NVDA English fallback either: straight to the built-in names.
        self.assertEqual(load_dictionary("nvda-fr", self.directory).name("∫"), "integral")

    def test_import_copies_a_valid_file_named_after_its_folder(self) -> None:
        source_folder = self.directory / "source" / "fr"
        source_folder.mkdir(parents=True)
        (source_folder / "symbols.dic").write_text(SAMPLE, encoding="utf-8")
        info = import_dictionary(source_folder / "symbols.dic", self.directory / "symbols")
        self.assertEqual(info.identifier, "fr")
        self.assertTrue(info.label.startswith("fr (imported "))
        self.assertEqual(
            read_provenance(info.path.read_text(encoding="utf-8"))["origin"], str(source_folder / "symbols.dic")
        )

    def test_import_does_not_trust_a_file_that_claims_to_be_nvda(self) -> None:
        claimed = self.directory / "fake.dic"
        claimed.write_text(provenance_header(source="NVDA", language="fr") + SAMPLE, encoding="utf-8")
        info = import_dictionary(claimed, self.directory / "symbols")
        self.assertFalse(info.from_nvda)
        self.assertEqual(parse_symbols(info.path.read_text(encoding="utf-8"))["∑"], "somme")

    def test_import_rejects_a_file_without_symbols(self) -> None:
        bad = self.directory / "notes.dic"
        bad.write_text("hello\n", encoding="utf-8")
        with self.assertRaises(SymbolDictionaryError):
            import_dictionary(bad, self.directory / "symbols")


class SymbolDownloadTests(unittest.TestCase):
    def test_download_saves_each_language_as_nvda_language(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            mock.patch.object(symbol_download, "_get", return_value=SAMPLE.encode("utf-8")) as get,
        ):
            path = symbol_download.download_language("fr", Path(directory))
            self.assertEqual(path.name, "nvda-fr.dic")
            provenance = read_provenance(path.read_text(encoding="utf-8"))
            self.assertEqual((provenance["source"], provenance["language"]), ("NVDA", "fr"))
            self.assertIn("/source/locale/fr/symbols.dic", get.call_args.args[0])
            self.assertEqual(load_dictionary("nvda-fr", Path(directory)).name("∑"), "somme")

    def test_a_language_without_symbols_is_skipped(self) -> None:
        missing = symbol_download.SymbolDownloadError("HTTP Error 404: Not Found")
        with (
            tempfile.TemporaryDirectory() as directory,
            mock.patch.object(symbol_download, "_get", side_effect=missing),
        ):
            self.assertIsNone(symbol_download.download_language("xx", Path(directory)))

    def test_only_locales_with_a_symbols_file_are_listed(self) -> None:
        tree = [
            {"path": "fr", "type": "tree"},
            {"path": "fr/symbols.dic", "type": "blob"},
            {"path": "fr/LC_MESSAGES/nvda.po", "type": "blob"},
            {"path": "id", "type": "tree"},
            {"path": "id/LC_MESSAGES/nvda.po", "type": "blob"},
            {"path": "en/symbols.dic", "type": "blob"},
            {"path": "de/extra/symbols.dic", "type": "blob"},
        ]
        self.assertEqual(symbol_download.locales_with_symbols(tree), ["en", "fr"])

    def test_locale_names_are_checked_before_building_a_url(self) -> None:
        with self.assertRaises(symbol_download.SymbolDownloadError):
            symbol_download.download_language("../../etc", Path("."))


if __name__ == "__main__":
    unittest.main()
