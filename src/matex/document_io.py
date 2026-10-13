from __future__ import annotations

from pathlib import Path


def markdown_path(path: str | Path) -> Path:
    result = Path(path).expanduser()
    if not result.suffix:
        result = result.with_suffix(".md")
    return result


def read_markdown(path: str | Path) -> str:
    with Path(path).open("r", encoding="utf-8", newline="") as document:
        return document.read()


def write_markdown(path: str | Path, source: str) -> Path:
    destination = markdown_path(path)
    with destination.open("w", encoding="utf-8", newline="") as document:
        document.write(source)
    return destination
