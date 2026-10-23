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
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .symbol_dictionary import parse_symbols, provenance_header, symbols_directory

REPOSITORY = "nvaccess/nvda"
BRANCH = "master"
_SOURCE_URL = f"https://api.github.com/repos/{REPOSITORY}/contents/source?ref={BRANCH}"
_TREE_URL = f"https://api.github.com/repos/{REPOSITORY}/git/trees/{{sha}}?recursive=1"
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
    """The NVDA locales that have a symbols.dic (many only translate the interface).

    Two API calls: the `source/locale` tree's id, then that tree listed
    recursively (unauthenticated GitHub allows 60 calls an hour, so not one
    call per locale).
    """
    try:
        entries = json.loads(_get(_SOURCE_URL))
        locale = next(entry for entry in entries if isinstance(entry, dict) and entry.get("name") == "locale")
        tree = json.loads(_get(_TREE_URL.format(sha=locale["sha"])))
    except (json.JSONDecodeError, StopIteration, KeyError, TypeError) as error:
        raise SymbolDownloadError(f"Unexpected answer listing NVDA's locales: {error!r}") from error
    return locales_with_symbols(tree.get("tree", []))


def locales_with_symbols(tree: list[dict]) -> list[str]:
    """From a recursive `source/locale` tree listing, the folders holding a symbols.dic."""
    return sorted(
        entry["path"].split("/")[0]
        for entry in tree
        if isinstance(entry, dict)
        and entry.get("type") == "blob"
        and entry.get("path", "").count("/") == 1
        and entry["path"].endswith("/symbols.dic")
    )


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
    # The only thing that marks a dictionary as NVDA's (see symbol_dictionary).
    header = provenance_header(
        source="NVDA",
        language=language,
        origin=_FILE_URL.format(language=language),
        downloaded=date.today().isoformat(),
    )
    target.write_text(header + text, encoding="utf-8")
    return target


@dataclass(slots=True)
class DownloadReport:
    saved: list[Path] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def download_languages(
    languages: list[str],
    directory: Path | None = None,
    progress: Callable[[int, str], None] | None = None,
) -> DownloadReport:
    """Fetch several languages; `progress(done, language)` is called before each one.

    Used by the command line and by Settings > Download NVDA dictionaries.
    """
    report = DownloadReport()
    for done, language in enumerate(languages):
        if progress is not None:
            progress(done, language)
        path = download_language(language, directory)
        if path is None:
            report.missing.append(language)
        else:
            report.saved.append(path)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download NVDA's symbol dictionaries for MateX.")
    parser.add_argument("languages", nargs="*", help="NVDA locale names (en, ro, de, pt_BR, ...); all when omitted")
    parser.add_argument("--directory", type=Path, default=None, help=f"target folder (default {symbols_directory()})")
    arguments = parser.parse_args(argv)
    try:
        languages = arguments.languages or nvda_languages()
        report = download_languages(languages, arguments.directory, lambda _done, language: print(f"{language}…"))
    except SymbolDownloadError as error:
        print(f"Download failed: {error}", file=sys.stderr)
        return 1
    for language in report.missing:
        print(f"{language}: NVDA has no symbols.dic")
    print(f"{len(report.saved)} dictionaries saved. Choose one in MateX: Settings > Symbol dictionary.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
