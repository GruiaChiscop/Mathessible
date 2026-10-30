"""The home screen Mathessible starts with, as other editors do: what to begin, and the recent documents.

It is the first window's own content until a document, a LaTeX document or
a notebook is begun or opened there (`MainFrame._leave_home`), so the menus
and their shortcuts work from it as from any window. Native controls only:
buttons for what to begin, and the recent documents as a list (Enter or a
double click opens one), which screen readers read as they are.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from mathessible.documents.recent_files import menu_labels
from mathessible.i18n import _

try:
    import wx
except ImportError:
    wx = None


if wx is not None:

    class HomePanel(wx.Panel):
        def __init__(
            self,
            parent: wx.Window,
            actions: Sequence[tuple[str, Callable[[], None]]],
            recent: Sequence[str],
            open_recent: Callable[[int], None],
        ):
            super().__init__(parent)
            self.SetName(_("Home"))
            self._open_recent = open_recent
            sizer = wx.BoxSizer(wx.VERTICAL)
            title = wx.StaticText(self, label="Mathessible")
            font = title.GetFont()
            font.SetPointSize(font.GetPointSize() * 2)
            font.MakeBold()
            title.SetFont(font)
            sizer.Add(title, 0, wx.LEFT | wx.RIGHT | wx.TOP, 24)
            row = wx.BoxSizer(wx.HORIZONTAL)
            self.buttons = []
            for label, action in actions:
                button = wx.Button(self, label=label)
                button.Bind(wx.EVT_BUTTON, lambda _event, action=action: action())
                row.Add(button, 0, wx.RIGHT, 8)
                self.buttons.append(button)
            sizer.Add(row, 0, wx.ALL, 24)
            heading = wx.StaticText(self, label=_("&Recent documents"))
            sizer.Add(heading, 0, wx.LEFT | wx.RIGHT, 24)
            self.recent = wx.ListBox(self)
            self.recent.SetName(_("Recent documents"))
            sizer.Add(self.recent, 1, wx.ALL | wx.EXPAND, 24)
            self.recent.Bind(wx.EVT_LISTBOX_DCLICK, lambda _event: self._open_selected())
            self.recent.Bind(wx.EVT_KEY_DOWN, self._on_recent_key)
            self.SetSizer(sizer)
            self.show_recent(recent)

        def show_recent(self, recent: Sequence[str]) -> None:
            """The recent documents, their folder too when two have the same name; or that there are none."""
            self._paths = list(recent)
            self.recent.Set(menu_labels(recent) if recent else [_("No recent documents")])
            self.recent.Enable(bool(recent))
            for index, path in enumerate(self._paths):
                self.recent.SetString(index, f"{self.recent.GetString(index)}   ({Path(path).parent})")
            if recent:
                self.recent.SetSelection(0)

        def focus(self) -> None:
            """The focus where work begins: the recent documents if there are any, else the first button."""
            (self.recent if self._paths else self.buttons[0]).SetFocus()

        def _open_selected(self) -> None:
            index = self.recent.GetSelection()
            if self._paths and index != wx.NOT_FOUND:
                self._open_recent(index)

        def _on_recent_key(self, event: wx.KeyEvent) -> None:
            if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                self._open_selected()
                return
            event.Skip()

else:

    class HomePanel:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed")
