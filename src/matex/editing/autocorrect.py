"""Math AutoCorrect as one list, as in Word: the defaults and the user's changes together.

The defaults are the converter's control words (`\\alpha` → α, read from
UnicodeMathML, so they follow the submodule) and MateX's symbol shortcuts
(`->` → →, space_conversion.SHORTCUTS). The user can change or delete any
entry and add new ones; only the differences are saved (entries added or
changed, defaults deleted), so a converter update still brings its new
words, and "Reset to defaults" just forgets the differences.

An entry typed as `\\word` is a control word (Space, punctuation, Tab and
completion know it); any other is a shortcut. A shortcut made only of
symbols (`->`) may convert as soon as it is typed; one with letters or
digits only on Space, as a whole word, so it never changes a word while
it is being typed.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache


@dataclass(frozen=True, slots=True)
class AutoCorrectTable:
    """The effective list: `defaults`, less `removed`, with `overrides` added or replacing."""

    defaults: Mapping[str, str]
    overrides: tuple[tuple[str, str], ...] = ()
    removed: tuple[str, ...] = ()

    def entries(self) -> dict[str, str]:
        removed = set(self.removed)
        table = {typed: replacement for typed, replacement in self.defaults.items() if typed not in removed}
        table.update(self.overrides)
        return table

    def control_words(self) -> dict[str, str]:
        """Control words without their backslash ("alpha": "α")."""
        return {typed[1:]: replacement for typed, replacement in self.entries().items() if is_control_word(typed)}

    def shortcuts(self) -> dict[str, str]:
        return {typed: replacement for typed, replacement in self.entries().items() if not is_control_word(typed)}

    def removed_words(self) -> tuple[str, ...]:
        """Default control words the user deleted and did not add back ("alpha"), for literal text."""
        entries = self.entries()
        return tuple(typed[1:] for typed in self.removed if is_control_word(typed) and typed not in entries)


def is_control_word(typed: str) -> bool:
    return typed.startswith("\\") and len(typed) > 1 and typed[1:].isascii() and typed[1:].isalnum()


def is_symbol_shortcut(typed: str) -> bool:
    """A shortcut that may convert as soon as its last character is typed.

    One with no letter or digit (`->`), or one closed by a brace
    (`\\mathbb{R}`, as Word converts it): nothing typed after either
    could still be part of a word.
    """
    if is_control_word(typed):
        return False
    return typed.endswith("}") or not any(character.isalnum() for character in typed)


# Greek letters the converter's table leaves out (TeX's tradition: capitals that
# look like Latin ones, and omicron). They are other characters (Α is U+0391,
# not A): MathCAT reads "cap alpha", and the converter builds them.
GREEK_ADDITIONS = {
    "Alpha": "Α",
    "Beta": "Β",
    "Epsilon": "Ε",
    "Zeta": "Ζ",
    "Eta": "Η",
    "Iota": "Ι",
    "Kappa": "Κ",
    "Mu": "Μ",
    "Nu": "Ν",
    "Omicron": "Ο",
    "Rho": "Ρ",
    "Tau": "Τ",
    "Chi": "Χ",
    "omicron": "ο",
}


# Word's names for the math alphabets (\doubleR, \scriptL, \frakturg), by
# Unicode's name for each. The converter computes \doubleR and \scriptL itself
# but keeps no table of them, so without these AutoCorrect would not know them.
MATH_ALPHABETS = {"double": "DOUBLE-STRUCK", "script": "SCRIPT", "fraktur": "FRAKTUR"}
_DIGIT_NAMES = ("ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE")


def math_alphabet_character(alphabet: str, character: str) -> str | None:
    """`character` (a letter or digit) in a math alphabet of MATH_ALPHABETS' values: ("DOUBLE-STRUCK", "R") is ℝ.

    Looked up by Unicode name, so the letters Unicode placed in Letterlike
    Symbols before the math alphabets existed (ℝ, ℂ, ℋ, ℭ, ℯ) come out right.
    """
    if character.isdigit():
        names = [f"MATHEMATICAL {alphabet} DIGIT {_DIGIT_NAMES[int(character)]}"]
    elif character.isascii() and character.isalpha():
        case = "CAPITAL" if character.isupper() else "SMALL"
        letter = character.upper()
        names = [f"MATHEMATICAL {alphabet} {case} {letter}", f"{alphabet} {case} {letter}"]
        if alphabet == "FRAKTUR":
            names.append(f"BLACK-LETTER {case} {letter}")
    else:
        return None
    for name in names:
        try:
            return unicodedata.lookup(name)
        except KeyError:
            continue
    return None


def math_alphabet_entries() -> dict[str, str]:
    """Word's math alphabet entries: `\\doubleR`, `\\scriptL`, `\\frakturg`, and `\\mathbb{R}` (on its "}")."""
    letters = [chr(code) for code in range(ord("A"), ord("Z") + 1)] + [
        chr(code) for code in range(ord("a"), ord("z") + 1)
    ]
    entries: dict[str, str] = {}
    for word, alphabet in MATH_ALPHABETS.items():
        for letter in letters:
            symbol = math_alphabet_character(alphabet, letter)
            if symbol is not None:
                entries[f"\\{word}{letter}"] = symbol
    for character in letters + [str(digit) for digit in range(10)]:
        symbol = math_alphabet_character("DOUBLE-STRUCK", character)
        if symbol is not None:
            entries[f"\\mathbb{{{character}}}"] = symbol
    return entries


def default_entries(control_words: Mapping[str, str] | None, shortcuts: Mapping[str, str]) -> dict[str, str]:
    words = {**GREEK_ADDITIONS, **(control_words or {})}  # The converter's own spelling wins.
    table = {**math_alphabet_entries(), **{f"\\{word}": symbol for word, symbol in words.items()}}
    table.update(shortcuts)
    return table


def differences(
    defaults: Mapping[str, str], entries: Mapping[str, str]
) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    """What to save for an edited list: (entries added or changed, defaults deleted), both sorted."""
    overrides = tuple(
        sorted((typed, replacement) for typed, replacement in entries.items() if defaults.get(typed) != replacement)
    )
    removed = tuple(sorted(typed for typed in defaults if typed not in entries))
    return overrides, removed


@cache
def autocorrect_defaults() -> Mapping[str, str]:
    """The default list: the converter's control words (a small fallback without it) and MateX's shortcuts.

    Built once (every key press asks); read-only, the dialog edits a copy.
    """
    from matex.editing.space_conversion import FALLBACK_CONTROL_WORDS, SHORTCUTS
    from matex.unicodemath import control_words

    try:
        words = control_words()
    except (OSError, ValueError):
        words = FALLBACK_CONTROL_WORDS
    return default_entries(words, SHORTCUTS)
