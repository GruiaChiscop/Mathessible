"""The HTML and BRF export dialogs, built as the PDF one is: this file's options, from Settings' defaults,
with Save as Defaults, and whether to open the file once written."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from mathessible.i18n import _
from mathessible.settings import AppSettings

try:
    import wx
except ImportError:
    wx = None


@dataclass(frozen=True, slots=True)
class WordDocument:
    """What belongs to one Word document only, never kept."""

    title: str
    author: str = ""
    subject: str = ""
    keywords: tuple[str, ...] = ()
    language: str = "en"


@dataclass(frozen=True, slots=True)
class HtmlDocument:
    """What belongs to one HTML file only, never kept."""

    title: str
    author: str = ""
    description: str = ""
    language: str = "en"


if wx is not None:
    from mathessible.ui.export_controls import BrailleCodeControl, BrfControls, DocxControls, FormRows, HtmlControls

    def export_buttons(dialog: wx.Dialog, on_save_defaults: Callable[[], None]) -> wx.Sizer:
        """Save as Defaults on the left; Cancel and Export, the default, on the right."""
        defaults = wx.Button(dialog, label=_("Save as &Defaults"))
        defaults.Bind(wx.EVT_BUTTON, lambda _event: on_save_defaults())
        export = wx.Button(dialog, wx.ID_OK, label=_("E&xport"))
        export.SetDefault()
        cancel = wx.Button(dialog, wx.ID_CANCEL)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        buttons.Add(defaults, 0)
        buttons.AddStretchSpacer()
        buttons.Add(cancel, 0, wx.RIGHT, 8)
        buttons.Add(export, 0)
        return buttons

    def open_after_checkbox(parent: wx.Window, settings: AppSettings) -> wx.CheckBox:
        checkbox = wx.CheckBox(parent, label=_("&Open the file once exported"))
        checkbox.SetName(_("Open the file once exported"))
        checkbox.SetValue(settings.export_open_after)
        return checkbox

    def saved_as_defaults(parent: wx.Window, message: str) -> None:
        wx.MessageBox(message, _("Save as Defaults"), wx.OK | wx.ICON_INFORMATION, parent)

    class _ExportDialog(wx.Dialog):
        """One page of options; subclasses add theirs to `self.rows` and say what Save as Defaults stores."""

        def __init__(self, parent: wx.Window, title: str, settings: AppSettings, save_defaults: Callable):
            super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE)
            self.SetName(_("{title} dialog").format(title=title))
            self._settings = replace(settings)  # This file's copy.
            self._save_defaults = save_defaults
            self.panel = wx.Panel(self)
            self.panel.SetSizer(wx.BoxSizer(wx.VERTICAL))
            self.rows = FormRows(self.panel)

        def finish(self) -> None:
            self.rows.finish(self.panel.GetSizer())
            self.open_after = open_after_checkbox(self.panel, self._settings)
            self.panel.GetSizer().Add(self.open_after, 0, wx.ALL, 12)
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(self.panel, 1, wx.EXPAND)
            sizer.Add(export_buttons(self, self._on_save_defaults), 0, wx.ALL | wx.EXPAND, 12)
            self.SetSizerAndFit(sizer)

        def store(self, settings: AppSettings) -> None:
            raise NotImplementedError

        @property
        def settings(self) -> AppSettings:
            self.store(self._settings)
            self._settings.export_open_after = self.open_after.GetValue()
            return self._settings

        def _on_save_defaults(self) -> None:
            self._save_defaults(self.settings)
            saved_as_defaults(self, _("These options are now the defaults."))

    class BrfExportDialog(_ExportDialog):
        """File > Export > BRF: the equations' code, the text's table, the page, page numbers."""

        def __init__(self, parent: wx.Window, settings: AppSettings, save_defaults: Callable[[AppSettings], None]):
            super().__init__(parent, _("Export as BRF"), settings, save_defaults)
            self.code = BrailleCodeControl(self.rows, settings)
            self.brf = BrfControls(self.rows, settings)
            self.finish()
            self.code.code.SetFocus()

        def store(self, settings: AppSettings) -> None:
            self.code.store(settings)
            self.brf.store(settings)

    class HtmlExportDialog(_ExportDialog):
        """File > Export > HTML: the document's title, author, description and language, and the page's look."""

        def __init__(
            self,
            parent: wx.Window,
            settings: AppSettings,
            document: HtmlDocument,
            save_defaults: Callable[[AppSettings], None],
        ):
            super().__init__(parent, _("Export as HTML"), settings, save_defaults)
            rows = self.rows
            self.title = rows.row(_("&Title"), rows.text(document.title), _("Title"))
            self.author = rows.row(_("&Author"), rows.text(document.author), _("Author"))
            self.description = rows.row(_("D&escription"), rows.text(document.description), _("Description"))
            self.language = rows.row(_("&Language (for example ro, en)"), rows.text(document.language), _("Language"))
            self.html = HtmlControls(rows, settings)
            self.finish()
            self.title.SetFocus()

        def store(self, settings: AppSettings) -> None:
            self.html.store(settings)

        @property
        def document(self) -> HtmlDocument:
            language = self.language.GetValue().strip().replace("_", "-").split("-")[0].lower() or "en"
            return HtmlDocument(
                self.title.GetValue().strip(),
                self.author.GetValue().strip(),
                self.description.GetValue().strip(),
                language,
            )

    class DocxExportDialog(_ExportDialog):
        """File > Export > Word Document: the document's properties, the page and the text."""

        def __init__(
            self,
            parent: wx.Window,
            settings: AppSettings,
            document: WordDocument,
            save_defaults: Callable[[AppSettings], None],
        ):
            super().__init__(parent, _("Export as Word Document"), settings, save_defaults)
            rows = self.rows
            self.title = rows.row(_("&Title"), rows.text(document.title), _("Title"))
            self.author = rows.row(_("&Author"), rows.text(document.author), _("Author"))
            self.subject = rows.row(_("&Subject"), rows.text(document.subject), _("Subject"))
            self.keywords = rows.row(
                _("&Keywords (comma-separated)"), rows.text(", ".join(document.keywords)), _("Keywords")
            )
            self.language = rows.row(_("&Language (for example ro, en)"), rows.text(document.language), _("Language"))
            self.docx = DocxControls(rows, settings)
            self.finish()
            self.title.SetFocus()

        def store(self, settings: AppSettings) -> None:
            self.docx.store(settings)

        @property
        def document(self) -> WordDocument:
            keywords = tuple(word.strip() for word in self.keywords.GetValue().split(",") if word.strip())
            language = self.language.GetValue().strip().replace("_", "-").split("-")[0].lower() or "en"
            return WordDocument(
                self.title.GetValue().strip(),
                self.author.GetValue().strip(),
                self.subject.GetValue().strip(),
                keywords,
                language,
            )

else:

    class BrfExportDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")

    HtmlExportDialog = DocxExportDialog = BrfExportDialog  # type: ignore[misc,assignment]
