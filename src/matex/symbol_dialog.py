from __future__ import annotations

from collections.abc import Callable, Mapping

from .completion import Suggestion, SymbolNamer, search_symbols

try:
    import wx
except ImportError:
    wx = None

# More would only slow the list down; a longer query narrows it.
MAX_RESULTS = 300


if wx is not None:

    class SymbolDialog(wx.Dialog):
        """Insert > Symbol: a search field over control words and symbol names, and the matches.

        Up/Down in the field move through the matches (spoken through
        `announce`, since the screen reader stays on the field); Enter
        inserts the selected one.
        """

        def __init__(
            self,
            parent: wx.Window,
            table: Mapping[str, str],
            name: SymbolNamer,
            announce: Callable[[str], None],
            query: str = "",
        ):
            super().__init__(parent, title="Insert Symbol", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
            self.SetName("Insert symbol dialog")
            self._table = table
            self._name = name
            self._announce = announce
            self._matches: list[Suggestion] = []
            self._pending: wx.CallLater | None = None

            sizer = wx.BoxSizer(wx.VERTICAL)
            search_label = wx.StaticText(self, label="&Search (control word, symbol or name)")
            self.search = wx.TextCtrl(self, value=query, style=wx.TE_PROCESS_ENTER)
            self.search.SetName("Search symbols")
            results_label = wx.StaticText(self, label="&Matches")
            self.results = wx.ListBox(self, size=(420, 260), style=wx.LB_SINGLE)
            self.results.SetName("Matching symbols")
            buttons = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)

            sizer.Add(search_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
            sizer.Add(self.search, 0, wx.ALL | wx.EXPAND, 12)
            sizer.Add(results_label, 0, wx.LEFT | wx.RIGHT, 12)
            sizer.Add(self.results, 1, wx.ALL | wx.EXPAND, 12)
            if buttons is not None:
                sizer.Add(buttons, 0, wx.ALL | wx.EXPAND, 12)
            self.SetSizerAndFit(sizer)

            self.search.Bind(wx.EVT_TEXT, self._on_text)
            self.search.Bind(wx.EVT_TEXT_ENTER, lambda _event: self._accept())
            self.search.Bind(wx.EVT_KEY_DOWN, self._on_search_key)
            self.results.Bind(wx.EVT_LISTBOX_DCLICK, lambda _event: self._accept())
            self._fill()
            self.search.SetFocus()
            self.search.SelectAll()

        @property
        def query(self) -> str:
            return self.search.GetValue()

        @property
        def selected(self) -> Suggestion | None:
            index = self.results.GetSelection()
            return self._matches[index] if 0 <= index < len(self._matches) else None

        def _fill(self) -> None:
            self._matches = search_symbols(self.query, self._table, self._name)[:MAX_RESULTS]
            self.results.Set([match.label(self._name) for match in self._matches])
            if self._matches:
                self.results.SetSelection(0)

        def _on_text(self, _event: wx.CommandEvent) -> None:
            self._fill()
            # Said once typing pauses, not on every letter.
            if self._pending is not None:
                self._pending.Stop()
            self._pending = wx.CallLater(400, self._speak_matches)

        def _speak_matches(self) -> None:
            self._pending = None
            if not self._matches:
                self._announce("no matches")
                return
            count = len(self._matches)
            more = "+" if count == MAX_RESULTS else ""
            self._announce(f"{count}{more} matches, {self._matches[0].speech(self._name)}")

        def _on_search_key(self, event: wx.KeyEvent) -> None:
            key = event.GetKeyCode()
            if key not in (wx.WXK_DOWN, wx.WXK_UP) or not self._matches:
                event.Skip()
                return
            index = self.results.GetSelection()
            step = 1 if key == wx.WXK_DOWN else -1
            index = max(0, min(len(self._matches) - 1, index + step))
            self.results.SetSelection(index)
            self._announce(f"{self._matches[index].speech(self._name)}, {index + 1} of {len(self._matches)}")

        def _accept(self) -> None:
            if self.selected is None:
                self._announce("no matches")
                return
            self.EndModal(wx.ID_OK)

else:

    class SymbolDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
