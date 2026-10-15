"""Download NVDA's symbol dictionaries into MateX's symbols directory.

NVDA's `source/locale/<lang>/symbols.dic` files are GPL-2.0 (as is MateX);
they are fetched from the NVDA repository on demand rather than kept in
MateX's repository. Each lands as `nvda-<lang>.dic` and can then be chosen
in Settings. Run:

    uv run matex-fetch-symbols            # every language NVDA has
    uv run matex-fetch-symbols en ro      # just these
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from .symbol_dictionary import parse_symbols, symbols_directory

REPOSITORY = "nvaccess/nvda"
BRANCH = "master"
_LOCALES_URL = f"https://api.github.com/repos/{REPOSITORY}/contents/source/locale?ref={BRANCH}"
_FILE_URL = f"https://raw.githubusercontent.com/{REPOSITORY}/{BRANCH}/source/locale/{{language}}/symbols.dic"
_TIMEOUT = 30


class SymbolDownloadError(RuntimeError):
    pass


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "MateX symbol dictionary download"})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError) as error:
        raise SymbolDownloadError(f"{url}: {error}") from error


def nvda_languages() -> list[str]:
    """The locale folders of NVDA's repository (not every one has a symbols.dic)."""
    try:
        entries = json.loads(_get(_LOCALES_URL))
    except json.JSONDecodeError as error:
        raise SymbolDownloadError(f"Unexpected answer listing NVDA's locales: {error}") from error
    return sorted(entry["name"] for entry in entries if isinstance(entry, dict) and entry.get("type") == "dir")


def download_language(language: str, directory: Path | None = None) -> Path | None:
    """Fetch one language's symbols.dic; None when NVDA has none for it."""
    directory = symbols_directory() if directory is None else directory
    if not language.replace("_", "").isalnum():
        raise SymbolDownloadError(f"Not a locale name: {language!r}")
    try:
        data = _get(_FILE_URL.format(language=language))
    except SymbolDownloadError as error:
        if "404" in str(error):
            return None
        raise
    text = data.decode("utf-8-sig")
    if not parse_symbols(text):
        raise SymbolDownloadError(f"NVDA's {language} symbols.dic has no symbols: section")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"nvda-{language}.dic"
    target.write_text(text, encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download NVDA's symbol dictionaries for MateX.")
    parser.add_argument("languages", nargs="*", help="NVDA locale names (en, ro, de, pt_BR, ...); all when omitted")
    parser.add_argument("--directory", type=Path, default=None, help=f"target folder (default {symbols_directory()})")
    arguments = parser.parse_args(argv)
    try:
        languages = arguments.languages or nvda_languages()
        saved = 0
        for language in languages:
            path = download_language(language, arguments.directory)
            if path is None:
                print(f"{language}: NVDA has no symbols.dic")
                continue
            saved += 1
            print(f"{language}: {path}")
    except SymbolDownloadError as error:
        print(f"Download failed: {error}", file=sys.stderr)
        return 1
    print(f"{saved} dictionaries saved. Choose one in MateX: Settings > Symbol dictionary.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
