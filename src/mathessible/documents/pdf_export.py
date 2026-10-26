"""A Markdown document as Typst source, for a tagged, accessible PDF.

The Markdown goes through markdown-it, each equation through the
converter (MathML) and `typst_math`; its spoken form (MathCAT's) is the
equation's `alt`, which Typst writes into the PDF's Formula tag. Text is
escaped for Typst markup, so nothing in a document is Typst code. The
page, text, numbering, outline, metadata, attachments and PDF standard
come from `PdfOptions`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from markdown_it import MarkdownIt

from mathessible.documents.html_export import ExportPage
from mathessible.documents.markdown_math import find_math_zones
from mathessible.documents.typst_math import TypstEquation


@dataclass(frozen=True, slots=True)
class PdfOptions:
    paper: str = "a4"  # Typst's paper names: "a4", "us-letter", "a5"...
    landscape: bool = False
    margins_mm: tuple[float, float, float, float] = (25, 25, 25, 25)  # Top, right, bottom, left.
    font: str = "Libertinus Serif"
    font_size: float = 11
    line_spacing: float = 0.65  # Typst's leading, in em.
    justify: bool = False
    page_numbers: bool = True
    page_number_position: str = "bottom-center"  # "bottom-center", "bottom-right", "top-right".
    header: str = ""  # Text at the top of every page; "" for none.
    title: str = ""
    author: str = ""
    subject: str = ""
    keywords: tuple[str, ...] = ()
    language: str = "en"
    table_of_contents: bool = False
    attach_source: bool = True  # The Markdown, so the PDF can be opened in Mathessible again.
    standards: tuple[str, ...] = ()  # Typst's: "ua-1", "a-2a", "a-3a"...
    watermark: str = ""  # Across every page, faint; "" for none.
    equation_numbering: str = ""  # Typst numbering of display equations: "(1)", "[1]"; "" for none.
    heading_numbering: str = ""  # "1.", "1.1."; "" for none.
    text_colour: str = ""  # "#1a1a1a"; "" for Typst's black.
    heading_colour: str = ""
    link_colour: str = ""
    columns: int = 1


# An equation's Typst math and spoken form; None when it does not build.
EquationOf = Callable[[str], tuple[TypstEquation | None, str]]

# Typst markup's own characters, written escaped in text.
_MARKUP = set("\\/[]{}#*_+=`$~-<>@\"'")
_COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")
_POSITIONS = {"bottom-center": "center + bottom", "bottom-right": "right + bottom", "top-right": "right + top"}


def escape_markup(text: str) -> str:
    return "".join("\\" + character if character in _MARKUP else character for character in text)


def typst_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _placeholder(index: int) -> str:
    return f"\ue000{index}\ue001"


_PLACEHOLDER = re.compile("\ue000(\\d+)\ue001")


class _Writer:
    def __init__(self, markdown: str, equation_of: EquationOf):
        self.zones = find_math_zones(markdown)
        self.sources = [zone.content(markdown) for zone in self.zones]
        self.equation_of = equation_of
        transformed = markdown
        for index, zone in reversed(list(enumerate(self.zones))):
            mark = _placeholder(index)
            transformed = (
                transformed[: zone.start] + (f"\n\n{mark}\n\n" if zone.display else mark) + transformed[zone.end :]
            )
        self.tokens = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"]).parse(transformed)

    def equation(self, index: int, block: bool) -> str:
        source = self.sources[index]
        math, speech = self.equation_of(source)
        if math is None:
            return f"#raw({typst_string(source)})"  # Does not build: its UnicodeMath, as code.
        arguments = [f"alt: {typst_string(speech or source)}"]
        if block:
            arguments.insert(0, "block: true")
            if math.number:
                arguments.append(f"numbering: _ => {typst_string(math.number)}")
        return f"#math.equation({', '.join(arguments)}, ${math.math}$)"

    def text(self, text: str) -> str:
        """Plain text with equation marks."""
        parts: list[str] = []
        position = 0
        for match in _PLACEHOLDER.finditer(text):
            parts.append(escape_markup(text[position : match.start()]))
            index = int(match.group(1))
            parts.append(self.equation(index, self.zones[index].display))
            position = match.end()
        parts.append(escape_markup(text[position:]))
        return "".join(parts)

    def inline(self, token: object) -> str:
        out: list[str] = []
        closers: list[str] = []
        for child in token.children or ():
            kind = child.type
            if kind == "text":
                out.append(self.text(child.content))
            elif kind == "code_inline":
                out.append(f"#raw({typst_string(child.content)})")
            elif kind == "softbreak":
                out.append(" ")
            elif kind == "hardbreak":
                out.append(" \\\n")
            elif kind in ("em_open", "strong_open", "s_open"):
                out.append({"em_open": "#emph[", "strong_open": "#strong[", "s_open": "#strike["}[kind])
                closers.append("]")
            elif kind in ("em_close", "strong_close", "s_close"):
                out.append(closers.pop() if closers else "")
            elif kind == "link_open":
                out.append(f"#link({typst_string(child.attrGet('href') or '')})[")
                closers.append("]")
            elif kind == "link_close":
                out.append(closers.pop() if closers else "")
            elif kind == "image":
                out.append(escape_markup(child.content))
        return "".join(out)

    def body(self) -> str:
        lines: list[str] = []
        lists: list[str] = []  # "-" or "+", per open list.
        quote_depth = 0
        table: list[list[str]] | None = None
        header_cells = 0
        in_cell = False
        heading = 0
        for token in self.tokens:
            kind = token.type
            indent = "  " * max(0, len(lists) - 1)
            if kind == "heading_open":
                heading = int(token.tag[1])
            elif kind == "heading_close":
                heading = 0
            elif kind in ("bullet_list_open", "ordered_list_open"):
                lists.append("+" if kind == "ordered_list_open" else "-")
            elif kind in ("bullet_list_close", "ordered_list_close"):
                lists.pop()
                lines.append("")
            elif kind == "blockquote_open":
                quote_depth += 1
                lines.append("#quote(block: true)[")
            elif kind == "blockquote_close":
                quote_depth -= 1
                lines.append("]")
            elif kind in ("fence", "code_block"):
                language = (token.info or "").split(" ")[0]
                lines.append(f"#raw(block: true, lang: {typst_string(language) if language else 'none'}, ")
                lines.append(f"  {typst_string(token.content.rstrip(chr(10)))})")
                lines.append("")
            elif kind == "hr":
                lines.append("#line(length: 100%)")
                lines.append("")
            elif kind == "table_open":
                table, header_cells = [], 0
            elif kind == "tr_open" and table is not None:
                table.append([])
            elif kind in ("th_open", "td_open"):
                in_cell = True
                if kind == "th_open":
                    header_cells += 1
            elif kind in ("th_close", "td_close"):
                in_cell = False
            elif kind == "table_close" and table is not None:
                lines.append(self.table(table, header_cells))
                table = None
            elif kind == "inline":
                content = self.inline(token)
                if in_cell and table is not None:
                    table[-1].append(content)
                elif heading:
                    lines.append(f"{'=' * heading} {content}")
                    lines.append("")
                elif lists and token.level > 0 and self._first_in_item(token):
                    lines.append(f"{indent}{lists[-1]} {content}")
                elif lists:
                    lines.append(f"{indent}  {content}")
                else:
                    lines.append(content)
                    lines.append("")
        return "\n".join(lines)

    def _first_in_item(self, token: object) -> bool:
        index = self.tokens.index(token)
        return index >= 2 and self.tokens[index - 2].type == "list_item_open"

    @staticmethod
    def table(rows: list[list[str]], header_cells: int) -> str:
        columns = max((len(row) for row in rows), default=1)
        cells: list[str] = []
        for number, row in enumerate(rows):
            padded = row + [""] * (columns - len(row))
            text = ", ".join(f"[{cell}]" for cell in padded)
            cells.append(f"table.header({text})" if number == 0 and header_cells else text)
        return f"#table(columns: {columns}, " + ", ".join(cells) + ")\n"


def _preamble(options: PdfOptions, title: str) -> str:
    top, right, bottom, left = options.margins_mm
    metadata = [f"title: {typst_string(options.title or title)}"]
    if options.author:
        metadata.append(f"author: {typst_string(options.author)}")
    if options.subject:
        metadata.append(f"description: {typst_string(options.subject)}")
    if options.keywords:
        metadata.append("keywords: (" + "".join(f"{typst_string(word)}, " for word in options.keywords) + ")")
    page = [
        f"paper: {typst_string(options.paper)}",
        f"flipped: {'true' if options.landscape else 'false'}",
        f"margin: (top: {top}mm, right: {right}mm, bottom: {bottom}mm, left: {left}mm)",
    ]
    if options.page_numbers:
        page.append('numbering: "1"')
        page.append(f"number-align: {_POSITIONS.get(options.page_number_position, 'center + bottom')}")
    if options.header:
        page.append(f"header: align(right, {typst_string(options.header)})")
    if options.columns > 1:
        page.append(f"columns: {int(options.columns)}")
    if options.watermark:
        # Page background: an artifact for screen readers, not part of the text.
        page.append(f"background: rotate(-45deg, text(64pt, fill: luma(88%), {typst_string(options.watermark)}))")
    styles = []
    if options.equation_numbering:
        styles.append(f"#set math.equation(numbering: {typst_string(options.equation_numbering)})")
    for target, colour in (
        ("", options.text_colour),
        ("heading", options.heading_colour),
        ("link", options.link_colour),
    ):
        if _COLOUR.match(colour):
            rule = f"set text(fill: rgb({typst_string(colour)}))"
            styles.append(f"#{rule}" if not target else f"#show {target}: {rule}")
    heading = typst_string(options.heading_numbering) if options.heading_numbering else "none"
    return "\n".join(
        [
            f"#set document({', '.join(metadata)})",
            f"#set text(lang: {typst_string(options.language)}, font: {typst_string(options.font)}, "
            f"size: {options.font_size}pt)",
            f"#set page({', '.join(page)})",
            f"#set par(justify: {'true' if options.justify else 'false'}, leading: {options.line_spacing}em)",
            f"#set heading(numbering: {heading})",
            *styles,
            "",
        ]
    )


def typst_document(pages: Sequence[ExportPage], title: str, equation_of: EquationOf, options: PdfOptions) -> str:
    """The whole Typst source: settings, outline, every page (a notebook's under their titles), attachments.

    The Markdown of an attached source is read from `sys.inputs` (see `pdf_inputs`), never written into the code.
    """
    parts = [_preamble(options, title)]
    if options.table_of_contents:
        parts.append("#outline()\n#pagebreak()\n")
    for number, page in enumerate(pages):
        if len(pages) > 1:
            if number:
                parts.append("#pagebreak()")
            parts.append(f"= {escape_markup(page.title)}\n")
        parts.append(_Writer(page.source, equation_of).body())
    if options.attach_source:
        for number, page in enumerate(pages):
            name = f"{page.title or 'document'}.md" if len(pages) > 1 else f"{title or 'document'}.md"
            parts.append(
                f"#pdf.attach({typst_string(name)}, bytes(sys.inputs.at({typst_string(f'page{number}')})), "
                'mime-type: "text/markdown", relationship: "source", '
                'description: "The Markdown source, to edit in Mathessible")'
            )
    return "\n".join(parts) + "\n"


def pdf_inputs(pages: Sequence[ExportPage]) -> dict[str, str]:
    """The `sys.inputs` the attachments read: each page's Markdown."""
    return {f"page{number}": page.source for number, page in enumerate(pages)}
