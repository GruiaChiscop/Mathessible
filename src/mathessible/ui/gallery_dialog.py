from __future__ import annotations

from collections.abc import Sequence

from mathessible.i18n import _
from mathessible.templates.insert_catalog import InsertItem
from mathessible.templates.saved_equations import SavedEquation, without_equation
from mathessible.templates.structure_gallery import MY_EQUATIONS, gallery_categories, written_form

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
        `saved` are the user's own equations (My Equations), which Delete
        removes; the edited list is `saved` afterwards.
        """

        def __init__(
            self,
            parent: wx.Window,
            control_words: bool,
            category: int = 0,
            structure: int = 0,
            saved: Sequence[SavedEquation] = (),
        ):
            super().__init__(parent, title=_("Insert Structure"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
            self.SetName(_("Insert structure dialog"))
            self._control_words = control_words
            self.saved = list(saved)
            self._categories = gallery_categories(self.saved)

            sizer = wx.BoxSizer(wx.VERTICAL)
            lists = wx.BoxSizer(wx.HORIZONTAL)
            left = wx.BoxSizer(wx.VERTICAL)
            right = wx.BoxSizer(wx.VERTICAL)
            categories_label = wx.StaticText(self, label=_("&Category"))
            self.categories = wx.ListBox(self, choices=self._category_names(), size=(180, 300), style=wx.LB_SINGLE)
            self.categories.SetName(_("Category"))
            structures_label = wx.StaticText(self, label=_("&Structure"))
            self.structures = wx.ListBox(self, size=(300, 300), style=wx.LB_SINGLE)
            self.structures.SetName(_("Structure"))
            written_label = wx.StaticText(self, label=_("&Written as"))
            self.written = wx.TextCtrl(self, style=wx.TE_READONLY)
            self.written.SetName(_("Written as"))
            self.delete_button = wx.Button(self, label=_("&Delete"))
            buttons = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)

            left.Add(categories_label, 0, wx.BOTTOM, 4)
            left.Add(self.categories, 1, wx.EXPAND)
            right.Add(structures_label, 0, wx.BOTTOM, 4)
            right.Add(self.structures, 1, wx.EXPAND)
            right.Add(self.delete_button, 0, wx.TOP, 8)
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
            self.delete_button.Bind(wx.EVT_BUTTON, lambda _event: self._delete())

            category = max(0, min(category, len(self._categories) - 1))
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
            items = self._categories[self.category].items
            index = self.structures.GetSelection()
            return items[index] if 0 <= index < len(items) else None

        def _show_category(self, structure: int) -> None:
            items = self._categories[self.category].items
            # The user's own equations keep their names; Word's structures are shown in the interface's language.
            mine = self._in_my_equations()
            self.structures.Set([item.label if mine else _(item.label) for item in items])
            if items:
                self.structures.SetSelection(max(0, min(structure, len(items) - 1)))
            self._show_written()

        def _category_names(self) -> list[str]:
            return [_(category.name) for category in self._categories]

        def _in_my_equations(self) -> bool:
            return self._categories[self.category].name == MY_EQUATIONS

        def _show_written(self) -> None:
            self.delete_button.Enable(self._in_my_equations() and self.selected is not None)
            item = self.selected
            text = written_form(item, self._control_words) if item is not None else ""
            self.written.SetValue(text or (_("opens a dialog") if item is not None and item.dialog else ""))

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
            if event.GetKeyCode() in (wx.WXK_DELETE, wx.WXK_BACK) and self._in_my_equations():
                self._delete()
                return
            event.Skip()

        def _delete(self) -> None:
            """Delete the selected one of My Equations, after asking."""
            item = self.selected
            if item is None or not self._in_my_equations():
                return
            answer = wx.MessageBox(
                _("Delete “{name}” from My Equations?").format(name=item.label),
                _("Delete Equation"),
                wx.YES_NO | wx.ICON_QUESTION,
                self,
            )
            if answer != wx.YES:
                return
            index = self.structures.GetSelection()
            self.saved = without_equation(self.saved, item.label)
            self._categories = gallery_categories(self.saved)
            self.categories.Set(self._category_names())
            self.categories.SetSelection(0)
            self._show_category(index)
            self.structures.SetFocus()

        def _accept(self) -> None:
            if self.selected is None:
                return
            self.EndModal(wx.ID_OK)

else:

    class GalleryDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
