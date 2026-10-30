"""The document's Insert dialogs: a link, a table and a chart. Native controls only, which screen readers read."""

from __future__ import annotations

from mathessible.i18n import _

try:
    import wx
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

else:

    class LinkDialog:  # type: ignore[no-redef]
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
