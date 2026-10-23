from __future__ import annotations

from .insert_catalog import InsertItem
from .structure_gallery import CATEGORIES, written_form

try:
    import wx
except ImportError:
    wx = None


if wx is not None:

    class GalleryDialog(wx.Dialog):
        """Insert > Structures: Word's structure gallery, as two lists.

        Categories on one side, their structures on the other; focus starts
        on the structures, Enter inserts. Native controls only, no
        announcements of its own: the screen reader reads them. "Written
        as" shows how the selected structure is typed in the linear view.
        """

        def __init__(
            self,
            parent: wx.Window,
            control_words: bool,
            category: int = 0,
            structure: int = 0,
        ):
            super().__init__(parent, title="Insert Structure", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
            self.SetName("Insert structure dialog")
            self._control_words = control_words

            sizer = wx.BoxSizer(wx.VERTICAL)
            lists = wx.BoxSizer(wx.HORIZONTAL)
            left = wx.BoxSizer(wx.VERTICAL)
            right = wx.BoxSizer(wx.VERTICAL)
            categories_label = wx.StaticText(self, label="&Category")
            self.categories = wx.ListBox(
                self, choices=[category.name for category in CATEGORIES], size=(180, 300), style=wx.LB_SINGLE
            )
            self.categories.SetName("Category")
            structures_label = wx.StaticText(self, label="&Structure")
            self.structures = wx.ListBox(self, size=(300, 300), style=wx.LB_SINGLE)
            self.structures.SetName("Structure")
            written_label = wx.StaticText(self, label="&Written as")
            self.written = wx.TextCtrl(self, style=wx.TE_READONLY)
            self.written.SetName("Written as")
            buttons = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)

            left.Add(categories_label, 0, wx.BOTTOM, 4)
            left.Add(self.categories, 1, wx.EXPAND)
            right.Add(structures_label, 0, wx.BOTTOM, 4)
            right.Add(self.structures, 1, wx.EXPAND)
            lists.Add(left, 0, wx.ALL | wx.EXPAND, 12)
            lists.Add(right, 1, wx.ALL | wx.EXPAND, 12)
            sizer.Add(lists, 1, wx.EXPAND)
            sizer.Add(written_label, 0, wx.LEFT | wx.RIGHT, 12)
            sizer.Add(self.written, 0, wx.ALL | wx.EXPAND, 12)
            if buttons is not None:
                sizer.Add(buttons, 0, wx.ALL | wx.EXPAND, 12)
            self.SetSizerAndFit(sizer)

            self.categories.Bind(wx.EVT_LISTBOX, lambda _event: self._show_category(0))
            self.categories.Bind(wx.EVT_LISTBOX_DCLICK, lambda _event: self.structures.SetFocus())
            self.categories.Bind(wx.EVT_KEY_DOWN, self._on_categories_key)
            self.structures.Bind(wx.EVT_LISTBOX, lambda _event: self._show_written())
            self.structures.Bind(wx.EVT_LISTBOX_DCLICK, lambda _event: self._accept())
            self.structures.Bind(wx.EVT_KEY_DOWN, self._on_structures_key)
            self.Bind(wx.EVT_BUTTON, lambda _event: self._accept(), id=wx.ID_OK)

            category = max(0, min(category, len(CATEGORIES) - 1))
            self.categories.SetSelection(category)
            self._show_category(structure)
            self.structures.SetFocus()

        @property
        def category(self) -> int:
            return max(0, self.categories.GetSelection())

        @property
        def structure(self) -> int:
            return max(0, self.structures.GetSelection())

        @property
        def selected(self) -> InsertItem | None:
            items = CATEGORIES[self.category].items
            index = self.structures.GetSelection()
            return items[index] if 0 <= index < len(items) else None

        def _show_category(self, structure: int) -> None:
            items = CATEGORIES[self.category].items
            self.structures.Set([item.label for item in items])
            if items:
                self.structures.SetSelection(max(0, min(structure, len(items) - 1)))
            self._show_written()

        def _show_written(self) -> None:
            item = self.selected
            text = written_form(item, self._control_words) if item is not None else ""
            self.written.SetValue(text or ("opens a dialog" if item is not None and item.dialog else ""))

        def _on_categories_key(self, event: wx.KeyEvent) -> None:
            key = event.GetKeyCode()
            if key in (wx.WXK_RIGHT, wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                self.structures.SetFocus()
                return
            event.Skip()

        def _on_structures_key(self, event: wx.KeyEvent) -> None:
            if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                self._accept()
                return
            event.Skip()

        def _accept(self) -> None:
            if self.selected is None:
                return
            self.EndModal(wx.ID_OK)

else:

    class GalleryDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
