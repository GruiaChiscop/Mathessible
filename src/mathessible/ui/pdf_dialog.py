from __future__ import annotations

from dataclasses import dataclass

try:
    import wx
except ImportError:
    wx = None


@dataclass(frozen=True, slots=True)
class PdfProperties:
    title: str
    author: str
    subject: str
    keywords: tuple[str, ...]
    language: str


if wx is not None:

    class PdfPropertiesDialog(wx.Dialog):
        """File > Export > PDF: the document's properties, which the PDF keeps (and PDF/UA requires a title
        and a language). Native controls only, no announcements of its own."""

        def __init__(self, parent: wx.Window, properties: PdfProperties):
            super().__init__(parent, title="PDF Document Properties", style=wx.DEFAULT_DIALOG_STYLE)
            self.SetName("PDF document properties dialog")
            grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=12)
            grid.AddGrowableCol(1)

            def field(label: str, value: str, name: str) -> wx.TextCtrl:
                control = wx.TextCtrl(self, value=value, size=(320, -1))
                control.SetName(name)
                grid.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
                grid.Add(control, 1, wx.EXPAND)
                return control

            self.title = field("&Title", properties.title, "Title")
            self.author = field("&Author", properties.author, "Author")
            self.subject = field("&Subject", properties.subject, "Subject")
            self.keywords = field("&Keywords (comma-separated)", ", ".join(properties.keywords), "Keywords")
            self.language = field("&Language (for example ro, en)", properties.language, "Language")
            buttons = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(grid, 0, wx.ALL | wx.EXPAND, 12)
            if buttons is not None:
                sizer.Add(buttons, 0, wx.ALL | wx.EXPAND, 12)
            self.SetSizerAndFit(sizer)
            self.title.SetFocus()

        @property
        def properties(self) -> PdfProperties:
            keywords = tuple(word.strip() for word in self.keywords.GetValue().split(",") if word.strip())
            language = self.language.GetValue().strip().replace("_", "-").split("-")[0].lower() or "en"
            return PdfProperties(
                self.title.GetValue().strip(),
                self.author.GetValue().strip(),
                self.subject.GetValue().strip(),
                keywords,
                language,
            )

else:

    class PdfPropertiesDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
