from __future__ import annotations

from mathessible.i18n import N_, _
from mathessible.templates.matrix_templates import MATRIX_FENCES, MAX_MATRIX_SIZE

try:
    import wx
except ImportError:
    wx = None


FENCE_LABELS = {
    "parentheses": N_("Parentheses ( )"),
    "brackets": N_("Brackets [ ]"),
    "bars": N_("Vertical bars | | (determinant)"),
}
# "none" (a bare `■(...)`) is left out on purpose: MathCAT reads an unfenced
# table as "2 lines" of equations, not a matrix, and its cell navigation
# then lands on the wrong cell. It stays available in insert_matrix_template.


if wx is not None:

    class MatrixDialog(wx.Dialog):
        def __init__(self, parent: wx.Window, rows: int = 2, columns: int = 2, fence: str = "parentheses"):
            super().__init__(parent, title=_("Insert Matrix"), style=wx.DEFAULT_DIALOG_STYLE)
            self.SetName(_("Insert matrix dialog"))

            sizer = wx.BoxSizer(wx.VERTICAL)
            grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=12)
            rows_label = wx.StaticText(self, label=_("&Rows"))
            self.rows = wx.SpinCtrl(self, min=1, max=MAX_MATRIX_SIZE, initial=rows)
            self.rows.SetName(_("Rows"))
            columns_label = wx.StaticText(self, label=_("&Columns"))
            self.columns = wx.SpinCtrl(self, min=1, max=MAX_MATRIX_SIZE, initial=columns)
            self.columns.SetName(_("Columns"))
            fence_label = wx.StaticText(self, label=_("&Brackets"))
            self._fence_keys = [key for key in FENCE_LABELS if key in MATRIX_FENCES]
            self.fence = wx.Choice(self, choices=[_(FENCE_LABELS[key]) for key in self._fence_keys])
            self.fence.SetName(_("Brackets"))
            self.fence.SetSelection(self._fence_keys.index(fence) if fence in self._fence_keys else 0)
            grid.AddMany(
                [
                    (rows_label, 0, wx.ALIGN_CENTER_VERTICAL),
                    (self.rows, 0, wx.EXPAND),
                    (columns_label, 0, wx.ALIGN_CENTER_VERTICAL),
                    (self.columns, 0, wx.EXPAND),
                    (fence_label, 0, wx.ALIGN_CENTER_VERTICAL),
                    (self.fence, 0, wx.EXPAND),
                ]
            )
            buttons = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)

            sizer.Add(grid, 0, wx.ALL | wx.EXPAND, 12)
            if buttons is not None:
                sizer.Add(buttons, 0, wx.ALL | wx.EXPAND, 12)
            self.SetSizerAndFit(sizer)
            self.rows.SetFocus()

        @property
        def selected_rows(self) -> int:
            return self.rows.GetValue()

        @property
        def selected_columns(self) -> int:
            return self.columns.GetValue()

        @property
        def selected_fence(self) -> str:
            return self._fence_keys[max(0, self.fence.GetSelection())]

else:

    class MatrixDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
