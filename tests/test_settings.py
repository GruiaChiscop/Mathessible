import tempfile
import unittest
from pathlib import Path

from matex.settings import (
    AppSettings,
    load_settings,
    parse_recognized_functions,
    save_settings,
)


class SettingsTests(unittest.TestCase):
    def test_missing_settings_file_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = load_settings(Path(directory) / "missing.json")
        self.assertFalse(settings.linear_navigation)
        self.assertTrue(settings.convert_on_space)
        self.assertTrue(settings.convert_shortcuts_immediately)
        self.assertTrue(settings.complete_control_words)
        self.assertEqual(settings.decimal_separator, ",")
        self.assertEqual(settings.braille_code, "Nemeth")
        self.assertTrue(settings.template_control_words)
        self.assertFalse(settings.open_built)
        self.assertTrue(settings.build_as_you_type)
        self.assertFalse(settings.argument_on_closing_paren)
        self.assertFalse(settings.auto_zoom_out)
        self.assertTrue(settings.structure_stops)

    def test_round_trip_preserves_linear_navigation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            save_settings(
                AppSettings(
                    linear_navigation=True,
                    structure_stops=False,
                    convert_on_space=False,
                    complete_control_words=False,
                    auto_zoom_out=True,
                    recognized_functions=("sin", "tg"),
                ),
                path,
            )
            settings = load_settings(path)
        self.assertTrue(settings.linear_navigation)
        self.assertFalse(settings.structure_stops)
        self.assertFalse(settings.convert_on_space)
        self.assertFalse(settings.complete_control_words)
        self.assertTrue(settings.auto_zoom_out)
        self.assertEqual(settings.recognized_functions, ("sin", "tg"))

    def test_invalid_settings_file_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("not json", encoding="utf-8")
            settings = load_settings(path)
        self.assertFalse(settings.linear_navigation)

    def test_math_autocorrect_differences_are_saved(self) -> None:
        settings = AppSettings(
            math_autocorrect=(("\\R", "ℝ"), ("deg", "°")),
            math_autocorrect_removed=("\\alpha",),
            removed_words_as_symbols=True,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            save_settings(settings, path)
            loaded = load_settings(path)
        self.assertEqual(loaded.math_autocorrect, settings.math_autocorrect)
        self.assertEqual(loaded.math_autocorrect_removed, ("\\alpha",))
        self.assertTrue(loaded.removed_words_as_symbols)
        self.assertFalse(AppSettings().removed_words_as_symbols)  # Off by default: deleted words stay text.

    def test_function_names_whose_case_matters_keep_it(self) -> None:
        self.assertEqual(parse_recognized_functions("PR, pr, Sin"), ("Pr", "sin"))

    def test_parse_recognized_functions_normalizes_and_deduplicates(self) -> None:
        self.assertEqual(parse_recognized_functions("sin, TG, tg,\nctg"), ("sin", "tg", "ctg"))


class BrailleCodeSettingTests(unittest.TestCase):
    def test_a_known_code_round_trips_and_an_unknown_one_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            save_settings(AppSettings(braille_code="UEB"), path)
            self.assertEqual(load_settings(path).braille_code, "UEB")
            path.write_text('{"braille_code": "Klingon"}', encoding="utf-8")
            self.assertEqual(load_settings(path).braille_code, "Nemeth")


if __name__ == "__main__":
    unittest.main()
