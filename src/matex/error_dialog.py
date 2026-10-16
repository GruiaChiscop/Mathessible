from __future__ import annotations

try:
    import wx
except ImportError:
    wx = None


if wx is not None:

    class ErrorListDialog(wx.Dialog):
        """F8: the equation's errors, one per line; Enter goes to the selected one."""

        def __init__(self, parent: wx.Window, descriptions: list[str]):
            count = len(descriptions)
            super().__init__(
                parent,
                title=f"Errors ({count})",
                style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            )
            self.SetName("Equation errors dialog")
            sizer = wx.BoxSizer(wx.VERTICAL)
            label = wx.StaticText(self, label=f"&{count} error{'' if count == 1 else 's'}; Enter goes to the error")
            self.errors = wx.ListBox(self, choices=descriptions, size=(480, 220), style=wx.LB_SINGLE)
            self.errors.SetName("Errors")
            self.errors.SetSelection(0)
            self.errors.Bind(wx.EVT_LISTBOX_DCLICK, lambda _event: self.EndModal(wx.ID_OK))
            buttons = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
            sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
            sizer.Add(self.errors, 1, wx.ALL | wx.EXPAND, 12)
            if buttons is not None:
                sizer.Add(buttons, 0, wx.ALL | wx.EXPAND, 12)
            ok = self.FindWindowById(wx.ID_OK)
            if ok is not None:
                ok.SetLabel("&Go to Error")
            self.SetSizerAndFit(sizer)
            self.errors.SetFocus()

        @property
        def selected(self) -> int:
            return self.errors.GetSelection()

else:

    class ErrorListDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
