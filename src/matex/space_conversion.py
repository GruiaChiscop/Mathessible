from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


# Typed shortcuts that are not control words.
SHORTCUTS = {
    "=>": "⇒",
    "->": "→",
    "<-": "←",
    ">=": "≥",
    "<=": "≤",
    "!=": "≠",
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
) -> SpaceConversion:
    """Space after a control word (`\\circ`) or shortcut (`->`) replaces it, as in Word.

    The space itself is consumed by a conversion. `control_words` is the
    converter's table, without the backslash; the small fallback is used when
    it is not available.
    """
    caret = max(0, min(caret, len(source)))
    if not enabled:
        return _insert_space(source, caret)
    match = _control_word_match(source, caret, control_words) or _shortcut_match(source, caret)
    if match is None:
        return _insert_space(source, caret)
    token_start, replacement = match
    updated = source[:token_start] + replacement + source[caret:]
    new_caret = token_start + len(replacement)
    return SpaceConversion(updated, new_caret, replacement, True)


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


def _shortcut_match(source: str, caret: int) -> tuple[int, str] | None:
    for token in sorted(SHORTCUTS, key=len, reverse=True):
        token_start = caret - len(token)
        if token_start >= 0 and source[token_start:caret] == token:
            return token_start, SHORTCUTS[token]
    return None
