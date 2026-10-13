from __future__ import annotations

from dataclasses import dataclass


TRIGGER_CHARACTERS = {" ", ",", ";"}
EQUATION_PUNCTUATION = {",", ";"}


@dataclass(frozen=True, slots=True)
class BuildTrigger:
    character: str
    should_attempt: bool
    include_character: bool


def build_trigger_for(source: str, caret: int, character: str) -> BuildTrigger:
    """Classify a typed character as a possible professional-mode trigger.

    Space behaves like Word's autobuild trigger: it asks the editor to build
    the source before the space, and the space itself is not part of the
    equation. Punctuation is more conservative: it can trigger a build at the
    end of an expression, but the punctuation is included in the source so the
    user's typed character is not lost.
    """
    caret = max(0, min(caret, len(source)))
    if character not in TRIGGER_CHARACTERS:
        return BuildTrigger(character, False, False)
    if caret != len(source) or not source.strip():
        return BuildTrigger(character, False, character in EQUATION_PUNCTUATION)
    if _looks_like_number_punctuation(source, caret, character):
        return BuildTrigger(character, False, True)
    return BuildTrigger(character, True, character in EQUATION_PUNCTUATION)


def build_source_for_trigger(source: str, caret: int, trigger: BuildTrigger) -> tuple[str, int]:
    caret = max(0, min(caret, len(source)))
    if not trigger.include_character:
        return source, caret
    return source[:caret] + trigger.character + source[caret:], caret + len(trigger.character)


def _looks_like_number_punctuation(source: str, caret: int, character: str) -> bool:
    if character != ",":
        return False
    previous_is_digit = caret > 0 and source[caret - 1].isdigit()
    next_is_digit = caret < len(source) and source[caret].isdigit()
    return previous_is_digit or next_is_digit
