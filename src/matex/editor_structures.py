"""The equation editor's context menu and the edits it offers on structures (matrices, fractions)."""

from __future__ import annotations

from collections.abc import Callable

from .clipboard import get_clipboard_text
from .fraction_styles import FRACTION_STYLES, built_fractions, fraction_at, restyle_fraction
from .insert_catalog import INSERT_GROUPS, InsertItem
from .template_source import TemplateEdit
from .matrix_templates import (
    delete_matrix_column,
    delete_matrix_row,
    insert_matrix_column,
    insert_matrix_row,
    insert_matrix_template,
    matrix_cell_caret,
    matrix_count,
    matrix_position_at,
)
from .matrix_dialog import MatrixDialog
from .mathml_model import MathMLDocument
from .unicodemath import UnicodeMathError

try:
    import wx
except ImportError:  # The interface is an optional dependency.
    wx = None


def append_insert_items(menu: wx.Menu) -> dict[int, InsertItem]:
    """Fill `menu` with the Insert entries, sections apart; returns them by menu id."""
    mac = wx.Platform == "__WXMAC__"
    entries: dict[int, InsertItem] = {}
    for index, group in enumerate(INSERT_GROUPS):
        if index:
            menu.AppendSeparator()
        for entry in group:
            accelerator = entry.accelerator(mac)
            item = menu.Append(wx.ID_ANY, f"{entry.label}\t{accelerator}" if accelerator else entry.label)
            entries[item.GetId()] = entry
    return entries


class StructureActionsMixin:
    """Methods of `EquationEditor` (editor.py); relies on its state."""

    def _show_context_menu(self, position: wx.Point) -> None:
        menu = wx.Menu()
        if self.mode == "linear":
            has_content = bool(self.document.source)
            cut_item = menu.Append(wx.ID_ANY, "Cu&t\tCtrl+X")
            copy_item = menu.Append(wx.ID_ANY, "&Copy\tCtrl+C")
            paste_item = menu.Append(wx.ID_ANY, "&Paste\tCtrl+V")
            menu.AppendSeparator()
            select_all_item = menu.Append(wx.ID_ANY, "Select &All\tCtrl+A")
            menu.AppendSeparator()
            insert_menu = wx.Menu()
            for item_id, entry in append_insert_items(insert_menu).items():
                self.Bind(wx.EVT_MENU, lambda _e, entry=entry: self.insert_item(entry), id=item_id)
            menu.AppendSubMenu(insert_menu, "&Insert")
            cut_item.Enable(has_content)
            copy_item.Enable(has_content)
            paste_item.Enable(get_clipboard_text() is not None)
            select_all_item.Enable(has_content)
            self.Bind(wx.EVT_MENU, lambda _e: self._cut_equation(), cut_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._copy_equation(), copy_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._paste_equation(), paste_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._select_all(), select_all_item)
        # Row/column edits act on the innermost matrix around the caret
        # (linear) or MathCAT's current cell (professional), so the
        # submenu only exists while one of those is in a matrix.
        caret = self._matrix_caret()
        position_in_matrix = matrix_position_at(self.document.source, caret) if caret is not None else None
        if position_in_matrix is not None:
            matrix_menu = wx.Menu()
            source = self.document.source
            matrix_actions = [
                ("Insert Row &Above", lambda: insert_matrix_row(source, caret, below=False)),
                ("Insert Row &Below", lambda: insert_matrix_row(source, caret, below=True)),
                ("Insert Column &Left", lambda: insert_matrix_column(source, caret, right=False)),
                ("Insert Column &Right", lambda: insert_matrix_column(source, caret, right=True)),
                None,
                ("Delete R&ow", lambda: delete_matrix_row(source, caret)),
                ("Delete C&olumn", lambda: delete_matrix_column(source, caret)),
            ]
            for action in matrix_actions:
                if action is None:
                    matrix_menu.AppendSeparator()
                    continue
                label, build = action
                item = matrix_menu.Append(wx.ID_ANY, label)
                self.Bind(wx.EVT_MENU, lambda _e, build=build: self._apply_matrix_edit(build()), item)
            delete_row, delete_column = matrix_menu.GetMenuItems()[-2:]
            delete_row.Enable(position_in_matrix.rows > 1)
            delete_column.Enable(position_in_matrix.columns > 1)
            menu.AppendSubMenu(matrix_menu, "Matri&x")
        fraction_caret = self._fraction_caret()
        if fraction_caret is not None:
            fraction_menu = wx.Menu()
            current_style = fraction_at(self.document.source, fraction_caret).style
            for style in FRACTION_STYLES:
                item = fraction_menu.AppendRadioItem(wx.ID_ANY, f"&{style.capitalize()}")
                item.Check(style == current_style)
                self.Bind(
                    wx.EVT_MENU,
                    lambda _e, style=style: self._apply_fraction_style(fraction_caret, style),
                    item,
                )
            menu.AppendSubMenu(fraction_menu, "&Fraction")
        if menu.GetMenuItemCount():
            menu.AppendSeparator()
        other_view = "Professional" if self.mode == "linear" else "Linear"
        view_item = menu.Append(wx.ID_ANY, f"Switch to {other_view} View\tF2")
        self.Bind(wx.EVT_MENU, lambda _e: self._toggle_mode(), view_item)
        self.PopupMenu(menu, position)
        menu.Destroy()

    def _matrix_caret(self) -> int | None:
        """A source offset in the matrix cell the user is on, if any.

        In professional mode MathCAT's cell is mapped back to the source
        by matrix order: the n-th `mtable` is the n-th `■(`. If the counts
        differ (another construct made a table), no mapping is trusted.
        """
        source = self.document.source
        if self.mode == "linear":
            return self.caret if matrix_position_at(source, self.caret) is not None else None
        if self.mathcat is None or self.mathcat.structure is None:
            return None
        location = self.mathcat.matrix_location()
        if location is None or len(self.mathcat.structure.tables()) != matrix_count(source):
            return None
        return matrix_cell_caret(source, *location)

    def _fraction_caret(self) -> int | None:
        """A source offset in the fraction the user is on, if any.

        In professional mode MathCAT's innermost `mfrac` is mapped back by
        order: the n-th `mfrac` is the n-th non-linear fraction operator.
        If the counts differ, no mapping is trusted.
        """
        source = self.document.source
        if self.mode == "linear":
            return self.caret if fraction_at(source, self.caret) is not None else None
        structure = self.mathcat.structure if self.mathcat is not None else None
        if structure is None:
            return None
        fraction = structure.enclosing_fraction(self.mathcat.current_id)
        built = built_fractions(source)
        found = structure.fractions()
        if fraction is None or len(found) != len(built):
            return None
        index = next(i for i, candidate in enumerate(found) if candidate is fraction)
        return built[index].operator

    def _apply_fraction_style(self, caret: int, style: str) -> None:
        edit = restyle_fraction(self.document.source, caret, style)
        if edit is None or edit.source == self.document.source:
            self._announce(edit.announcement if edit is not None else "not in a fraction")
            return
        self._clear_selection()
        self._replace_linear(edit.source, edit.caret)
        self.SetFocus()
        if self.mode == "professional":
            self._rebuild_professional_at_caret(edit.announcement, place=self._place_on_fraction)
            return
        self._announce(edit.announcement)

    def _place_on_fraction(self) -> None:
        """Put MathCAT on the fraction around the caret (a linear one has no `mfrac`)."""
        self._highlight_matrix_cell = False
        source = self.document.source
        fraction = fraction_at(source, self.caret)
        built = built_fractions(source)
        found = self.mathcat.structure.fractions() if self.mathcat.structure is not None else ()
        if fraction is None or fraction not in built or len(found) != len(built):
            return
        target = found[built.index(fraction)]
        if target.identifier:
            self.mathcat.move_to(target.identifier)

    def _apply_matrix_edit(self, edit: TemplateEdit | None) -> None:
        if edit is None:
            self._announce("not in a matrix")
            return
        self._clear_selection()
        self._replace_linear(edit.source, edit.caret)
        self.SetFocus()
        if self.mode == "professional":
            self._rebuild_professional_at_caret(edit.announcement)
            return
        self._announce(edit.announcement)

    def _rebuild_professional_at_caret(self, announcement: str, place: Callable[[], None] | None = None) -> None:
        """Reload the edited equation and put MathCAT on the caret's cell (or wherever `place` puts it)."""
        try:
            conversion = self._convert_source()
            self._professional_mathml = conversion.mathml
            self.mathml_document = MathMLDocument.parse(
                conversion.mathml,
                recognized_functions=self.settings.recognized_functions,
            )
            if self.mathcat is not None:
                self.mathcat.load(conversion.mathml)
                self.mathml_document = self.mathcat.structure
                if place is not None:
                    place()
                else:
                    position = matrix_position_at(self.document.source, self.caret)
                    if position is not None:
                        self.mathcat.move_to_cell(position.index, position.row, position.column)
                    self._highlight_matrix_cell = True
                self._sync_mathcat_cursor()
                self._start_linear_preparation()
        except (UnicodeMathError, OSError, RuntimeError, ValueError) as error:
            self.mode = "linear"
            self._update_braille_display()
            self._announce(f"{announcement}. Professional mode could not be rebuilt, linear mode. {error}")
            self.Refresh()
            return
        self._announce(announcement)
        self.Refresh()

    def _insert_matrix(self) -> None:
        if self.mode != "linear":
            return
        rows, columns, fence = self._last_matrix_shape
        dialog = MatrixDialog(self, rows=rows, columns=columns, fence=fence)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                self.SetFocus()
                return
            shape = (dialog.selected_rows, dialog.selected_columns, dialog.selected_fence)
        finally:
            dialog.Destroy()
        self._last_matrix_shape = shape
        edit = insert_matrix_template(self.document.source, self.caret, *shape)
        self._clear_selection()
        self._replace_linear(edit.source, edit.caret)
        self.SetFocus()
        self._announce(edit.announcement)
