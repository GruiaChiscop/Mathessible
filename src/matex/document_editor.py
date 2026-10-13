from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass

from .editor import EquationEditor
from .markdown_math import MathZone, math_zone_at
from .settings import AppSettings
from .speech import AssistiveOutput, create_output

try:
    import wx
except ImportError:
    wx = None


# Option+= types "≠" on macOS (and the character was swallowed by the
# shortcut), so there the physical Control key is used, as in Word for Mac.
# Command+= stays free for the equation editor's subscript template.
EQUATION_SHORTCUT_LABEL = "Control+=" if sys.platform == "darwin" else "Alt+="


@dataclass(frozen=True, slots=True)
class EquationEditSession:
    zone: MathZone
    selection_start: int
    selection_end: int


if wx is not None:

    def _is_equation_shortcut(event: wx.KeyEvent) -> bool:
        keys = {event.GetKeyCode(), event.GetUnicodeKey()}
        if not keys & {ord("="), ord("+")}:
            return False
        if sys.platform == "darwin":
            return event.RawControlDown() and not event.CmdDown() and not event.AltDown()
        return event.AltDown()

    class EquationDialog(wx.Dialog):
        def __init__(self, parent: wx.Window, output: AssistiveOutput, settings: AppSettings):
            super().__init__(
                parent,
                title="Equation Editor",
                size=(900, 520),
                style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            )
            self.SetMinSize((620, 420))
            self.SetName("Equation Editor dialog")
            sizer = wx.BoxSizer(wx.VERTICAL)
            self.heading = wx.StaticText(
                self,
                label=f"Enter or {EQUATION_SHORTCUT_LABEL} saves. Escape cancels.",
            )
            self.equation = EquationEditor(self, source="", output=output, settings=settings)
            sizer.Add(self.heading, 0, wx.ALL | wx.EXPAND, 10)
            sizer.Add(self.equation, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
            self.SetSizer(sizer)
            self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
            self.Bind(wx.EVT_CLOSE, self._on_close)

        def prepare(self, source: str, display: bool) -> None:
            kind = "display" if display else "inline"
            self.heading.SetLabel(
                f"Edit {kind} equation — Enter or {EQUATION_SHORTCUT_LABEL} saves. Escape cancels."
            )
            self.equation.set_source(source)

        def _on_char_hook(self, event: wx.KeyEvent) -> None:
            key = event.GetKeyCode()
            if key == wx.WXK_ESCAPE:
                self.EndModal(wx.ID_CANCEL)
                return
            # The equation editor has no use for Enter itself, so it saves.
            if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                self.EndModal(wx.ID_OK)
                return
            if _is_equation_shortcut(event):
                self.EndModal(wx.ID_OK)
                return
            event.Skip()

        def _on_close(self, event: wx.CloseEvent) -> None:
            if self.IsModal():
                self.EndModal(wx.ID_CANCEL)
            else:
                event.Skip()

    class DocumentEditor(wx.Panel):
        def __init__(
            self,
            parent: wx.Window,
            source: str = "",
            output: AssistiveOutput | None = None,
            settings: AppSettings | None = None,
        ):
            super().__init__(parent)
            self.settings = settings or AppSettings()
            self.output = output or create_output()
            self._session: EquationEditSession | None = None
            # Called with True before the equation dialog opens and False once
            # it has closed (the main frame swaps its Edit menu items).
            self.on_equation_editing: Callable[[bool], None] | None = None

            self.markdown = wx.TextCtrl(
                self,
                value=source,
                style=wx.TE_MULTILINE | wx.TE_RICH2,
            )
            self.markdown.SetName("Markdown editor")
            # macOS turns "--" into "—" and straight quotes into curly ones,
            # which breaks Markdown and UnicodeMath source.
            if hasattr(self.markdown, "OSXDisableAllSmartSubstitutions"):
                self.markdown.OSXDisableAllSmartSubstitutions()
            self.equation_dialog = EquationDialog(self, self.output, self.settings)

            self._sizer = wx.BoxSizer(wx.VERTICAL)
            self._sizer.Add(self.markdown, 1, wx.EXPAND)
            self.SetSizer(self._sizer)

            self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

            self._shortcut_id = wx.NewIdRef()
            self.Bind(wx.EVT_MENU, self._on_equation_accelerator, id=self._shortcut_id)
            self.SetAcceleratorTable(
                wx.AcceleratorTable([(self._shortcut_modifier(), ord("="), self._shortcut_id)])
            )

        @staticmethod
        def _shortcut_modifier() -> int:
            return wx.ACCEL_RAW_CTRL if sys.platform == "darwin" else wx.ACCEL_ALT

        @property
        def source(self) -> str:
            return self.markdown.GetValue()

        @property
        def editing_equation(self) -> bool:
            return self._session is not None

        def set_source(self, source: str) -> None:
            if self._session is not None:
                self._session = None
            self.markdown.ChangeValue(source)
            self.markdown.SetInsertionPoint(0)
            self.markdown.SetFocus()

        def commit_active_equation(self) -> None:
            if self._session is not None and self.equation_dialog.IsModal():
                self.equation_dialog.EndModal(wx.ID_OK)

        def _announce(self, message: str) -> None:
            try:
                self.output.announce(message, interrupt=True)
            except Exception:
                pass

        def _on_char_hook(self, event: wx.KeyEvent) -> None:
            if not self.editing_equation and _is_equation_shortcut(event):
                self._open_equation()
                return
            event.Skip()

        def _on_equation_accelerator(self, _event: wx.CommandEvent) -> None:
            if not self.editing_equation:
                self._open_equation()

        def _open_equation(self, _event: wx.CommandEvent | None = None) -> None:
            if self.editing_equation:
                return
            source = self.markdown.GetValue()
            selection_start, selection_end = self.markdown.GetSelection()
            zone = math_zone_at(source, selection_start, selection_end)
            if zone is None:
                zone = MathZone(
                    selection_start,
                    selection_start,
                    selection_end,
                    selection_end,
                    False,
                )
                content = source[selection_start:selection_end]
            else:
                content = zone.content(source)

            self._session = EquationEditSession(zone, selection_start, selection_end)
            self.equation_dialog.prepare(content, zone.display)
            wx.CallAfter(self.equation_dialog.equation.SetFocus)
            if content:
                wx.CallAfter(self.equation_dialog.equation.read_expression)
            self.equation_dialog.CentreOnParent()
            if self.on_equation_editing is not None:
                self.on_equation_editing(True)
            try:
                result = self.equation_dialog.ShowModal()
            finally:
                if self.on_equation_editing is not None:
                    self.on_equation_editing(False)
            session = self._session
            self._session = None
            if session is None:
                return
            if result == wx.ID_OK:
                replacement = (
                    f"{session.zone.delimiter}{self.equation_dialog.equation.source}"
                    f"{session.zone.delimiter}"
                )
                self.markdown.SetSelection(session.zone.start, session.zone.end)
                self.markdown.WriteText(replacement)
                caret = session.zone.start + len(replacement)
                self.markdown.SetSelection(caret, caret)
                self._announce("equation saved")
            else:
                self.markdown.SetSelection(session.selection_start, session.selection_end)
                self._announce("equation editing canceled")
            self.markdown.SetFocus()

else:

    class DocumentEditor:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
