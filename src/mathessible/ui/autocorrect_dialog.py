from __future__ import annotations

from collections.abc import Mapping

try:
    import wx
except ImportError:
    wx = None


if wx is not None:

    class AutoCorrectDialog(wx.Dialog):
        """Settings > Math AutoCorrect: Word's dialog, one list of every entry, defaults and the user's alike.

        Typing in Replace moves the list to the entry it matches (and fills
        With when it matches exactly); choosing an entry fills both. Native
        controls only, no announcements of its own: the screen reader reads
        them. `entries` is the edited list; the caller saves its differences
        from `defaults`.
        """

        def __init__(
            self,
            parent: wx.Window,
            defaults: Mapping[str, str],
            entries: Mapping[str, str],
        ):
            super().__init__(parent, title="Math AutoCorrect", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
            self.SetName("Math AutoCorrect dialog")
            self._defaults = dict(defaults)
            self.entries = dict(entries)
            self._keys: list[str] = []

            sizer = wx.BoxSizer(wx.VERTICAL)
            fields = wx.FlexGridSizer(cols=2, vgap=8, hgap=12)
            fields.AddGrowableCol(1)
            replace_label = wx.StaticText(self, label="&Replace")
            self.replace = wx.TextCtrl(self)
            self.replace.SetName("Replace")
            with_label = wx.StaticText(self, label="&With")
            self.replacement = wx.TextCtrl(self)
            self.replacement.SetName("With")
            fields.Add(replace_label, 0, wx.ALIGN_CENTER_VERTICAL)
            fields.Add(self.replace, 1, wx.EXPAND)
            fields.Add(with_label, 0, wx.ALIGN_CENTER_VERTICAL)
            fields.Add(self.replacement, 1, wx.EXPAND)
            list_label = wx.StaticText(self, label="&Entries")
            self.list = wx.ListBox(self, size=(420, 280), style=wx.LB_SINGLE)
            self.list.SetName("Math AutoCorrect entries")
            row = wx.BoxSizer(wx.HORIZONTAL)
            self.add_button = wx.Button(self, label="&Add")
            self.delete_button = wx.Button(self, label="&Delete")
            reset_button = wx.Button(self, label="Reset to De&faults")
            row.Add(self.add_button, 0, wx.RIGHT, 8)
            row.Add(self.delete_button, 0, wx.RIGHT, 8)
            row.Add(reset_button, 0)
            buttons = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)

            sizer.Add(fields, 0, wx.ALL | wx.EXPAND, 12)
            sizer.Add(list_label, 0, wx.LEFT | wx.RIGHT, 12)
            sizer.Add(self.list, 1, wx.ALL | wx.EXPAND, 12)
            sizer.Add(row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            if buttons is not None:
                sizer.Add(buttons, 0, wx.ALL | wx.EXPAND, 12)
            self.SetSizerAndFit(sizer)

            self.replace.Bind(wx.EVT_TEXT, self._on_replace_text)
            self.replacement.Bind(wx.EVT_TEXT, lambda _event: self._update_buttons())
            self.list.Bind(wx.EVT_LISTBOX, self._on_select)
            self.add_button.Bind(wx.EVT_BUTTON, lambda _event: self._add())
            self.delete_button.Bind(wx.EVT_BUTTON, lambda _event: self._delete())
            reset_button.Bind(wx.EVT_BUTTON, lambda _event: self._reset())
            self._fill()
            self.replace.SetFocus()

        def _fill(self, select: str | None = None) -> None:
            self._keys = sorted(self.entries, key=lambda typed: (typed.lstrip("\\").lower(), typed))
            self.list.Set([f"{typed}  →  {self.entries[typed]}" for typed in self._keys])
            if select in self.entries:
                self.list.SetSelection(self._keys.index(select))
            self._update_buttons()

        def _on_replace_text(self, _event: wx.CommandEvent) -> None:
            typed = self.replace.GetValue().strip()
            if typed in self.entries:
                self.list.SetSelection(self._keys.index(typed))
                self.replacement.ChangeValue(self.entries[typed])
            elif typed:
                match = next((index for index, key in enumerate(self._keys) if key.startswith(typed)), None)
                if match is not None:
                    self.list.SetSelection(match)
            self._update_buttons()

        def _on_select(self, _event: wx.CommandEvent) -> None:
            index = self.list.GetSelection()
            if 0 <= index < len(self._keys):
                typed = self._keys[index]
                self.replace.ChangeValue(typed)
                self.replacement.ChangeValue(self.entries[typed])
            self._update_buttons()

        def _update_buttons(self) -> None:
            typed = self.replace.GetValue().strip()
            self.add_button.SetLabel("&Replace" if typed in self.entries else "&Add")
            valid = bool(typed) and not any(character.isspace() for character in typed) and typed != "\\"
            self.add_button.Enable(valid and bool(self.replacement.GetValue().strip()))
            self.delete_button.Enable(typed in self.entries)

        def _add(self) -> None:
            typed, replacement = self.replace.GetValue().strip(), self.replacement.GetValue().strip()
            if not typed or not replacement:
                return
            self.entries[typed] = replacement
            self._fill(select=typed)

        def _delete(self) -> None:
            typed = self.replace.GetValue().strip()
            if typed not in self.entries:
                return
            del self.entries[typed]
            self.replace.ChangeValue("")
            self.replacement.ChangeValue("")
            self._fill()

        def _reset(self) -> None:
            self.entries = dict(self._defaults)
            self._fill(select=self.replace.GetValue().strip())

else:

    class AutoCorrectDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
