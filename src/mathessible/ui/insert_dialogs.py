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

try:
    import wx
    import wx.lib.scrolledpanel
except ImportError:
    wx = None


if wx is not None:

    class _FormDialog(wx.Dialog):
        def __init__(self, parent: wx.Window, title: str):
            super().__init__(parent, title=title)
            self.grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=12)
            self.grid.AddGrowableCol(1)

        def _row(self, label: str, control: wx.Window, name: str) -> wx.Window:
            control.SetName(name)
            self.grid.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            self.grid.Add(control, 1, wx.EXPAND)
            return control

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
            """A graph's function and range, or a data chart's rows and series: only the kind's are enabled."""
            kind = self.selected_kind()
            graph = kind == "function"
            data = kind != "function"
            for control in (self.function, self.start, self.end):
                control.Enable(graph)
            for control in (self.rows, self.series):
                control.Enable(data)
            self.series.Enable(data and kind != "pie")

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
        as Markdown. Tab goes through the cells row by row, Command+Option+arrow to the next cell that way.
        The buttons act on the last cell that had the focus. OK gives `table`, which the caller writes back."""

        def __init__(self, parent: wx.Window, table: GridTable):
            super().__init__(parent, title=_("Edit Table"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
            self.table = table
            self.cell: GridCell = table.cells[0]
            self.cells = wx.lib.scrolledpanel.ScrolledPanel(self, size=(640, 320), style=wx.BORDER_THEME)
            self.fields: list[wx.TextCtrl] = []  # In the order of `table.cells`.
            self.header = wx.SpinCtrl(self, min=0, max=table.rows, initial=header_row_count(table))
            self.header.SetName(_("Header rows"))
            self.actions: list[tuple[wx.Button, Callable[[], bool]]] = []
            buttons = wx.GridSizer(cols=3, vgap=6, hgap=6)
            for label, action, applies in (
                (_("Insert Row &Above"), lambda: self._insert_row(0), lambda: True),
                (_("Insert Row &Below"), lambda: self._insert_row(self.cell.rowspan), lambda: True),
                (_("&Delete Row"), self._delete_row, lambda: self.table.rows > 1),
                (_("Insert Column &Left"), lambda: self._insert_column(0), lambda: True),
                (_("Insert Column &Right"), lambda: self._insert_column(self.cell.colspan), lambda: True),
                (_("Delete Col&umn"), self._delete_column, lambda: self.table.columns > 1),
                (_("&Merge with Right"), self._merge_right, lambda: can_merge_right(self.table, self.cell)),
                (_("Merge with Belo&w"), self._merge_down, lambda: can_merge_down(self.table, self.cell)),
                (_("&Split Cell"), self._split, lambda: self.cell.rowspan > 1 or self.cell.colspan > 1),
            ):
                button = wx.Button(self, label=label)
                button.Bind(wx.EVT_BUTTON, lambda _event, action=action: action())
                buttons.Add(button, 0, wx.EXPAND)
                self.actions.append((button, applies))
            header = wx.BoxSizer(wx.HORIZONTAL)
            header.Add(wx.StaticText(self, label=_("&Header rows:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
            header.Add(self.header)
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(self.cells, 1, wx.ALL | wx.EXPAND, 16)
            sizer.Add(header, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 16)
            sizer.Add(buttons, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 16)
            sizer.Add(self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL), 0, wx.ALL | wx.EXPAND, 16)
            self.SetSizer(sizer)
            self.header.Bind(wx.EVT_SPINCTRL, lambda _event: self._set_header())
            self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
            self._show(0, 0)
            self.Fit()

        def _show(self, row: int, column: int, focus: bool = True) -> None:
            """The grid again, the cell at (row, column) the current one (and focused, with `focus`)."""
            self.cell = cell_at(self.table, min(row, self.table.rows - 1), min(column, self.table.columns - 1))
            self.cells.DestroyChildren()
            self.fields = []
            grid = wx.GridBagSizer(vgap=4, hgap=4)
            for index, cell in enumerate(self.table.cells):  # Row by row: the order Tab takes.
                field = wx.TextCtrl(self.cells, value=cell.content, style=wx.TE_MULTILINE, size=(150, 64))
                set_accessibility_label(field, cell_position(cell))
                if cell.header:
                    field.SetFont(field.GetFont().Bold())
                field.Bind(wx.EVT_TEXT, lambda _event, index=index: self._edit_content(index))
                field.Bind(wx.EVT_SET_FOCUS, lambda event, index=index: self._focused(event, index))
                grid.Add(field, (cell.row, cell.column), (cell.rowspan, cell.colspan), wx.EXPAND)
                self.fields.append(field)
            for column in range(self.table.columns):
                grid.AddGrowableCol(column)
            self.cells.SetSizer(grid)
            self.cells.SetupScrolling(scrollToTop=False)
            self.header.SetRange(0, self.table.rows)
            self.header.SetValue(header_row_count(self.table))
            self._update_actions()
            if focus:
                self.fields[self.table.cells.index(self.cell)].SetFocus()

        def _focused(self, event: wx.FocusEvent, index: int) -> None:
            self.cell = self.table.cells[index]
            self._update_actions()
            event.Skip()

        def _on_key(self, event: wx.KeyEvent) -> None:
            """Command+Option+arrow: the next cell that way (a merged cell's first row or column)."""
            direction = _ARROWS.get(event.GetKeyCode())
            focused = wx.Window.FindFocus()
            if direction is None or event.GetModifiers() != wx.MOD_CONTROL | wx.MOD_ALT or focused not in self.fields:
                event.Skip()
                return
            target = neighbour(self.table, self.table.cells[self.fields.index(focused)], direction)
            if target is not None:
                self.fields[self.table.cells.index(target)].SetFocus()

        def _update_actions(self) -> None:
            for button, applies in self.actions:
                button.Enable(applies())

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
