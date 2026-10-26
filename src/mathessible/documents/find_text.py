"""Find and replace in the Markdown document: plain text, equations' source included."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FindOptions:
    match_case: bool = False
    whole_word: bool = False


PLAIN = FindOptions()


def _pattern(query: str, options: FindOptions) -> re.Pattern[str]:
    text = re.escape(query)
    if options.whole_word:
        text = rf"(?<!\w){text}(?!\w)"
    return re.compile(text, 0 if options.match_case else re.IGNORECASE)


def find(
    text: str, query: str, start: int, forward: bool = True, options: FindOptions = PLAIN
) -> tuple[int, int] | None:
    """The next match from `start` (the previous one before it when not `forward`), wrapping around."""
    if not query:
        return None
    matches = [(match.start(), match.end()) for match in _pattern(query, options).finditer(text)]
    if not matches:
        return None
    if forward:
        return next((span for span in matches if span[0] >= start), matches[0])
    return next((span for span in reversed(matches) if span[1] <= start), matches[-1])


def is_match(selected: str, query: str, options: FindOptions = PLAIN) -> bool:
    """Whether the selection is exactly a match, so Replace replaces it."""
    return bool(query) and _pattern(query, options).fullmatch(selected) is not None


def replace_all(text: str, query: str, replacement: str, options: FindOptions = PLAIN) -> tuple[str, int]:
    """`text` with every match replaced, and how many there were."""
    if not query:
        return text, 0
    return _pattern(query, options).subn(lambda _match: replacement, text)
