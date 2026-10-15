from __future__ import annotations

import threading
from collections.abc import Callable

from .clipboard import get_clipboard_text, set_clipboard_text
from .build_repair import BuildRepair
from .character_speech import character_name, deleted_character, inserted_character
from .insertion_point import describe_insertion_point
from .source_map import anchor_offset, leaf_before, leaf_nodes, map_leaves
from .symbol_dictionary import load_dictionary
from .editor_drawing import EditorDrawingMixin
from .editor_renderer import EquationRendererMixin
from .editor_structures import StructureActionsMixin
from .edit_history import EditHistory, EditState
from .mathcat import MathCatNavigator, create_mathcat_navigator
from .insert_catalog import InsertItem, item_for_key
from .math_templates import group_function_argument, move_to_slot
from .mathml_model import MathMLDocument
from .model import EquationDocument
from .settings import AppSettings
from .speech import AssistiveOutput, create_output
from .space_conversion import convert_before_character, convert_on_space, convert_shortcut_on_character
from .theme import Palette, palette
from .unicodemath import ConversionResult, UnicodeMathError, control_words
from .word_navigation import next_word_boundary, previous_word_boundary

try:
    import wx
    import wx.html2
except ImportError:  # The interface is an optional dependency.
    wx = None


if wx is not None:

    def _converter_control_words() -> dict[str, str] | None:
        """The converter's control-word table, or None (fallback list) without the submodule."""
        try:
            return control_words()
        except (OSError, ValueError):
            return None

    def _word_navigation_down(event: wx.KeyEvent) -> bool:
        """The word-navigation modifier: Option on macOS, Ctrl elsewhere."""
        return event.AltDown() if wx.Platform == "__WXMAC__" else event.ControlDown()

    def _template_variant_down(event: wx.KeyEvent) -> bool:
        """The template-variant modifier (limits, n-th root): physical Control on macOS, Alt elsewhere.

        Not Option on macOS: Option+S/P/I type ß, π and a dead key there
        (the same reason the equation shortcut is Control+=).
        """
        if wx.Platform == "__WXMAC__":
            return event.RawControlDown() and not event.CmdDown() and not event.AltDown()
        return event.AltDown() and not event.ControlDown()

    def _cell_navigation_down(event: wx.KeyEvent) -> bool:
        """The matrix-cell modifier: Command+Option on macOS, Ctrl+Alt elsewhere."""
        # CmdDown() is Command on macOS and Ctrl elsewhere.
        return event.CmdDown() and event.AltDown()

    def _effective_key(event: wx.KeyEvent) -> int:
        """The key code, with macOS's Command+Left/Right read as Home/End.

        Macs commonly have no Home/End keys; Command+Left/Right is the
        platform's own start/end-of-line gesture. Home/End keep working too.
        """
        key = event.GetKeyCode()
        if wx.Platform == "__WXMAC__" and event.CmdDown() and not event.AltDown():
            if key == wx.WXK_LEFT:
                return wx.WXK_HOME
            if key == wx.WXK_RIGHT:
                return wx.WXK_END
        return key

    class EquationEditor(EquationRendererMixin, StructureActionsMixin, EditorDrawingMixin, wx.Window):
        _BRAILLE_STRIP_HEIGHT = 28

        def __init__(
            self,
            parent: wx.Window,
            source: str = "a/(b+c)",
            output: AssistiveOutput | None = None,
            settings: AppSettings | None = None,
        ):
            super().__init__(parent, style=wx.BORDER_SIMPLE | wx.WANTS_CHARS)
            self.SetName("Equation editor")
            self.SetMinSize((500, 200))
            self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
            self.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))
            self.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT))
            self.document = EquationDocument(source)
            self.settings = settings or AppSettings()
            self.symbols = load_dictionary(self.settings.symbol_dictionary)
            self.output = output or create_output()
            self.mathcat: MathCatNavigator | None = create_mathcat_navigator(
                recognized_functions=self.settings.recognized_functions,
                auto_zoom_out=self._auto_zoom_out,
                boundary_stops=self._boundary_stops,
                structural_stops=self._structural_stops,
                invisible_operator_stops=self.settings.invisible_operator_stops,
            )
            self.mode = "linear"
            self.caret = len(source)
            self.selection_anchor: int | None = None
            self._dragging = False
            self.history = EditHistory(source, self.caret)
            self._layout = None
            self.mathml_document: MathMLDocument | None = None
            self.mathml_current_id: str | None = None
            self._highlight_matrix_cell = False
            self._last_matrix_shape = (2, 2, "parentheses")
            self._renderer_ready = False
            self._renderer_error: str | None = None
            self._pending_read = False
            self._webview: wx.html2.WebView | None = None
            # What the visible renderer currently shows: (mode, MathML) and the
            # highlighted node id; compared on paint to know when to update it.
            self._rendered: tuple[str, str] | None = None
            self._rendered_highlight: str | None = None
            self._renderer_sync_pending = False
            self._converting = False
            self._conversion_token = 0
            self._preparing = False
            self._preparing_announced = False
            self._preparation_token: object | None = None
            self._drawn_target: tuple[object, ...] | None = None
            self._professional_mathml: str | None = None
            # The text last built: the source, or it repaired (build_repair).
            self._repair = BuildRepair("", "")
            self.braille_label = wx.StaticText(self, label="Braille")
            self.braille_label.SetForegroundColour(self._colour(self._palette().subtle_text))
            self.braille_display = wx.TextCtrl(self, style=wx.TE_READONLY)
            self.braille_display.SetName("Equation braille")
            self.Bind(wx.EVT_PAINT, self._on_paint)
            self.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
            self.Bind(wx.EVT_CHAR, self._on_char)
            self.Bind(wx.EVT_SET_FOCUS, self._on_focus)
            self.Bind(wx.EVT_KILL_FOCUS, self._on_blur)
            self.Bind(wx.EVT_SIZE, self._on_size)
            self.Bind(wx.EVT_LEFT_DOWN, self._on_left_down)
            self.Bind(wx.EVT_LEFT_UP, self._on_left_up)
            self.Bind(wx.EVT_MOTION, self._on_motion)
            self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self._on_capture_lost)
            self.Bind(wx.EVT_RIGHT_DOWN, self._on_right_down)
            self._create_renderer()
            self._layout_children()

        def _start_linear_preparation(self) -> None:
            """Compute linear-navigation stops on a worker thread before navigating.

            Each MathCAT command re-derives the whole expression (~90 ms on a
            long one), and Left can only retrace Right over stops already
            found. Navigation is not held up meanwhile: Right discovers the
            next stop itself, and Left works over stops reached that way.
            Only Left/Right after a jump to an undiscovered spot (End, a
            click, ...) waits for this thread, which has its own MathCAT.
            """
            self._preparation_token = None
            self._preparing = False
            navigator = self.mathcat
            if navigator is None or not self.settings.linear_navigation or navigator.linear_ready:
                return
            token = object()
            self._preparation_token = token
            self._preparing = True
            self._preparing_announced = False
            mathml, job = navigator.mathml, navigator.linear_stops_job()

            def work() -> None:
                try:
                    stops = job()
                except (ImportError, OSError, RuntimeError, ValueError):
                    stops = ()
                wx.CallAfter(self._linear_preparation_done, token, navigator, mathml, stops)

            threading.Thread(target=work, name="matex-linear-stops", daemon=True).start()

        def _linear_preparation_done(
            self, token: object, navigator: MathCatNavigator, mathml: str, stops: tuple[object, ...]
        ) -> None:
            if not self or token is not self._preparation_token:
                return
            self._preparing = False
            self._preparation_token = None
            if navigator is self.mathcat:
                navigator.adopt_linear_stops(mathml, stops)  # type: ignore[arg-type]
            if self._preparing_announced and self.mode == "professional":
                self._announce("equation ready")

        def _palette(self) -> Palette:
            appearance = wx.SystemSettings.GetAppearance() if hasattr(wx.SystemSettings, "GetAppearance") else None
            return palette(dark=bool(appearance is not None and appearance.IsDark()))

        @staticmethod
        def _colour(rgb: tuple[int, int, int]) -> wx.Colour:
            return wx.Colour(*rgb)

        def _on_size(self, event: wx.SizeEvent) -> None:
            self._layout_children()
            event.Skip()

        def _layout_children(self) -> None:
            if self._webview is not None and self._webview.IsShown():
                self._webview.SetSize(self._renderer_rect().Deflate(3, 3))
            width, height = self.GetClientSize()
            strip_y = max(0, height - 30 - self._BRAILLE_STRIP_HEIGHT)
            label_width = 56
            control_height = max(1, self._BRAILLE_STRIP_HEIGHT - 6)
            self.braille_label.SetSize(wx.Rect(14, strip_y + 3, label_width, control_height))
            self.braille_display.SetSize(
                wx.Rect(
                    14 + label_width + 4,
                    strip_y + 1,
                    max(1, width - 28 - label_width - 4),
                    control_height,
                )
            )

        def _announce(self, text: str) -> None:
            try:
                self.output.announce(text, interrupt=True)
            except Exception:
                # Assistive output must never be able to close the editor.
                pass

        @property
        def source(self) -> str:
            return self.document.source

        def set_source(self, source: str) -> None:
            self.document = EquationDocument(source)
            self.caret = len(source)
            self.selection_anchor = None
            self.mode = "linear"
            self.mathml_document = None
            self.mathml_current_id = None
            self._highlight_matrix_cell = False
            self._pending_read = False
            self.history.reset(source, self.caret)
            self._update_braille_display()
            self.Refresh()

        @property
        def _auto_zoom_out(self) -> bool:
            # Linear navigation flows through every structure by design, so
            # it needs MathCAT to step out at a structure's end regardless.
            return self.settings.auto_zoom_out or self.settings.linear_navigation

        @property
        def _boundary_stops(self) -> bool:
            return self.settings.structure_stops and self.settings.linear_navigation

        @property
        def _structural_stops(self) -> bool:
            return self.settings.structure_stops and not self.settings.linear_navigation

        def apply_settings(self) -> None:
            self.symbols = load_dictionary(self.settings.symbol_dictionary)
            if self.mathcat is not None:
                self.mathcat.recognized_functions = self.settings.recognized_functions
                self.mathcat.auto_zoom_out = self._auto_zoom_out
                self.mathcat.boundary_stops = self._boundary_stops
                self.mathcat.structural_stops = self._structural_stops
                self.mathcat.invisible_operator_stops = self.settings.invisible_operator_stops
                if self.mathcat.mathml:
                    try:
                        self.mathcat.load(self.mathcat.mathml, keep_position=True)
                    except (OSError, RuntimeError, ValueError):
                        self.mathcat = create_mathcat_navigator(
                            recognized_functions=self.settings.recognized_functions,
                            auto_zoom_out=self._auto_zoom_out,
                            boundary_stops=self._boundary_stops,
                            structural_stops=self._structural_stops,
                            invisible_operator_stops=self.settings.invisible_operator_stops,
                        )
            if self.mode == "professional":
                self._sync_mathcat_cursor()
                self._start_linear_preparation()
            self._update_braille_display()
            self.Refresh()

        def _update_braille_display(self) -> None:
            """Mirror MathCAT's braille for the current navigation position.

            Only meaningful in professional mode, where a MathCAT position
            exists; linear mode shows raw text and has nothing to braille.
            """
            if self.mode != "professional" or self.mathcat is None:
                self.braille_display.ChangeValue("")
                return
            try:
                braille = self.mathcat.current_braille
            except (OSError, RuntimeError, ValueError):
                braille = ""
            self.braille_display.ChangeValue(braille)

        def _on_focus(self, event: wx.FocusEvent) -> None:
            self._announce(f"Equation editor, {self.mode} mode")
            self.Refresh()
            event.Skip()

        def _on_blur(self, event: wx.FocusEvent) -> None:
            self.Refresh()
            event.Skip()

        def _on_left_down(self, event: wx.MouseEvent) -> None:
            self.SetFocus()
            if self.mode != "linear":
                return
            position = self._caret_from_point(event.GetPosition())
            if event.ShiftDown():
                if self.selection_anchor is None:
                    self.selection_anchor = self.caret
            else:
                self.selection_anchor = position
            self.caret = position
            self._dragging = True
            if not self.HasCapture():
                self.CaptureMouse()
            self.Refresh()

        def _on_motion(self, event: wx.MouseEvent) -> None:
            if not self._dragging or not event.LeftIsDown():
                event.Skip()
                return
            self.caret = self._caret_from_point(event.GetPosition())
            self.Refresh()

        def _on_left_up(self, event: wx.MouseEvent) -> None:
            if self._dragging:
                self._dragging = False
                if self.HasCapture():
                    self.ReleaseMouse()
                if self._selection_range() is None:
                    self.selection_anchor = None
                else:
                    self._announce_selection()
            event.Skip()

        def _on_capture_lost(self, _event: wx.MouseCaptureLostEvent) -> None:
            self._dragging = False

        def _caret_from_point(self, point: wx.Point) -> int:
            dc = wx.ClientDC(self)
            dc.SetFont(self._source_font())
            content = self._source_rect()
            return self._caret_from_x(dc, point.x, content.x + 14)

        def _on_right_down(self, event: wx.MouseEvent) -> None:
            self.SetFocus()
            self._show_context_menu(event.GetPosition())

        def _caret_point(self) -> wx.Point:
            if self.mode != "linear":
                content = self._content_rect()
                return wx.Point(content.x + content.width // 2, content.y + content.height // 2)
            content = self._source_rect()
            dc = wx.ClientDC(self)
            dc.SetFont(self._source_font())
            width = dc.GetTextExtent(self.document.source[: self.caret])[0] if self.caret else 0
            return wx.Point(content.x + 14 + width, content.y + content.height // 2)

        def read_expression(self) -> None:
            if not self or not self.document.source:
                return
            if self._converting:
                wx.CallLater(30, self.read_expression)
                return
            if not self._renderer_ready:
                self._pending_read = True
                return
            self._pending_read = False
            try:
                conversion = self._convert_source()
                self.mathml_document = MathMLDocument.parse(
                    conversion.mathml,
                    recognized_functions=self.settings.recognized_functions,
                )
                if self.mathcat is not None:
                    speech = self.mathcat.load(conversion.mathml)
                    self.mathml_document = self.mathcat.structure
                    self._sync_mathcat_cursor()
                    self._announce(speech)
            except (UnicodeMathError, RuntimeError, ValueError) as error:
                self._announce(f"The equation could not be read. {error}")

        def _toggle_mode(self, attempts: int = 40) -> None:
            if self.mode == "linear" and self._converting and attempts > 0:
                # F2 arrived inside the live preview's RunScript (its nested
                # event loop): wait for that conversion instead of failing
                # with "busy".
                wx.CallLater(30, self._retry_toggle_mode, attempts - 1)
                return
            self._clear_selection()
            if self.mode == "linear":
                try:
                    conversion = self._convert_source()
                except (UnicodeMathError, RuntimeError, ValueError) as error:
                    self._announce(f"Professional mode could not be built. {error}")
                    return
                self._enter_professional_mode(conversion, error_prefix="Professional mode could not be built")
            else:
                self.mode = "linear"
                self._update_braille_display()
                self._announce("linear mode")
            self.Refresh()

        def _retry_toggle_mode(self, attempts: int) -> None:
            if self and self.mode == "linear":  # Not destroyed, not toggled meanwhile.
                self._toggle_mode(attempts)

        def _enter_professional_mode(self, conversion: ConversionResult, error_prefix: str) -> bool:
            self._professional_mathml = conversion.mathml
            try:
                self.mode = "professional"
                self.mathml_document = MathMLDocument.parse(
                    conversion.mathml,
                    recognized_functions=self.settings.recognized_functions,
                )
                if self.mathcat is not None:
                    try:
                        self.mathcat.load(conversion.mathml)
                        self.mathml_document = self.mathcat.structure
                        speech = self.mathcat.command("ZoomIn")
                        self._sync_mathcat_cursor()
                        self._announce(f"professional mode, {speech}")
                        self._start_linear_preparation()
                    except (OSError, RuntimeError, ValueError):
                        self.mathcat = None
                        self._announce("professional mode, equation")
                else:
                    self._announce("professional mode, equation")
                self._sync_mathcat_cursor()
                return True
            except (RuntimeError, ValueError) as error:
                self.mode = "linear"
                self._announce(f"{error_prefix}. {error}")
                return False

        def _on_key_down(self, event: wx.KeyEvent) -> None:
            key = event.GetKeyCode()
            command_modifier = event.CmdDown()
            if command_modifier and key in (ord("C"), ord("c")):
                self._copy_equation()
                return
            # Keyboard access to the right-click menu: the Menu key (Windows),
            # or Shift+F10 everywhere, as in other native text fields; both modes.
            if (
                key == wx.WXK_WINDOWS_MENU or (key == wx.WXK_F10 and event.ShiftDown() and not command_modifier)
            ):
                self._show_context_menu(self._caret_point())
                return
            if self.mode == "linear" and key in (wx.WXK_LEFT, wx.WXK_RIGHT) and _word_navigation_down(event):
                self._word_step(-1 if key == wx.WXK_LEFT else 1, extend=event.ShiftDown())
                return
            if self.mode == "professional" and self.mathcat is not None and command_modifier:
                if key in (ord("Z"), ord("z")):
                    self._built_history("redo" if event.ShiftDown() else "undo")
                    return
                if key in (ord("Y"), ord("y")):
                    self._built_history("redo")
                    return
                if self._insert_for_key(event, "command"):
                    return
            if self.mode == "professional" and self.mathcat is not None and _template_variant_down(event):
                if self._insert_for_key(event, "variant"):
                    return
            if self.mode == "linear" and _template_variant_down(event):
                # Control+I/S/P/R/L/O (Alt elsewhere): the variants of Cmd+I/S/P/R/L/Shift+O.
                if self._insert_for_key(event, "variant"):
                    return
            if self.mode == "linear" and command_modifier:
                if key in (ord("X"), ord("x")):
                    self._cut_equation()
                    return
                if key in (ord("V"), ord("v")):
                    self._paste_equation()
                    return
                if key in (ord("A"), ord("a")):
                    self._select_all()
                    return
                if key in (ord("Z"), ord("z")):
                    action = "redo" if event.ShiftDown() else "undo"
                    state = self.history.redo() if event.ShiftDown() else self.history.undo()
                    self._restore_history(state, action)
                    return
                if key in (ord("Y"), ord("y")):
                    self._restore_history(self.history.redo(), "redo")
                    return
                if self._insert_for_key(event, "command"):
                    return
            handled_keys = {
                wx.WXK_F2,
                wx.WXK_TAB,
                wx.WXK_LEFT,
                wx.WXK_RIGHT,
                wx.WXK_UP,
                wx.WXK_DOWN,
                wx.WXK_HOME,
                wx.WXK_END,
                wx.WXK_BACK,
                wx.WXK_DELETE,
                wx.WXK_SPACE,
            }
            if self.mode == "professional" and self._types_into_built_equation(event, key):
                # The character arrives as EVT_CHAR, with its real case.
                event.Skip()
                return
            if self.mode == "professional" or key in handled_keys:
                self._on_char(event)
                return
            event.Skip()

        def _insert_for_key(self, event: wx.KeyEvent, modifier: str) -> bool:
            # With the physical Control key the key code can be a control
            # character; the Unicode key still names the letter.
            codes = (event.GetKeyCode(), event.GetUnicodeKey())
            key = next((chr(code) for code in codes if 32 < code < 127), "")
            item = item_for_key(key, modifier, event.ShiftDown()) if key else None
            if item is None:
                return False
            self.insert_item(item)
            return True

        def insert_item(self, item: InsertItem) -> None:
            """Insert an Insert-menu entry at the caret, or where MathCAT is in professional view."""
            if self.mode == "professional" and self.mathcat is not None and self.mathcat.structure is not None:
                self._edit_in_built(lambda: self._insert_linear(item), glue=True)
                return
            if self.mode != "linear":
                return
            announcement = self._insert_linear(item)
            if announcement:
                self._announce(announcement)

        def _insert_linear(self, item: InsertItem) -> str | None:
            """Insert in the linear source; returns what to announce (the matrix dialog speaks itself)."""
            if item.insert is None:
                self._insert_matrix()
                return None
            self._clear_selection()
            edit = self._edit(item.insert)
            self._replace_linear(edit.source, edit.caret)
            return edit.announcement

        def edit_command(self, command: str) -> None:
            """An Edit-menu command, acting as its shortcut does (only Copy outside linear view)."""
            if command == "copy":
                self._copy_equation()
                return
            if self.mode == "professional" and command in ("undo", "redo") and self.mathcat is not None:
                self._built_history(command)
                return
            if self.mode != "linear":
                return
            if command == "undo":
                self._restore_history(self.history.undo(), "undo")
            elif command == "redo":
                self._restore_history(self.history.redo(), "redo")
            elif command == "cut":
                self._cut_equation()
            elif command == "paste":
                self._paste_equation()
            elif command == "select_all":
                self._select_all()

        def toggle_mode(self) -> None:
            """F2 / View > Professional View: switch between linear and professional view."""
            self._toggle_mode()

        def _restore_history(self, state: EditState | None, action: str) -> None:
            if state is None:
                self._announce(f"nothing to {action}")
                return
            self.document.replace_source(state.source, state.caret)
            self.caret = state.caret
            self._announce(action)
            self.Refresh()

        def _selection_range(self) -> tuple[int, int] | None:
            if self.selection_anchor is None or self.selection_anchor == self.caret:
                return None
            return (min(self.selection_anchor, self.caret), max(self.selection_anchor, self.caret))

        def _clear_selection(self) -> None:
            self.selection_anchor = None

        def _replace_selection(self, text: str) -> bool:
            """Replace the active selection with text in a single history entry."""
            selection = self._selection_range()
            if selection is None:
                return False
            start, end = selection
            self._replace_linear(self.document.source[:start] + text + self.document.source[end:], start + len(text))
            self._clear_selection()
            return True

        def _announce_selection(self) -> None:
            selection = self._selection_range()
            if selection is None:
                self._announce("selection cleared")
                return
            count = selection[1] - selection[0]
            self._announce(f"{count} character{'' if count == 1 else 's'} selected")

        def _select_all(self) -> None:
            if not self.document.source:
                self._announce("nothing to select")
                return
            self.selection_anchor = 0
            self.caret = len(self.document.source)
            self._announce_selection()
            self.Refresh()

        def _copy_equation(self) -> None:
            selection = self._selection_range()
            text = self.document.source[selection[0] : selection[1]] if selection else self.document.source
            if not text:
                self._announce("nothing to copy")
                return
            if not set_clipboard_text(text):
                self._announce("could not copy")
                return
            self._announce("selection copied" if selection else "equation copied")

        def _cut_equation(self) -> None:
            selection = self._selection_range()
            text = self.document.source[selection[0] : selection[1]] if selection else self.document.source
            if not text:
                self._announce("nothing to cut")
                return
            if not set_clipboard_text(text):
                self._announce("could not cut")
                return
            if selection:
                self._replace_selection("")
                self._announce("selection cut")
            else:
                self._replace_linear("", 0)
                self._announce("equation cut")

        def _paste_equation(self) -> None:
            text = get_clipboard_text()
            if not text:
                self._announce("clipboard is empty")
                return
            # UnicodeMath source renders as a single line; keep only the first
            # line of pasted text rather than corrupting the layout.
            text = text.replace("\r\n", "\n").replace("\r", "\n").split("\n", 1)[0]
            if not text:
                self._announce("clipboard is empty")
                return
            if not self._replace_selection(text):
                self._replace_linear(
                    self.document.source[: self.caret] + text + self.document.source[self.caret :],
                    self.caret + len(text),
                )
            self._announce("equation pasted")

        def _on_char(self, event: wx.KeyEvent) -> None:
            key = _effective_key(event)
            if key == wx.WXK_F2:
                self._toggle_mode()
                return
            if self.mode == "professional":
                if (
                    self._preparing
                    and key in (wx.WXK_LEFT, wx.WXK_RIGHT)
                    and not _cell_navigation_down(event)
                    and self.mathcat is not None
                    and not self.mathcat.linear_position_known
                ):
                    self._preparing_announced = True
                    self._announce("still preparing the equation, please wait")
                    return
                if self.mathcat is not None:
                    if key == wx.WXK_SPACE and event.AltDown() and event.ShiftDown() and not event.CmdDown():
                        # Where typing would go ("after a, before plus").
                        self._announce(self._insertion_point())
                        return
                    if key == wx.WXK_SPACE and event.AltDown() and not event.CmdDown():
                        self._announce(self.mathcat.read_current_zone())
                        return
                    if key == wx.WXK_SPACE and event.ShiftDown() and not event.CmdDown():
                        self._announce(self.mathcat.current_context())
                        return
                    if _cell_navigation_down(event):
                        commands = {
                            wx.WXK_LEFT: "MoveCellPrevious",
                            wx.WXK_RIGHT: "MoveCellNext",
                            wx.WXK_UP: "MoveCellUp",
                            wx.WXK_DOWN: "MoveCellDown",
                            wx.WXK_HOME: "MoveColumnStart",
                            wx.WXK_END: "MoveColumnEnd",
                            wx.WXK_SPACE: "ReadCellCurrent",
                        }
                        cell_navigation = True
                    else:
                        commands = {
                            wx.WXK_LEFT: "MovePrevious",
                            wx.WXK_RIGHT: "MoveNext",
                            wx.WXK_DOWN: "ZoomIn",
                            wx.WXK_UP: "ZoomOut",
                            wx.WXK_HOME: "MoveStart",
                            wx.WXK_END: "MoveEnd",
                            wx.WXK_SPACE: "ReadCurrent",
                        }
                        cell_navigation = False
                    command = commands.get(key)
                    if command in ("ZoomIn", "ZoomOut") and self.settings.linear_navigation:
                        # Flat reading has no levels: a stray Up/Down only
                        # threw MathCAT off the linear stops. Ignored, silently.
                        return
                    if command is not None:
                        try:
                            self._highlight_matrix_cell = cell_navigation
                            if command == "MoveColumnStart":
                                speech = self.mathcat.move_to_column_boundary(False)
                            elif command == "MoveColumnEnd":
                                speech = self.mathcat.move_to_column_boundary(True)
                            elif cell_navigation:
                                speech = self.mathcat.cell_command(command)
                            elif self.settings.linear_navigation:
                                speech = self.mathcat.linear_command(command)
                            elif self.mathcat.structural_stops:
                                speech = self.mathcat.structural_command(command)
                            else:
                                speech = self.mathcat.command_with_boundaries(command)
                            self._sync_mathcat_cursor()
                            if speech:
                                self._announce(speech)
                            self.Refresh()
                        except (OSError, RuntimeError, ValueError):
                            self.mathcat = None
                            self._announce("MathCAT is no longer available; fallback navigation is active")
                        return
                    if key == wx.WXK_TAB:
                        self._built_slot(reverse=event.ShiftDown())
                        return
                    if key in (wx.WXK_BACK, wx.WXK_DELETE) or self._is_typed_character(event):
                        self._edit_built_equation(event)
                        return
                moved = False
                if key == wx.WXK_LEFT:
                    moved = self.document.cursor.move_previous(self.document.root)
                elif key == wx.WXK_RIGHT:
                    moved = self.document.cursor.move_next(self.document.root)
                elif key == wx.WXK_DOWN:
                    moved = self.document.cursor.move_into(self.document.root)
                elif key == wx.WXK_UP:
                    moved = self.document.cursor.move_out()
                elif key == wx.WXK_SPACE:
                    self._announce(self.document.announcement)
                    return
                else:
                    return
                if moved:
                    self._announce(self.document.announcement)
                    self.Refresh()
                return

            if key == wx.WXK_TAB:
                self._clear_selection()
                edit = self._edit(lambda source, caret: move_to_slot(source, caret, event.ShiftDown(), self.settings.recognized_functions))
                if edit is None:
                    self._announce("no slot")
                    return
                self.caret = edit.caret
                self._announce(edit.announcement)
                self.Refresh()
                return
            if key == wx.WXK_SPACE and self.settings.convert_on_space and self._selection_range() is None:
                # Space after lim_(...)/log_(...) opens the argument box, as in Word.
                functions = self.settings.recognized_functions
                group = self._edit(lambda source, caret: group_function_argument(source, caret, functions))
                if group is not None:
                    self._replace_linear(group.source, group.caret)
                    self._announce(group.announcement)
                    return
            if key == wx.WXK_SPACE:
                selection = self._selection_range()
                if selection is not None:
                    source = self.document.source[: selection[0]] + self.document.source[selection[1] :]
                    caret = selection[0]
                    self._clear_selection()
                else:
                    source, caret = self.document.source, self.caret
                edit = convert_on_space(
                    source, caret, enabled=self.settings.convert_on_space, control_words=_converter_control_words()
                )
                self._replace_linear(edit.source, edit.caret)
                self._announce(edit.announcement)
                return
            if key == wx.WXK_LEFT:
                self._step_caret(-1, extend=event.ShiftDown())
            elif key == wx.WXK_RIGHT:
                self._step_caret(1, extend=event.ShiftDown())
            elif key in (wx.WXK_UP, wx.WXK_DOWN):
                # The linear source is a single line, like a one-line text
                # field: Up/Down read it, Shift+Up/Down select to its start/end.
                if event.ShiftDown():
                    target, label = (0, "start") if key == wx.WXK_UP else (len(self.document.source), "end")
                    self._jump_caret(target, label, extend=True)
                else:
                    self._announce(self.document.source or "blank")
            elif key == wx.WXK_HOME:
                self._jump_caret(0, "start", extend=event.ShiftDown())
            elif key == wx.WXK_END:
                self._jump_caret(len(self.document.source), "end", extend=event.ShiftDown())
            elif key == wx.WXK_BACK:
                if self._replace_selection(""):
                    self._announce("selection deleted")
                elif self.caret:
                    deleted = self.document.source[self.caret - 1]
                    self._replace_linear(self.document.source[: self.caret - 1] + self.document.source[self.caret :], self.caret - 1)
                    self._announce(deleted_character(deleted, self.symbols))
            elif key == wx.WXK_DELETE:
                if self._replace_selection(""):
                    self._announce("selection deleted")
                elif self.caret < len(self.document.source):
                    deleted = self.document.source[self.caret]
                    self._replace_linear(self.document.source[: self.caret] + self.document.source[self.caret + 1 :], self.caret)
                    self._announce(deleted_character(deleted, self.symbols))
            else:
                codepoint = event.GetUnicodeKey()
                if codepoint not in (wx.WXK_NONE, 0) and codepoint >= 32:
                    value = chr(codepoint)
                    if self._selection_range() is None:
                        edit = convert_before_character(
                            self.document.source,
                            self.caret,
                            value,
                            enabled=self.settings.convert_on_space,
                            control_words=_converter_control_words(),
                        )
                        if edit is not None:
                            self._replace_linear(edit.source, edit.caret)
                            self._announce(f"{edit.announcement}, {inserted_character(value, self.symbols)}")
                            return
                        if self.settings.convert_shortcuts_immediately:
                            edit = convert_shortcut_on_character(self.document.source, self.caret, value)
                            if edit is not None:
                                self._replace_linear(edit.source, edit.caret)
                                self._announce(edit.announcement)
                                return
                    if not self._replace_selection(value):
                        self._replace_linear(
                            self.document.source[: self.caret] + value + self.document.source[self.caret :],
                            self.caret + len(value),
                        )
                    self._announce(inserted_character(value, self.symbols))
                    return
                event.Skip()
                return
            self.Refresh()

        def _types_into_built_equation(self, event: wx.KeyEvent, key: int) -> bool:
            """A key that types a character into the built equation (not a shortcut or navigation)."""
            if self.mathcat is None or event.CmdDown() or event.RawControlDown() or key == wx.WXK_SPACE:
                return False
            return 32 < key < 127 or event.GetUnicodeKey() > 127

        @staticmethod
        def _is_typed_character(event: wx.KeyEvent) -> bool:
            return event.GetEventType() == wx.wxEVT_CHAR and event.GetUnicodeKey() not in (wx.WXK_NONE, 0) and (
                event.GetUnicodeKey() > 32
            )

        def _edit_built_equation(self, event: wx.KeyEvent) -> None:
            """Type, Backspace or Delete in professional mode, as if in the source.

            The key is handled exactly as in linear mode (autocorrect,
            history, speech) at MathCAT's position; see `_edit_in_built`.
            """
            def handle_key() -> None:
                self._on_char(event)  # Announces the character itself.

            typed = chr(event.GetUnicodeKey()) if self._is_typed_character(event) else ""
            # A letter, digit, group or control word glued to a structure joins it.
            self._edit_in_built(handle_key, glue=bool(typed) and (typed.isalnum() or typed in '(\\"'))

        def _insertion_point(self) -> str:
            assert self.mathcat is not None
            if self.mathcat.structure is None:
                return "equation"
            node_id, side, outside = self.mathcat.edit_anchor()
            return describe_insertion_point(self.mathcat.structure, node_id, side, outside, self.symbols)

        def _built_offset(self, glue: bool = False) -> int:
            """The source offset of MathCAT's position (`edit_anchor`, `source_map`).

            With `glue` (something that would join an operand is about to be
            typed) at the outer edge of a structure, a space is put between:
            UnicodeMath joins `(1)/(2)x` into the denominator and `x(1)/(2)`
            into the numerator, while `(1)/(2) x` and `x (1)/(2)` stay apart.
            """
            assert self.mathcat is not None and self.mathcat.structure is not None
            node_id, side, outside = self.mathcat.edit_anchor()
            source = self.document.source
            repair = self._built_repair()
            offset = repair.to_real(anchor_offset(repair.text, self.mathcat.structure, node_id, side, outside))
            if not (glue and outside and self._joins_structure(node_id, side)):
                return offset
            if side == "after" and 0 < offset and source[offset - 1] != " ":
                self.document.replace_source(source[:offset] + " " + source[offset:], offset + 1)
                return offset + 1
            if side == "before" and offset < len(source) and source[offset] != " ":
                self.document.replace_source(source[:offset] + " " + source[offset:], offset)
            return offset

        def _built_repair(self) -> BuildRepair:
            """The text the built equation came from, if it is still this source's."""
            source = self.document.source
            return self._repair if self._repair.source == source else BuildRepair(source, source)

        def _joins_structure(self, node_id: str, side: str) -> bool:
            """Whether typing next to this edge would run into a structure (a whole one, or the math's first/last)."""
            structure = self.mathcat.structure if self.mathcat is not None else None
            if structure is None:
                return False
            node = structure.node(node_id)
            if node is not structure.root:
                return True
            leaves = [leaf for leaf in leaf_nodes(structure) if leaf.text not in "\u2061\u2062\u2063\u2064"]
            if not leaves:
                return False
            edge = leaves[-1] if side == "after" else leaves[0]
            return bool(structure.region_entries(edge.identifier or ""))

        def _edit_in_built(self, action: Callable[[], str | None], glue: bool = False) -> None:
            """Run a linear-mode edit at MathCAT's position, then rebuild the equation.

            `action` runs in linear mode with the caret on that offset and may
            announce on its own or return what to announce after rebuilding.
            """
            source = self.document.source
            self._clear_selection()
            self.caret = self._built_offset(glue)
            self.mode = "linear"
            announcement = action() or ""
            if self.document.source == source:
                self.mode = "professional"
                if announcement:
                    self._announce(announcement)
                self.Refresh()
                return
            self._finish_built_edit(announcement)

        def _finish_built_edit(self, announcement: str) -> None:
            """Rebuild after an edit made from professional mode, MathCAT on the caret's node.

            A source that converts only to a total failure (a bare "∫▒") stays
            in linear view; partial errors ("a/") stay built.
            """
            try:
                mathml = self._convert_source().mathml
            except (UnicodeMathError, RuntimeError):
                mathml = 'mathcolor="#F00"'
            if 'mathcolor="#F00"' in mathml:
                # Not even a repair builds (an extra ")"): keep typing in linear view.
                self.mode = "linear"
                self._update_braille_display()
                self._announce(f"{announcement}, linear mode" if announcement else "linear mode")
                self.Refresh()
                return
            self.mode = "professional"
            self._update_braille_display()
            self._rebuild_professional_at_caret(announcement, place=self._place_after_caret)

        def _built_slot(self, reverse: bool) -> None:
            """Tab/Shift+Tab in professional mode: the next template slot, no rebuild needed."""
            self.caret = self._built_offset()
            edit = self._edit(lambda source, caret: move_to_slot(source, caret, reverse, self.settings.recognized_functions))
            if edit is None:
                self._announce("no slot")
                return
            self.caret = edit.caret
            self._place_after_caret()
            self._sync_mathcat_cursor()
            self._announce(edit.announcement)
            self.Refresh()

        def _built_history(self, action: str) -> None:
            """Undo/redo from professional mode: restore the source, then rebuild there."""
            state = self.history.undo() if action == "undo" else self.history.redo()
            if state is None:
                self._announce(f"nothing to {action}")
                return
            self.document.replace_source(state.source, state.caret)
            self.caret = state.caret
            self._finish_built_edit(action)

        def _place_after_caret(self) -> None:
            """Put MathCAT on the leaf holding the character before the caret (the start of the math at 0)."""
            assert self.mathcat is not None and self.mathcat.structure is not None
            self._highlight_matrix_cell = False
            repair = self._built_repair()
            spans = map_leaves(repair.text, self.mathcat.structure)
            leaf = leaf_before(spans, repair.to_repaired(self.caret), self.mathcat.structure)
            if leaf is None:
                self.mathcat.command("ZoomIn")
            else:
                self.mathcat.move_to(leaf)

        def _step_caret(self, delta: int, extend: bool) -> None:
            if not extend:
                selection = self._selection_range()
                if selection is not None:
                    self.caret = selection[0] if delta < 0 else selection[1]
                    self._clear_selection()
                    self._announce_linear_position(moved_right=delta > 0)
                    return
                self.caret = max(0, min(len(self.document.source), self.caret + delta))
                self._announce_linear_position(moved_right=delta > 0)
                return
            if self.selection_anchor is None:
                self.selection_anchor = self.caret
            self.caret = max(0, min(len(self.document.source), self.caret + delta))
            self._announce_selection()

        def _jump_caret(self, position: int, label: str, extend: bool) -> None:
            if extend:
                if self.selection_anchor is None:
                    self.selection_anchor = self.caret
                self.caret = position
                self._announce_selection()
                return
            self._clear_selection()
            self.caret = position
            self._announce(label)

        def _word_step(self, direction: int, extend: bool) -> None:
            target = (
                next_word_boundary(self.document.source, self.caret)
                if direction > 0
                else previous_word_boundary(self.document.source, self.caret)
            )
            if not extend:
                self._clear_selection()
                self.caret = target
                self._announce_linear_position(moved_right=direction > 0)
                self.Refresh()
                return
            if self.selection_anchor is None:
                self.selection_anchor = self.caret
            self.caret = target
            self._announce_selection()
            self.Refresh()

        def _sync_mathcat_cursor(self) -> None:
            if self.mathcat is None:
                return
            self.mathml_document = self.mathcat.structure
            position = self.mathcat.current_table_position
            self.mathml_current_id = (
                position.cell_id
                if self._highlight_matrix_cell and position is not None and position.cell_id
                else self.mathcat.display_id
            )
            self._update_braille_display()
            path = self.mathcat.current_path
            if path is None:
                return
            from .ast import node_at_path

            try:
                node_at_path(self.document.root, path)
            except (IndexError, KeyError):
                return
            self.document.cursor.path = path


        def _replace_linear(self, source: str, caret: int) -> None:
            self.document.replace_source(source, caret)
            self.caret = caret
            self.history.push(source, caret)
            self.Refresh()

        def _announce_linear_position(self, moved_right: bool) -> None:
            if not self.document.source:
                self._announce("start")
            elif moved_right and self.caret > 0:
                self._announce(character_name(self.document.source[self.caret - 1], self.symbols))
            elif not moved_right and self.caret < len(self.document.source):
                self._announce(character_name(self.document.source[self.caret], self.symbols))
            elif self.caret == 0:
                self._announce("start")
            else:
                self._announce("end")













else:

    class EquationEditor:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
