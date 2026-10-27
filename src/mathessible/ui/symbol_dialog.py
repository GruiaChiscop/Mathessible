from __future__ import annotations

from collections.abc import Mapping

from mathessible.editing.completion import Suggestion, SymbolNamer, search_symbols
from mathessible.i18n import _

try:
    import wx
except ImportError:
    wx = None

# More would only slow the list down; a longer query narrows it.
MAX_RESULTS = 300


if wx is not None:

    class SymbolDialog(wx.Dialog):
        """Insert > Symbol: a search field over control words and symbol names, and the matches.

        Native controls only, no announcements of its own: the screen
        reader reads the field and the list (Tab to it). Enter, in either,
        inserts the selected match.
        """

        def __init__(
            self,
            parent: wx.Window,
            table: Mapping[str, str],
            name: SymbolNamer,
            query: str = "",
        ):
            super().__init__(parent, title=_("Insert Symbol"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
            self.SetName(_("Insert symbol dialog"))
            self._table = table
            self._name = name
            self._matches: list[Suggestion] = []

            sizer = wx.BoxSizer(wx.VERTICAL)
            search_label = wx.StaticText(self, label=_("&Search (control word, symbol or name)"))
            self.search = wx.TextCtrl(self, value=query, style=wx.TE_PROCESS_ENTER)
            self.search.SetName(_("Search symbols"))
            results_label = wx.StaticText(self, label=_("&Matches"))
            self.results = wx.ListBox(self, size=(420, 260), style=wx.LB_SINGLE)
            self.results.SetName(_("Matching symbols"))
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

        def _accept(self) -> None:
            if self.selected is not None:
                self.EndModal(wx.ID_OK)

else:

    class SymbolDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
