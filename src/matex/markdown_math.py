from __future__ import annotations

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


def math_zone_at(source: str, start: int, end: int | None = None) -> MathZone | None:
    end = start if end is None else end
    for zone in find_math_zones(source):
        if zone.contains(start, end):
            return zone
    return None
