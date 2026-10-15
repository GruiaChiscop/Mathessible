from __future__ import annotations

from .symbol_dictionary import BUILTIN_ID, SymbolDictionary, load_dictionary

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
