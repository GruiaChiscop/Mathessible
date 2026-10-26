from __future__ import annotations

import re
import unicodedata

from mathessible.symbols.dictionary import BUILTIN_ID, SymbolDictionary, load_dictionary

# The names come from a symbols.dic dictionary (symbol_dictionary.py); the
# built-in one is used when none is passed.
_BUILTIN: SymbolDictionary | None = None


def _default() -> SymbolDictionary:
    global _BUILTIN
    if _BUILTIN is None:
        _BUILTIN = load_dictionary(BUILTIN_ID)
    return _BUILTIN


def character_name(character: str, symbols: SymbolDictionary | None = None) -> str:
    if not character:
        return ""
    spoken = (symbols or _default()).name(character)
    return spoken or character


def inserted_character(character: str, symbols: SymbolDictionary | None = None) -> str:
    return character_name(character, symbols)


def deleted_character(character: str, symbols: SymbolDictionary | None = None) -> str:
    name = character_name(character, symbols)
    return f"deleted {name}" if name else "deleted"


def name_unknown_symbols(text: str) -> str:
    """Each symbol left unnamed in speech (🜁, ⟁ when nothing named it) as its Unicode name.

    MathCAT and the symbol dictionary pass a character they do not know
    through as itself, and the screen reader may not know it either. Only
    symbols (Unicode categories Sm, So, Sc, Sk) past ASCII: letters (ș, 中)
    and a text's punctuation are read well as they are.
    """
    if text.isascii():
        return text
    parts: list[str] = []
    for character in text:
        name = unicodedata.name(character, "") if ord(character) > 127 else ""
        if name and unicodedata.category(character).startswith("S"):
            parts.append(f" {name.lower()} ")
        else:
            parts.append(character)
    return re.sub(r" {2,}", " ", "".join(parts)).strip()
