"""The suggestions shown under the caret while a command is typed in the document (`document_completion`).

The list is spoken too (the current suggestion and how many there are);
this is what a sighted writer sees: a few suggestions around the current
one, which is marked. It never takes the focus, so typing goes on in the
document, where Up/Down browse and Tab takes the current suggestion.
"""

from __future__ import annotations

from mathessible.editing.completion import Completion
from mathessible.ui.theme import palette

try:
    import wx
except ImportError:
    wx = None

_SHOWN = 8  # Suggestions shown at a time, the current one among them.


if wx is not None:

    class CompletionPopup(wx.PopupWindow):
        def __init__(self, parent: wx.Window):
            super().__init__(parent, flags=wx.BORDER_SIMPLE)
            appearance = wx.SystemSettings.GetAppearance() if hasattr(wx.SystemSettings, "GetAppearance") else None
            colors = palette(dark=bool(appearance is not None and appearance.IsDark()))
            self.SetBackgroundColour(wx.Colour(*colors.panel))
            self.text = wx.StaticText(self, label="")
            self.text.SetForegroundColour(wx.Colour(*colors.text))
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(self.text, 0, wx.ALL, 6)
            self.SetSizer(sizer)

        def show(self, completion: Completion, at: wx.Point) -> None:
            """The suggestions around the current one, the current marked, at `at` (screen coordinates)."""
            count = len(completion.suggestions)
            first = max(0, min(completion.index - _SHOWN // 2, count - _SHOWN))
            lines = []
            for index in range(first, min(count, first + _SHOWN)):
                suggestion = completion.suggestions[index]
                word = suggestion.word if completion.environment else f"\\{suggestion.word}"
                text = f"{word}   {suggestion.symbol}" if suggestion.symbol else word
                lines.append(("▸ " if index == completion.index else "   ") + text)
            if count > _SHOWN:
                lines.append(f"   {completion.index + 1} / {count}")
            self.text.SetLabel("\n".join(lines))
            self.Fit()
            self.Position(at, wx.Size(0, 0))
            if not self.IsShown():
                self.Show()

else:

    class CompletionPopup:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed")
