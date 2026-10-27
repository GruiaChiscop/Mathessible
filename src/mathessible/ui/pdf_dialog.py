from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from mathessible.documents.pdf_export import PdfDocument
from mathessible.documents.pdf_security import PdfSecurity
from mathessible.i18n import _
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
        (`save_defaults`), never its title, watermark or passwords. The
        header and footer are the document's (Insert > Header and Footer).
        Native controls only, no announcements of its own.
        """

        def __init__(
            self,
            parent: wx.Window,
            settings: AppSettings,
            document: PdfDocument,
            save_defaults: Callable[[AppSettings], None],
        ):
            super().__init__(parent, title=_("Export as PDF"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
            self.SetName(_("Export as PDF dialog"))
            self._settings = replace(settings)  # This PDF's copy.
            self._save_defaults = save_defaults
            self.notebook = wx.Notebook(self)
            self.notebook.SetName(_("PDF export categories"))

            page = self._page(_("Document"))
            rows = FormRows(page)
            self.title = rows.row(_("&Title"), rows.text(document.title), _("Title"))
            self.author = rows.row(_("&Author"), rows.text(document.author), _("Author"))
            self.subject = rows.row(_("&Subject"), rows.text(document.subject), _("Subject"))
            self.keywords = rows.row(
                _("&Keywords (comma-separated)"), rows.text(", ".join(document.keywords)), _("Keywords")
            )
            self.language = rows.row(_("&Language (for example ro, en)"), rows.text(document.language), _("Language"))
            rows.finish(page.GetSizer())

            page = self._page(_("Layout"))
            rows = FormRows(page)
            self.layout = PdfLayoutControls(rows, settings)
            rows.finish(page.GetSizer())

            page = self._page(_("Content"))
            rows = FormRows(page)
            self.watermark = rows.row(_("&Watermark text"), rows.text(document.watermark), _("Watermark text"))
            self.content = PdfContentControls(rows, settings)
            rows.finish(page.GetSizer())

            page = self._page(_("Security"))
            rows = FormRows(page)
            self.standard = PdfStandardControl(rows, settings)
            self.open_password = rows.row(
                _("Password to &open"), wx.TextCtrl(page, style=wx.TE_PASSWORD), _("Password to open")
            )
            self.permissions_password = rows.row(
                _("Password for &permissions"), wx.TextCtrl(page, style=wx.TE_PASSWORD), _("Password for permissions")
            )
            self.allow_printing = rows.checkbox(
                _("Allow p&rinting"), _("Allow printing"), document.security.allow_printing
            )
            self.allow_copying = rows.checkbox(
                _("Allow &copying text (screen readers can always read)"),
                _("Allow copying text"),
                document.security.allow_copying,
            )
            self.allow_editing = rows.checkbox(_("Allow &editing"), _("Allow editing"), document.security.allow_editing)
            rows.finish(page.GetSizer())
            note = wx.StaticText(page, label=_("Passwords are never kept. PDF/A does not allow them."))
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
            saved_as_defaults(self, _("This layout, content, standard and author are now the defaults."))

else:

    class PdfExportDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
