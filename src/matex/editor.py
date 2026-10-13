from __future__ import annotations

import threading

from .character_speech import character_name, deleted_character, inserted_character
from .layout import Line, Text, professional_layout
from .macos_webview import guard_webview_key_equivalents
from .edit_history import EditHistory, EditState
from .mathcat import MathCatNavigator, create_mathcat_navigator
from .math_templates import (
    TemplateEdit,
    delete_matrix_column,
    delete_matrix_row,
    insert_absolute_value_template,
    insert_matrix_column,
    insert_matrix_row,
    insert_fraction_template,
    insert_integral_template,
    insert_matrix_template,
    insert_product_template,
    insert_square_root_template,
    insert_subscript_template,
    insert_sum_template,
    insert_superscript_template,
    matrix_cell_caret,
    matrix_count,
    matrix_position_at,
    move_to_slot,
)
from .mathml_layout import mathml_layout
from .matrix_dialog import MatrixDialog
from .mathml_model import MathMLDocument, MathMLModelError, sanitize_mathml
from .model import EquationDocument
from .settings import AppSettings
from .speech import AssistiveOutput, create_output
from .space_conversion import convert_before_character, convert_on_space, convert_shortcut_on_character
from .theme import Palette, palette
from .unicodemath import (
    ConversionResult,
    StrayScriptResult,
    UnicodeMathError,
    control_words,
    conversion_script,
    decode_conversion,
    highlight_script,
    render_script,
    renderer_page,
)
from .word_navigation import next_word_boundary, previous_word_boundary

try:
    import wx
    import wx.html2
except ImportError:  # The interface is an optional dependency.
    wx = None


if wx is not None:

    def _set_clipboard_text(text: str) -> bool:
        if not wx.TheClipboard.Open():
            return False
        try:
            wx.TheClipboard.SetData(wx.TextDataObject(text))
        finally:
            wx.TheClipboard.Close()
        return True

    def _get_clipboard_text() -> str | None:
        if not wx.TheClipboard.Open():
            return None
        try:
            data = wx.TextDataObject()
            if not wx.TheClipboard.GetData(data):
                return None
        finally:
            wx.TheClipboard.Close()
        return data.GetText()

    def _converter_control_words() -> dict[str, str] | None:
        """The converter's control-word table, or None (fallback list) without the submodule."""
        try:
            return control_words()
        except (OSError, ValueError):
            return None

    def _word_navigation_down(event: wx.KeyEvent) -> bool:
        """The word-navigation modifier: Option on macOS, Ctrl elsewhere."""
        return event.AltDown() if wx.Platform == "__WXMAC__" else event.ControlDown()

    def _nary_limits_down(event: wx.KeyEvent) -> bool:
        """The with-limits n-ary modifier: the physical Control key on macOS, Alt elsewhere.

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

    class EquationEditor(wx.Window):
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

        def _create_renderer(self) -> None:
            try:
                page, base_url = renderer_page()
                self._webview = wx.html2.WebView.New(self)
                # Never focused, so it must not take Cmd+A/C/V/X either.
                guard_webview_key_equivalents()
                self._webview.SetName("")
                self._webview.Hide()
                # Purely visual: keyboard focus and speech stay with the editor.
                if hasattr(self._webview, "SetCanFocus"):
                    self._webview.SetCanFocus(False)
                self._webview.Bind(wx.EVT_SET_FOCUS, self._on_renderer_focus)
                self._webview.Bind(wx.html2.EVT_WEBVIEW_LOADED, self._on_renderer_loaded)
                if hasattr(self._webview, "AddScriptMessageHandler"):
                    self._webview.AddScriptMessageHandler("matex")
                    self._webview.Bind(wx.html2.EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED, self._on_renderer_click)
                self._webview.SetPage(page, base_url)
            except (FileNotFoundError, RuntimeError) as error:
                self._renderer_error = str(error)

        def _on_renderer_loaded(self, event: wx.html2.WebViewEvent) -> None:
            if self._webview is not None:
                success, value = self._webview.RunScript(
                    "typeof window.matexConvert === 'function' && "
                    "typeof window.matexRender === 'function'"
                )
                self._renderer_ready = success and value.strip().lower() == "true"
                if not self._renderer_ready:
                    self._renderer_error = "the UnicodeMathML engine did not initialize"
                else:
                    # LOADED can fire for an earlier, blank page first.
                    self._renderer_error = None
                    if self._pending_read:
                        wx.CallAfter(self.read_expression)
                self.Refresh()
            event.Skip()

        def _on_renderer_focus(self, event: wx.FocusEvent) -> None:
            wx.CallAfter(self.SetFocus)
            event.Skip()

        def _on_renderer_click(self, event: wx.html2.WebViewEvent) -> None:
            """A click on the rendered equation moves MathCAT to that node."""
            self.SetFocus()
            identifier = event.GetString()
            if self.mode != "professional" or self.mathcat is None or not identifier:
                return
            try:
                self.mathcat.move_to(identifier)
                self._highlight_matrix_cell = False
                self._sync_mathcat_cursor()
                self._announce(self.mathcat.command("ReadCurrent"))
            except (OSError, RuntimeError, ValueError):
                return
            self.Refresh()

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

        def _schedule_renderer_sync(self) -> None:
            if not self._renderer_sync_pending:
                self._renderer_sync_pending = True
                wx.CallAfter(self._sync_renderer)

        def _renderer_target(self) -> tuple[tuple[str, str] | None, str | None]:
            """What the renderer should show now: ((mode, MathML), highlighted id)."""
            if self.mode == "linear":
                if not self.document.source:
                    return ("linear", ""), None
                try:
                    mathml = self.convert_unicode_math(self.document.source)
                except (UnicodeMathError, RuntimeError, ValueError):
                    return ("linear", ""), None
                return ("linear", mathml), None
            mathml = self.mathcat.mathml if self.mathcat is not None else self._professional_mathml
            if not mathml:
                return None, None
            return ("professional", mathml), self.mathml_current_id

        def _sync_renderer(self) -> None:
            """Show, place and fill the visible renderer for the current mode.

            Professional mode shows MathCAT's own MathML, so its node ids are
            exactly the ones `mathml_current_id` highlights. Everything is
            passed through the same allow-list as HTML export first: the page
            is visible now, and an equation may come from someone else's file.
            """
            if not self:  # Destroyed before the deferred call ran.
                return
            if self._converting:
                # RunScript spins a nested event loop; a second synchronous
                # script started inside it gets the other one's result.
                wx.CallLater(30, self._sync_renderer)
                return
            self._renderer_sync_pending = False
            webview = self._webview
            if webview is None:
                return
            target, highlight = self._renderer_target() if self._renderer_ready else (None, None)
            if target is None:
                if webview.IsShown():
                    webview.Hide()
                    self.Refresh()
                self._rendered = None
                return
            if target != self._rendered:
                mode, mathml = target
                try:
                    safe = sanitize_mathml(mathml) if mathml else ""
                except MathMLModelError:
                    safe = ""
                webview.RunScriptAsync(render_script(safe, preview=mode == "linear"))
                self._rendered = target
                self._rendered_highlight = None
            if highlight != self._rendered_highlight:
                webview.RunScriptAsync(highlight_script(highlight))
                self._rendered_highlight = highlight
            rect = self._renderer_rect().Deflate(3, 3)
            if webview.GetRect() != rect:
                webview.SetSize(rect)
            if not webview.IsShown():
                webview.Show()
                self.Refresh()
            self._keep_focus_off_renderer()

        def _keep_focus_off_renderer(self) -> None:
            """WebKit takes focus when shown or clicked, and wx sends no focus
            event for it; put keyboard focus (and VoiceOver) back on the editor."""
            focused = wx.Window.FindFocus()
            if focused is not None and focused is self._webview:
                self.SetFocus()

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

        @property
        def converter_busy(self) -> bool:
            return self._converting

        @property
        def converter_ready(self) -> bool:
            return self._renderer_ready and self._webview is not None

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
                matrix_item = menu.Append(wx.ID_ANY, "Insert &Matrix…\tCtrl+Shift+M")
                cut_item.Enable(has_content)
                copy_item.Enable(has_content)
                paste_item.Enable(_get_clipboard_text() is not None)
                select_all_item.Enable(has_content)
                self.Bind(wx.EVT_MENU, lambda _e: self._cut_equation(), cut_item)
                self.Bind(wx.EVT_MENU, lambda _e: self._copy_equation(), copy_item)
                self.Bind(wx.EVT_MENU, lambda _e: self._paste_equation(), paste_item)
                self.Bind(wx.EVT_MENU, lambda _e: self._select_all(), select_all_item)
                self.Bind(wx.EVT_MENU, lambda _e: self._insert_matrix(), matrix_item)
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

        def _rebuild_professional_at_caret(self, announcement: str) -> None:
            """Reload the edited equation and put MathCAT on the caret's cell."""
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

        def convert_unicode_math(self, source: str) -> str:
            if not self._renderer_ready or self._webview is None:
                reason = self._renderer_error or "the UnicodeMathML converter is still loading"
                raise UnicodeMathError(reason)
            if self._converting:
                # RunScript spins a nested event loop: a conversion started
                # from inside it (a timer, a deferred call) would receive the
                # outer one's result. Refuse instead; callers already handle
                # a failed conversion.
                raise UnicodeMathError("the UnicodeMathML converter is busy")
            self._converting = True
            try:
                # RunScript takes whichever script result arrives first, e.g.
                # an earlier RunScriptAsync's (matexRender/matexHighlight).
                # Results arrive in order, so the conversion's own one is
                # queued behind those strays: wait for it with no-op scripts
                # (a new conversion would only fall behind the same way).
                self._conversion_token += 1
                token = self._conversion_token
                success, value = self._webview.RunScript(conversion_script(source, token))
                for _attempt in range(8):
                    if success:
                        try:
                            conversion = decode_conversion(value, token)
                            break
                        except StrayScriptResult:
                            pass
                    success, value = self._webview.RunScript("null")
                else:
                    raise UnicodeMathError("the UnicodeMathML converter could not run")
            finally:
                self._converting = False
            if conversion.error:
                raise UnicodeMathError(conversion.error)
            return conversion.mathml

        def _convert_source(self):
            return ConversionResult(mathml=self.convert_unicode_math(self.document.source))

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
            if self.mode == "linear" and _nary_limits_down(event):
                # Control+I/S/P (Alt elsewhere): integral/sum/product with limits.
                inserters = {
                    ord("I"): insert_integral_template,
                    ord("S"): insert_sum_template,
                    ord("P"): insert_product_template,
                }
                letters = {event.GetKeyCode(), event.GetUnicodeKey()}
                inserter = next((inserters[code] for code in inserters if letters & {code, code + 32}), None)
                if inserter is not None:
                    edit = inserter(self.document.source, self.caret, limits=True)
                    self._replace_linear(edit.source, edit.caret)
                    self._announce(edit.announcement)
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
                if key == ord("/"):
                    edit = insert_fraction_template(self.document.source, self.caret)
                    self._replace_linear(edit.source, edit.caret)
                    self._announce(edit.announcement)
                    return
                if key in (ord("R"), ord("r")):
                    edit = insert_square_root_template(self.document.source, self.caret)
                    self._replace_linear(edit.source, edit.caret)
                    self._announce(edit.announcement)
                    return
                if key in (ord("="), ord("+")):
                    edit = (
                        insert_superscript_template(self.document.source, self.caret)
                        if event.ShiftDown()
                        else insert_subscript_template(self.document.source, self.caret)
                    )
                    self._replace_linear(edit.source, edit.caret)
                    self._announce(edit.announcement)
                    return
                if key in (ord("\\"), ord("|")):
                    edit = insert_absolute_value_template(self.document.source, self.caret)
                    self._replace_linear(edit.source, edit.caret)
                    self._announce(edit.announcement)
                    return
                if key in (ord("I"), ord("i")):
                    edit = insert_integral_template(self.document.source, self.caret)
                    self._replace_linear(edit.source, edit.caret)
                    self._announce(edit.announcement)
                    return
                if key in (ord("S"), ord("s")):
                    edit = insert_sum_template(self.document.source, self.caret)
                    self._replace_linear(edit.source, edit.caret)
                    self._announce(edit.announcement)
                    return
                if key in (ord("P"), ord("p")):
                    edit = insert_product_template(self.document.source, self.caret)
                    self._replace_linear(edit.source, edit.caret)
                    self._announce(edit.announcement)
                    return
                # Shift is required: plain Command+M is macOS's Minimize,
                # which the frame's Window menu claims before we see it.
                if key in (ord("M"), ord("m")) and event.ShiftDown():
                    self._insert_matrix()
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
            if self.mode == "professional" or key in handled_keys:
                self._on_char(event)
                return
            event.Skip()

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
            if not _set_clipboard_text(text):
                self._announce("could not copy")
                return
            self._announce("selection copied" if selection else "equation copied")

        def _cut_equation(self) -> None:
            selection = self._selection_range()
            text = self.document.source[selection[0] : selection[1]] if selection else self.document.source
            if not text:
                self._announce("nothing to cut")
                return
            if not _set_clipboard_text(text):
                self._announce("could not cut")
                return
            if selection:
                self._replace_selection("")
                self._announce("selection cut")
            else:
                self._replace_linear("", 0)
                self._announce("equation cut")

        def _paste_equation(self) -> None:
            text = _get_clipboard_text()
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
                edit = move_to_slot(self.document.source, self.caret, reverse=event.ShiftDown())
                if edit is None:
                    self._announce("no slot")
                    return
                self.caret = edit.caret
                self._announce(edit.announcement)
                self.Refresh()
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
                    self._announce(deleted_character(deleted))
            elif key == wx.WXK_DELETE:
                if self._replace_selection(""):
                    self._announce("selection deleted")
                elif self.caret < len(self.document.source):
                    deleted = self.document.source[self.caret]
                    self._replace_linear(self.document.source[: self.caret] + self.document.source[self.caret + 1 :], self.caret)
                    self._announce(deleted_character(deleted))
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
                            self._announce(f"{edit.announcement}, {inserted_character(value)}")
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
                    self._announce(inserted_character(value))
                    return
                event.Skip()
                return
            self.Refresh()

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

        def _replace_linear(self, source: str, caret: int) -> None:
            self.document.replace_source(source, caret)
            self.caret = caret
            self.history.push(source, caret)
            self.Refresh()

        def _announce_linear_position(self, moved_right: bool) -> None:
            if not self.document.source:
                self._announce("start")
            elif moved_right and self.caret > 0:
                self._announce(character_name(self.document.source[self.caret - 1]))
            elif not moved_right and self.caret < len(self.document.source):
                self._announce(character_name(self.document.source[self.caret]))
            elif self.caret == 0:
                self._announce("start")
            else:
                self._announce("end")

        def _source_font(self) -> wx.Font:
            return wx.Font(22, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        def _ui_font(self, size: int = 12, weight: int = wx.FONTWEIGHT_NORMAL) -> wx.Font:
            return wx.Font(size, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, weight)

        _HEADER_HEIGHT = 36
        _STATUS_HEIGHT = 30
        _SOURCE_HEIGHT = 64
        _PREVIEW_LABEL_HEIGHT = 26

        def _content_rect(self) -> wx.Rect:
            """Everything between the title bar and the braille strip."""
            width, height = self.GetClientSize()
            top = self._HEADER_HEIGHT + 10
            bottom = height - self._STATUS_HEIGHT - self._BRAILLE_STRIP_HEIGHT - 8
            return wx.Rect(14, top, max(1, width - 28), max(1, bottom - top))

        def _source_rect(self) -> wx.Rect:
            content = self._content_rect()
            return wx.Rect(content.x, content.y, content.width, min(self._SOURCE_HEIGHT, content.height))

        def _renderer_rect(self) -> wx.Rect:
            """Linear mode: the preview under the source. Professional: all of it."""
            content = self._content_rect()
            if self.mode != "linear":
                return content
            top = content.y + self._SOURCE_HEIGHT + self._PREVIEW_LABEL_HEIGHT
            return wx.Rect(content.x, top, content.width, max(1, content.bottom - top))

        def _caret_from_x(self, dc: wx.DC, x: int, origin_x: int) -> int:
            source = self.document.source
            if not source:
                return 0
            relative_x = x - origin_x
            if relative_x <= 0:
                return 0
            best_index = 0
            best_distance = abs(relative_x)
            for index in range(1, len(source) + 1):
                width = dc.GetTextExtent(source[:index]).width
                distance = abs(relative_x - width)
                if distance < best_distance:
                    best_index = index
                    best_distance = distance
            return best_index

        def _status_text(self) -> str:
            if self.mode == "linear":
                if not self.document.source:
                    return "UnicodeMath source — empty equation"
                return f"UnicodeMath source — character {self.caret + 1} of {len(self.document.source) + 1}"
            navigation = "linear navigation" if self.settings.linear_navigation else "structural navigation"
            return (
                f"Professional mode — {navigation}; Space reads; "
                "Shift+Space context; Alt+Space zone; F2 source"
            )

        def _draw_editor_chrome(self, dc: wx.DC, colors: Palette) -> None:
            width, height = self.GetClientSize()
            focused = self.HasFocus()
            dc.SetBrush(wx.Brush(self._colour(colors.background)))
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.DrawRectangle(0, 0, width, height)

            dc.SetBrush(wx.Brush(self._colour(colors.panel)))
            dc.DrawRectangle(0, 0, width, self._HEADER_HEIGHT)
            dc.DrawRectangle(0, max(0, height - self._STATUS_HEIGHT), width, self._STATUS_HEIGHT)

            title = "Linear (UnicodeMath source)" if self.mode == "linear" else "Professional (built equation)"
            dc.SetFont(self._ui_font(13, wx.FONTWEIGHT_BOLD))
            dc.SetTextForeground(self._colour(colors.text))
            dc.DrawText(title, 16, 9)
            hint = "F2 switches view"
            dc.SetFont(self._ui_font(12))
            dc.SetTextForeground(self._colour(colors.subtle_text))
            dc.DrawText(hint, width - 16 - dc.GetTextExtent(hint).width, 10)

            status_y = max(0, height - self._STATUS_HEIGHT + 7)
            dc.DrawText(self._status_text(), 16, status_y)

            border = wx.Pen(self._colour(colors.focus if focused else colors.border), 2 if focused else 1)
            dc.SetBrush(wx.Brush(self._colour(colors.background)))
            if self.mode == "linear":
                dc.SetPen(border)
                source = self._source_rect()
                dc.DrawRoundedRectangle(source.x, source.y, source.width, source.height, 8)
                dc.SetFont(self._ui_font(12, wx.FONTWEIGHT_BOLD))
                dc.SetTextForeground(self._colour(colors.subtle_text))
                dc.DrawText("Preview", source.x + 2, source.bottom + 7)
                preview = self._renderer_rect()
                dc.SetPen(wx.Pen(self._colour(colors.border), 1))
                dc.DrawRoundedRectangle(preview.x, preview.y, preview.width, preview.height, 8)
            else:
                dc.SetPen(border)
                content = self._content_rect()
                dc.DrawRoundedRectangle(content.x, content.y, content.width, content.height, 8)
            dc.SetTextForeground(self._colour(colors.text))

        def _on_paint(self, _event: wx.PaintEvent) -> None:
            self._draw(wx.AutoBufferedPaintDC(self))

        def _draw(self, dc: wx.DC) -> None:
            colors = self._palette()
            self._draw_editor_chrome(dc, colors)
            if self._webview is not None:
                target = (self.mode, self.document.source, self.mathml_current_id, self._professional_mathml)
                if target != self._drawn_target:
                    self._drawn_target = target
                    self._schedule_renderer_sync()
            if self.mode == "linear":
                self._draw_source(dc, colors)
                if self._webview is None or not self._webview.IsShown():
                    preview = self._renderer_rect()
                    dc.SetFont(self._ui_font(12))
                    dc.SetTextForeground(self._colour(colors.subtle_text))
                    message = self._renderer_error or ("" if self._renderer_ready else "Loading the math renderer…")
                    dc.DrawText(message, preview.x + 14, preview.y + 12)
                return
            if self._webview is not None and self._webview.IsShown():
                return
            self._draw_fallback_layout(dc, colors)

        def _draw_source(self, dc: wx.DC, colors: Palette) -> None:
            content = self._source_rect()
            dc.SetClippingRegion(content)
            dc.SetFont(self._source_font())
            line_height = dc.GetTextExtent("Mg").height
            x = content.x + 14
            y = content.y + max(4, (content.height - line_height) // 2)
            selection = self._selection_range()
            if selection is not None:
                start_x = x + dc.GetTextExtent(self.document.source[: selection[0]]).width
                end_x = x + dc.GetTextExtent(self.document.source[: selection[1]]).width
                dc.SetBrush(wx.Brush(self._colour(colors.selection)))
                dc.SetPen(wx.TRANSPARENT_PEN)
                dc.DrawRectangle(int(start_x), y - 2, int(end_x - start_x), line_height + 4)
            if self.document.source:
                dc.SetTextForeground(self._colour(colors.text))
                dc.DrawText(self.document.source, x, y)
            else:
                dc.SetTextForeground(self._colour(colors.subtle_text))
                dc.DrawText("Type UnicodeMath here, e.g. (a+b)/2", x, y)
            prefix_width = dc.GetTextExtent(self.document.source[: self.caret]).width
            dc.SetPen(wx.Pen(self._colour(colors.focus), 2))
            dc.DrawLine(x + prefix_width, y - 2, x + prefix_width, y + line_height + 2)
            dc.DestroyClippingRegion()

        def _draw_fallback_layout(self, dc: wx.DC, colors: Palette) -> None:
            """Our own rough layout, for when the WebKit renderer is unavailable."""
            content = self._content_rect()
            dc.SetClippingRegion(content)
            dc.SetTextForeground(self._colour(colors.text))
            if self.mathml_document is not None:
                self._layout = mathml_layout(self.mathml_document)
                selected_key: object | None = self.mathml_current_id
            elif self.document.parse_error is not None:
                dc.SetFont(self._source_font())
                dc.DrawText(self.document.source, content.x + 12, content.y + 16)
                dc.DestroyClippingRegion()
                return
            else:
                self._layout = professional_layout(self.document.root)
                selected_key = self.document.cursor.path
            origin_x = content.x + max(12, (content.width - self._layout.width) / 2)
            origin_y = content.y + max(12, (content.height - self._layout.height) / 2)
            selected = self._layout.boxes.get(selected_key)
            if selected is not None:
                dc.SetBrush(wx.Brush(self._colour(colors.highlight_fill)))
                dc.SetPen(wx.Pen(self._colour(colors.focus), 2))
                dc.DrawRoundedRectangle(
                    int(origin_x + selected.x - 3),
                    int(origin_y + selected.y - 3),
                    int(selected.width + 6),
                    int(selected.height + 6),
                    4,
                )
            for primitive in self._layout.primitives:
                if isinstance(primitive, Text):
                    font = wx.Font(
                        max(10, int(18 * primitive.scale)),
                        wx.FONTFAMILY_ROMAN,
                        wx.FONTSTYLE_NORMAL,
                        wx.FONTWEIGHT_NORMAL,
                    )
                    dc.SetFont(font)
                    dc.DrawText(primitive.value, int(origin_x + primitive.x), int(origin_y + primitive.y))
                elif isinstance(primitive, Line):
                    dc.SetPen(wx.Pen(self._colour(colors.text), 2))
                    dc.DrawLine(
                        int(origin_x + primitive.x1),
                        int(origin_y + primitive.y1),
                        int(origin_x + primitive.x2),
                        int(origin_y + primitive.y2),
                    )
            dc.DestroyClippingRegion()

else:

    class EquationEditor:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
