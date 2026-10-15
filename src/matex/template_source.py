"""What every template edit shares: the edit result and source scanning."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TemplateEdit:
    source: str
    caret: int
    announcement: str


def insert_template(source: str, caret: int, template: str, first_slot_offset: int, announcement: str) -> TemplateEdit:
    caret = max(0, min(caret, len(source)))
    return TemplateEdit(
        source=source[:caret] + template + source[caret:],
        caret=caret + first_slot_offset,
        announcement=announcement,
    )


def matching_parens(source: str) -> dict[int, int]:
    """Map each "(" to its matching ")", by real nesting depth; unmatched ones are skipped."""
    pairs: dict[int, int] = {}
    stack: list[int] = []
    for index, character in enumerate(source):
        if character == "(":
            stack.append(index)
        elif character == ")" and stack:
            pairs[stack.pop()] = index
    return pairs


def operand_end(source: str, start: int, pairs: dict[int, int] | None = None) -> int:
    """Roughly where an integrand or function argument stops: at a top-level space or relation/sum sign."""
    pairs = matching_parens(source) if pairs is None else pairs
    index = start
    while index < len(source):
        character = source[index]
        if character == "(" and index in pairs:
            index = pairs[index] + 1
            continue
        if character in " +-=<>,":
            break
        index += 1
    return index
