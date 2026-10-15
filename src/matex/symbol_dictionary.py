"""Symbol names for speech, read from dictionaries in NVDA's symbols.dic format.

A dictionary is a text file with a `symbols:` section of tab-separated
lines, `identifier<TAB>replacement[<TAB>level[<TAB>preserve]][<TAB># name]`,
exactly as NVDA's `source/locale/<lang>/symbols.dic`. MateX ships its own
English one (`symbols/matex-en.dic`); NVDA's can be downloaded with
`symbol_download` and any other file imported into `symbols_directory()`.
Only `symbols:` is read: `complexSymbols:` are NVDA's sentence-level regular
expressions, which have no use for single-character echo.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

BUILTIN_ID = "matex-en"
BUILTIN_PATH = Path(__file__).resolve().parent / "symbols" / "matex-en.dic"
# NVDA leaves a field it does not set as "-" (the base English file fills it in).
_UNSET = "-"
_ESCAPES = {"0": "\0", "t": "\t", "n": "\n", "r": "\r", "f": "\f", "v": "\v", "#": "#", "\\": "\\"}


class SymbolDictionaryError(ValueError):
    pass


def symbols_directory() -> Path:
    """Where downloaded and imported dictionaries live: one `.dic` file each."""
    return Path.home() / ".matex" / "symbols"


def parse_symbols(text: str) -> dict[str, str]:
    """The `symbols:` section of a symbols.dic text, identifier -> spoken replacement."""
    names: dict[str, str] = {}
    section = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r")
        if not line or line.startswith("#"):
            continue
        if line.endswith(":") and "\t" not in line:
            section = line[:-1].strip()
            continue
        if section != "symbols":
            continue
        fields = line.split("\t")
        if len(fields) < 2:
            continue
        identifier = _unescape(fields[0])
        replacement = fields[1].strip()
        if not identifier or not replacement or replacement == _UNSET or replacement.startswith("#"):
            continue
        names[identifier] = replacement
    return names


def _unescape(identifier: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(identifier):
        character = identifier[index]
        if character == "\\" and index + 1 < len(identifier) and identifier[index + 1] in _ESCAPES:
            result.append(_ESCAPES[identifier[index + 1]])
            index += 2
            continue
        result.append(character)
        index += 1
    return "".join(result)


@dataclass(frozen=True, slots=True)
class SymbolDictionary:
    """Names looked up in `layers` in order: the chosen dictionary, then its fallbacks."""

    layers: tuple[Mapping[str, str], ...]

    def name(self, character: str) -> str | None:
        for names in self.layers:
            spoken = names.get(character)
            if spoken:
                return spoken
        return None


@dataclass(frozen=True, slots=True)
class DictionaryInfo:
    identifier: str
    label: str
    path: Path


def available_dictionaries(directory: Path | None = None) -> list[DictionaryInfo]:
    """The built-in dictionary first, then every `.dic` file in the symbols directory."""
    directory = symbols_directory() if directory is None else directory
    found = [DictionaryInfo(BUILTIN_ID, "MateX (English, built in)", BUILTIN_PATH)]
    if directory.is_dir():
        for path in sorted(directory.glob("*.dic")):
            found.append(DictionaryInfo(path.stem, _label(path.stem), path))
    return found


def _label(identifier: str) -> str:
    if identifier.startswith("nvda-"):
        return f"NVDA ({identifier[len('nvda-'):]})"
    return identifier


def load_dictionary(identifier: str, directory: Path | None = None) -> SymbolDictionary:
    """The chosen dictionary layered over its fallbacks; unknown or unreadable ones fall back silently.

    An NVDA locale file only names what differs from NVDA's English one, so
    `nvda-en` (when downloaded) comes next; MateX's built-in names come last.
    """
    directory = symbols_directory() if directory is None else directory
    layers: list[Mapping[str, str]] = []
    chosen = [info for info in available_dictionaries(directory) if info.identifier == identifier]
    if chosen and identifier != BUILTIN_ID:
        layers.append(_read(chosen[0].path))
        english = directory / "nvda-en.dic"
        if identifier.startswith("nvda-") and identifier != "nvda-en" and english.is_file():
            layers.append(_read(english))
    layers.append(_read(BUILTIN_PATH))
    return SymbolDictionary(tuple(layers))


def _read(path: Path) -> dict[str, str]:
    try:
        return parse_symbols(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError):
        return {}


def import_dictionary(source: Path, directory: Path | None = None) -> DictionaryInfo:
    """Copy a symbols.dic file from anywhere into the symbols directory; it must name some symbols."""
    directory = symbols_directory() if directory is None else directory
    try:
        names = parse_symbols(source.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError) as error:
        raise SymbolDictionaryError(f"Could not read {source.name}: {error}") from error
    if not names:
        raise SymbolDictionaryError(f"{source.name} has no symbols: section in the NVDA symbols.dic format")
    identifier = source.stem if source.stem != "symbols" else source.parent.name
    if identifier == BUILTIN_ID:
        identifier = f"{identifier}-imported"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{identifier}.dic"
    shutil.copyfile(source, target)
    return DictionaryInfo(identifier, _label(identifier), target)
