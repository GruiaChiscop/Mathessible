from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MathZone:
    start: int
    content_start: int
    content_end: int
    end: int
    display: bool

    @property
    def delimiter(self) -> str:
        return "$$" if self.display else "$"

    def content(self, source: str) -> str:
        return source[self.content_start : self.content_end]

    def contains(self, start: int, end: int | None = None) -> bool:
        end = start if end is None else end
        return self.start <= start and end <= self.end


def _is_escaped(source: str, position: int) -> bool:
    backslashes = 0
    position -= 1
    while position >= 0 and source[position] == "\\":
        backslashes += 1
        position -= 1
    return backslashes % 2 == 1


def _skip_code_span(source: str, start: int) -> int:
    ticks = 1
    while start + ticks < len(source) and source[start + ticks] == "`":
        ticks += 1
    marker = "`" * ticks
    closing = source.find(marker, start + ticks)
    return len(source) if closing < 0 else closing + ticks


def _skip_tilde_fence(source: str, start: int) -> int:
    tildes = 3
    while start + tildes < len(source) and source[start + tildes] == "~":
        tildes += 1
    marker = "~" * tildes
    closing = source.find(marker, start + tildes)
    return len(source) if closing < 0 else closing + tildes


def _find_display_close(source: str, start: int) -> int | None:
    position = start
    while position < len(source) - 1:
        position = source.find("$$", position)
        if position < 0:
            return None
        if not _is_escaped(source, position):
            return position
        position += 2
    return None


def _find_inline_close(source: str, start: int) -> int | None:
    position = start
    while position < len(source):
        char = source[position]
        if char == "\n":
            return None
        if char == "$" and not _is_escaped(source, position):
            if source.startswith("$$", position):
                position += 2
                continue
            if position > start and not source[position - 1].isspace():
                return position
        position += 1
    return None


def find_math_zones(source: str) -> list[MathZone]:
    """Find Markdown math while ignoring escaped dollars and code spans."""
    zones: list[MathZone] = []
    position = 0
    while position < len(source):
        if source[position] == "`" and not _is_escaped(source, position):
            position = _skip_code_span(source, position)
            continue
        if source.startswith("~~~", position) and not _is_escaped(source, position):
            position = _skip_tilde_fence(source, position)
            continue
        if source[position] != "$" or _is_escaped(source, position):
            position += 1
            continue

        if source.startswith("$$", position):
            closing = _find_display_close(source, position + 2)
            if closing is None:
                position += 2
                continue
            zones.append(MathZone(position, position + 2, closing, closing + 2, True))
            position = closing + 2
            continue

        content_start = position + 1
        if content_start >= len(source) or source[content_start].isspace():
            position += 1
            continue
        closing = _find_inline_close(source, content_start)
        if closing is None:
            position += 1
            continue
        zones.append(MathZone(position, content_start, closing, closing + 1, False))
        position = closing + 1
    return zones


def literal_ranges(source: str) -> list[tuple[int, int]]:
    """Code spans, code fences and equations: where Markdown's own syntax (`[^1]`) is not syntax."""
    ranges: list[tuple[int, int]] = [(zone.start, zone.end) for zone in find_math_zones(source)]
    position = 0
    while position < len(source):
        if source[position] == "`" and not _is_escaped(source, position):
            end = _skip_code_span(source, position)
            ranges.append((position, end))
            position = end
        elif source.startswith("~~~", position) and not _is_escaped(source, position):
            end = _skip_tilde_fence(source, position)
            ranges.append((position, end))
            position = end
        else:
            position += 1
    return sorted(ranges)


def with_marks(source: str, zones: list[MathZone], mark: Callable[[int], str]) -> str:
    """The Markdown with each equation replaced by its mark, for a Markdown parser that must not see it.

    A display equation becomes a paragraph of its own, except in a
    footnote's note, which a paragraph break would end: there it stays in
    the note's text (the exporters still write it as a display equation).
    """
    transformed = source
    for index, zone in reversed(list(enumerate(zones))):
        block = zone.display and not _in_footnote_note(source, zone.start)
        transformed = (
            transformed[: zone.start] + (f"\n\n{mark(index)}\n\n" if block else mark(index)) + transformed[zone.end :]
        )
    return transformed


_NOTE_START = re.compile(r" {0,3}\[\^[^\]\s]+\]:")


def _in_footnote_note(source: str, position: int) -> bool:
    """Whether the paragraph at `position` is a footnote's note (`[^1]: ...`)."""
    paragraph = source.rfind("\n\n", 0, position)
    start = 0 if paragraph < 0 else paragraph + 2
    return _NOTE_START.match(source, start) is not None


def math_zone_at(source: str, start: int, end: int | None = None) -> MathZone | None:
    end = start if end is None else end
    for zone in find_math_zones(source):
        if zone.contains(start, end):
            return zone
    return None


def toggle_display(source: str, zone: MathZone) -> tuple[str, MathZone] | None:
    """Word's Change to Display / Change to Inline on one zone: the new source and zone.

    Display goes on a line of its own, as in Word, by a line break where text
    shares its line (a soft break: the paragraph stays one). Inline keeps the
    equation where it is. None when the equation cannot be inline: empty, on
    several lines or holding a `$`.
    """
    content = zone.content(source)
    before, after = source[: zone.start], source[zone.end :]
    if zone.display:
        content = content.strip()
        if not content or "\n" in content or "$" in content:
            return None
        start = len(before)
        new_zone = MathZone(start, start + 1, start + 1 + len(content), start + 2 + len(content), False)
        return f"{before}${content}${after}", new_zone
    if before[before.rfind("\n") + 1 :].strip():
        before = before.rstrip(" \t") + "\n"
    if after.split("\n", 1)[0].strip():
        after = "\n" + after.lstrip(" \t")
    start = len(before)
    new_zone = MathZone(start, start + 2, start + 2 + len(content), start + 4 + len(content), True)
    return f"{before}$${content}$${after}", new_zone
