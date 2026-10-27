"""The export controls: the same in Settings (the defaults) and in each export's dialog (this file),
so the two never differ. Each set reads its values from an `AppSettings` and writes them back with
`store`."""

from __future__ import annotations

from collections.abc import Callable

from mathessible.i18n import N_, _
from mathessible.settings import (
    BRAILLE_CODES,
    BRF_CELLS,
    BRF_LINES,
    DOCX_LINE_SPACINGS,
    HTML_COLOUR_SCHEMES,
    HTML_FONTS,
    PDF_COLOURS,
    PDF_COLUMNS,
    PDF_EQUATION_NUMBERING,
    PDF_FONT_SIZES,
    PDF_HEADING_NUMBERING,
    PDF_MARGINS,
    PDF_NUMBER_POSITIONS,
    PDF_PAPERS,
    PDF_STANDARDS,
    AppSettings,
)
from mathessible.symbols.system_languages import preferred_languages
from mathessible.symbols.text_braille import default_table, text_tables

try:
    import wx
except ImportError:
    wx = None

# The fonts Typst brings with it, offered first: they are in every PDF it writes.
TYPST_FONTS = ("Libertinus Serif", "New Computer Modern", "DejaVu Sans Mono")
Options = tuple[tuple[str, str], ...]
# The margins in Settings' order (Typst's and Word's): each one's label and its spin control's name.
MARGIN_SIDES = (
    (N_("&Top"), N_("Top margin (mm)")),
    (N_("&Right"), N_("Right margin (mm)")),
    (N_("&Bottom"), N_("Bottom margin (mm)")),
    (N_("&Left"), N_("Left margin (mm)")),
)


def _chosen(control: object, options: Options, current: str) -> str:
    index = control.GetSelection()
    return options[index][0] if index != wx.NOT_FOUND else current


if wx is not None:

    class FormRows:
        """Labelled controls in two columns on a page, checkboxes under them; every change calls `changed`."""

        def __init__(self, page: wx.Window, changed: Callable[[], None] | None = None):
            self.page = page
            self.changed = changed or (lambda: None)
            self.grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=12)
            self.grid.AddGrowableCol(1)
            self.checkboxes: list[wx.CheckBox] = []

        def row(self, label: str, control: wx.Window, name: str) -> wx.Window:
            control.SetName(name)
            self.grid.Add(wx.StaticText(self.page, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            self.grid.Add(control, 0, wx.EXPAND)
            return control

        def row_of(self, label: str, sizer: wx.Sizer) -> None:
            self.grid.Add(wx.StaticText(self.page, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            self.grid.Add(sizer, 0, wx.EXPAND)

        def choice(self, options: Options, value: str) -> wx.Choice:
            control = wx.Choice(self.page, choices=[_(label) for _value, label in options])
            values = [option for option, _label in options]
            control.SetSelection(values.index(value) if value in values else 0)
            control.Bind(wx.EVT_CHOICE, lambda _event: self.changed())
            return control

        def spin(self, value: int, bounds: tuple[int, int], parent: wx.Window | None = None) -> wx.SpinCtrl:
            control = wx.SpinCtrl(parent or self.page, min=bounds[0], max=bounds[1], initial=value)
            control.Bind(wx.EVT_SPINCTRL, lambda _event: self.changed())
            return control

        def text(self, value: str) -> wx.TextCtrl:
            control = wx.TextCtrl(self.page, value=value)
            control.Bind(wx.EVT_KILL_FOCUS, lambda event: (self.changed(), event.Skip()))
            return control

        def checkbox(self, label: str, name: str, value: bool) -> wx.CheckBox:
            control = wx.CheckBox(self.page, label=label)
            control.SetName(name)
            control.SetValue(value)
            control.Bind(wx.EVT_CHECKBOX, lambda _event: self.changed())
            self.checkboxes.append(control)
            return control

        def finish(self, sizer: wx.Sizer) -> None:
            """Add the rows, then the checkboxes, to the page's `sizer`."""
            sizer.Add(self.grid, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)
            for control in self.checkboxes:
                sizer.Add(control, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)

    class PdfLayoutControls:
        """The page and the text: paper, orientation, margins, columns, font, size, spacing, justification."""

        def __init__(self, rows: FormRows, settings: AppSettings):
            page = rows.page
            self.paper = rows.row(_("&Paper"), rows.choice(PDF_PAPERS, settings.pdf_paper), _("Paper"))
            margins = wx.BoxSizer(wx.HORIZONTAL)
            self.margins: list[wx.SpinCtrl] = []
            for (label, name), value in zip(MARGIN_SIDES, settings.pdf_margins, strict=True):
                margins.Add(wx.StaticText(page, label=_(label)), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
                spin = rows.spin(value, PDF_MARGINS)
                spin.SetName(_(name))
                margins.Add(spin, 0, wx.RIGHT, 10)
                self.margins.append(spin)
            rows.row_of(_("Margins (mm)"), margins)
            self.columns = rows.row(_("Colu&mns"), rows.spin(settings.pdf_columns, PDF_COLUMNS), _("Columns"))
            installed = sorted(set(wx.FontEnumerator().GetFacenames()) - set(TYPST_FONTS), key=str.casefold)
            self.fonts = [*TYPST_FONTS, *installed]
            self.font = rows.row(_("&Font"), wx.Choice(page, choices=self.fonts), _("Font"))
            self.font.SetSelection(self.fonts.index(settings.pdf_font) if settings.pdf_font in self.fonts else 0)
            self.font.Bind(wx.EVT_CHOICE, lambda _event: rows.changed())
            self.font_size = rows.row(
                _("Font si&ze (pt)"), rows.spin(settings.pdf_font_size, PDF_FONT_SIZES), _("Font size")
            )
            self.line_spacing = rows.row(
                _("Line s&pacing (em)"),
                wx.SpinCtrlDouble(page, min=0.2, max=3, initial=settings.pdf_line_spacing, inc=0.05),
                _("Line spacing"),
            )
            self.line_spacing.Bind(wx.EVT_SPINCTRLDOUBLE, lambda _event: rows.changed())
            self.landscape = rows.checkbox(_("Lan&dscape"), _("Landscape"), settings.pdf_landscape)
            self.justify = rows.checkbox(_("&Justify the text"), _("Justify the text"), settings.pdf_justify)

        def store(self, settings: AppSettings) -> None:
            settings.pdf_paper = _chosen(self.paper, PDF_PAPERS, settings.pdf_paper)
            settings.pdf_margins = tuple(control.GetValue() for control in self.margins)
            settings.pdf_columns = self.columns.GetValue()
            font = self.font.GetSelection()
            if font != wx.NOT_FOUND:
                settings.pdf_font = self.fonts[font]
            settings.pdf_font_size = self.font_size.GetValue()
            settings.pdf_line_spacing = round(self.line_spacing.GetValue(), 2)
            settings.pdf_landscape = self.landscape.GetValue()
            settings.pdf_justify = self.justify.GetValue()

    class PdfContentControls:
        """Numbering, colours, the table of contents and the attached source."""

        def __init__(self, rows: FormRows, settings: AppSettings):
            self.number_position = rows.row(
                _("Page number p&osition"),
                rows.choice(PDF_NUMBER_POSITIONS, settings.pdf_page_number_position),
                _("Page number position"),
            )
            self.heading_numbering = rows.row(
                _("Heading n&umbers"),
                rows.choice(PDF_HEADING_NUMBERING, settings.pdf_heading_numbering),
                _("Heading numbers"),
            )
            self.equation_numbering = rows.row(
                _("E&quation numbers"),
                rows.choice(PDF_EQUATION_NUMBERING, settings.pdf_equation_numbering),
                _("Equation numbers"),
            )
            self.text_colour = rows.row(
                _("Te&xt colour"), rows.choice(PDF_COLOURS, settings.pdf_text_colour), _("Text colour")
            )
            self.heading_colour = rows.row(
                _("Headin&g colour"), rows.choice(PDF_COLOURS, settings.pdf_heading_colour), _("Heading colour")
            )
            self.link_colour = rows.row(
                _("L&ink colour"), rows.choice(PDF_COLOURS, settings.pdf_link_colour), _("Link colour")
            )
            self.page_numbers = rows.checkbox(_("&Number the pages"), _("Number the pages"), settings.pdf_page_numbers)
            self.table_of_contents = rows.checkbox(
                _("Table of &contents (from the headings)"), _("Table of contents"), settings.pdf_table_of_contents
            )
            self.attach_source = rows.checkbox(
                _("Attach the Markdown &source (the PDF can be opened in Mathessible again)"),
                _("Attach the Markdown source"),
                settings.pdf_attach_source,
            )

        def store(self, settings: AppSettings) -> None:
            settings.pdf_page_number_position = _chosen(
                self.number_position, PDF_NUMBER_POSITIONS, settings.pdf_page_number_position
            )
            settings.pdf_heading_numbering = _chosen(
                self.heading_numbering, PDF_HEADING_NUMBERING, settings.pdf_heading_numbering
            )
            settings.pdf_equation_numbering = _chosen(
                self.equation_numbering, PDF_EQUATION_NUMBERING, settings.pdf_equation_numbering
            )
            settings.pdf_text_colour = _chosen(self.text_colour, PDF_COLOURS, settings.pdf_text_colour)
            settings.pdf_heading_colour = _chosen(self.heading_colour, PDF_COLOURS, settings.pdf_heading_colour)
            settings.pdf_link_colour = _chosen(self.link_colour, PDF_COLOURS, settings.pdf_link_colour)
            settings.pdf_page_numbers = self.page_numbers.GetValue()
            settings.pdf_table_of_contents = self.table_of_contents.GetValue()
            settings.pdf_attach_source = self.attach_source.GetValue()

    class PdfStandardControl:
        def __init__(self, rows: FormRows, settings: AppSettings):
            self.standard = rows.row(
                _("&Standard"), rows.choice(PDF_STANDARDS, settings.pdf_standard), _("PDF standard")
            )

        def store(self, settings: AppSettings) -> None:
            settings.pdf_standard = _chosen(self.standard, PDF_STANDARDS, settings.pdf_standard)

    class BrfControls:
        """BRF: the text's braille table, the page, page numbers."""

        def __init__(self, rows: FormRows, settings: AppSettings):
            self.tables = text_tables()
            files = [table.file for table in self.tables]
            self.table = rows.row(
                _("&Text braille table"),
                wx.Choice(rows.page, choices=[table.name for table in self.tables]),
                _("Text braille table"),
            )
            chosen = settings.braille_text_table or default_table(preferred_languages(), self.tables)
            if chosen in files:
                self.table.SetSelection(files.index(chosen))
            self.table.Bind(wx.EVT_CHOICE, lambda _event: rows.changed())
            self.cells = rows.row(
                _("&Cells per line"), rows.spin(settings.brf_cells_per_line, BRF_CELLS), _("Cells per line")
            )
            self.lines = rows.row(
                _("&Lines per page"), rows.spin(settings.brf_lines_per_page, BRF_LINES), _("Lines per page")
            )
            self.page_numbers = rows.checkbox(
                _("&Number the pages (at the right of each page's last line, as braille formats require)"),
                _("Number the pages"),
                settings.brf_page_numbers,
            )

        def store(self, settings: AppSettings) -> None:
            index = self.table.GetSelection()
            if index != wx.NOT_FOUND:
                settings.braille_text_table = self.tables[index].file
            settings.brf_cells_per_line = self.cells.GetValue()
            settings.brf_lines_per_page = self.lines.GetValue()
            settings.brf_page_numbers = self.page_numbers.GetValue()

    class BrailleCodeControl:
        """The equations' braille code, for one BRF (Settings' code, the braille strip's, by default)."""

        def __init__(self, rows: FormRows, settings: AppSettings):
            self.code = rows.row(
                _("&Equations in"),
                rows.choice(BRAILLE_CODES, settings.braille_code),
                _("Braille code for the equations"),
            )

        def store(self, settings: AppSettings) -> None:
            settings.braille_code = _chosen(self.code, BRAILLE_CODES, settings.braille_code)

    class HtmlControls:
        """HTML: the table of contents, the font and the colours."""

        def __init__(self, rows: FormRows, settings: AppSettings):
            self.font = rows.row(_("&Font"), rows.choice(HTML_FONTS, settings.html_font), _("Font"))
            self.colour_scheme = rows.row(
                _("&Colours"), rows.choice(HTML_COLOUR_SCHEMES, settings.html_colour_scheme), _("Colours")
            )
            self.table_of_contents = rows.checkbox(
                _("Table of &contents (the pages of a notebook, the headings of a document)"),
                _("Table of contents"),
                settings.html_table_of_contents,
            )

        def store(self, settings: AppSettings) -> None:
            settings.html_font = _chosen(self.font, HTML_FONTS, settings.html_font)
            settings.html_colour_scheme = _chosen(self.colour_scheme, HTML_COLOUR_SCHEMES, settings.html_colour_scheme)
            settings.html_table_of_contents = self.table_of_contents.GetValue()

    class DocxControls:
        """Word: the page, the text, page numbers and the table of contents."""

        def __init__(self, rows: FormRows, settings: AppSettings):
            page = rows.page
            self.paper = rows.row(_("&Paper"), rows.choice(PDF_PAPERS, settings.docx_paper), _("Paper"))
            margins = wx.BoxSizer(wx.HORIZONTAL)
            self.margins: list[wx.SpinCtrl] = []
            for (label, name), value in zip(MARGIN_SIDES, settings.docx_margins, strict=True):
                margins.Add(wx.StaticText(page, label=_(label)), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
                spin = rows.spin(value, PDF_MARGINS)
                spin.SetName(_(name))
                margins.Add(spin, 0, wx.RIGHT, 10)
                self.margins.append(spin)
            rows.row_of(_("Margins (mm)"), margins)
            self.fonts = sorted(set(wx.FontEnumerator().GetFacenames()) | {settings.docx_font}, key=str.casefold)
            self.font = rows.row(_("&Font"), wx.Choice(page, choices=self.fonts), _("Font"))
            self.font.SetSelection(self.fonts.index(settings.docx_font))
            self.font.Bind(wx.EVT_CHOICE, lambda _event: rows.changed())
            self.font_size = rows.row(
                _("Font si&ze (pt)"), rows.spin(settings.docx_font_size, PDF_FONT_SIZES), _("Font size")
            )
            self.line_spacing = rows.row(
                _("Line s&pacing"), rows.choice(DOCX_LINE_SPACINGS, settings.docx_line_spacing), _("Line spacing")
            )
            self.landscape = rows.checkbox(_("Lan&dscape"), _("Landscape"), settings.docx_landscape)
            self.justify = rows.checkbox(_("&Justify the text"), _("Justify the text"), settings.docx_justify)
            self.page_numbers = rows.checkbox(_("&Number the pages"), _("Number the pages"), settings.docx_page_numbers)
            self.table_of_contents = rows.checkbox(
                _("Table of &contents (Word fills it in when the document is opened)"),
                _("Table of contents"),
                settings.docx_table_of_contents,
            )

        def store(self, settings: AppSettings) -> None:
            settings.docx_paper = _chosen(self.paper, PDF_PAPERS, settings.docx_paper)
            settings.docx_margins = tuple(control.GetValue() for control in self.margins)
            font = self.font.GetSelection()
            if font != wx.NOT_FOUND:
                settings.docx_font = self.fonts[font]
            settings.docx_font_size = self.font_size.GetValue()
            settings.docx_line_spacing = _chosen(self.line_spacing, DOCX_LINE_SPACINGS, settings.docx_line_spacing)
            settings.docx_landscape = self.landscape.GetValue()
            settings.docx_justify = self.justify.GetValue()
            settings.docx_page_numbers = self.page_numbers.GetValue()
            settings.docx_table_of_contents = self.table_of_contents.GetValue()
