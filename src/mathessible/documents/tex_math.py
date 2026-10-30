"""The equations of a LaTeX document (a `.tex` file), as `markdown_math` finds a Markdown document's.

Inline math is `$...$`, `\\(...\\)` or the `math` environment; display math
`$$...$$`, `\\[...\\]` or an environment: `equation`, `displaymath`, and the
multi-line ones (`align`, `gather`, `multline`, `eqnarray`, `flalign`,
`alignat`, starred or not), whose rows build as `aligned` (the zone's
`environment`). Comments (`%` to the end of the line), `\\verb` and the
verbatim environments are not searched; an escaped `\\$` is a dollar.

A zone's content is what is between its marks: an edited equation is put
back between the same marks, so the file is saved as it was written.
"""

from __future__ import annotations

import re

from mathessible.documents.markdown_math import MathZone

# Display environments, and the environment their rows build as.
_ENVIRONMENTS = {
    "equation": "",
    "displaymath": "",
    "align": "aligned",
    "gather": "aligned",
    "multline": "aligned",
    "eqnarray": "aligned",
    "flalign": "aligned",
    "alignat": "aligned",
}
_VERBATIM = ("verbatim", "verbatim*", "lstlisting", "minted", "comment", "Verbatim")
_BEGIN = re.compile(r"\\begin\s*\{([A-Za-z]+\*?)\}")
_ALIGNAT_COLUMNS = re.compile(r"\s*\{[^{}]*\}")

# The marks of a new equation, and of one changed to inline or display.
INLINE_MARKS = ("$", "$")
DISPLAY_MARKS = ("\\[", "\\]")
# A new LaTeX document (File > New > LaTeX Document): an article with amsmath, its text to be written where
# NEW_DOCUMENT_CARET is, inside the document environment.
NEW_DOCUMENT = "\\documentclass{article}\n\\usepackage{amsmath}\n\n\\begin{document}\n\n\\end{document}\n"
NEW_DOCUMENT_CARET = NEW_DOCUMENT.index("\\end{document}") - 1


def _environment_end(source: str, name: str, start: int) -> tuple[int, int] | None:
    pattern = re.compile(r"\\end\s*\{" + re.escape(name) + r"\}")
    found = pattern.search(source, start)
    return None if found is None else (found.start(), found.end())


def _closing(source: str, mark: str, start: int) -> int | None:
    """The next unescaped `mark` from `start`, None if there is none (or, for `$`, a blank line first)."""
    position = start
    while True:
        found = source.find(mark, position)
        if found < 0:
            return None
        if mark == "$" and "\n\n" in source[position:found]:
            return None  # Inline math does not cross a paragraph.
        backslashes = len(source[:found]) - len(source[:found].rstrip("\\"))
        if mark.startswith("\\") or backslashes % 2 == 0:
            if mark != "$" or not source.startswith("$$", found):
                return found
            position = found + 2
            continue
        position = found + len(mark)


def find_tex_math_zones(source: str) -> list[MathZone]:
    """The equations of a LaTeX document, in order."""
    zones: list[MathZone] = []
    position = 0
    while position < len(source):
        character = source[position]
        if character == "%":
            line_end = source.find("\n", position)
            position = len(source) if line_end < 0 else line_end + 1
            continue
        if character == "\\":
            following = source[position + 1 : position + 2]
            if following in ("(", "["):
                closing_mark = "\\)" if following == "(" else "\\]"
                closing = _closing(source, closing_mark, position + 2)
                if closing is None:
                    position += 2
                    continue
                zones.append(MathZone(position, position + 2, closing, closing + 2, following == "["))
                position = closing + 2
                continue
            if source.startswith("\\verb", position) and not source[position + 5 : position + 6].isalpha():
                start = position + 5 + (source[position + 5 : position + 6] == "*")
                delimiter = source[start : start + 1]
                end = source.find(delimiter, start + 1) if delimiter else -1
                position = len(source) if end < 0 else end + 1
                continue
            begin = _BEGIN.match(source, position)
            if begin is not None:
                name = begin.group(1)
                base = name.rstrip("*")
                if name in _VERBATIM or base in _VERBATIM:
                    end = _environment_end(source, name, begin.end())
                    position = len(source) if end is None else end[1]
                    continue
                if base in _ENVIRONMENTS or base == "math":
                    content_start = begin.end()
                    if base == "alignat":
                        columns = _ALIGNAT_COLUMNS.match(source, content_start)
                        content_start = columns.end() if columns else content_start
                    end = _environment_end(source, name, content_start)
                    if end is None:
                        position = begin.end()
                        continue
                    environment = _ENVIRONMENTS.get(base, "")
                    zones.append(MathZone(position, content_start, end[0], end[1], base != "math", environment))
                    position = end[1]
                    continue
            position += 2  # A control symbol (`\$`, `\%`, `\\`) or the start of a control word.
            continue
        if character == "$":
            if source.startswith("$$", position):
                closing = source.find("$$", position + 2)
                if closing < 0:
                    position += 2
                    continue
                zones.append(MathZone(position, position + 2, closing, closing + 2, True))
                position = closing + 2
                continue
            closing = _closing(source, "$", position + 1)
            if closing is None or closing == position + 1:
                position += 1
                continue
            zones.append(MathZone(position, position + 1, closing, closing + 1, False))
            position = closing + 1
            continue
        position += 1
    return zones


def tex_math_zone_at(source: str, start: int, end: int | None = None) -> MathZone | None:
    end = start if end is None else end
    for zone in find_tex_math_zones(source):
        if zone.contains(start, end):
            return zone
    return None


def toggle_tex_display(source: str, zone: MathZone) -> tuple[str, MathZone] | None:
    """Change to Display / Change to Inline in a LaTeX document: `$x$` and `\\(x\\)` become `\\[x\\]`, and
    `\\[x\\]`, `$$x$$` and an `equation` become `$x$`, in place. None for one that cannot be inline: empty, on
    several lines, holding a `$`, or a multi-line environment (align's rows)."""
    content = zone.content(source)
    if zone.display:
        content = content.strip()
        if not content or "\n" in content or "$" in content or zone.environment:
            return None
        opening, closing = INLINE_MARKS
    else:
        opening, closing = DISPLAY_MARKS
    start = zone.start
    new_source = source[:start] + opening + content + closing + source[zone.end :]
    content_start = start + len(opening)
    content_end = content_start + len(content)
    return new_source, MathZone(start, content_start, content_end, content_end + len(closing), not zone.display)
