from __future__ import annotations

import unicodedata
from collections.abc import Mapping

from mathessible.symbols.braille_signs import cells_from_text, dots_of, symbol_from_text

try:
    import wx
except ImportError:
    wx = None


if wx is not None:

    class BrailleSignsDialog(wx.Dialog):
        """Settings > Braille signs: the user's own sign for a symbol, over one braille code.

        Like Math AutoCorrect: choosing an entry fills both fields, typing a
        symbol already there selects it. The symbol may be typed as itself,
        a control word (`\\sqsubset`) or a code (`U+228F`), the braille as
        cells or dot numbers (`4-456-126`). Native controls only, no
        announcements of its own. `signs` is the edited list.
        """

        def __init__(
            self,
            parent: wx.Window,
            code_label: str,
            signs: Mapping[str, str],
            control_words: Mapping[str, str] | None = None,
        ):
            super().__init__(
                parent, title=f"Braille signs: {code_label}", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
            )
            self.SetName("Braille signs dialog")
            self.signs = dict(signs)
            self._control_words = dict(control_words or {})
            self._symbols: list[str] = []

            sizer = wx.BoxSizer(wx.VERTICAL)
            help_text = wx.StaticText(
                self,
                label=(
                    f"Your own braille for symbols in {code_label}; each replaces the code's sign. "
                    "Symbol: the character, a control word (\\sqsubset) or a code (U+228F). "
                    "Braille: cells, or dot numbers with hyphens between cells (4-456-126)."
                ),
            )
            help_text.Wrap(460)
            fields = wx.FlexGridSizer(cols=2, vgap=8, hgap=12)
            fields.AddGrowableCol(1)
            symbol_label = wx.StaticText(self, label="S&ymbol")
            self.symbol = wx.TextCtrl(self)
            self.symbol.SetName("Symbol")
            braille_label = wx.StaticText(self, label="&Braille")
            self.braille = wx.TextCtrl(self)
            self.braille.SetName("Braille")
            fields.Add(symbol_label, 0, wx.ALIGN_CENTER_VERTICAL)
            fields.Add(self.symbol, 1, wx.EXPAND)
            fields.Add(braille_label, 0, wx.ALIGN_CENTER_VERTICAL)
            fields.Add(self.braille, 1, wx.EXPAND)
            list_label = wx.StaticText(self, label="&Signs")
            self.list = wx.ListBox(self, size=(460, 240), style=wx.LB_SINGLE)
            self.list.SetName("Braille signs")
            row = wx.BoxSizer(wx.HORIZONTAL)
            self.add_button = wx.Button(self, label="&Add")
            self.delete_button = wx.Button(self, label="&Delete")
            row.Add(self.add_button, 0, wx.RIGHT, 8)
            row.Add(self.delete_button, 0)
            buttons = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)

            sizer.Add(help_text, 0, wx.ALL | wx.EXPAND, 12)
            sizer.Add(fields, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 12)
            sizer.Add(list_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
            sizer.Add(self.list, 1, wx.ALL | wx.EXPAND, 12)
            sizer.Add(row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            if buttons is not None:
                sizer.Add(buttons, 0, wx.ALL | wx.EXPAND, 12)
            self.SetSizerAndFit(sizer)

            self.symbol.Bind(wx.EVT_TEXT, self._on_symbol_text)
            self.braille.Bind(wx.EVT_TEXT, lambda _event: self._update_buttons())
            self.list.Bind(wx.EVT_LISTBOX, self._on_select)
            self.add_button.Bind(wx.EVT_BUTTON, lambda _event: self._add())
            self.delete_button.Bind(wx.EVT_BUTTON, lambda _event: self._delete())
            self._fill()
            self.symbol.SetFocus()

        def _typed_symbol(self) -> str | None:
            return symbol_from_text(self.symbol.GetValue(), self._control_words)

        def _fill(self, select: str | None = None) -> None:
            self._symbols = sorted(self.signs)
            self.list.Set([self._entry_text(symbol) for symbol in self._symbols])
            if select in self.signs:
                self.list.SetSelection(self._symbols.index(select))
            self._update_buttons()

        def _entry_text(self, symbol: str) -> str:
            name = unicodedata.name(symbol, "").lower()
            cells = self.signs[symbol]
            return f"{symbol}  {name}: {cells} (dots {dots_of(cells)})" if name else f"{symbol}: {cells}"

        def _on_symbol_text(self, _event: wx.CommandEvent) -> None:
            symbol = self._typed_symbol()
            if symbol in self.signs:
                self.list.SetSelection(self._symbols.index(symbol))
                self.braille.ChangeValue(self.signs[symbol])
            self._update_buttons()

        def _on_select(self, _event: wx.CommandEvent) -> None:
            index = self.list.GetSelection()
            if 0 <= index < len(self._symbols):
                symbol = self._symbols[index]
                self.symbol.ChangeValue(symbol)
                self.braille.ChangeValue(self.signs[symbol])
            self._update_buttons()

        def _update_buttons(self) -> None:
            symbol = self._typed_symbol()
            self.add_button.SetLabel("&Replace" if symbol in self.signs else "&Add")
            self.add_button.Enable(symbol is not None and cells_from_text(self.braille.GetValue()) is not None)
            self.delete_button.Enable(symbol in self.signs)

        def _add(self) -> None:
            symbol, cells = self._typed_symbol(), cells_from_text(self.braille.GetValue())
            if symbol is None or cells is None:
                return
            self.signs[symbol] = cells
            self._fill(select=symbol)

        def _delete(self) -> None:
            symbol = self._typed_symbol()
            if symbol not in self.signs:
                return
            del self.signs[symbol]
            self.symbol.ChangeValue("")
            self.braille.ChangeValue("")
            self._fill()

else:

    class BrailleSignsDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
