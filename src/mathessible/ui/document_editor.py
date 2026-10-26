from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass

from mathessible import session_log
from mathessible.documents.clipboard_html import document_html
from mathessible.documents.markdown_math import MathZone, math_zone_at, toggle_display
from mathessible.editing.autocorrect import AutoCorrectTable, autocorrect_defaults
from mathessible.editing.space_conversion import convert_in_text, convert_shortcut_on_character
from mathessible.editor.equation_editor import EquationEditor
from mathessible.editor.structures import append_insert_items
from mathessible.settings import AppSettings
from mathessible.ui.clipboard import set_clipboard_text
from mathessible.ui.help_menu import append_help_menu
from mathessible.ui.speech import AssistiveOutput, create_output

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

    class EquationWindow(wx.Frame):
        """The equation editor: a window of its own with its own menu bar.

        Not a modal dialog: on macOS a modal session disables the menu bar of
        every other window, so the Insert menu could never be used. Instead
        the other windows are disabled while it is open (`begin`/`finish`),
        and its menus (Equation, Edit, Insert, View) replace the document's
        in the menu bar while it is active.
        """

        def __init__(self, parent: wx.Window, output: AssistiveOutput, settings: AppSettings):
            super().__init__(
                wx.GetTopLevelParent(parent),
                title="Equation Editor",
                size=(900, 560),
                style=wx.DEFAULT_FRAME_STYLE | wx.FRAME_FLOAT_ON_PARENT,
            )
            self.SetMinSize((620, 440))
            self.SetName("Equation Editor window")
            self._on_done: Callable[[bool], None] | None = None
            self._disabled: list[wx.TopLevelWindow] = []
            panel = wx.Panel(self)
            sizer = wx.BoxSizer(wx.VERTICAL)
            self.heading = wx.StaticText(
                panel,
                label=f"Enter or {EQUATION_SHORTCUT_LABEL} saves. Escape cancels.",
            )
            self.equation = EquationEditor(panel, source="", output=output, settings=settings)
            sizer.Add(self.heading, 0, wx.ALL | wx.EXPAND, 10)
            sizer.Add(self.equation, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
            panel.SetSizer(sizer)
            self._create_menu()
            self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
            self.Bind(wx.EVT_CLOSE, self._on_close)

        def _create_menu(self) -> None:
            # Plain ids, never the stock wxID_CUT/COPY/...: wxOSX maps those to
            # native actions only a native text view can perform.
            menu_bar = wx.MenuBar()
            equation_menu = wx.Menu()
            save_item = equation_menu.Append(wx.ID_ANY, "&Save Equation (Enter)")
            cancel_item = equation_menu.Append(wx.ID_ANY, "&Cancel (Escape)")
            self.Bind(wx.EVT_MENU, lambda _event: self.finish(True), save_item)
            self.Bind(wx.EVT_MENU, lambda _event: self.finish(False), cancel_item)
            equation_menu.AppendSeparator()
            errors_item = equation_menu.Append(wx.ID_ANY, "&Errors…\tF8")
            self.Bind(wx.EVT_MENU, lambda _event: self.equation.show_errors(), errors_item)
            new_equation_item = equation_menu.Append(wx.ID_ANY, "Save as &New Equation…")
            self.Bind(wx.EVT_MENU, lambda _event: self.equation.save_as_new_equation(), new_equation_item)
            display_item = equation_menu.Append(wx.ID_ANY, "Change to &Display")
            self.Bind(wx.EVT_MENU, lambda _event: self.toggle_display(), display_item)
            self.Bind(
                wx.EVT_UPDATE_UI,
                lambda event: event.SetText("Change to &Inline" if self.equation.display else "Change to &Display"),
                display_item,
            )
            menu_bar.Append(equation_menu, "E&quation")
            edit_menu = wx.Menu()
            edit_items = (
                ("undo", "&Undo\tCtrl+Z"),
                ("redo", "&Redo\tCtrl+Shift+Z"),
                None,
                ("cut", "Cu&t\tCtrl+X"),
                ("copy", "&Copy\tCtrl+C"),
                ("paste", "&Paste\tCtrl+V"),
                None,
                ("select_all", "Select &All\tCtrl+A"),
            )
            for entry in edit_items:
                if entry is None:
                    edit_menu.AppendSeparator()
                    continue
                command, label = entry
                item = edit_menu.Append(wx.ID_ANY, label)
                self.Bind(wx.EVT_MENU, lambda _event, command=command: self.equation.edit_command(command), item)
                if command in ("undo", "redo", "cut", "paste", "select_all"):
                    # Undo works on the built equation too (it is rebuilt).
                    self.Bind(wx.EVT_UPDATE_UI, self._enable_when_editable, item)
                elif command != "copy":
                    self.Bind(wx.EVT_UPDATE_UI, self._enable_in_linear_view, item)
            menu_bar.Append(edit_menu, "&Edit")
            insert_menu = wx.Menu()
            for item_id, entry in append_insert_items(insert_menu).items():
                self.Bind(wx.EVT_MENU, lambda _event, entry=entry: self.equation.insert_item(entry), id=item_id)
                self.Bind(wx.EVT_UPDATE_UI, self._enable_when_editable, id=item_id)
            menu_bar.Append(insert_menu, "&Insert")
            view_menu = wx.Menu()
            professional_item = view_menu.AppendCheckItem(wx.ID_ANY, "&Professional View\tF2")
            writing_item = view_menu.AppendCheckItem(wx.ID_ANY, "&Writing Mode\tF10")
            view_menu.AppendSeparator()
            zoom_in = view_menu.Append(wx.ID_ANY, "Zoom &In\tCtrl+Alt+=")
            zoom_out = view_menu.Append(wx.ID_ANY, "Zoom &Out\tCtrl+Alt+-")
            actual_size = view_menu.Append(wx.ID_ANY, "&Actual Size\tCtrl+Alt+0")
            self.Bind(wx.EVT_MENU, lambda _event: self.equation.zoom(1), zoom_in)
            self.Bind(wx.EVT_MENU, lambda _event: self.equation.zoom(-1), zoom_out)
            self.Bind(wx.EVT_MENU, lambda _event: self.equation.zoom(0), actual_size)
            self.Bind(wx.EVT_MENU, lambda _event: self.equation.toggle_writing(), writing_item)
            self.Bind(wx.EVT_UPDATE_UI, lambda event: event.Check(self.equation.writing_enabled), writing_item)
            self.Bind(wx.EVT_MENU, lambda _event: self.equation.toggle_mode(), professional_item)
            self.Bind(
                wx.EVT_UPDATE_UI,
                lambda event: event.Check(self.equation.mode == "professional"),
                professional_item,
            )
            menu_bar.Append(view_menu, "&View")
            append_help_menu(self, menu_bar)
            self.SetMenuBar(menu_bar)

        def _enable_in_linear_view(self, event: wx.UpdateUIEvent) -> None:
            event.Enable(self.equation.mode == "linear")

        def _enable_when_editable(self, event: wx.UpdateUIEvent) -> None:
            # Professional view edits the source too, where MathCAT is.
            event.Enable(self.equation.mode == "linear" or self.equation.mathcat is not None)

        def prepare(self, source: str, display: bool) -> None:
            self.equation.display = display
            self._show_kind()
            self.equation.set_source(source)

        def toggle_display(self) -> None:
            """Word's Change to Display / Change to Inline; it takes effect when the equation is saved."""
            self.equation.display = not self.equation.display
            kind = "display" if self.equation.display else "inline"
            session_log.write("command", f"change to {kind}")
            self._show_kind()
            try:
                self.equation.output.announce(f"{kind} equation", interrupt=True)
            except Exception:
                pass

        def _show_kind(self) -> None:
            kind = "display" if self.equation.display else "inline"
            self.heading.SetLabel(f"Edit {kind} equation — Enter or {EQUATION_SHORTCUT_LABEL} saves. Escape cancels.")

        def begin(self, on_done: Callable[[bool, bool], None]) -> None:
            """Show the editor, the other windows disabled until `finish` calls `on_done(saved, new_line)`."""
            self._on_done = on_done
            self.CentreOnParent()
            # Not wx.WindowDisabler: on macOS it begins a modal session too,
            # which dims this window's own menus as well.
            self._disabled = [window for window in wx.GetTopLevelWindows() if window is not self and window.IsEnabled()]
            for window in self._disabled:
                window.Disable()
            self.Show()
            self.Raise()

        def finish(self, saved: bool, new_line: bool = False) -> None:
            """Close the editor; `new_line` (Enter) also starts a new line after the equation, as in Word."""
            on_done, self._on_done = self._on_done, None
            if on_done is None:
                return
            if saved:
                self.equation.remove_extra_spaces()
            session_log.write("close", f"{'saved' if saved else 'cancelled'}: {self.equation.source!r}")
            self._enable_others()
            self.Hide()
            on_done(saved, new_line)

        def _on_char_hook(self, event: wx.KeyEvent) -> None:
            key = event.GetKeyCode()
            if key == wx.WXK_ESCAPE:
                if self.equation.dismiss_completion():
                    return
                self.finish(False)
                return
            # The equation editor has no use for Enter itself, so it saves, and
            # goes on on a new line after the equation, as Enter does in Word.
            if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                self.finish(True, new_line=True)
                return
            if _is_equation_shortcut(event):
                self.finish(True)
                return
            event.Skip()

        def _on_close(self, event: wx.CloseEvent) -> None:
            # Closing the window cancels; it is kept for the next equation.
            if event.CanVeto():
                event.Veto()
                self.finish(False)
                return
            self._enable_others()
            event.Skip()

        def _enable_others(self) -> None:
            for window in self._disabled:
                if window:  # A window destroyed meanwhile is falsy.
                    window.Enable()
            self._disabled = []

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
            self.equation_window = EquationWindow(self, self.output, self.settings)

            self._sizer = wx.BoxSizer(wx.VERTICAL)
            self._sizer.Add(self.markdown, 1, wx.EXPAND)
            self.SetSizer(self._sizer)

            self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
            self.markdown.Bind(wx.EVT_CHAR, self._on_markdown_char)

            self._shortcut_id = wx.NewIdRef()
            self.Bind(wx.EVT_MENU, self._on_equation_accelerator, id=self._shortcut_id)
            self.SetAcceleratorTable(wx.AcceleratorTable([(self._shortcut_modifier(), ord("="), self._shortcut_id)]))

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
            if self._session is not None:
                self.equation_window.finish(True)

        def _announce(self, message: str) -> None:
            try:
                self.output.announce(message, interrupt=True)
            except Exception:
                pass

        def copy_selection(self, cut: bool = False) -> bool:
            """Copy (or cut) the selection with its equations as MathML beside the text, for Word.

            False when the selection holds no equation or the converter is
            not ready: the Markdown editor's own Copy/Cut then does it.
            """
            start, end = self.markdown.GetSelection()
            equation = self.equation_window.equation
            if start == end or not equation.converter_ready:
                return False
            text = self.markdown.GetValue()[start:end]
            html = document_html(text, equation.convert_unicode_math)
            if html is None or not set_clipboard_text(text, html):
                return False
            if cut:
                self.markdown.Remove(start, end)
            return True

        def equation_at_caret(self) -> MathZone | None:
            start, end = self.markdown.GetSelection()
            return math_zone_at(self.markdown.GetValue(), start, end)

        def toggle_equation_display(self) -> None:
            """Word's Change to Display / Change to Inline on the equation at the caret."""
            source = self.markdown.GetValue()
            zone = self.equation_at_caret()
            if zone is None or self.editing_equation:
                return
            result = toggle_display(source, zone)
            if result is None:
                session_log.write("command", "document: cannot be inline")
                self._announce("this equation cannot be inline")
                return
            caret = self.markdown.GetInsertionPoint()
            new_source, new_zone = result
            session_log.write("command", f"document: change to {'display' if new_zone.display else 'inline'}")
            self.replace_source(new_source)
            offset = min(max(caret - zone.content_start, 0), new_zone.content_end - new_zone.content_start)
            self.markdown.SetInsertionPoint(new_zone.content_start + offset)
            self._announce("display equation" if new_zone.display else "inline equation")

        def replace_source(self, new_source: str) -> None:
            """Replace only the text that changed, as an edit of the Markdown editor, not a new document."""
            old = self.markdown.GetValue()
            start = 0
            while start < min(len(old), len(new_source)) and old[start] == new_source[start]:
                start += 1
            end_old, end_new = len(old), len(new_source)
            while end_old > start and end_new > start and old[end_old - 1] == new_source[end_new - 1]:
                end_old -= 1
                end_new -= 1
            self.markdown.SetSelection(start, end_old)
            self.markdown.WriteText(new_source[start:end_new])

        def _on_char_hook(self, event: wx.KeyEvent) -> None:
            if not self.editing_equation and _is_equation_shortcut(event):
                self._open_equation()
                return
            event.Skip()

        def _on_markdown_char(self, event: wx.KeyEvent) -> None:
            """Math AutoCorrect anywhere in the document, when on: Space, punctuation or Enter converts the entry before it."""
            if not self.settings.autocorrect_in_document or self.editing_equation:
                event.Skip()
                return
            key = event.GetKeyCode()
            character = "\n" if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) else chr(event.GetUnicodeKey() or 0)
            start, end = self.markdown.GetSelection()
            source = self.markdown.GetValue()
            typed = character == "\n" or character.isprintable()
            if event.HasModifiers() or start != end or not typed:
                event.Skip()
                return
            table = AutoCorrectTable(
                autocorrect_defaults(), self.settings.math_autocorrect, self.settings.math_autocorrect_removed
            )
            converted = None
            if self.settings.convert_shortcuts_immediately:
                # A symbol shortcut converts as its last character is typed (`->`), as in Word.
                converted = convert_shortcut_on_character(source, start, character, table.shortcuts())
            if converted is None:
                converted = convert_in_text(source, start, character, table.control_words(), table.shortcuts())
            if converted is None:
                event.Skip()
                return
            self.replace_source(converted.source)
            self.markdown.SetInsertionPoint(converted.caret)

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
            self.equation_window.prepare(content, zone.display)
            wx.CallAfter(self.equation_window.equation.SetFocus)
            if content:
                wx.CallAfter(self.equation_window.equation.read_expression)
            self.equation_window.begin(self._finish_equation)

        def _finish_equation(self, saved: bool, new_line: bool = False) -> None:
            session = self._session
            self._session = None
            if session is None:
                return
            if saved:
                content = self.equation_window.equation.source
                display = self.equation_window.equation.display
                replacement = f"{session.zone.delimiter}{content}{session.zone.delimiter}"
                self.markdown.SetSelection(session.zone.start, session.zone.end)
                self.markdown.WriteText(replacement)
                caret = session.zone.start + len(replacement)
                if display != session.zone.display:
                    zone = math_zone_at(self.markdown.GetValue(), session.zone.start + 1)
                    toggled = toggle_display(self.markdown.GetValue(), zone) if zone is not None else None
                    if toggled is not None:
                        self.replace_source(toggled[0])
                        caret = toggled[1].end
                self.markdown.SetSelection(caret, caret)
                if new_line:
                    self.markdown.WriteText("\n")
                self._announce("equation saved, new line" if new_line else "equation saved")
            else:
                self.markdown.SetSelection(session.selection_start, session.selection_end)
                self._announce("equation editing canceled")
            wx.GetTopLevelParent(self).Raise()
            self.markdown.SetFocus()

else:

    class DocumentEditor:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
