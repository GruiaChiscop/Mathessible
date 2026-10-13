from __future__ import annotations

from dataclasses import dataclass


CONVERSIONS = {
    "=>": "⇒",
    "->": "→",
    "<-": "←",
    ">=": "≥",
    "<=": "≤",
    "!=": "≠",
    "\\alpha": "α",
    "\\beta": "β",
    "\\gamma": "γ",
    "\\delta": "δ",
    "\\pi": "π",
    "\\theta": "θ",
    "\\lambda": "λ",
    "\\mu": "μ",
    "\\sigma": "σ",
    "\\phi": "φ",
    "\\omega": "ω",
    "\\infty": "∞",
    "\\inf": "∞",
    "\\times": "×",
    "\\cdot": "·",
    "\\neq": "≠",
    "\\le": "≤",
    "\\ge": "≥",
}


@dataclass(frozen=True, slots=True)
class SpaceConversion:
    source: str
    caret: int
    announcement: str
    converted: bool


def convert_on_space(source: str, caret: int, enabled: bool = True) -> SpaceConversion:
    caret = max(0, min(caret, len(source)))
    if not enabled:
        return _insert_space(source, caret)
    match = _conversion_match(source, caret)
    if match is None:
        return _insert_space(source, caret)
    token_start, token, replacement = match
    updated = source[:token_start] + replacement + source[caret:]
    new_caret = token_start + len(replacement)
    return SpaceConversion(updated, new_caret, replacement, True)


def _insert_space(source: str, caret: int) -> SpaceConversion:
    return SpaceConversion(source[:caret] + " " + source[caret:], caret + 1, "space", False)


def _token_start(source: str, caret: int) -> int:
    index = caret
    while index > 0 and not source[index - 1].isspace():
        index -= 1
    return index


def _conversion_match(source: str, caret: int) -> tuple[int, str, str] | None:
    for token in sorted(CONVERSIONS, key=len, reverse=True):
        token_start = caret - len(token)
        if token_start < 0:
            continue
        if source[token_start:caret] != token:
            continue
        if token_start > 0 and not _can_start_conversion_after(source[token_start - 1], token):
            continue
        return token_start, token, CONVERSIONS[token]
    return None


def _can_start_conversion_after(previous: str, token: str) -> bool:
    if token.startswith("\\"):
        return previous.isspace()
    return True
