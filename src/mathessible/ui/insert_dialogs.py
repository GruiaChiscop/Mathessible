"""The document's Insert dialogs: a link, a table and a chart, and Edit Table for a grid table. Native controls
only, which screen readers read."""

from __future__ import annotations

from collections.abc import Callable

from mathessible.documents.grid_tables import GridCell, GridTable, header_row_count
from mathessible.editing.grid_table_edit import (
    TableEditError,
    can_merge_down,
    can_merge_right,
    cell_at,
    cell_position,
    delete_column,
    delete_row,
    insert_column,
    insert_row,
    merge_down,
    merge_right,
    neighbour,
    split,
    with_content,
    with_header_rows,
)
from mathessible.i18n import _
from mathessible.ui.accessibility import set_accessibility_label
from mathessible.ui.theme import palette

try:
    import wx
    import wx.lib.scrolledpanel
except ImportError:
    wx = None


if wx is not None:

    def _outline(window: wx.Window, fields: list[wx.TextCtrl], margin: int, radius: float = 0) -> None:
        """A line around each of `window`'s multiline fields, whose own border hardly shows in dark appearance;
        a thicker one in the focus colour around the focused field."""
        appearance = wx.SystemSettings.GetAppearance() if hasattr(wx.SystemSettings, "GetAppearance") else None
        colors = palette(dark=bool(appearance is not None and appearance.IsDark()))
        focused = wx.Window.FindFocus()
        dc = wx.PaintDC(window)
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        for field in sorted(fields, key=lambda field: field == focused):
            dc.SetPen(wx.Pen(wx.Colour(*colors.focus), 2) if field == focused else wx.Pen(wx.Colour(*colors.grid_line)))
            dc.DrawRoundedRectangle(field.GetRect().Inflate(margin, margin), radius)

    class _FormDialog(wx.Dialog):
        def __init__(self, parent: wx.Window, title: str):
            super().__init__(parent, title=title)
            self.grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=12)
            self.grid.AddGrowableCol(1)
            self.labels: dict[wx.Window, wx.StaticText] = {}
            self.multiline: list[wx.TextCtrl] = []
            self.Bind(wx.EVT_PAINT, lambda _event: _outline(self, self.multiline, 1, 5))

        def _row(self, label: str, control: wx.Window, name: str) -> wx.Window:
            control.SetName(name)
            text = wx.StaticText(self, label=label)
            self.labels[control] = text
            if isinstance(control, wx.TextCtrl) and control.IsMultiLine():
                self.multiline.append(control)
                control.Bind(wx.EVT_SET_FOCUS, self._redraw)
                control.Bind(wx.EVT_KILL_FOCUS, self._redraw)
                self.grid.Add(text, 0, wx.TOP, 4)  # Beside the field's first line.
            else:
                self.grid.Add(text, 0, wx.ALIGN_CENTER_VERTICAL)
            self.grid.Add(control, 1, wx.EXPAND)
            return control

        def _redraw(self, event: wx.FocusEvent) -> None:
            self.Refresh()
            event.Skip()

        def _finish(self, first: wx.Window) -> None:
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(self.grid, 1, wx.ALL | wx.EXPAND, 16)
            buttons = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
            sizer.Add(buttons, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 16)
            self.SetSizerAndFit(sizer)
            self.SetMinSize((420, -1))
            self.Fit()
            first.SetFocus()

    class LinkDialog(_FormDialog):
        """Insert > Link: the text shown (the selection, if there is one) and the address."""

        def __init__(self, parent: wx.Window, text: str = ""):
            super().__init__(parent, _("Insert Link"))
            self.text = self._row(_("&Text:"), wx.TextCtrl(self, value=text), _("Link text"))
            self.address = self._row(_("&Address:"), wx.TextCtrl(self, value="https://"), _("Link address"))
            self._finish(self.address if text else self.text)
            self.address.SetInsertionPointEnd()

    class TableDialog(_FormDialog):
        """Insert > Table: its rows (its header row included) and columns."""

        def __init__(self, parent: wx.Window):
            super().__init__(parent, _("Insert Table"))
            self.rows = self._row(_("&Rows:"), wx.SpinCtrl(self, min=1, max=100, initial=3), _("Rows"))
            self.columns = self._row(_("&Columns:"), wx.SpinCtrl(self, min=1, max=20, initial=3), _("Columns"))
            self.grid.Add((0, 0))
            self.header = wx.CheckBox(self, label=_("First row is the &header"))
            self.header.SetValue(True)
            self.grid.Add(self.header)
            self.grid.Add((0, 0))
            self.grid_table = wx.CheckBox(self, label=_("Cells hold paragraphs or lists (&grid table)"))
            self.grid.Add(self.grid_table)
            self._finish(self.rows)

    class ChartDialog(_FormDialog):
        """Insert > Chart: its kind, title and description, then a function and its x range for a graph, or
        the rows and series of a chart of data (a table to fill in)."""

        KINDS = ("function", "bar", "line", "scatter", "pie")

        def __init__(self, parent: wx.Window):
            super().__init__(parent, _("Insert Chart"))
            names = [
                _("Function graph"),
                _("Bar chart"),
                _("Line chart"),
                _("Scatter plot"),
                _("Pie chart"),
            ]
            self.kind = self._row(_("&Kind:"), wx.Choice(self, choices=names), _("Kind"))
            self.kind.SetSelection(0)
            self.title = self._row(_("&Title:"), wx.TextCtrl(self), _("Title"))
            self.description = self._row(
                _("&Description:"), wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(-1, 60)), _("Description")
            )
            self.function = self._row(_("&Function of x:"), wx.TextCtrl(self, value="sin(x)"), _("Function of x"))
            self.start = self._row(_("x fro&m:"), wx.TextCtrl(self, value="-5"), _("x from"))
            self.end = self._row(_("x t&o:"), wx.TextCtrl(self, value="5"), _("x to"))
            self.rows = self._row(_("&Rows:"), wx.SpinCtrl(self, min=1, max=100, initial=3), _("Rows"))
            self.series = self._row(_("&Series:"), wx.SpinCtrl(self, min=1, max=10, initial=1), _("Series"))
            self.kind.Bind(wx.EVT_CHOICE, lambda _event: self._show_fields())
            self._finish(self.kind)
            self._show_fields()

        def selected_kind(self) -> str:
            return self.KINDS[max(0, self.kind.GetSelection())]

        def _show_fields(self) -> None:
            """A graph's function and range, or a data chart's rows and series: only the kind's are shown."""
            kind = self.selected_kind()
            graph = kind == "function"
            for control, shown in (
                (self.function, graph),
                (self.start, graph),
                (self.end, graph),
                (self.rows, not graph),
                (self.series, not graph and kind != "pie"),
            ):
                control.Show(shown)
                self.labels[control].Show(shown)
            self.Fit()
            self.Layout()

    class FlowchartDialog(_FormDialog):
        """Insert > Flowchart: its title, description and reading direction."""

        DIRECTIONS = ("TD", "LR", "BT", "RL")

        def __init__(self, parent: wx.Window):
            super().__init__(parent, _("Insert Flowchart"))
            self.title = self._row(_("&Title:"), wx.TextCtrl(self), _("Title"))
            self.description = self._row(
                _("&Description:"), wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(-1, 60)), _("Description")
            )
            names = [_("Top to bottom"), _("Left to right"), _("Bottom to top"), _("Right to left")]
            self.direction = self._row(_("Di&rection:"), wx.Choice(self, choices=names), _("Direction"))
            self.direction.SetSelection(0)
            self._finish(self.title)

        def selected_direction(self) -> str:
            return self.DIRECTIONS[max(0, self.direction.GetSelection())]

    class TableEditDialog(wx.Dialog):
        """Format > Edit Table: a grid table as a grid of native text fields, one per cell (a merged cell
        spans its rows and columns), each named for VoiceOver by where it is; its text is edited in place,
        as Markdown. Tab goes through the cells row by row, Command+Option+arrow to the next cell that way,
        and the cell moved to is named by what changed. The Actions button's menu acts on the last cell
        that had the focus; from a cell, Command+Option+T opens it and Command+Option+Shift+Right or Down
        merges. OK gives `table`, which the caller writes back."""

        def __init__(self, parent: wx.Window, table: GridTable):
            super().__init__(parent, title=_("Edit Table"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
            self.table = table
            self.cell: GridCell = table.cells[0]
            self.cells = wx.lib.scrolledpanel.ScrolledPanel(self, size=(640, 320), style=wx.BORDER_THEME)
            self.cells.Bind(wx.EVT_PAINT, lambda _event: _outline(self.cells, self.fields, 2))
            self.fields: list[wx.TextCtrl] = []  # In the order of `table.cells`.
            self.header = wx.SpinCtrl(self, min=0, max=table.rows, initial=header_row_count(table))
            self.header.SetName(_("Header rows"))
            self.actions: tuple[tuple[str, Callable[[], None], Callable[[], bool]], ...] = (
                (_("Insert Row &Above"), lambda: self._insert_row(0), lambda: True),
                (_("Insert Row &Below"), lambda: self._insert_row(self.cell.rowspan), lambda: True),
                (_("&Delete Row"), self._delete_row, lambda: self.table.rows > 1),
                (_("Insert Column &Left"), lambda: self._insert_column(0), lambda: True),
                (_("Insert Column &Right"), lambda: self._insert_column(self.cell.colspan), lambda: True),
                (_("Delete Col&umn"), self._delete_column, lambda: self.table.columns > 1),
                (
                    _("&Merge with Right") + "\tCtrl+Alt+Shift+Right",
                    self._merge_right,
                    lambda: can_merge_right(self.table, self.cell),
                ),
                (
                    _("Merge with Belo&w") + "\tCtrl+Alt+Shift+Down",
                    self._merge_down,
                    lambda: can_merge_down(self.table, self.cell),
                ),
                (_("&Split Cell"), self._split, lambda: self.cell.rowspan > 1 or self.cell.colspan > 1),
            )
            actions = wx.Button(self, label=_("&Actions"))
            actions.Bind(wx.EVT_BUTTON, lambda _event: self._show_actions())
            header = wx.BoxSizer(wx.HORIZONTAL)
            header.Add(wx.StaticText(self, label=_("&Header rows:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
            header.Add(self.header)
            header.AddStretchSpacer()
            header.Add(actions)
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(self.cells, 1, wx.ALL | wx.EXPAND, 16)
            sizer.Add(header, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 16)
            sizer.Add(self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL), 0, wx.ALL | wx.EXPAND, 16)
            self.SetSizer(sizer)
            self.header.Bind(wx.EVT_SPINCTRL, lambda _event: self._set_header())
            self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
            self._show(0, 0)

        def _show(self, row: int, column: int, focus: bool = True) -> None:
            """The grid again, the cell at (row, column) the current one (and focused, with `focus`)."""
            self.cell = cell_at(self.table, min(row, self.table.rows - 1), min(column, self.table.columns - 1))
            self.fields = []
            self.cells.DestroyChildren()
            grid = wx.GridBagSizer(vgap=4, hgap=4)
            for index, cell in enumerate(self.table.cells):  # Row by row: the order Tab takes.
                field = wx.TextCtrl(self.cells, value=cell.content, style=wx.TE_MULTILINE, size=(150, 64))
                set_accessibility_label(field, cell_position(cell))
                if cell.header:
                    field.SetFont(field.GetFont().Bold())
                field.Bind(wx.EVT_TEXT, lambda _event, index=index: self._edit_content(index))
                field.Bind(wx.EVT_SET_FOCUS, lambda event, index=index: self._focused(event, index))
                field.Bind(wx.EVT_KILL_FOCUS, lambda event, index=index: self._left(event, index))
                field.Bind(wx.EVT_CONTEXT_MENU, lambda _event: self._show_actions())
                grid.Add(field, (cell.row, cell.column), (cell.rowspan, cell.colspan), wx.EXPAND)
                self.fields.append(field)
            for column in range(self.table.columns):
                grid.AddGrowableCol(column)
            margin = wx.BoxSizer(wx.VERTICAL)  # Room for the lines around the outer cells.
            margin.Add(grid, 1, wx.ALL | wx.EXPAND, 3)
            self.cells.SetSizer(margin)
            self.cells.SetMinSize((640, min(margin.GetMinSize().height + 8, 320)))  # No taller than the table.
            self.cells.SetupScrolling(scrollToTop=False)
            self.cells.Refresh()
            self.Fit()
            self.header.SetRange(0, self.table.rows)
            self.header.SetValue(header_row_count(self.table))
            if focus:
                self.fields[self.table.cells.index(self.cell)].SetFocus()

        def _focused(self, event: wx.FocusEvent, index: int) -> None:
            self.cell = self.table.cells[index]
            self.cells.Refresh()
            event.Skip()

        def _left(self, event: wx.FocusEvent, index: int) -> None:
            """The cell's whole name again: it may be read next from anywhere."""
            if index < len(self.fields):
                set_accessibility_label(self.fields[index], cell_position(self.table.cells[index]))
                self.cells.Refresh()
            event.Skip()

        def _on_key(self, event: wx.KeyEvent) -> None:
            """In a cell, with Command+Option: an arrow, the next cell that way (a merged cell's first row or
            column); T, the actions' menu; with Shift too, Right and Down merge. Tab names the next cell."""
            focused = wx.Window.FindFocus()
            if focused not in self.fields:
                event.Skip()
                return
            key, modifiers = event.GetKeyCode(), event.GetModifiers()
            index = self.fields.index(focused)
            cell = self.table.cells[index]
            if key == wx.WXK_TAB and modifiers in (wx.MOD_NONE, wx.MOD_SHIFT):
                target = index + (1 if modifiers == wx.MOD_NONE else -1)
                if 0 <= target < len(self.fields):
                    self._name_from(cell, target)
                event.Skip()
            elif modifiers == wx.MOD_CONTROL | wx.MOD_ALT and key in _ARROWS:
                found = neighbour(self.table, cell, _ARROWS[key])
                if found is not None:
                    target = self.table.cells.index(found)
                    self._name_from(cell, target)
                    self.fields[target].SetFocus()
            elif modifiers == wx.MOD_CONTROL | wx.MOD_ALT and key == ord("T"):
                self._show_actions()
            elif modifiers == wx.MOD_CONTROL | wx.MOD_ALT | wx.MOD_SHIFT and key == wx.WXK_RIGHT:
                if can_merge_right(self.table, cell):
                    self._merge_right()
            elif modifiers == wx.MOD_CONTROL | wx.MOD_ALT | wx.MOD_SHIFT and key == wx.WXK_DOWN:
                if can_merge_down(self.table, cell):
                    self._merge_down()
            else:
                event.Skip()

        def _name_from(self, cell: GridCell, target: int) -> None:
            """Name the field about to take the focus by what changes, before the screen reader reads it."""
            set_accessibility_label(self.fields[target], cell_position(self.table.cells[target], cell))

        def _show_actions(self) -> None:
            """The actions on the current cell, as a menu: from a cell, the focus stays in it."""
            menu = wx.Menu()
            for label, action, applies in self.actions:
                item = menu.Append(wx.ID_ANY, label)
                item.Enable(applies())
                menu.Bind(wx.EVT_MENU, lambda _event, action=action: wx.CallAfter(action), item)
            self.PopupMenu(menu)
            menu.Destroy()

        def _edit_content(self, index: int) -> None:
            self.table = with_content(self.table, self.table.cells[index], self.fields[index].GetValue())
            self.cell = self.table.cells[index]

        def _change(self, table: GridTable, row: int, column: int) -> None:
            self.table = table
            self._show(row, column)

        def _insert_row(self, offset: int) -> None:
            self._change(insert_row(self.table, self.cell.row + offset), self.cell.row + offset, self.cell.column)

        def _delete_row(self) -> None:
            self._change(delete_row(self.table, self.cell.row), self.cell.row, self.cell.column)

        def _insert_column(self, offset: int) -> None:
            index = self.cell.column + offset
            self._change(insert_column(self.table, index), self.cell.row, index)

        def _delete_column(self) -> None:
            self._change(delete_column(self.table, self.cell.column), self.cell.row, self.cell.column)

        def _merge_right(self) -> None:
            table, merged = merge_right(self.table, self.cell)
            self._change(table, merged.row, merged.column)

        def _merge_down(self) -> None:
            table, merged = merge_down(self.table, self.cell)
            self._change(table, merged.row, merged.column)

        def _split(self) -> None:
            self._change(split(self.table, self.cell), self.cell.row, self.cell.column)

        def _set_header(self) -> None:
            try:
                table = with_header_rows(self.table, self.header.GetValue())
            except TableEditError:
                wx.MessageBox(
                    _("A merged cell crosses the end of the header. Split it, or choose another number of rows."),
                    _("Edit Table"),
                    wx.OK | wx.ICON_WARNING,
                    self,
                )
                self.header.SetValue(header_row_count(self.table))
                return
            self.table = table
            self._show(self.cell.row, self.cell.column, focus=False)

    _ARROWS = {wx.WXK_UP: "up", wx.WXK_DOWN: "down", wx.WXK_LEFT: "left", wx.WXK_RIGHT: "right"}

else:

    class LinkDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed")

    class TableEditDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed")

    class TableDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed")

    class ChartDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed")

    class FlowchartDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed")
