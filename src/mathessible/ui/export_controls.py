"""The export controls: the same in Settings (the defaults) and in each export's dialog (this file),
so the two never differ. Each set reads its values from an `AppSettings` and writes them back with
`store`."""

from __future__ import annotations

from collections.abc import Callable

from mathessible.settings import (
    BRAILLE_CODES,
    BRF_CELLS,
    BRF_LINES,
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
            control = wx.Choice(self.page, choices=[label for _value, label in options])
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
            self.paper = rows.row("&Paper", rows.choice(PDF_PAPERS, settings.pdf_paper), "Paper")
            margins = wx.BoxSizer(wx.HORIZONTAL)
            self.margins: list[wx.SpinCtrl] = []
            for label, value in zip(("&Top", "&Right", "&Bottom", "&Left"), settings.pdf_margins, strict=True):
                margins.Add(wx.StaticText(page, label=label), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
                spin = rows.spin(value, PDF_MARGINS)
                spin.SetName(f"{label.replace('&', '')} margin (mm)")
                margins.Add(spin, 0, wx.RIGHT, 10)
                self.margins.append(spin)
            rows.row_of("Margins (mm)", margins)
            self.columns = rows.row("Colu&mns", rows.spin(settings.pdf_columns, PDF_COLUMNS), "Columns")
            installed = sorted(set(wx.FontEnumerator().GetFacenames()) - set(TYPST_FONTS), key=str.casefold)
            self.fonts = [*TYPST_FONTS, *installed]
            self.font = rows.row("&Font", wx.Choice(page, choices=self.fonts), "Font")
            self.font.SetSelection(self.fonts.index(settings.pdf_font) if settings.pdf_font in self.fonts else 0)
            self.font.Bind(wx.EVT_CHOICE, lambda _event: rows.changed())
            self.font_size = rows.row("Font si&ze (pt)", rows.spin(settings.pdf_font_size, PDF_FONT_SIZES), "Font size")
            self.line_spacing = rows.row(
                "Line s&pacing (em)",
                wx.SpinCtrlDouble(page, min=0.2, max=3, initial=settings.pdf_line_spacing, inc=0.05),
                "Line spacing",
            )
            self.line_spacing.Bind(wx.EVT_SPINCTRLDOUBLE, lambda _event: rows.changed())
            self.landscape = rows.checkbox("Lan&dscape", "Landscape", settings.pdf_landscape)
            self.justify = rows.checkbox("&Justify the text", "Justify the text", settings.pdf_justify)

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
                "Page number p&osition",
                rows.choice(PDF_NUMBER_POSITIONS, settings.pdf_page_number_position),
                "Page number position",
            )
            self.heading_numbering = rows.row(
                "Heading n&umbers",
                rows.choice(PDF_HEADING_NUMBERING, settings.pdf_heading_numbering),
                "Heading numbers",
            )
            self.equation_numbering = rows.row(
                "E&quation numbers",
                rows.choice(PDF_EQUATION_NUMBERING, settings.pdf_equation_numbering),
                "Equation numbers",
            )
            self.text_colour = rows.row(
                "Te&xt colour", rows.choice(PDF_COLOURS, settings.pdf_text_colour), "Text colour"
            )
            self.heading_colour = rows.row(
                "Headin&g colour", rows.choice(PDF_COLOURS, settings.pdf_heading_colour), "Heading colour"
            )
            self.link_colour = rows.row(
                "L&ink colour", rows.choice(PDF_COLOURS, settings.pdf_link_colour), "Link colour"
            )
            self.page_numbers = rows.checkbox("&Number the pages", "Number the pages", settings.pdf_page_numbers)
            self.table_of_contents = rows.checkbox(
                "Table of &contents (from the headings)", "Table of contents", settings.pdf_table_of_contents
            )
            self.attach_source = rows.checkbox(
                "Attach the Markdown &source (the PDF can be opened in Mathessible again)",
                "Attach the Markdown source",
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
            self.standard = rows.row("&Standard", rows.choice(PDF_STANDARDS, settings.pdf_standard), "PDF standard")

        def store(self, settings: AppSettings) -> None:
            settings.pdf_standard = _chosen(self.standard, PDF_STANDARDS, settings.pdf_standard)

    class BrfControls:
        """BRF: the text's braille table, the page, page numbers."""

        def __init__(self, rows: FormRows, settings: AppSettings):
            self.tables = text_tables()
            files = [table.file for table in self.tables]
            self.table = rows.row(
                "&Text braille table",
                wx.Choice(rows.page, choices=[table.name for table in self.tables]),
                "Text braille table",
            )
            chosen = settings.braille_text_table or default_table(preferred_languages(), self.tables)
            if chosen in files:
                self.table.SetSelection(files.index(chosen))
            self.table.Bind(wx.EVT_CHOICE, lambda _event: rows.changed())
            self.cells = rows.row(
                "&Cells per line", rows.spin(settings.brf_cells_per_line, BRF_CELLS), "Cells per line"
            )
            self.lines = rows.row(
                "&Lines per page", rows.spin(settings.brf_lines_per_page, BRF_LINES), "Lines per page"
            )
            self.page_numbers = rows.checkbox(
                "&Number the pages (at the right of each page's last line, as braille formats require)",
                "Number the pages",
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
                "&Equations in", rows.choice(BRAILLE_CODES, settings.braille_code), "Braille code for the equations"
            )

        def store(self, settings: AppSettings) -> None:
            settings.braille_code = _chosen(self.code, BRAILLE_CODES, settings.braille_code)

    class HtmlControls:
        """HTML: the table of contents, the font and the colours."""

        def __init__(self, rows: FormRows, settings: AppSettings):
            self.font = rows.row("&Font", rows.choice(HTML_FONTS, settings.html_font), "Font")
            self.colour_scheme = rows.row(
                "&Colours", rows.choice(HTML_COLOUR_SCHEMES, settings.html_colour_scheme), "Colours"
            )
            self.table_of_contents = rows.checkbox(
                "Table of &contents (the pages of a notebook, the headings of a document)",
                "Table of contents",
                settings.html_table_of_contents,
            )

        def store(self, settings: AppSettings) -> None:
            settings.html_font = _chosen(self.font, HTML_FONTS, settings.html_font)
            settings.html_colour_scheme = _chosen(self.colour_scheme, HTML_COLOUR_SCHEMES, settings.html_colour_scheme)
            settings.html_table_of_contents = self.table_of_contents.GetValue()
