from __future__ import annotations

from mathessible.documents.front_matter import HeaderFooter
from mathessible.i18n import _

try:
    import wx
except ImportError:
    wx = None


if wx is not None:

    class HeaderFooterDialog(wx.Dialog):
        """Insert > Header and Footer: the document's own, kept in its front matter, for the PDF and Word exports."""

        def __init__(self, parent: wx.Window, current: HeaderFooter):
            super().__init__(parent, title=_("Header and Footer"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
            self.SetName(_("Header and footer dialog"))
            sizer = wx.BoxSizer(wx.VERTICAL)
            grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=12)
            grid.AddGrowableCol(1)
            self.header = self._row(grid, _("&Header"), current.header, _("Header"))
            self.footer = self._row(grid, _("&Footer"), current.footer, _("Footer"))
            note = wx.StaticText(
                self,
                label=_(
                    "At the top and bottom of every page of the PDF and Word exports, beside the page number. "
                    "Leave one empty for none."
                ),
            )
            note.Wrap(420)
            buttons = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
            sizer.Add(grid, 0, wx.ALL | wx.EXPAND, 12)
            sizer.Add(note, 0, wx.LEFT | wx.RIGHT, 12)
            if buttons is not None:
                sizer.Add(buttons, 0, wx.ALL | wx.EXPAND, 12)
            self.SetSizerAndFit(sizer)
            self.header.SetFocus()

        def _row(self, grid: wx.FlexGridSizer, label: str, value: str, name: str) -> wx.TextCtrl:
            control = wx.TextCtrl(self, value=value, size=(320, -1))
            control.SetName(name)
            grid.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(control, 0, wx.EXPAND)
            return control

        @property
        def chosen(self) -> HeaderFooter:
            # One line each: a line break would end the front matter's field.
            return HeaderFooter(*(" ".join(control.GetValue().split()) for control in (self.header, self.footer)))

else:

    class HeaderFooterDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
