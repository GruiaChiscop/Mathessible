import re
import tempfile
import unittest
from pathlib import Path

from mathessible import i18n

CATALOG = r"""msgid ""
msgstr ""
"Language: de\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\n"
"Content-Type: text/plain; charset=UTF-8\n"

msgid "&Save"
msgstr "&Speichern"

msgid "{count} replacement made."
msgid_plural "{count} replacements made."
msgstr[0] "{count} Ersetzung vorgenommen."
msgstr[1] "{count} Ersetzungen vorgenommen."
"""

SLOT_CATALOG = r"""msgid ""
msgstr ""
"Language: de\n"
"Content-Type: text/plain; charset=UTF-8\n"

msgid "empty {role}"
msgstr "leer: {role}"

msgid "line {number}"
msgstr "Zeile {number}"

msgid "numerator"
msgstr "Zähler"
"""


class I18nTests(unittest.TestCase):
    def tearDown(self) -> None:
        i18n.set_language("en")

    def test_a_catalog_translates_and_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            path = i18n.catalog_path("de", folder)
            path.parent.mkdir(parents=True)
            path.write_text(CATALOG, encoding="utf-8")
            i18n.set_language("de", folder)
            self.assertEqual(i18n._("&Save"), "&Speichern")
            self.assertEqual(i18n._("Not translated"), "Not translated")
            singular, plural = "{count} replacement made.", "{count} replacements made."
            self.assertEqual(i18n.ngettext(singular, plural, 1).format(count=1), "1 Ersetzung vorgenommen.")
            self.assertEqual(i18n.ngettext(singular, plural, 3).format(count=3), "3 Ersetzungen vorgenommen.")

    def test_english_or_a_missing_catalog_is_the_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            i18n.set_language("fi", Path(directory))
            self.assertEqual(i18n._("&Save"), "&Save")

    def test_the_language_chosen_then_the_systems(self) -> None:
        self.assertEqual(i18n.interface_language("", ["en-RO", "ro-RO"]), "en")
        self.assertEqual(i18n.interface_language("", ["ro-RO"]), "en")  # Not one of MathCAT's: English.
        self.assertEqual(i18n.interface_language("", ["ro-RO", "de-AT"]), "de")
        self.assertEqual(i18n.interface_language("", ["zh-Hant-TW"]), "zh-TW")
        self.assertEqual(i18n.interface_language("", ["no"]), "nb")
        self.assertEqual(i18n.interface_language("fr", ["de"]), "fr")

    def test_every_catalog_shipped_is_one_of_the_languages(self) -> None:
        codes = {code.replace("-", "_") for code, _name in i18n.LANGUAGES}
        shipped = {path.parent.parent.name for path in i18n.LOCALE_DIRECTORY.glob("*/LC_MESSAGES/*.po")}
        self.assertLessEqual(shipped, codes)

    def test_every_slot_role_and_template_name_can_be_spoken(self) -> None:
        from babel.messages.pofile import read_po

        from mathessible import spoken
        from mathessible.templates import math_templates

        with (i18n.LOCALE_DIRECTORY / f"{i18n.DOMAIN}.pot").open("rb") as file:
            texts = {message.id for message in read_po(file) if message.id}
        names = set(math_templates.NARYAND_ROLES) | set(math_templates.NARYAND_ROLES.values())
        names |= {name for pair in math_templates.CONTENT_SIGNS.values() for name in pair}
        names |= {pair[1] for pair in math_templates.BRACKET_PAIRS.values()}
        names |= {"fraction", "numerator", "denominator", "root", "index", "radicand", "scripts", "base"}
        names |= {"subscript", "superscript", "binomial", "top", "bottom", "argument", "value", "label"}
        self.assertLessEqual(names, texts)
        # The forms slots are announced in ("empty numerator", "end binomial", "empty line 1").
        for form in ("empty {role}", "end {region}", "line {number}"):
            self.assertIn(form, texts)
        self.assertEqual(spoken.translate("empty line 1"), "empty line 1")  # English: unchanged.
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            path = i18n.catalog_path("de", folder)
            path.parent.mkdir(parents=True)
            path.write_text(SLOT_CATALOG, encoding="utf-8")
            i18n.set_speech_language("de", folder)
            try:
                self.assertEqual(spoken.translate("empty numerator"), "leer: Zähler")
                self.assertEqual(spoken.translate("empty line 1"), "leer: Zeile 1")
            finally:
                i18n.set_speech_language("en")

    def test_every_translation_keeps_its_placeholders_and_mnemonic(self) -> None:
        from babel.messages.pofile import read_po

        placeholder = re.compile(r"\{[a-z_]+\}")
        mnemonic = re.compile(r"(?<!&)&(?=[^&\s])")
        for path in sorted(i18n.LOCALE_DIRECTORY.glob("*/LC_MESSAGES/*.po")):
            with path.open("rb") as file:
                catalog = read_po(file)
            for message in catalog:
                if not message.id or message.fuzzy:
                    continue
                ids = message.id if isinstance(message.id, tuple) else (message.id,)
                strings = message.string if isinstance(message.string, tuple) else (message.string,)
                expected = set(placeholder.findall(ids[-1]))
                wants_mnemonic = bool(mnemonic.search(ids[0]))
                for index, string in enumerate(strings):
                    if not string:
                        continue
                    with self.subTest(language=path.parent.parent.name, text=ids[0], form=index):
                        found = set(placeholder.findall(string))
                        # A plural's first form may say "one" instead of {count}.
                        if len(ids) > 1 and index == 0:
                            self.assertLessEqual(found, expected)
                        else:
                            self.assertEqual(found, expected)
                        self.assertEqual(len(mnemonic.findall(string)), int(wants_mnemonic))


if __name__ == "__main__":
    unittest.main()
