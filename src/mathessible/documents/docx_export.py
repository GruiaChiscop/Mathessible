"""A Markdown document as a Word document (DOCX), every equation a native Word equation.

The Markdown goes through markdown-it, each equation through the
converter (MathML) and `omml_math`, written into the paragraph as Office
Math: inline in its line, a display equation as a paragraph of its own.
Headings use Word's Heading styles (navigation pane, table of contents,
screen readers), lists its List styles, the document's properties and
language are set, and the page, font, page numbers and a table of
contents come from `DocxOptions`.
"""

from __future__ import annotations

import io
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from xml.sax.saxutils import escape

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Mm, Pt
from markdown_it import MarkdownIt

from mathessible.documents.html_export import ExportPage
from mathessible.documents.markdown_math import find_math_zones
from mathessible.documents.omml_math import M, OmmlEquation

# Paper sizes in millimetres, portrait.
PAPERS = {"a4": (210, 297), "a5": (148, 210), "a3": (297, 420), "us-letter": (215.9, 279.4), "us-legal": (215.9, 355.6)}
_MONOSPACE = "Courier New"


@dataclass(frozen=True, slots=True)
class DocxOptions:
    paper: str = "a4"
    landscape: bool = False
    margins_mm: tuple[float, float, float, float] = (25, 25, 25, 25)  # Top, right, bottom, left.
    font: str = "Calibri"
    font_size: float = 11
    line_spacing: float = 1.15  # A multiple of single spacing.
    justify: bool = False
    page_numbers: bool = True
    table_of_contents: bool = False
    title: str = ""
    author: str = ""
    subject: str = ""
    keywords: tuple[str, ...] = ()
    language: str = "en-US"  # Word's language tag, for proofing and screen readers.


# An equation's Office Math; None when it does not build.
OmmlOf = Callable[[str], OmmlEquation | None]


def _placeholder(index: int) -> str:
    return f"{index}"


_PLACEHOLDER = re.compile("(\\d+)")


def _language_tag(language: str) -> str:
    """Word wants a region: "ro" → "ro-RO", "en" → "en-US"."""
    if "-" in language:
        return language
    return {"en": "en-US", "pt": "pt-PT", "zh": "zh-CN"}.get(language, f"{language}-{language.upper()}")


class _Writer:
    def __init__(self, document: Document, markdown: str, omml_of: OmmlOf):
        self.document = document
        self.zones = find_math_zones(markdown)
        self.sources = [zone.content(markdown) for zone in self.zones]
        self.omml_of = omml_of
        transformed = markdown
        for index, zone in reversed(list(enumerate(self.zones))):
            mark = _placeholder(index)
            transformed = (
                transformed[: zone.start] + (f"\n\n{mark}\n\n" if zone.display else mark) + transformed[zone.end :]
            )
        self.tokens = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"]).parse(transformed)

    # Inline content

    def _equation(self, paragraph: object, index: int) -> None:
        source = self.sources[index]
        equation = self.omml_of(source)
        if equation is None:
            run = paragraph.add_run(source)  # Does not build: its UnicodeMath, as code.
            run.font.name = _MONOSPACE
            return
        paragraph._p.append(parse_xml(equation.xml))

    def _text(self, paragraph: object, text: str, style: dict[str, bool], link: str | None) -> None:
        position = 0
        for match in _PLACEHOLDER.finditer(text):
            self._run(paragraph, text[position : match.start()], style, link)
            self._equation(paragraph, int(match.group(1)))
            position = match.end()
        self._run(paragraph, text[position:], style, link)

    def _run(self, paragraph: object, text: str, style: dict[str, bool], link: str | None) -> None:
        if not text:
            return
        if link:
            self._hyperlink(paragraph, text, link)
            return
        run = paragraph.add_run(text)
        run.bold = style.get("bold") or None
        run.italic = style.get("italic") or None
        if style.get("strike"):
            run.font.strike = True
        if style.get("code"):
            run.font.name = _MONOSPACE

    def _hyperlink(self, paragraph: object, text: str, url: str) -> None:
        relationship = paragraph.part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
        hyperlink = OxmlElement("w:hyperlink")
        hyperlink.set(qn("r:id"), relationship)
        run = OxmlElement("w:r")
        properties = OxmlElement("w:rPr")
        style = OxmlElement("w:rStyle")
        style.set(qn("w:val"), "Hyperlink")
        properties.append(style)
        underline = OxmlElement("w:u")
        underline.set(qn("w:val"), "single")
        properties.append(underline)
        run.append(properties)
        text_element = OxmlElement("w:t")
        text_element.text = text
        text_element.set(qn("xml:space"), "preserve")
        run.append(text_element)
        hyperlink.append(run)
        paragraph._p.append(hyperlink)

    def inline(self, paragraph: object, token: object) -> None:
        style = {"bold": False, "italic": False, "strike": False, "code": False}
        link: str | None = None
        for child in token.children or ():
            kind = child.type
            if kind == "text":
                self._text(paragraph, child.content, style, link)
            elif kind == "code_inline":
                self._run(paragraph, child.content, {**style, "code": True}, link)
            elif kind == "softbreak":
                self._run(paragraph, " ", style, link)
            elif kind == "hardbreak":
                paragraph.add_run().add_break()
            elif kind in ("strong_open", "strong_close"):
                style["bold"] = kind == "strong_open"
            elif kind in ("em_open", "em_close"):
                style["italic"] = kind == "em_open"
            elif kind in ("s_open", "s_close"):
                style["strike"] = kind == "s_open"
            elif kind == "link_open":
                link = child.attrGet("href") or None
            elif kind == "link_close":
                link = None
            elif kind == "image":
                self._run(paragraph, child.content, style, link)

    # Blocks

    def _display(self, index: int) -> None:
        """A display equation: Word's equation paragraph (`m:oMathPara`), centred; its number after it."""
        source = self.sources[index]
        equation = self.omml_of(source)
        paragraph = self.document.add_paragraph()
        if equation is None:
            run = paragraph.add_run(source)
            run.font.name = _MONOSPACE
            return
        math = parse_xml(equation.xml)
        if equation.number:
            # As Word numbers an equation (`#` in its linear format): an array whose line ends in "#(1)".
            number = escape(equation.number.strip("()"))
            math = parse_xml(
                f'<m:oMath xmlns:m="{M}"><m:eqArr><m:e>{equation.body}<m:r><m:t>#</m:t></m:r>'
                f"<m:d><m:e><m:r><m:t>{number}</m:t></m:r></m:e></m:d></m:e></m:eqArr></m:oMath>"
            )
        block = OxmlElement("m:oMathPara")
        block.append(math)
        paragraph._p.append(block)

    def body(self) -> None:
        lists: list[str] = []  # "Bullet" or "Number", per open list.
        quote = 0
        heading = 0
        table: list[list[object]] | None = None
        cell_token: list[object] = []
        rows_tokens: list[list[object]] = []
        for token in self.tokens:
            kind = token.type
            if kind == "heading_open":
                heading = int(token.tag[1])
            elif kind == "heading_close":
                heading = 0
            elif kind in ("bullet_list_open", "ordered_list_open"):
                lists.append("Number" if kind == "ordered_list_open" else "Bullet")
            elif kind in ("bullet_list_close", "ordered_list_close"):
                lists.pop()
            elif kind == "blockquote_open":
                quote += 1
            elif kind == "blockquote_close":
                quote -= 1
            elif kind in ("fence", "code_block"):
                for line in token.content.rstrip("\n").split("\n"):
                    paragraph = self.document.add_paragraph(style="No Spacing")
                    run = paragraph.add_run(line)
                    run.font.name = _MONOSPACE
            elif kind == "hr":
                self._rule()
            elif kind == "table_open":
                table, rows_tokens = [], []
            elif kind == "tr_open" and table is not None:
                rows_tokens.append([])
            elif kind in ("th_open", "td_open"):
                cell_token = [kind]
            elif kind == "table_close" and table is not None:
                self._table(rows_tokens)
                table = None
            elif kind == "inline":
                if table is not None and cell_token:
                    rows_tokens[-1].append((cell_token[0], token))
                    cell_token = []
                    continue
                text = "".join(child.content for child in token.children or () if child.type == "text").strip()
                only = _PLACEHOLDER.fullmatch(text)
                if only is not None and self.zones[int(only.group(1))].display and len(token.children or ()) == 1:
                    self._display(int(only.group(1)))
                    continue
                if heading:
                    paragraph = self.document.add_heading(level=min(heading, 9))
                elif lists:
                    level = len(lists)
                    style = f"List {lists[-1]}" + (f" {level}" if 1 < level <= 3 else "")
                    paragraph = self.document.add_paragraph(style=style)
                elif quote:
                    paragraph = self.document.add_paragraph(style="Quote")
                else:
                    paragraph = self.document.add_paragraph()
                self.inline(paragraph, token)

    def _table(self, rows: list[list[tuple[str, object]]]) -> None:
        columns = max((len(row) for row in rows), default=1)
        table = self.document.add_table(rows=len(rows), cols=columns)
        table.style = "Table Grid"
        for row_index, row in enumerate(rows):
            for column, (kind, token) in enumerate(row):
                paragraph = table.cell(row_index, column).paragraphs[0]
                self.inline(paragraph, token)
                if kind == "th_open":
                    for run in paragraph.runs:
                        run.bold = True
        self.document.add_paragraph()

    def _rule(self) -> None:
        paragraph = self.document.add_paragraph()
        borders = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        for name, value in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", "auto")):
            bottom.set(qn(name), value)
        borders.append(bottom)
        paragraph._p.get_or_add_pPr().append(borders)


def _field(paragraph: object, instruction: str, placeholder: str = "") -> None:
    """A Word field (PAGE, TOC), its result filled in when Word updates the fields."""
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    run._r.append(begin)
    code = OxmlElement("w:instrText")
    code.set(qn("xml:space"), "preserve")
    code.text = f" {instruction} "
    run._r.append(code)
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    run._r.append(separate)
    if placeholder:
        run._r.append(_text_element(placeholder))
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(end)


def _text_element(text: str) -> object:
    element = OxmlElement("w:t")
    element.text = text
    return element


def _set_up(document: Document, options: DocxOptions, title: str) -> None:
    properties = document.core_properties
    properties.title = options.title or title
    properties.author = options.author
    properties.subject = options.subject
    properties.keywords = ", ".join(options.keywords)
    properties.language = _language_tag(options.language)

    normal = document.styles["Normal"]
    normal.font.name = options.font
    normal.font.size = Pt(options.font_size)
    normal.paragraph_format.line_spacing = options.line_spacing
    if options.justify:
        normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    # The document's language, for proofing and for screen readers.
    defaults = document.styles.element.find(qn("w:docDefaults"))
    if defaults is not None:
        run_defaults = defaults.find(qn("w:rPrDefault"))
        run_properties = run_defaults.find(qn("w:rPr")) if run_defaults is not None else None
        if run_properties is not None:
            language = run_properties.find(qn("w:lang"))
            if language is None:
                language = OxmlElement("w:lang")
                run_properties.append(language)
            language.set(qn("w:val"), _language_tag(options.language))

    section = document.sections[0]
    width, height = PAPERS.get(options.paper, PAPERS["a4"])
    if options.landscape:
        width, height = height, width
        section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = Mm(width), Mm(height)
    top, right, bottom, left = options.margins_mm
    section.top_margin, section.right_margin = Mm(top), Mm(right)
    section.bottom_margin, section.left_margin = Mm(bottom), Mm(left)
    if options.page_numbers:
        footer = section.footer.paragraphs[0]
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _field(footer, "PAGE", "1")


def docx_document(pages: Sequence[ExportPage], title: str, omml_of: OmmlOf, options: DocxOptions) -> bytes:
    """The whole document as DOCX bytes: a notebook's pages under their titles, each on a new page."""
    document = Document()
    _set_up(document, options, title)
    if options.table_of_contents:
        document.add_heading("Contents", level=1)
        _field(document.add_paragraph(), 'TOC \\o "1-3" \\h \\z \\u', "The table of contents is filled in by Word.")
        update = OxmlElement("w:updateFields")
        update.set(qn("w:val"), "true")  # Word offers to fill it in on opening.
        document.settings.element.append(update)
        document.add_page_break()
    for number, page in enumerate(pages):
        if len(pages) > 1:
            if number:
                document.add_page_break()
            document.add_heading(page.title, level=1)
        _Writer(document, page.source, omml_of).body()
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()
