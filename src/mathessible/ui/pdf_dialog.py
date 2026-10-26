from __future__ import annotations

from dataclasses import dataclass, field

from mathessible.documents.pdf_security import PdfSecurity

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
    security: PdfSecurity = field(default_factory=PdfSecurity)  # Asked each time, never kept.


if wx is not None:

    class PdfPropertiesDialog(wx.Dialog):
        """File > Export > PDF: the document's properties, which the PDF keeps (and PDF/UA requires a title
        and a language). Native controls only, no announcements of its own."""

        def __init__(self, parent: wx.Window, properties: PdfProperties):
            super().__init__(parent, title="PDF Document Properties", style=wx.DEFAULT_DIALOG_STYLE)
            self.SetName("PDF document properties dialog")
            grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=12)
            grid.AddGrowableCol(1)

            def text_field(label: str, value: str, name: str, style: int = 0) -> wx.TextCtrl:
                control = wx.TextCtrl(self, value=value, size=(320, -1), style=style)
                control.SetName(name)
                grid.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
                grid.Add(control, 1, wx.EXPAND)
                return control

            self.title = text_field("&Title", properties.title, "Title")
            self.author = text_field("&Author", properties.author, "Author")
            self.subject = text_field("&Subject", properties.subject, "Subject")
            self.keywords = text_field("&Keywords (comma-separated)", ", ".join(properties.keywords), "Keywords")
            self.language = text_field("&Language (for example ro, en)", properties.language, "Language")
            security = wx.StaticBoxSizer(wx.VERTICAL, self, "Security (optional)")
            box = security.GetStaticBox()
            secrets = wx.FlexGridSizer(cols=2, vgap=8, hgap=12)
            secrets.AddGrowableCol(1)
            self.open_password = wx.TextCtrl(box, style=wx.TE_PASSWORD, size=(240, -1))
            self.open_password.SetName("Password to open")
            self.permissions_password = wx.TextCtrl(box, style=wx.TE_PASSWORD, size=(240, -1))
            self.permissions_password.SetName("Password for permissions")
            secrets.Add(wx.StaticText(box, label="Password to &open"), 0, wx.ALIGN_CENTER_VERTICAL)
            secrets.Add(self.open_password, 1, wx.EXPAND)
            secrets.Add(wx.StaticText(box, label="Password for &permissions"), 0, wx.ALIGN_CENTER_VERTICAL)
            secrets.Add(self.permissions_password, 1, wx.EXPAND)
            security.Add(secrets, 0, wx.ALL | wx.EXPAND, 8)
            self.allow_printing = wx.CheckBox(box, label="Allow p&rinting")
            self.allow_copying = wx.CheckBox(box, label="Allow &copying text (screen readers can always read)")
            self.allow_editing = wx.CheckBox(box, label="Allow &editing")
            for checkbox in (self.allow_printing, self.allow_copying, self.allow_editing):
                checkbox.SetValue(True)
                security.Add(checkbox, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
            buttons = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(grid, 0, wx.ALL | wx.EXPAND, 12)
            sizer.Add(security, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 12)
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
                PdfSecurity(
                    self.open_password.GetValue(),
                    self.permissions_password.GetValue(),
                    self.allow_printing.GetValue(),
                    self.allow_copying.GetValue(),
                    self.allow_editing.GetValue(),
                ),
            )

else:

    class PdfPropertiesDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
