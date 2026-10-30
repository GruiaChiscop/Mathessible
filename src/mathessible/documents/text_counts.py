"""A document's counts for the status bar, as editors for writing papers show them: words, characters, and
the section the caret is in.

Words are counted in the text a reader reads: Markdown's marks (`#`, `**`,
`[...](...)`, `|`) and LaTeX's commands are not words, an equation is one
word, as word processors count one, and a .tex file is counted from its
body as its preview reads it (`tex_markdown`). Characters are the text's,
spaces included and not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from mathessible.documents.front_matter import body
from mathessible.documents.markdown_math import find_math_zones
from mathessible.documents.tex_markdown import tex_to_markdown

_FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_MARKS = re.compile(r"^\s{0,3}(?:#{1,6}|>|[-*+]|\d+[.)]|:)\s+|\[[ xX]\]\s|[*_`~|]|^\s*-{3,}\s*$", re.MULTILINE)
_FOOTNOTE = re.compile(r"\[\^[^\]]+\]:?")
_WORD = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*")
_MARKDOWN_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
_TEX_HEADING = re.compile(
    r"\\(?:part|chapter|section|subsection|subsubsection|paragraph)\*?\s*(?:\[[^\]]*\])?\s*\{([^{}]*)\}"
)
_NUMBERED_HEADING = re.compile(r"^(#{1,6} )[\d.]+ ", re.MULTILINE)
_EQUATION = "\ue000"  # An equation, standing in as one word while the text's are counted.


@dataclass(frozen=True, slots=True)
class Counts:
    words: int
    characters: int
    characters_without_spaces: int


def _readable(markdown: str) -> str:
    """The text a reader reads in Markdown: each equation one stand-in word, the marks left out."""
    text = body(markdown)
    zones = find_math_zones(text)
    for zone in reversed(zones):
        text = text[: zone.start] + f" {_EQUATION} " + text[zone.end :]
    text = _FENCE.sub(" ", text)
    text = _LINK.sub(r"\1", text)
    text = _FOOTNOTE.sub(" ", text)
    return _MARKS.sub(" ", text)


def counts(source: str, tex: bool = False) -> Counts:
    """The words and characters of a document (or of a selection of one)."""
    # A .tex file as its preview reads it, without the numbers LaTeX gives its headings (not the writer's).
    text = _readable(_NUMBERED_HEADING.sub(r"\1", tex_to_markdown(source)) if tex else source)
    words = len(_WORD.findall(text.replace(_EQUATION, "x")))
    shown = re.sub(r"\s+", " ", text.replace(_EQUATION, "x")).strip()
    return Counts(words, len(shown), len(shown.replace(" ", "")))


def current_section(source: str, caret: int, tex: bool = False) -> str:
    """The heading of the section the caret is in ("" before the first)."""
    pattern = _TEX_HEADING if tex else _MARKDOWN_HEADING
    found = ""
    for heading in pattern.finditer(source, 0, max(0, caret)):
        found = heading.group(1).strip()
    return found
