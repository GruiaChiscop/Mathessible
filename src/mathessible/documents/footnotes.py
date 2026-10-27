"""Footnotes in the Markdown, as GitHub, Pandoc and markdown-it's footnote plugin write them.

A reference `text[^1]` anywhere, and its note anywhere, usually at the end:

    [^1]: The note, which may hold equations.

Labels are names, not numbers: exports number the notes in the order of
their references. These are the editor's operations on the source (Insert
Footnote, going between a reference and its note); the exports read
footnotes through markdown-it's plugin.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from mathessible.documents.markdown_math import literal_ranges

_REFERENCE = re.compile(r"\[\^([^\]\s]+)\](?!:)")
_NOTE = re.compile(r"^ {0,3}\[\^([^\]\s]+)\]:[ \t]?", re.MULTILINE)
# A note runs to a blank line that no indented line continues.
_NOTE_END = re.compile(r"\n[ \t]*\n(?![ \t])")


@dataclass(frozen=True, slots=True)
class Footnote:
    label: str
    start: int
    end: int  # A reference: after its "]"; a note: the end of its text.
    text_start: int  # A note: where its text starts; a reference: its end.


def _outside(source: str, matches: list[re.Match[str]]) -> list[re.Match[str]]:
    literal = literal_ranges(source)
    return [match for match in matches if not any(start <= match.start() < end for start, end in literal)]


def notes(source: str) -> list[Footnote]:
    found = []
    for match in _outside(source, list(_NOTE.finditer(source))):
        end = _NOTE_END.search(source, match.end())
        found.append(Footnote(match.group(1), match.start(), end.start() if end else len(source), match.end()))
    return found


def references(source: str) -> list[Footnote]:
    # A note's own label is followed by ":", so it is not a reference.
    matches = _outside(source, list(_REFERENCE.finditer(source)))
    return [Footnote(match.group(1), match.start(), match.end(), match.end()) for match in matches]


def next_label(source: str) -> str:
    """The next free number, after the highest one used as a label."""
    numbers = [int(note.label) for note in notes(source) + references(source) if note.label.isdigit()]
    return str(max(numbers, default=0) + 1)


def insert_footnote(source: str, caret: int) -> tuple[str, int, str]:
    """Word's Insert Footnote: a reference at the caret and its note at the end of the document.

    The new source, the caret in the note (to type it) and the label.
    """
    label = next_label(source)
    reference = f"[^{label}]"
    text = source[:caret] + reference + source[caret:]
    stripped = text.rstrip()
    note = f"[^{label}]: "
    new_source = stripped + ("\n\n" if stripped else "") + note
    return new_source, len(new_source), label


def counterpart(source: str, position: int) -> tuple[int, str, bool] | None:
    """From a reference to its note's text, or from a note to its first reference.

    Where to go, the label and whether that is the note; None when the
    position is in neither or the other half is missing.
    """
    found = notes(source)
    for reference in references(source):
        if reference.start <= position <= reference.end:
            note = next((note for note in found if note.label == reference.label), None)
            return None if note is None else (note.text_start, note.label, True)
    for note in found:
        if note.start <= position <= note.end:
            reference = next((each for each in references(source) if each.label == note.label), None)
            return None if reference is None else (reference.end, note.label, False)
    return None
