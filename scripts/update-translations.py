"""Extract the texts to translate and bring every language's catalog up to date.

Usage: uv run python scripts/update-translations.py
Writes src/mathessible/locale/mathessible.pot from every `_`, `N_`, `ngettext`,
`spoken` and `spoken_n` call, then creates or updates
src/mathessible/locale/<language>/LC_MESSAGES/mathessible.po for each language in
`mathessible.i18n.LANGUAGES`: new texts are added untranslated, texts gone from
the code are kept as obsolete entries (`#~`), and a text whose English changed
is marked fuzzy, which is not used until a translator checks it. The `.po`
files are read by the app as they are; there is nothing to compile.
"""

from __future__ import annotations

from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.extract import extract_from_dir
from babel.messages.pofile import read_po, write_po

from mathessible.i18n import DOMAIN, LANGUAGES, LOCALE_DIRECTORY, catalog_path

SOURCE = Path(__file__).resolve().parents[1] / "src" / "mathessible"
HEADER = {
    "copyright_holder": "Mathessible contributors",
    "msgid_bugs_address": "https://github.com/GruiaChiscop/Mathessible/issues",
}
KEYWORDS = {"_": None, "N_": None, "ngettext": (1, 2), "spoken": None, "spoken_n": (1, 2)}


def template() -> Catalog:
    catalog = Catalog(project="Mathessible", domain=DOMAIN, charset="utf-8", fuzzy=False, **HEADER)
    for filename, lineno, message, comments, context in extract_from_dir(
        SOURCE,
        method_map=[("**.py", "python")],
        keywords=KEYWORDS,
        comment_tags=("Translators:",),
        strip_comment_tags=True,
    ):
        catalog.add(message, None, [(f"src/mathessible/{filename}", lineno)], auto_comments=comments, context=context)
    return catalog


def _translated(string: str | tuple[str, ...]) -> bool:
    return all(string) if isinstance(string, tuple) else bool(string)


def _write(catalog: Catalog, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as file:
        write_po(file, catalog, width=100, omit_header=False, sort_by_file=True)


def main() -> None:
    pot = template()
    pot.header_comment = (
        "# The texts of Mathessible to translate.\n# Distributed under the same license as Mathessible."
    )
    _write(pot, LOCALE_DIRECTORY / f"{DOMAIN}.pot")
    for code, name in LANGUAGES:
        if code == "en":
            continue
        locale = code.replace("-", "_")
        path = catalog_path(code)
        if path.is_file():
            with path.open("rb") as file:
                catalog = read_po(file, locale=locale)
            catalog.update(pot, update_creation_date=False)
        else:
            catalog = Catalog(
                locale=locale, domain=DOMAIN, project="Mathessible", charset="utf-8", fuzzy=False, **HEADER
            )
            catalog.header_comment = (
                f"# {name} translation of Mathessible.\n# Distributed under the same license as Mathessible."
            )
            catalog.update(pot)
        _write(catalog, path)
        translated = sum(1 for message in catalog if message.id and _translated(message.string) and not message.fuzzy)
        print(f"{code} ({name}): {translated} of {len(pot)} translated")


if __name__ == "__main__":
    main()
