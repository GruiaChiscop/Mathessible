"""The interface in the user's language: gettext, the catalogs read from the `.po` files themselves.

Every text the user sees or hears from Mathessible goes through `_` (or
`ngettext` for a count) in English, the source language. What the
equation editor says about an equation (its stops, "start fraction", where
typing goes) is in the speech language instead, MathCAT's, through
`spoken`/`spoken_n`: the navigation keeps those texts English inside, as
identifiers, and they are translated only when said. The catalogs are
in `src/mathessible/locale/<language>/LC_MESSAGES/mathessible.po`. A
`.po` file is compiled in memory when the language is chosen (Babel), so
there is no build step and no `.mo` to keep in step. A text with no
translation stays English. The languages offered are MathCAT's, so that
the interface and the speech of equations can be in one language.
"""

from __future__ import annotations

import gettext as _gettext
import io
from pathlib import Path

DOMAIN = "mathessible"
LOCALE_DIRECTORY = Path(__file__).resolve().parent / "locale"

# The interface languages (MathCAT's speech languages), with their names in themselves.
LANGUAGES: tuple[tuple[str, str], ...] = (
    ("en", "English"),
    ("de", "Deutsch"),
    ("el", "Ελληνικά"),
    ("es", "Español"),
    ("fi", "Suomi"),
    ("fr", "Français"),
    ("hu", "Magyar"),
    ("id", "Bahasa Indonesia"),
    ("nb", "Norsk bokmål"),
    ("pl", "Polski"),
    ("pt", "Português"),
    ("ru", "Русский"),
    ("sv", "Svenska"),
    ("vi", "Tiếng Việt"),
    ("zh-TW", "中文（台灣）"),
)

_translations: _gettext.NullTranslations = _gettext.NullTranslations()
_language = "en"
_speech: _gettext.NullTranslations = _gettext.NullTranslations()
_speech_language = "en"


def catalog_path(language: str, directory: Path | None = None) -> Path:
    return (directory or LOCALE_DIRECTORY) / language.replace("-", "_") / "LC_MESSAGES" / f"{DOMAIN}.po"


def load_translations(language: str, directory: Path | None = None) -> _gettext.NullTranslations:
    """The language's catalog, compiled from its `.po`; English (no translation) when it has none."""
    path = catalog_path(language, directory)
    if language == "en" or not path.is_file():
        return _gettext.NullTranslations()
    from babel.messages.mofile import write_mo
    from babel.messages.pofile import read_po

    with path.open("rb") as file:
        catalog = read_po(file, locale=language.replace("-", "_"))
    compiled = io.BytesIO()
    write_mo(compiled, catalog, use_fuzzy=False)
    compiled.seek(0)
    return _gettext.GNUTranslations(compiled)


def interface_language(chosen: str, preferred: list[str]) -> str:
    """The language to show: the one chosen in Settings, else the first preferred one offered, else English."""
    codes = {code.lower(): code for code, _name in LANGUAGES}
    candidates = [chosen] if chosen else []
    candidates += preferred
    for candidate in candidates:
        normalized = candidate.replace("_", "-").lower()
        if normalized in codes:
            return codes[normalized]
        base = normalized.split("-")[0]
        if normalized in ("zh-tw", "zh-hk") or normalized.startswith("zh-hant"):
            return "zh-TW"  # Traditional Chinese; MathCAT has no Simplified.
        if base in codes and base != "zh":
            return codes[base]
        if base == "no":  # Norwegian, written in bokmål.
            return "nb"
    return "en"


def set_language(language: str, directory: Path | None = None) -> None:
    """Use `language` from now on (the interface is built once: a change needs a restart)."""
    global _translations, _language
    _translations = load_translations(language, directory)
    _language = language


def current_language() -> str:
    return _language


def set_speech_language(language: str, directory: Path | None = None) -> None:
    """Say the equation editor's own words about equations in `language` (applies at once)."""
    global _speech, _speech_language
    if language != _speech_language or directory is not None:
        _speech = load_translations(language, directory)
        _speech_language = language


def spoken(text: str) -> str:
    """`text`, words the equation editor says about an equation, in the speech language."""
    return _speech.gettext(text)


def spoken_n(singular: str, plural: str, count: int) -> str:
    return _speech.ngettext(singular, plural, count)


def N_(text: str) -> str:
    """Mark a text for translation where it is defined (module level, before the language is chosen);
    `_` or `spoken` translates it where it is used."""
    return text


def _(text: str) -> str:
    """`text` in the interface language."""
    return _translations.gettext(text)


def ngettext(singular: str, plural: str, count: int) -> str:
    """The form for `count` in the interface language (`{count}` in the text is left to `.format`)."""
    return _translations.ngettext(singular, plural, count)
