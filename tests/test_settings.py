import tempfile
import unittest
from pathlib import Path

from matex.settings import AppSettings, load_settings, parse_recognized_functions, save_settings


class SettingsTests(unittest.TestCase):
    def test_missing_settings_file_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = load_settings(Path(directory) / "missing.json")
        self.assertFalse(settings.linear_navigation)
        self.assertTrue(settings.convert_on_space)
        self.assertTrue(settings.convert_shortcuts_immediately)
        self.assertTrue(settings.template_control_words)
        self.assertFalse(settings.open_built)
        self.assertTrue(settings.build_as_you_type)
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
                    auto_zoom_out=True,
                    recognized_functions=("sin", "tg"),
                ),
                path,
            )
            settings = load_settings(path)
        self.assertTrue(settings.linear_navigation)
        self.assertFalse(settings.structure_stops)
        self.assertFalse(settings.convert_on_space)
        self.assertTrue(settings.auto_zoom_out)
        self.assertEqual(settings.recognized_functions, ("sin", "tg"))

    def test_invalid_settings_file_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("not json", encoding="utf-8")
            settings = load_settings(path)
        self.assertFalse(settings.linear_navigation)

    def test_parse_recognized_functions_normalizes_and_deduplicates(self) -> None:
        self.assertEqual(parse_recognized_functions("sin, TG, tg,\nctg"), ("sin", "tg", "ctg"))


if __name__ == "__main__":
    unittest.main()
