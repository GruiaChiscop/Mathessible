"""File > Open Recent: the documents and notebooks opened last, most recent first."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

LIMIT = 10


def remember(recent: Sequence[str], path: Path, limit: int = LIMIT) -> tuple[str, ...]:
    """`path` first, without its earlier place, the list cut at `limit`."""
    entry = str(path.expanduser().resolve())
    return tuple([entry, *(item for item in recent if item != entry)][:limit])


def still_there(recent: Sequence[str]) -> tuple[str, ...]:
    """The entries whose file or folder still exists."""
    return tuple(item for item in recent if Path(item).exists())


def menu_labels(recent: Sequence[str]) -> list[str]:
    """Each entry's name; with its folder when two have the same name ("notes.md — Algebra")."""
    names = [Path(item).name for item in recent]
    return [
        f"{name} — {Path(item).parent.name}" if names.count(name) > 1 else name
        for name, item in zip(names, recent, strict=True)
    ]
