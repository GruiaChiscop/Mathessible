"""A Markdown document as a BRF file: braille ready to emboss or read on a braille display.

The text goes through liblouis (`text_braille`), each equation through
MathCAT (`math_braille`), both giving Unicode braille cells. The cells are
laid out in lines and pages and written in North American Braille ASCII,
the BRF encoding (6 dots: MathCAT's dots 7 and 8, the cursor, are dropped).
Layout, as in common braille formats: a paragraph starts in cell 3 and runs
over to cell 1, a list item in cell 1 with runovers in cell 3, a display
equation in cell 5 with runovers in cell 7, a main heading centred; a blank
line between blocks.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from markdown_it import MarkdownIt

from mathessible.documents.html_export import ExportPage
from mathessible.documents.markdown_math import find_math_zones

BrailleOf = Callable[[str], str]

# North American Braille ASCII, by dot pattern (bit 0 is dot 1).
_ASCII = " A1B'K2L@CIF/MSP\"E3H9O6R^DJG>NTQ,*5<-U8V.%[$+X!&;:4\\0Z7(_?W]#Y)="
BLANK = "⠀"


@dataclass(frozen=True, slots=True)
class BrfLayout:
    cells_per_line: int = 40
    lines_per_page: int = 25


STANDARD = BrfLayout()


@dataclass(frozen=True, slots=True)
class _Block:
    cells: str
    first: int  # The cell the first line starts in (0-based).
    runover: int  # The cell the following lines start in.
    centred: bool = False
    lines: bool = False  # Code: its own line breaks kept, one per line.


def ascii_braille(cells: str) -> str:
    """Unicode braille as Braille ASCII; dots 7 and 8 dropped, a non-braille character kept as it is."""
    return "".join(_ASCII[(ord(cell) - 0x2800) & 0x3F] if "⠀" <= cell <= "⣿" else cell for cell in cells)


def _placeholder(index: int) -> str:
    return f"{index}"  # Private-use marks: never in a document, never split by Markdown.


_PLACEHOLDER = re.compile("(\\d+)")


def _blocks(markdown: str, text_braille: BrailleOf, math_braille: BrailleOf) -> list[_Block]:
    zones = find_math_zones(markdown)
    equations = [zone.content(markdown) for zone in zones]
    transformed = markdown
    for index, zone in reversed(list(enumerate(zones))):
        mark = _placeholder(index)
        transformed = (
            transformed[: zone.start] + (f"\n\n{mark}\n\n" if zone.display else mark) + transformed[zone.end :]
        )

    def braille(text: str) -> str:
        """Text with equation marks: each part by its own translator."""
        cells: list[str] = []
        position = 0
        for match in _PLACEHOLDER.finditer(text):
            if match.start() > position:
                cells.append(text_braille(text[position : match.start()]))
            cells.append(math_braille(equations[int(match.group(1))]))
            position = match.end()
        if position < len(text):
            cells.append(text_braille(text[position:]))
        return "".join(cells)

    blocks: list[_Block] = []
    tokens = MarkdownIt("commonmark").enable("table").parse(transformed)
    heading: int | None = None
    lists: list[list[int]] = []  # Per open list: [ordered (0/1), next number].
    item_marker: str | None = None
    row: list[str] = []
    in_cell = False
    for token in tokens:
        kind = token.type
        if kind == "heading_open":
            heading = int(token.tag[1])
        elif kind == "heading_close":
            heading = None
        elif kind in ("bullet_list_open", "ordered_list_open"):
            lists.append([1 if kind == "ordered_list_open" else 0, int(token.attrGet("start") or 1)])
        elif kind in ("bullet_list_close", "ordered_list_close"):
            lists.pop()
        elif kind == "list_item_open":
            ordered, number = lists[-1]
            item_marker = f"{number}. " if ordered else "• "
            lists[-1][1] += 1
        elif kind in ("fence", "code_block"):
            code = token.content.rstrip("\n").split("\n")
            blocks.append(_Block("\n".join(text_braille(line) for line in code), 0, 0, lines=True))
        elif kind == "tr_open":
            row = []
        elif kind == "tr_close":
            blocks.append(_Block(braille(" ".join(row)), 0, 2))  # A table row, its cells in a line.
        elif kind in ("th_open", "td_open", "th_close", "td_close"):
            in_cell = kind.endswith("_open")
        elif kind == "inline":
            text = _inline_text(token)
            if in_cell:
                row.append(text)
                continue
            depth = 2 * (len(lists) - 1) if lists else 0
            only = _PLACEHOLDER.fullmatch(text.strip())
            if heading is not None:
                blocks.append(_Block(braille(text), 0, 0, centred=heading == 1))
            elif only is not None and zones[int(only.group(1))].display:
                blocks.append(_Block(braille(text.strip()), 4 + depth, 6 + depth))
            elif item_marker is not None:
                blocks.append(_Block(braille(item_marker + text), depth, depth + 2))
                item_marker = None
            elif lists:
                blocks.append(_Block(braille(text), depth + 2, depth + 2))
            else:
                blocks.append(_Block(braille(text), 2, 0))
    return blocks


def _inline_text(token: object) -> str:
    """An inline token's text: soft breaks as spaces, code as its text, links as their text."""
    parts: list[str] = []
    for child in token.children or ():
        if child.type in ("text", "code_inline"):
            parts.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
        elif child.type == "image":
            parts.append(child.content)
    return "".join(parts)


def _lay_out(block: _Block, width: int) -> list[str]:
    """The block's cells in lines of `width`, broken between words (a longer word is split)."""
    if block.lines:
        lines: list[str] = []
        for line in block.cells.split("\n"):
            lines.extend(line[start : start + width] for start in range(0, max(len(line), 1), width))
        return lines
    words = [word for word in block.cells.replace("\n", BLANK).split(BLANK) if word]
    lines = []
    line = ""
    indent = block.first
    for word in words:
        while word:
            room = max(1, width - indent)
            if len(line) + (1 if line else 0) + len(word) <= room:
                line = f"{line}{BLANK}{word}" if line else word
                word = ""
            elif line:
                lines.append(BLANK * indent + line)
                line, indent = "", block.runover
            else:
                lines.append(BLANK * indent + word[:room])  # Longer than a line: split.
                word, indent = word[room:], block.runover
    if line or not lines:
        lines.append(BLANK * indent + line)
    if block.centred:
        lines = [BLANK * max(0, (width - len(line)) // 2) + line for line in lines]
    return lines


def braille_lines(markdown: str, text_braille: BrailleOf, math_braille: BrailleOf, layout: BrfLayout) -> list[str]:
    """The document's braille lines (Unicode braille), a blank line between blocks."""
    lines: list[str] = []
    for block in _blocks(markdown, text_braille, math_braille):
        if lines:
            lines.append("")
        lines.extend(_lay_out(block, layout.cells_per_line))
    return lines


# Nemeth within UEB text (UEB rule 14.6, BANA's Nemeth guidance): the opening
# Nemeth Code indicator and a space before the maths, a space and the
# Nemeth Code terminator after it; their spaces stand for nothing in print.
OPEN_NEMETH = "⠸⠩"
CLOSE_NEMETH = "⠸⠱"


def nemeth_in_ueb(cells: str) -> str:
    """An equation's Nemeth cells between the switch indicators UEB text needs around them."""
    return f"{OPEN_NEMETH}{BLANK}{cells}{BLANK}{CLOSE_NEMETH}"


def _paginate(lines: Sequence[str], layout: BrfLayout, first: int, page_number: BrailleOf | None) -> list[list[str]]:
    """Lines in pages; with `page_number`, each page's number at the right of its last line (BANA Braille
    Formats 1.15.1: at least three blank cells before it), a line it does not leave room on moving on."""
    pages: list[list[str]] = []
    queue = list(lines)
    width, height = layout.cells_per_line, layout.lines_per_page
    while queue or not pages:
        page = queue[:height]
        del queue[: len(page)]
        if page_number is not None:
            number = page_number(str(first + len(pages)))
            page += [""] * (height - len(page))
            last = page[-1].rstrip(BLANK)
            if len(last) + 3 + len(number) > width and height > 1:
                queue.insert(0, last)  # The number's line: the text goes on the next page.
                last = ""
            page[-1] = last + BLANK * (width - len(last) - len(number)) + number
        pages.append(page)
    return pages


def brf_pages(sections: Sequence[Sequence[str]], layout: BrfLayout, page_number: BrailleOf | None = None) -> str:
    """Sections of lines as a BRF file, each starting a new page: Braille ASCII, CR LF line ends, a form
    feed after each page; `page_number` (the text's braille for "12") numbers the pages from 1."""
    pages: list[list[str]] = []
    for section in sections:
        pages.extend(_paginate(section, layout, len(pages) + 1, page_number))
    return "".join("\r\n".join(ascii_braille(line).rstrip(" ") for line in page) + "\r\n\f" for page in pages)


def notebook_brf(
    pages: Sequence[ExportPage],
    text_braille: BrailleOf,
    math_braille: BrailleOf,
    layout: BrfLayout = STANDARD,
    page_numbers: bool = True,
) -> str:
    """Every page, its title as a main heading, each starting on a new braille page, the pages numbered."""
    sections = [
        braille_lines(
            (f"# {page.title}\n\n" if len(pages) > 1 else "") + page.source, text_braille, math_braille, layout
        )
        for page in pages
    ]
    return brf_pages(sections or [[]], layout, text_braille if page_numbers else None)
