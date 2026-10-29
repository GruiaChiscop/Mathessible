"""A template or symbol inserted into LaTeX typed in the linear view.

The Insert entries are UnicodeMath templates; in a LaTeX equation MathCAT
writes each one as LaTeX (`mathcat.latex`), its empty slots `{}`, and it is
inserted here: the caret goes into the first empty slot, as a template's
does in UnicodeMath. A control word is never run into a letter (`\\alpha`
before `x` is not `\\alphax`): a space keeps the two apart, as LaTeX needs.
Tab and Shift+Tab go from one brace group to the next (`move_to_latex_slot`),
as they go from slot to slot in UnicodeMath.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from mathessible.templates.template_source import TemplateEdit

_ENDS_IN_CONTROL_WORD = re.compile(r"(?<!\\)\\[A-Za-z]+$")
_COMMAND_BEFORE = re.compile(r"\\([A-Za-z]+)\*?\s*$")
# Each command's arguments, by their place; any other command's are "argument".
_ROLES = {
    "frac": ("numerator", "denominator"),
    "dfrac": ("numerator", "denominator"),
    "tfrac": ("numerator", "denominator"),
    "binom": ("top", "bottom"),
    "sqrt": ("radicand",),
    "overset": ("overscript", "base"),
    "underset": ("underscript", "base"),
    "stackrel": ("overscript", "base"),
}
_STRUCTURES = {
    "frac": "fraction",
    "dfrac": "fraction",
    "tfrac": "fraction",
    "binom": "binomial",
    "sqrt": "square root",
    "^": "superscript",
    "_": "subscript",
}


def insert_latex(source: str, caret: int, latex: str) -> tuple[str, int]:
    """The source with `latex` inserted at the caret, and the caret in its first empty slot (else after it)."""
    before, after = source[:caret], source[caret:]
    if _ENDS_IN_CONTROL_WORD.search(before) and latex[:1].isalpha():
        latex = " " + latex
    if _ENDS_IN_CONTROL_WORD.search(latex) and after[:1].isalpha():
        latex += " "
    slot = latex.find("{}")
    new_caret = caret + (slot + 1 if slot >= 0 else len(latex))
    return before + latex + after, new_caret


def within_environment(latex: str, environment: str, typed: str) -> str:
    """LaTeX written for an equation whose rows a .tex environment holds (`align`: `environment` "aligned"),
    without that environment's own `\\begin`/`\\end`, spaced at its ends as the LaTeX typed was."""
    if not environment:
        return latex
    opening, closing = f"\\begin{{{environment}}}", f"\\end{{{environment}}}"
    stripped = latex.strip()
    if stripped.startswith(opening) and stripped.endswith(closing):
        latex = stripped[len(opening) : -len(closing)].strip()
    leading = typed[: len(typed) - len(typed.lstrip())]
    trailing = typed[len(typed.rstrip()) :]
    return f"{leading}{latex}{trailing}"


@dataclass(frozen=True, slots=True)
class _Group:
    """A brace group: `start`/`end` bound its content; `after` is past the last argument of its command."""

    start: int
    end: int
    after: int
    role: str
    structure: str


def _brace_groups(source: str) -> list[_Group]:
    """The source's brace groups in source order, except an environment's name (`\\begin{cases}`)."""
    closing: dict[int, int] = {}  # Each group's opening brace, by its closing one.
    pairs: list[tuple[int, int]] = []
    opened: list[int] = []
    index = 0
    while index < len(source):
        character = source[index]
        if character == "\\":
            index += 2  # `\\{` and `\\}` are braces of the equation, not groups.
            continue
        if character == "{":
            opened.append(index)
        elif character == "}" and opened:
            start = opened.pop()
            closing[index] = start
            pairs.append((start, index))
        index += 1
    following = dict(pairs)
    groups: list[_Group] = []
    for start, end in sorted(pairs):
        owner, place = _owner(source, start, closing)
        if owner in ("begin", "end"):
            continue
        after = end + 1
        while True:  # Past the command's further arguments: `\\frac{a}{b}` is left after `{b}`.
            next_start = after + len(source[after:]) - len(source[after:].lstrip(" "))
            if next_start not in following or owner in ("^", "_", ""):
                break
            after = following[next_start] + 1
        roles = _ROLES.get(owner, ())
        if owner == "sqrt[":
            role, owner = "index", "sqrt"
        elif owner == "^":
            role = "superscript" if place == 0 else "group"
        elif owner == "_":
            role = "subscript" if place == 0 else "group"
        elif not owner:
            role = "group"
        else:
            role = roles[place] if place < len(roles) else "argument"
        groups.append(_Group(start + 1, end, after, role, _STRUCTURES.get(owner, "group")))
    return groups


def _owner(source: str, start: int, closing: dict[int, int]) -> tuple[str, int]:
    """The command whose argument the group opening at `start` is, and its place among the command's
    arguments: `sqrt[` for a root's index, `^`/`_` for a script, "" for a group of its own."""
    place = 0
    position = start
    while True:
        before = source[:position].rstrip(" ")
        if before.endswith("}") and len(before) - 1 in closing:
            position = closing[len(before) - 1]
            place += 1
        elif before.endswith("]") and "[" in before:
            position = before.rindex("[")  # An optional argument (`\\sqrt[n]{x}`) is not counted.
        else:
            break
    before = source[:position].rstrip(" ")
    if before.endswith("[") and _COMMAND_BEFORE.search(before[:-1]):
        found = _COMMAND_BEFORE.search(before[:-1])
        return ("sqrt[" if found.group(1) == "sqrt" else found.group(1)), 0
    if before.endswith(("^", "_")):
        return before[-1], place
    found = _COMMAND_BEFORE.search(before)
    if found and found.group(1) in ("begin", "end") and place > 0:
        return "", 0  # A group after an environment's name (`\\begin{cases}{}`) is its content.
    return (found.group(1) if found else ""), place


def move_to_latex_slot(source: str, caret: int, reverse: bool = False) -> TemplateEdit | None:
    """Tab/Shift+Tab in LaTeX: the next/previous brace group, filled or empty, the caret at the end of its
    content. Tab from a command's last argument leaves the command (`\\frac{a}{b}` is left after `{b}`)."""
    groups = _brace_groups(source)
    caret = max(0, min(caret, len(source)))
    if reverse:
        previous = [group for group in groups if group.start < caret and not group.start <= caret <= group.end]
        return _enter(source, previous[-1]) if previous else None
    for group in groups:
        if group.start > caret:
            return _enter(source, group)
    around = [group for group in groups if group.start <= caret <= group.end]
    if not around:
        return None
    current = around[-1]
    return TemplateEdit(source, current.after, f"end {current.structure}")


def _enter(source: str, group: _Group) -> TemplateEdit:
    content = source[group.start : group.end]
    announcement = f"{group.role}, {content}" if content else f"empty {group.role}"
    return TemplateEdit(source, group.end, announcement)
