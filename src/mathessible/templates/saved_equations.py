"""The user's own equations (Word's Save as New Equation), offered in the Structure Gallery.

Kept in `~/.mathessible/equations.json`: a list of `{"name", "source"}`,
the source in UnicodeMath, so a class can share one file.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SavedEquation:
    name: str
    source: str


def equations_path() -> Path:
    return Path.home() / ".mathessible" / "equations.json"


def load_equations(path: Path | None = None) -> list[SavedEquation]:
    """The saved equations; a missing or unreadable file, or a bad entry, is left out."""
    try:
        data = json.loads((path or equations_path()).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [
        SavedEquation(entry["name"].strip(), entry["source"])
        for entry in data
        if isinstance(entry, dict)
        and isinstance(entry.get("name"), str)
        and isinstance(entry.get("source"), str)
        and entry["name"].strip()
        and entry["source"]
    ]


def save_equations(equations: Sequence[SavedEquation], path: Path | None = None) -> None:
    target = path or equations_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    data = [{"name": equation.name, "source": equation.source} for equation in equations]
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_equation(equations: Sequence[SavedEquation], name: str) -> SavedEquation | None:
    """The equation saved under `name`, whatever its case."""
    key = name.strip().casefold()
    return next((equation for equation in equations if equation.name.casefold() == key), None)


def with_equation(equations: Sequence[SavedEquation], name: str, source: str) -> list[SavedEquation]:
    """`equations` with `source` saved as `name`, replacing one of that name where it was."""
    new = SavedEquation(name.strip(), source)
    old = find_equation(equations, name)
    if old is None:
        return [*equations, new]
    return [new if equation is old else equation for equation in equations]


def without_equation(equations: Sequence[SavedEquation], name: str) -> list[SavedEquation]:
    old = find_equation(equations, name)
    return [equation for equation in equations if equation is not old]
