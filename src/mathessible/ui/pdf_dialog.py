from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from mathessible.documents.pdf_export import PdfDocument
from mathessible.documents.pdf_security import PdfSecurity
from mathessible.settings import AppSettings

try:
    import wx
except ImportError:
    wx = None


if wx is not None:
    from mathessible.ui.export_controls import FormRows, PdfContentControls, PdfLayoutControls, PdfStandardControl
    from mathessible.ui.export_dialogs import export_buttons, open_after_checkbox, saved_as_defaults

    class PdfExportDialog(wx.Dialog):
        """File > Export > PDF: this PDF's properties, layout, content and security, in tabs.

        Layout and content start from Settings → PDF; Save as Defaults
        makes this PDF's layout, content, standard and author the defaults
        (`save_defaults`), never its title, header, watermark or passwords.
        Native controls only, no announcements of its own.
        """

        def __init__(
            self,
            parent: wx.Window,
            settings: AppSettings,
            document: PdfDocument,
            save_defaults: Callable[[AppSettings], None],
        ):
            super().__init__(parent, title="Export as PDF", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
            self.SetName("Export as PDF dialog")
            self._settings = replace(settings)  # This PDF's copy.
            self._save_defaults = save_defaults
            self.notebook = wx.Notebook(self)
            self.notebook.SetName("PDF export categories")

            page = self._page("Document")
            rows = FormRows(page)
            self.title = rows.row("&Title", rows.text(document.title), "Title")
            self.author = rows.row("&Author", rows.text(document.author), "Author")
            self.subject = rows.row("&Subject", rows.text(document.subject), "Subject")
            self.keywords = rows.row("&Keywords (comma-separated)", rows.text(", ".join(document.keywords)), "Keywords")
            self.language = rows.row("&Language (for example ro, en)", rows.text(document.language), "Language")
            rows.finish(page.GetSizer())

            page = self._page("Layout")
            rows = FormRows(page)
            self.layout = PdfLayoutControls(rows, settings)
            rows.finish(page.GetSizer())

            page = self._page("Content")
            rows = FormRows(page)
            self.header = rows.row("&Header text", rows.text(document.header), "Header text")
            self.watermark = rows.row("&Watermark text", rows.text(document.watermark), "Watermark text")
            self.content = PdfContentControls(rows, settings)
            rows.finish(page.GetSizer())

            page = self._page("Security")
            rows = FormRows(page)
            self.standard = PdfStandardControl(rows, settings)
            self.open_password = rows.row(
                "Password to &open", wx.TextCtrl(page, style=wx.TE_PASSWORD), "Password to open"
            )
            self.permissions_password = rows.row(
                "Password for &permissions", wx.TextCtrl(page, style=wx.TE_PASSWORD), "Password for permissions"
            )
            self.allow_printing = rows.checkbox("Allow p&rinting", "Allow printing", document.security.allow_printing)
            self.allow_copying = rows.checkbox(
                "Allow &copying text (screen readers can always read)",
                "Allow copying text",
                document.security.allow_copying,
            )
            self.allow_editing = rows.checkbox("Allow &editing", "Allow editing", document.security.allow_editing)
            rows.finish(page.GetSizer())
            note = wx.StaticText(page, label="Passwords are never kept. PDF/A does not allow them.")
            note.Wrap(420)
            page.GetSizer().Add(note, 0, wx.ALL, 12)

            self.open_after = open_after_checkbox(self, settings)
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 8)
            sizer.Add(self.open_after, 0, wx.LEFT | wx.RIGHT, 12)
            sizer.Add(export_buttons(self, self._on_save_defaults), 0, wx.ALL | wx.EXPAND, 12)
            self.SetSizerAndFit(sizer)
            self.title.SetFocus()

        def _page(self, title: str) -> wx.Panel:
            page = wx.Panel(self.notebook)
            page.SetName(title)
            page.SetSizer(wx.BoxSizer(wx.VERTICAL))
            self.notebook.AddPage(page, title)
            return page

        @property
        def settings(self) -> AppSettings:
            """This PDF's layout, content and standard."""
            self.layout.store(self._settings)
            self.content.store(self._settings)
            self.standard.store(self._settings)
            self._settings.pdf_author = self.author.GetValue().strip()
            self._settings.export_open_after = self.open_after.GetValue()
            return self._settings

        @property
        def document(self) -> PdfDocument:
            keywords = tuple(word.strip() for word in self.keywords.GetValue().split(",") if word.strip())
            language = self.language.GetValue().strip().replace("_", "-").split("-")[0].lower() or "en"
            return PdfDocument(
                self.title.GetValue().strip(),
                self.author.GetValue().strip(),
                self.subject.GetValue().strip(),
                keywords,
                language,
                self.header.GetValue().strip(),
                self.watermark.GetValue().strip(),
                PdfSecurity(
                    self.open_password.GetValue(),
                    self.permissions_password.GetValue(),
                    self.allow_printing.GetValue(),
                    self.allow_copying.GetValue(),
                    self.allow_editing.GetValue(),
                ),
            )

        def _on_save_defaults(self) -> None:
            self._save_defaults(self.settings)
            saved_as_defaults(self, "This layout, content, standard and author")

else:

    class PdfExportDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
