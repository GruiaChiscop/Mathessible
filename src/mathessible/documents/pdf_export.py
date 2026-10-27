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
from dataclasses import dataclass, field

from mathessible.documents.front_matter import HeaderFooter, header_and_footer
from mathessible.documents.front_matter import body as without_front_matter
from mathessible.documents.html_export import ExportPage, markdown_parser
from mathessible.documents.markdown_math import find_math_zones, with_marks
from mathessible.documents.pdf_security import PdfSecurity
from mathessible.documents.typst_math import TypstEquation
from mathessible.settings import AppSettings, pdf_standards


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


@dataclass(frozen=True, slots=True)
class PdfDocument:
    """What belongs to one PDF only, never kept: its properties, watermark and passwords."""

    title: str
    author: str
    subject: str = ""
    keywords: tuple[str, ...] = ()
    language: str = "en"
    watermark: str = ""
    security: PdfSecurity = field(default_factory=PdfSecurity)


def options_for(settings: AppSettings, document: PdfDocument, title: str) -> PdfOptions:
    """One PDF's options: its layout and content (Settings' defaults, or the export dialog's) and its own document."""
    return PdfOptions(
        paper=settings.pdf_paper,
        landscape=settings.pdf_landscape,
        margins_mm=settings.pdf_margins,
        font=settings.pdf_font,
        font_size=settings.pdf_font_size,
        line_spacing=settings.pdf_line_spacing,
        justify=settings.pdf_justify,
        page_numbers=settings.pdf_page_numbers,
        page_number_position=settings.pdf_page_number_position,
        title=document.title or title,
        author=document.author,
        subject=document.subject,
        keywords=document.keywords,
        language=document.language,
        table_of_contents=settings.pdf_table_of_contents,
        attach_source=settings.pdf_attach_source,
        standards=pdf_standards(settings.pdf_standard),
        watermark=document.watermark,
        equation_numbering=settings.pdf_equation_numbering,
        heading_numbering=settings.pdf_heading_numbering,
        text_colour=settings.pdf_text_colour,
        heading_colour=settings.pdf_heading_colour,
        link_colour=settings.pdf_link_colour,
        columns=settings.pdf_columns,
    )


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
    def __init__(self, markdown: str, equation_of: EquationOf, page: int = 0):
        markdown = without_front_matter(markdown)
        self.zones = find_math_zones(markdown)
        self.sources = [zone.content(markdown) for zone in self.zones]
        self.equation_of = equation_of
        self.page = page
        self.tokens = markdown_parser().parse(with_marks(markdown, self.zones, _placeholder))
        self.notes: dict[int, str] = {}
        self.notes = self._notes()

    def _notes(self) -> dict[int, str]:
        """Each footnote's text, by its number, written where it is referenced (Typst's footnotes)."""
        notes: dict[int, str] = {}
        current: int | None = None
        for token in self.tokens:
            if token.type == "footnote_open":
                current = token.meta["id"]
                notes[current] = ""
            elif token.type == "footnote_close":
                current = None
            elif token.type == "inline" and current is not None:
                notes[current] += ("\n\n" if notes[current] else "") + self.inline(token)
        return notes

    def footnote(self, meta: dict) -> str:
        label = f"<mathessible-note-{self.page}-{meta['id']}>"
        if meta.get("subId", 0) > 0:
            return f"#footnote({label})"  # A note referenced again: the same number.
        return f"#footnote[{self.notes.get(meta['id'], '')}]{label}"

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
            elif kind == "footnote_ref":
                out.append(self.footnote(child.meta))
        return "".join(out)

    def body(self) -> str:
        lines: list[str] = []
        lists: list[str] = []  # "-" or "+", per open list.
        quote_depth = 0
        table: list[list[str]] | None = None
        header_cells = 0
        in_cell = False
        heading = 0
        in_notes = False
        for token in self.tokens:
            kind = token.type
            indent = "  " * max(0, len(lists) - 1)
            if kind in ("footnote_block_open", "footnote_block_close"):
                in_notes = kind == "footnote_block_open"  # The notes are written at their references.
            elif in_notes:
                continue
            elif kind == "heading_open":
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


def _running_heads(options: PdfOptions, running: HeaderFooter) -> list[str]:
    """The document's header and footer, as `set page` arguments: the text at the left, the page number
    (when it shares the line) at its own place."""
    position = options.page_number_position if options.page_numbers else ""
    arguments = []
    for name, text, line in (("header", running.header, "top"), ("footer", running.footer, "bottom")):
        if not text:
            continue
        number = 'context counter(page).display("1")'
        cell = f"align(left, text({typst_string(text)}))"
        if position == f"{line}-center":
            value = f"grid(columns: (1fr, auto, 1fr), {cell}, {number}, [])"
        elif position == f"{line}-right":
            value = f"grid(columns: (1fr, auto), column-gutter: 1em, {cell}, {number})"
        else:
            value = cell
        arguments.append(f"{name}: {value}")
    return arguments


def _preamble(options: PdfOptions, title: str, running: HeaderFooter) -> str:
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
    page.extend(_running_heads(options, running))
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
    heads = [header_and_footer(page.source) for page in pages]
    parts = [_preamble(options, title, heads[0] if heads else HeaderFooter())]
    if options.table_of_contents:
        parts.append("#outline()\n#pagebreak()\n")
    for number, page in enumerate(pages):
        if len(pages) > 1:
            if number and heads[number] != heads[number - 1]:
                # A notebook page's own header and footer: `set page` starts its page.
                none = ["header: auto", "footer: auto"]  # Typst's own: the page number, if any.
                arguments = _running_heads(options, heads[number])
                names = {argument.split(":")[0] for argument in arguments}
                arguments += [argument for argument in none if argument.split(":")[0] not in names]
                parts.append(f"#set page({', '.join(arguments)})")
            elif number:
                parts.append("#pagebreak()")
            parts.append(f"= {escape_markup(page.title)}\n")
        parts.append(_Writer(page.source, equation_of, number).body())
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
