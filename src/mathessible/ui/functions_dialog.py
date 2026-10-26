from __future__ import annotations

from collections.abc import Iterable

from mathessible.settings import DEFAULT_RECOGNIZED_FUNCTIONS, function_name

try:
    import wx
except ImportError:
    wx = None


if wx is not None:

    class RecognizedFunctionsDialog(wx.Dialog):
        """Settings > Recognized Functions, as Word's: a name field, the list, Add and Delete.

        Typing a name already in the list selects it; choosing one fills the
        field. Native controls only, no announcements of its own.
        `functions` is the edited list.
        """

        def __init__(self, parent: wx.Window, functions: Iterable[str]):
            super().__init__(parent, title="Recognized Functions", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
            self.SetName("Recognized functions dialog")
            self.functions = list(functions)
            self._shown: list[str] = []

            sizer = wx.BoxSizer(wx.VERTICAL)
            help_text = wx.StaticText(
                self,
                label=(
                    "Space after a recognized function opens its argument, and the function is "
                    "navigated as its name and argument, as in Word."
                ),
            )
            help_text.Wrap(360)
            name_label = wx.StaticText(self, label="&Function")
            self.name = wx.TextCtrl(self)
            self.name.SetName("Function")
            list_label = wx.StaticText(self, label="&Recognized functions")
            self.list = wx.ListBox(self, size=(360, 240), style=wx.LB_SINGLE)
            self.list.SetName("Recognized functions")
            row = wx.BoxSizer(wx.HORIZONTAL)
            self.add_button = wx.Button(self, label="&Add")
            self.delete_button = wx.Button(self, label="&Delete")
            reset_button = wx.Button(self, label="Reset to De&faults")
            row.Add(self.add_button, 0, wx.RIGHT, 8)
            row.Add(self.delete_button, 0, wx.RIGHT, 8)
            row.Add(reset_button, 0)
            buttons = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)

            sizer.Add(help_text, 0, wx.ALL | wx.EXPAND, 12)
            sizer.Add(name_label, 0, wx.LEFT | wx.RIGHT, 12)
            sizer.Add(self.name, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)
            sizer.Add(list_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
            sizer.Add(self.list, 1, wx.ALL | wx.EXPAND, 12)
            sizer.Add(row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            if buttons is not None:
                sizer.Add(buttons, 0, wx.ALL | wx.EXPAND, 12)
            self.SetSizerAndFit(sizer)

            self.name.Bind(wx.EVT_TEXT, self._on_name_text)
            self.list.Bind(wx.EVT_LISTBOX, self._on_select)
            self.add_button.Bind(wx.EVT_BUTTON, lambda _event: self._add())
            self.delete_button.Bind(wx.EVT_BUTTON, lambda _event: self._delete())
            reset_button.Bind(wx.EVT_BUTTON, lambda _event: self._reset())
            self._fill()
            self.name.SetFocus()

        def _fill(self, select: str | None = None) -> None:
            self._shown = sorted(self.functions, key=str.lower)
            self.list.Set(self._shown)
            if select in self._shown:
                self.list.SetSelection(self._shown.index(select))
            self._update_buttons()

        def _on_name_text(self, _event: wx.CommandEvent) -> None:
            name = function_name(self.name.GetValue())
            if name in self._shown:
                self.list.SetSelection(self._shown.index(name))
            self._update_buttons()

        def _on_select(self, _event: wx.CommandEvent) -> None:
            index = self.list.GetSelection()
            if 0 <= index < len(self._shown):
                self.name.ChangeValue(self._shown[index])
            self._update_buttons()

        def _update_buttons(self) -> None:
            name = function_name(self.name.GetValue())
            self.add_button.Enable(name is not None and name not in self.functions)
            # The list is never left empty: without functions, the defaults come back.
            self.delete_button.Enable(name in self.functions and len(self.functions) > 1)

        def _add(self) -> None:
            name = function_name(self.name.GetValue())
            if name is None or name in self.functions:
                return
            self.functions.append(name)
            self._fill(select=name)

        def _delete(self) -> None:
            name = function_name(self.name.GetValue())
            if name not in self.functions or len(self.functions) == 1:
                return
            self.functions.remove(name)
            self.name.ChangeValue("")
            self._fill()

        def _reset(self) -> None:
            self.functions = list(DEFAULT_RECOGNIZED_FUNCTIONS)
            self.name.ChangeValue("")
            self._fill()

else:

    class RecognizedFunctionsDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
