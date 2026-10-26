"""The user's own braille signs for symbols, over an existing braille code (MathCAT patch 0008).

Where Nemeth or UEB defines no sign for a symbol, both leave it to the
transcriber, and a school or a teacher may have its own conventions. One
plain text file per code, `~/.mathessible/braille/Nemeth.txt`, one sign per line:

    # Square image of: the class's sign.
    ⊏ ⠈⠸⠣
    ⊐ 4-456-28

The symbol, then its cells, as braille characters or as dot numbers (a
cell's dots, cells apart by hyphens or spaces). A line starting with `#`
is a comment. MathCAT reads the signs after the code's own table, so each
replaces the code's sign for that symbol.
"""

from __future__ import annotations

import re
from pathlib import Path

_DOTS = re.compile(r"^[1-8]+(?:[- ][1-8]+)*$")
_BRAILLE = re.compile(r"^[⠀-⣿]+$")


def signs_directory() -> Path:
    return Path.home() / ".mathessible" / "braille"


def signs_path(code: str, directory: Path | None = None) -> Path:
    return (directory or signs_directory()) / f"{code}.txt"


def cells_from_text(text: str) -> str | None:
    """Braille cells from what was typed: the cells themselves, or dot numbers ("4-456-126"); else None."""
    text = " ".join(text.split())
    if _BRAILLE.match(text.replace(" ", "")):
        return text.replace(" ", "")
    if _DOTS.match(text):
        cells = []
        for cell in re.split(r"[- ]", text):
            bits = 0
            for dot in cell:
                bits |= 1 << (int(dot) - 1)
            cells.append(chr(0x2800 + bits))
        return "".join(cells)
    return None


def dots_of(cells: str) -> str:
    """Cells as dot numbers ("⠈⠸⠣" is "4-456-126"), the way they are read aloud; a blank cell is 0."""
    return "-".join(
        "".join(str(dot) for dot in range(1, 9) if (ord(cell) - 0x2800) >> (dot - 1) & 1) or "0" for cell in cells
    )


def parse_signs(text: str) -> dict[str, str]:
    """Symbol -> cells from a signs file; lines that are not a sign are skipped."""
    signs: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        symbol, _space, rest = line.partition(" ")
        cells = cells_from_text(rest)
        if len(symbol) == 1 and cells:
            signs[symbol] = cells
    return signs


def format_signs(signs: dict[str, str]) -> str:
    lines = ["# Mathessible braille signs: a symbol, then its braille (cells or dot numbers)."]
    lines += [f"{symbol} {cells}" for symbol, cells in sorted(signs.items())]
    return "\n".join(lines) + "\n"


def load_signs(code: str, directory: Path | None = None) -> dict[str, str]:
    path = signs_path(code, directory)
    try:
        return parse_signs(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return {}


def save_signs(code: str, signs: dict[str, str], directory: Path | None = None) -> None:
    path = signs_path(code, directory)
    if not signs:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_signs(signs), encoding="utf-8")


def signs_yaml(signs: dict[str, str]) -> str:
    """The signs as MathCAT unicode.yaml entries (` - "⊏": [t: "⠈⠸⠣"]`)."""
    lines = []
    for symbol, cells in sorted(signs.items()):
        quoted = symbol.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f' - "{quoted}": [t: "{cells}"]')
    return "\n".join(lines) + ("\n" if lines else "")


def symbol_from_text(text: str, control_words: dict[str, str] | None = None) -> str | None:
    """The symbol typed: the character itself, a control word (`\\sqsubset`) or a code (`U+228F`); else None."""
    text = text.strip()
    if len(text) == 1:
        return text
    if text.startswith("\\") and control_words is not None:
        symbol = control_words.get(text[1:], "")
        return symbol if len(symbol) == 1 else None
    match = re.fullmatch(r"(?:U\+|0x)?([0-9A-Fa-f]{4,6})", text)
    if match and int(match.group(1), 16) <= 0x10FFFF:
        return chr(int(match.group(1), 16))
    return None
