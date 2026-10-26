"""liblouis's tables for the document's text in braille (BRF export), from the `liblouis` submodule.

A table is offered when it is a literary one with a name (its `#+type`
and `#-index-name` metadata, "Romanian, uncontracted") and not for 8-dot
braille: BRF is 6-dot. Names come only from the tables themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TextTable:
    file: str  # "ro-g0.utb"
    name: str  # "Romanian, uncontracted"
    language: str  # "ro"
    contraction: str  # "no", "partial", "full"
    system: str = ""  # "ueb", "bfu"...


def tables_directory() -> Path:
    """liblouis's tables in the submodule (Mathessible runs from its checkout)."""
    return Path(__file__).resolve().parents[3] / "liblouis" / "tables"


def _metadata(path: Path) -> dict[str, str]:
    """The `#+key: value` and `#-key: value` lines at the top of a table."""
    found: dict[str, str] = {}
    try:
        with path.open(encoding="utf-8", errors="replace") as file:
            for line in file:
                if line.strip() and not line.startswith("#"):
                    break
                if line[:2] in ("#+", "#-") and ":" in line:
                    key, value = line[2:].split(":", 1)
                    found.setdefault(key.strip(), value.strip())
    except OSError:
        return {}
    return found


def text_tables(directory: Path | None = None) -> list[TextTable]:
    """The literary 6-dot tables with a name, by name."""
    folder = directory or tables_directory()
    tables: list[TextTable] = []
    for path in sorted(folder.glob("*.*")) if folder.is_dir() else ():
        metadata = _metadata(path)
        if metadata.get("type") != "literary" or "index-name" not in metadata or metadata.get("dots") == "8":
            continue
        tables.append(
            TextTable(
                path.name,
                metadata["index-name"],
                metadata.get("language", ""),
                metadata.get("contraction", ""),
                metadata.get("system", ""),
            )
        )
    return sorted(tables, key=lambda table: table.name.casefold())


def default_table(language: str, tables: list[TextTable]) -> str:
    """The table for a language ("ro", "en_GB"): uncontracted, Unified English Braille where there is a choice;
    English UEB uncontracted for a language without one."""
    code = language.replace("_", "-").split("-")[0].lower()
    matching = [table for table in tables if table.language.split("-")[0].lower() == code]
    matching.sort(key=lambda table: (table.contraction != "no", table.system != "ueb", table.name))
    if matching:
        return matching[0].file
    return "en-ueb-g1.ctb"
