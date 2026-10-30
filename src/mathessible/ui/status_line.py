"""The document window's status line: the document, the caret's section, the counts, the caret's line.

wx's status bar on macOS draws its fields itself, so VoiceOver could not
read them; these are native labels (NSTextFields) in a row at the window's
foot, which VoiceOver reads when it reaches them, and View > Read Status
says them all without moving the focus (`spoken`).
"""

from __future__ import annotations

from collections.abc import Sequence

from mathessible.i18n import _

try:
    import wx
except ImportError:
    wx = None


if wx is not None:

    class StatusLine(wx.Panel):
        def __init__(self, parent: wx.Window, proportions: Sequence[int]):
            super().__init__(parent)
            self.SetName(_("Status"))
            sizer = wx.BoxSizer(wx.HORIZONTAL)
            self.fields: list[wx.StaticText] = []
            for proportion in proportions:
                field = wx.StaticText(self, label="", style=wx.ST_ELLIPSIZE_END)
                sizer.Add(field, proportion, wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, 6)
                self.fields.append(field)
            outer = wx.BoxSizer(wx.VERTICAL)
            outer.Add(wx.StaticLine(self), 0, wx.EXPAND)
            outer.Add(sizer, 1, wx.EXPAND)
            self.SetSizer(outer)

        def set(self, text: str, number: int = 0) -> None:
            if 0 <= number < len(self.fields) and self.fields[number].GetLabel() != text:
                self.fields[number].SetLabel(text.replace("&", "&&"))

        def spoken(self) -> str:
            """Every field that has something, in order, as one sentence for the screen reader."""
            return "; ".join(field.GetLabel().replace("&&", "&") for field in self.fields if field.GetLabel())

else:

    class StatusLine:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed")
