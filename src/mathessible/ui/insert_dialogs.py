"""The document's Insert dialogs: a link and a table. Native controls only, which screen readers read."""

from __future__ import annotations

from mathessible.i18n import _

try:
    import wx
except ImportError:
    wx = None


if wx is not None:

    class _FormDialog(wx.Dialog):
        def __init__(self, parent: wx.Window, title: str):
            super().__init__(parent, title=title)
            self.grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=12)
            self.grid.AddGrowableCol(1)

        def _row(self, label: str, control: wx.Window, name: str) -> wx.Window:
            control.SetName(name)
            self.grid.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            self.grid.Add(control, 1, wx.EXPAND)
            return control

        def _finish(self, first: wx.Window) -> None:
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(self.grid, 1, wx.ALL | wx.EXPAND, 16)
            buttons = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
            sizer.Add(buttons, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 16)
            self.SetSizerAndFit(sizer)
            self.SetMinSize((420, -1))
            self.Fit()
            first.SetFocus()

    class LinkDialog(_FormDialog):
        """Insert > Link: the text shown (the selection, if there is one) and the address."""

        def __init__(self, parent: wx.Window, text: str = ""):
            super().__init__(parent, _("Insert Link"))
            self.text = self._row(_("&Text:"), wx.TextCtrl(self, value=text), _("Link text"))
            self.address = self._row(_("&Address:"), wx.TextCtrl(self, value="https://"), _("Link address"))
            self._finish(self.address if text else self.text)
            self.address.SetInsertionPointEnd()

    class TableDialog(_FormDialog):
        """Insert > Table: its rows (its header row included) and columns."""

        def __init__(self, parent: wx.Window):
            super().__init__(parent, _("Insert Table"))
            self.rows = self._row(_("&Rows:"), wx.SpinCtrl(self, min=1, max=100, initial=3), _("Rows"))
            self.columns = self._row(_("&Columns:"), wx.SpinCtrl(self, min=1, max=20, initial=3), _("Columns"))
            self.grid.Add((0, 0))
            self.header = wx.CheckBox(self, label=_("First row is the &header"))
            self.header.SetValue(True)
            self.grid.Add(self.header)
            self._finish(self.rows)

else:

    class LinkDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed")

    class TableDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed")
