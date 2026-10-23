from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .autocorrect import is_symbol_shortcut

# Typed shortcuts that are not control words (a subset of Word's math
# AutoCorrect list). Some extend others: "<-" then ">" is "<->".
SHORTCUTS = {
    "=>": "⇒",
    "->": "→",
    "<-": "←",
    "<->": "↔",
    "<=>": "⇔",
    ">=": "≥",
    "<=": "≤",
    "!=": "≠",
    "<<": "≪",
    ">>": "≫",
    "+-": "±",
    "-+": "∓",
    "~=": "≅",
    ":=": "≔",
    "...": "…",
}

# Used only when the converter's own table (unicodemath.control_words) cannot
# be read, e.g. without the UnicodeMathML submodule.
FALLBACK_CONTROL_WORDS = {
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "pi": "π",
    "theta": "θ",
    "lambda": "λ",
    "mu": "μ",
    "sigma": "σ",
    "phi": "φ",
    "omega": "ω",
    "infty": "∞",
    "inf": "∞",
    "times": "×",
    "cdot": "·",
    "neq": "≠",
    "le": "≤",
    "ge": "≥",
}


@dataclass(frozen=True, slots=True)
class SpaceConversion:
    source: str
    caret: int
    announcement: str
    converted: bool


def convert_on_space(
    source: str,
    caret: int,
    enabled: bool = True,
    control_words: Mapping[str, str] | None = None,
    shortcuts: Mapping[str, str] | None = None,
) -> SpaceConversion:
    """Space after a control word (`\\circ`) or shortcut (`->`) replaces it, as in Word.

    The space itself is consumed by a conversion. `control_words` is the
    converter's table, without the backslash; the small fallback is used when
    it is not available.
    """
    caret = max(0, min(caret, len(source)))
    if not enabled:
        return _insert_space(source, caret)
    match = _control_word_match(source, caret, control_words) or _shortcut_match(source, caret, shortcuts)
    if match is None:
        return _insert_space(source, caret)
    token_start, replacement = match
    updated = source[:token_start] + replacement + source[caret:]
    new_caret = token_start + len(replacement)
    return SpaceConversion(updated, new_caret, replacement, True)


def convert_before_character(
    source: str,
    caret: int,
    character: str,
    enabled: bool = True,
    control_words: Mapping[str, str] | None = None,
) -> SpaceConversion | None:
    """Typing punctuation or an operator right after a control word converts it, as in Word.

    `\\int_` becomes `∫_`: unlike Space, the typed character is kept. Letters
    and digits never trigger (they continue the word, as in `\\2root`), nor do
    typed shortcuts (`->` is only converted by Space). None when nothing
    converts and the character should be inserted as usual.
    """
    caret = max(0, min(caret, len(source)))
    if not enabled or character.isspace() or (character.isascii() and character.isalnum()):
        return None
    match = _control_word_match(source, caret, control_words) or _function_spelling_match(source, caret)
    if match is None:
        return None
    token_start, replacement = match
    updated = source[:token_start] + replacement + character + source[caret:]
    return SpaceConversion(updated, token_start + len(replacement) + len(character), replacement, True)


def convert_word_before(
    source: str, caret: int, enabled: bool = True, control_words: Mapping[str, str] | None = None
) -> SpaceConversion | None:
    """A control word right before the caret, converted with nothing typed after it (Tab leaving a slot)."""
    caret = max(0, min(caret, len(source)))
    if not enabled:
        return None
    match = _control_word_match(source, caret, control_words)
    if match is None:
        return None
    token_start, replacement = match
    updated = source[:token_start] + replacement + source[caret:]
    return SpaceConversion(updated, token_start + len(replacement), replacement, True)


def convert_shortcut_on_character(
    source: str, caret: int, character: str, shortcuts: Mapping[str, str] | None = None
) -> SpaceConversion | None:
    """The typed character completes a shortcut: convert it at once (`<` + `<` is `≪`).

    A shortcut that extends an already converted one replaces its symbol:
    `←` (from "<-") followed by ">" becomes `↔`. None when nothing completes.
    Only shortcuts made of symbols: one with a letter or digit waits for
    Space (autocorrect.is_symbol_shortcut). `shortcuts` is the effective
    Math AutoCorrect list's; SHORTCUTS without one.
    """
    caret = max(0, min(caret, len(source)))
    table = SHORTCUTS if shortcuts is None else shortcuts
    table = {typed: replacement for typed, replacement in table.items() if is_symbol_shortcut(typed)}
    for token in sorted(table, key=len, reverse=True):
        if token[-1] != character:
            continue
        prefix = token[:-1]
        candidates = [prefix]
        if prefix in table:
            candidates.append(table[prefix])  # Already converted on the way.
        for typed in candidates:
            start = caret - len(typed)
            if start >= 0 and source[start:caret] == typed:
                replacement = table[token]
                updated = source[:start] + replacement + source[caret:]
                return SpaceConversion(updated, start + len(replacement), replacement, True)
    return None


def _insert_space(source: str, caret: int) -> SpaceConversion:
    return SpaceConversion(source[:caret] + " " + source[caret:], caret + 1, "space", False)


def _control_word_match(
    source: str, caret: int, control_words: Mapping[str, str] | None
) -> tuple[int, str] | None:
    # Converted wherever it is typed, like Word: "2\pi" becomes "2π".
    start = caret
    while start > 0 and source[start - 1].isascii() and source[start - 1].isalnum():
        start -= 1
    if start == caret or start == 0 or source[start - 1] != "\\":
        return None
    table = control_words if control_words is not None else FALLBACK_CONTROL_WORDS
    symbol = table.get(source[start:caret])
    if symbol is None:
        return None
    token_start = start - 1
    if symbol == "▒":
        # "∫_-1^1 \of": that space only ended the upper limit, but the
        # converter rejects any space before ▒, so it goes with the word.
        while token_start > 0 and source[token_start - 1] == " ":
            token_start -= 1
    return token_start, symbol


def _function_spelling_match(source: str, caret: int) -> tuple[int, str] | None:
    """`liminf`/`limsup` as a whole word before the caret: the converter's `lim inf` (FUNCTION_SPELLINGS)."""
    from .math_templates import FUNCTION_SPELLINGS

    start = caret
    while start > 0 and source[start - 1].isascii() and source[start - 1].isalpha():
        start -= 1
    spelled = FUNCTION_SPELLINGS.get(source[start:caret])
    if spelled is None or (start > 0 and (source[start - 1].isalnum() or source[start - 1] == "\\")):
        return None
    return start, spelled


def _shortcut_match(source: str, caret: int, shortcuts: Mapping[str, str] | None = None) -> tuple[int, str] | None:
    table = SHORTCUTS if shortcuts is None else shortcuts
    for token in sorted(table, key=len, reverse=True):
        token_start = caret - len(token)
        if token_start < 0 or source[token_start:caret] != token:
            continue
        if token[0].isalnum() and token_start > 0 and source[token_start - 1].isalnum():
            continue  # A user entry made of letters ("deg") only as a whole word, not inside "pedegree".
        return token_start, table[token]
    return None
