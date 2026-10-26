"""Symbol names for speech, read from dictionaries in NVDA's symbols.dic format.

A dictionary is a text file with a `symbols:` section of tab-separated
lines, `identifier<TAB>replacement[<TAB>level[<TAB>preserve]][<TAB># name]`,
exactly as NVDA's `source/locale/<lang>/symbols.dic`. Mathessible ships its own
English one (`symbols/mathessible-en.dic`); NVDA's can be downloaded with
`symbol_download` and any other file imported into `symbols_directory()`.
Only `symbols:` is read: `complexSymbols:` are NVDA's sentence-level regular
expressions, which have no use for single-character echo.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from itertools import islice
from pathlib import Path

BUILTIN_ID = "mathessible-en"
BUILTIN_PATH = Path(__file__).resolve().parent / "mathessible-en.dic"
# NVDA leaves a field it does not set as "-" (the base English file fills it in).
_UNSET = "-"
_ESCAPES = {"0": "\0", "t": "\t", "n": "\n", "r": "\r", "f": "\f", "v": "\v", "#": "#", "\\": "\\"}


# Provenance Mathessible writes at the top of a file it brings in ("# Mathessible-Source:
# NVDA"). Labels and fallbacks come only from these lines, never from the
# file name: a file without them is just a file, whatever it is called.
_PROVENANCE_PREFIX = "# Mathessible-"


class SymbolDictionaryError(ValueError):
    pass


def provenance_header(**fields: str) -> str:
    """Comment lines recording where a dictionary came from, e.g. `source="NVDA", language="ro"`."""
    lines = [f"{_PROVENANCE_PREFIX}{key.capitalize()}: {value}" for key, value in fields.items() if value]
    return "\n".join(lines) + "\n"


def read_provenance(text: str) -> dict[str, str]:
    """The `# Mathessible-Key: value` lines at the top of a dictionary, keys lowercased."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith(_PROVENANCE_PREFIX):
            break
        key, _, value = line[len(_PROVENANCE_PREFIX) :].partition(":")
        if value.strip():
            fields[key.strip().lower()] = value.strip()
    return fields


def symbols_directory() -> Path:
    """Where downloaded and imported dictionaries live: one `.dic` file each."""
    return Path.home() / ".mathessible" / "symbols"


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
    provenance: dict[str, str] = field(default_factory=dict)

    @property
    def from_nvda(self) -> bool:
        return self.provenance.get("source") == "NVDA"


def available_dictionaries(directory: Path | None = None) -> list[DictionaryInfo]:
    """The built-in dictionary first, then every `.dic` file in the symbols directory."""
    directory = symbols_directory() if directory is None else directory
    found = [DictionaryInfo(BUILTIN_ID, "Mathessible (English, built in)", BUILTIN_PATH)]
    if directory.is_dir():
        for path in sorted(directory.glob("*.dic")):
            provenance = _provenance_of(path)
            found.append(DictionaryInfo(path.stem, _label(path.stem, provenance), path, provenance))
    return found


def _provenance_of(path: Path) -> dict[str, str]:
    try:
        with path.open(encoding="utf-8-sig") as file:
            head = "".join(islice(file, 10))
    except (OSError, UnicodeDecodeError):
        return {}
    return read_provenance(head)


def _label(identifier: str, provenance: dict[str, str]) -> str:
    language = provenance.get("language")
    if provenance.get("source") == "NVDA" and language:
        downloaded = provenance.get("downloaded")
        return f"{language} (NVDA, downloaded {downloaded})" if downloaded else f"{language} (NVDA)"
    imported = provenance.get("imported")
    return f"{identifier} (imported {imported})" if imported else identifier


def load_dictionary(identifier: str, directory: Path | None = None) -> SymbolDictionary:
    """The chosen dictionary layered over its fallbacks; unknown or unreadable ones fall back silently.

    An NVDA locale file only names what differs from NVDA's English one, so
    a downloaded NVDA English dictionary (when there is one) comes next;
    Mathessible's built-in names come last. "NVDA" means the file's provenance
    header says so, not its name.
    """
    directory = symbols_directory() if directory is None else directory
    layers: list[Mapping[str, str]] = []
    dictionaries = available_dictionaries(directory)
    chosen = next((info for info in dictionaries if info.identifier == identifier), None)
    if chosen is not None and identifier != BUILTIN_ID:
        layers.append(_read(chosen.path))
        if chosen.from_nvda and chosen.provenance.get("language") != "en":
            english = next(
                (info for info in dictionaries if info.from_nvda and info.provenance.get("language") == "en"), None
            )
            if english is not None:
                layers.append(_read(english.path))
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
    # Whatever the file says about itself, Mathessible only knows it was imported
    # from this path: earlier provenance lines are replaced, not trusted.
    text = source.read_text(encoding="utf-8-sig")
    body = "\n".join(line for line in text.splitlines() if not line.startswith(_PROVENANCE_PREFIX))
    provenance = {"origin": str(source), "imported": date.today().isoformat()}
    target.write_text(provenance_header(**provenance) + body + "\n", encoding="utf-8")
    return DictionaryInfo(identifier, _label(identifier, provenance), target, provenance)
