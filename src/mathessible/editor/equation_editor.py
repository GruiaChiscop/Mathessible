from __future__ import annotations

import re
import threading
from dataclasses import dataclass

from mathessible import session_log
from mathessible.documents.clipboard_html import equation_html
from mathessible.documents.tex_macros import LatexMacro
from mathessible.editing.autocorrect import AutoCorrectTable, autocorrect_defaults
from mathessible.editing.build_repair import BuildRepair
from mathessible.editing.character_speech import (
    character_name,
    deleted_character,
    inserted_character,
    name_unknown_symbols,
)
from mathessible.editing.completion import Completion
from mathessible.editing.edit_history import EditHistory, EditState
from mathessible.editing.equation_source import EquationSource
from mathessible.editing.latex_insert import insert_latex, move_to_latex_slot, within_environment
from mathessible.editing.linear_runs import Runs
from mathessible.editing.normal_text import in_text, toggle_normal_text
from mathessible.editing.pasted_math import pasted_mathml, plain_letters
from mathessible.editing.source_lines import line_at, line_step
from mathessible.editing.source_view import view_of
from mathessible.editing.space_conversion import (
    convert_before_character,
    convert_on_space,
    convert_shortcut_on_character,
    convert_word_before,
)
from mathessible.editing.space_tidy import caret_after_tidy, tidy_spaces
from mathessible.editing.word_navigation import next_word_boundary, previous_word_boundary
from mathessible.editor.assist import EditorAssistMixin
from mathessible.editor.built import BuiltEditingMixin
from mathessible.editor.drawing import EditorDrawingMixin
from mathessible.editor.keys import (
    cell_navigation_down,
    describe_key,
    effective_key,
    template_variant_down,
    word_navigation_down,
)
from mathessible.editor.renderer import EquationRendererMixin
from mathessible.editor.structures import StructureActionsMixin
from mathessible.i18n import _, current_language, set_speech_language, spoken, spoken_n
from mathessible.mathcat.mathml_model import MathMLDocument
from mathessible.mathcat.navigator import (
    MATHCAT_MISSING,
    MathCatNavigator,
    create_mathcat_navigator,
    mathcat_language,
)
from mathessible.settings import ZOOM_LEVELS, AppSettings, save_settings
from mathessible.spoken import translate as translate_speech
from mathessible.symbols.braille_signs import load_signs, signs_yaml
from mathessible.symbols.dictionary import load_dictionary
from mathessible.templates.insert_catalog import InsertItem, item_for_key
from mathessible.templates.math_templates import (
    fill_empty_slots,
    group_function_argument,
    move_to_slot,
    script_on_function,
)
from mathessible.ui.clipboard import get_clipboard_html, get_clipboard_text, set_clipboard_text
from mathessible.ui.speech import AssistiveOutput, create_output
from mathessible.ui.theme import Palette, palette
from mathessible.unicodemath import ConversionResult, UnicodeMathError, mathml_has_parse_error

try:
    import wx
    import wx.html2
except ImportError:  # The interface is an optional dependency.
    wx = None


# Keys key-down hands to _on_char in the linear view (they arrive there as no character).
_KEYS_HANDLED_ON_KEY_DOWN = (
    frozenset(
        {
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
    )
    if wx is not None
    else frozenset()
)


@dataclass(frozen=True, slots=True)
class _LatexEditing:
    """A LaTeX equation edited in the professional view: the linear view's LaTeX, caret and history as they
    were, and the UnicodeMath the LaTeX built as (unchanged, the LaTeX is kept as typed)."""

    latex: str
    caret: int
    unicodemath: str
    history: EditHistory


if wx is not None:

    class EquationEditor(
        BuiltEditingMixin,
        EditorAssistMixin,
        EquationRendererMixin,
        StructureActionsMixin,
        EditorDrawingMixin,
        wx.Window,
    ):
        _BRAILLE_STRIP_HEIGHT = 28

        def __init__(
            self,
            parent: wx.Window,
            source: str = "a/(b+c)",
            output: AssistiveOutput | None = None,
            settings: AppSettings | None = None,
        ):
            super().__init__(parent, style=wx.BORDER_SIMPLE | wx.WANTS_CHARS)
            self.SetName(_("Equation editor"))
            self.SetMinSize((500, 200))
            self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
            self.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))
            self.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT))
            self.document = EquationSource(source)
            self.settings = settings or AppSettings()
            self.symbols = load_dictionary(self.settings.symbol_dictionary)
            self.output = output or create_output()
            # Writing mode (default) or, after F10, exploration mode: nothing can
            # change the equation, Space always reads in professional view (no
            # typing streak), and navigation follows the settings (`_linear_now`).
            self.writing_enabled = True
            # The document's equations are LaTeX (front matter `math: latex`): the linear view is
            # LaTeX text, built through Sargent's converter (`latex` says when the source is LaTeX).
            self.latex_document = False
            # The LaTeX environment the equation's rows build as (a .tex file's align: "aligned"), else "".
            self.latex_environment = ""
            # The commands the LaTeX document defines (`\\newcommand`), expanded before an equation is built.
            self.latex_macros: dict[str, LatexMacro] = {}
            # While the professional view edits a LaTeX equation, it edits the UnicodeMath that the
            # LaTeX builds as: the LaTeX is kept as typed unless it is edited there (`_LatexEditing`).
            self._latex_editing: _LatexEditing | None = None
            set_speech_language(self._speech_language)
            self.mathcat: MathCatNavigator | None = create_mathcat_navigator(
                recognized_functions=self.settings.recognized_functions,
                auto_zoom_out=self._auto_zoom_out,
                boundary_stops=self._boundary_stops,
                structural_stops=self._structural_stops,
                invisible_operator_stops=self.settings.invisible_operator_stops,
                language=self._speech_language,
            )
            if self.mathcat is not None:
                self.mathcat.decimal_separator = self.settings.decimal_separator
                self.mathcat.braille_code = self.settings.braille_code
                self.mathcat.braille_signs = signs_yaml(load_signs(self.settings.braille_code))
            self.mode = "linear"
            self.caret = len(source)
            self.selection_anchor: int | None = None
            self._dragging = False
            self.history = EditHistory(source, self.caret)
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
            self._rendered_highlight: tuple[str | None, bool] | None = None
            # The caret the renderer shows in the built equation (`_caret_spec`), None when hidden.
            self._rendered_caret: dict | None = None
            # Where a mouse press in the built equation put the caret, while the button is down.
            self._mouse_anchor: int | None = None
            # Display or inline, as the equation is saved (Change to Display/Inline); copied as such.
            self.display = False
            self._rendered_zoom: float | None = None
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
            # Set while a professional-view edit runs its linear handling (no autobuild then).
            self._editing_built = False
            # What was typed into the built equation and is not built yet
            # (linear_runs), as source ranges; a trigger typed during the
            # edit sets `_build_requested` (its announcement). `_last_spoken` is the edit's own speech.
            self._linear_runs: Runs = ()
            self._build_requested: str | None = None
            self._build_on_space = False
            # A script chain built one script at a time by Space (`a^b^c`):
            # (source, its end, its run's start, the step built last).
            self._script_chain: tuple[str, int, int, int] | None = None
            self._last_spoken = ""
            # A whole structure Backspace/Delete was pressed on once: the next
            # press deletes it, any other key forgets it (never by accident).
            self._armed_removal: str | None = None
            # The control word being typed and its suggestions (Up/Down, Tab),
            # with the source they were made for; any other key drops them.
            self._completion: tuple[Completion, str] | None = None
            self._last_symbol_query = ""
            self._last_gallery = (0, 0)  # Category and structure the gallery last closed on.
            # Writing mode's caret between the characters of a leaf ("12",
            # "sin"): (leaf id, characters before it, the characters, MathML).
            # MathCAT stays on the leaf's own stop meanwhile.
            self._inside_leaf: tuple[str, int, str, str] | None = None
            # The real source caret after a professional-view edit or build,
            # (source, caret, MathML): typing goes on exactly there until a
            # navigation command moves MathCAT. A typed space has no node, so
            # MathCAT's position alone put the next character before it.
            self._built_caret: tuple[str, int, str] | None = None
            # Professional view's selection (Shift+arrows in writing mode) is
            # `selection_anchor`..`caret` in real-source offsets, as in linear
            # view; these are its leaves, highlighted in the renderer.
            self._selected_ids: tuple[str, ...] = ()
            # The last conversion (source, result), for the parser's error position.
            self._last_conversion: tuple[str, ConversionResult] | None = None
            # `_convert_source`'s last result: ((source, caret, decimal separator), repair, MathML).
            self._built_conversion: tuple[tuple[str, int, str], BuildRepair, str] | None = None
            self.braille_label = wx.StaticText(self, label=_("Braille"))
            self.braille_label.SetForegroundColour(self._colour(self._palette().subtle_text))
            self.braille_display = wx.TextCtrl(self, style=wx.TE_READONLY)
            self.braille_display.SetName(_("Equation braille"))
            self.Bind(wx.EVT_PAINT, self._on_paint)
            self.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
            self.Bind(wx.EVT_CHAR, self._on_char)
            self.Bind(wx.EVT_SET_FOCUS, self._on_focus)
            self.Bind(wx.EVT_KILL_FOCUS, self._on_blur)
            self.Bind(wx.EVT_SIZE, self._on_size)
            self.Bind(wx.EVT_LEFT_DOWN, self._on_left_down)
            self.Bind(wx.EVT_LEFT_DCLICK, self._on_double_click)
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
            if navigator is None or not self._linear_now or navigator.linear_ready:
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

            threading.Thread(target=work, name="mathessible-linear-stops", daemon=True).start()

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
                self._announce(spoken("equation ready"))

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
            text = translate_speech(text)  # The navigation's English words, in the speech language.
            if self.settings.name_unknown_symbols:
                text = name_unknown_symbols(text)
            self._last_spoken = text
            if session_log.enabled():
                session_log.write("say", text)
                caret = self.caret
                source = self.document.source
                session_log.write("state", f"{self.mode}, caret {caret}: {source[:caret]!r} | {source[caret:]!r}")
            try:
                self.output.announce(text, interrupt=True)
            except Exception:
                # Assistive output must never be able to close the editor.
                pass

        @property
        def source(self) -> str:
            return self.document.source

        @property
        def document_source(self) -> str:
            """The equation as its document stores it: while the professional view edits a LaTeX equation,
            the LaTeX it opened with (an edit is written in LaTeX on leaving it, `end_latex_editing`)."""
            return self.document.source if self._latex_editing is None else self._latex_editing.latex

        @property
        def latex(self) -> bool:
            """The source is LaTeX: a LaTeX document's equation, but for the professional view's UnicodeMath."""
            return self.latex_document and self._latex_editing is None

        def set_source(self, source: str) -> None:
            session_log.write("open", repr(source))
            if not self.writing_enabled:
                # Every equation opens in writing mode.
                self.writing_enabled = True
                if self.mathcat is not None:
                    self.mathcat.auto_zoom_out = self._auto_zoom_out
                    self.mathcat.boundary_stops = self._boundary_stops
                    self.mathcat.structural_stops = self._structural_stops
            self.document = EquationSource(source)
            self.caret = len(source)
            self._latex_editing = None
            self.selection_anchor = None
            self._selected_ids = ()
            self.mode = "linear"
            self.mathml_document = None
            self.mathml_current_id = None
            self._highlight_matrix_cell = False
            self._pending_read = False
            self._armed_removal = None
            self._completion = None
            self._inside_leaf = None
            self._built_caret = None
            self._linear_runs = ()
            self._script_chain = None
            self.history.reset(source, self.caret)
            self._update_braille_display()
            self.Refresh()

        @property
        def _linear_now(self) -> bool:
            """Writing mode always navigates linearly; exploration (F10) as the setting says."""
            return self.writing_enabled or self.settings.linear_navigation

        @property
        def _auto_zoom_out(self) -> bool:
            # Linear navigation flows through every structure by design, so
            # it needs MathCAT to step out at a structure's end regardless.
            return self.settings.auto_zoom_out or self._linear_now

        @property
        def _boundary_stops(self) -> bool:
            return self.settings.structure_stops and self._linear_now

        @property
        def _structural_stops(self) -> bool:
            return self.settings.structure_stops and not self._linear_now

        @property
        def _speech_language(self) -> str:
            """MathCAT's language: Settings' speech language, else the interface's."""
            return self.settings.speech_language or current_language()

        def apply_settings(self) -> None:
            self.symbols = load_dictionary(self.settings.symbol_dictionary)
            set_speech_language(self._speech_language)
            if self.mathcat is not None and self.mathcat.language != mathcat_language(self._speech_language):
                # Another speech language: MathCAT starts again in it, the equation reloaded below.
                mathml = self.mathcat.mathml
                self.mathcat = create_mathcat_navigator(
                    recognized_functions=self.settings.recognized_functions,
                    auto_zoom_out=self._auto_zoom_out,
                    boundary_stops=self._boundary_stops,
                    structural_stops=self._structural_stops,
                    invisible_operator_stops=self.settings.invisible_operator_stops,
                    language=self._speech_language,
                )
                if self.mathcat is not None:
                    self.mathcat.mathml = mathml
            if self.mathcat is not None:
                self.mathcat.recognized_functions = self.settings.recognized_functions
                self.mathcat.auto_zoom_out = self._auto_zoom_out
                self.mathcat.boundary_stops = self._boundary_stops
                self.mathcat.structural_stops = self._structural_stops
                self.mathcat.invisible_operator_stops = self.settings.invisible_operator_stops
                self.mathcat.decimal_separator = self.settings.decimal_separator
                self.mathcat.braille_code = self.settings.braille_code
                self.mathcat.braille_signs = signs_yaml(load_signs(self.settings.braille_code))
                if self.mathcat.mathml:
                    try:
                        self.mathcat.load(self.mathcat.mathml, keep_position=True, speak=False)
                    except (OSError, RuntimeError, ValueError):
                        self.mathcat = create_mathcat_navigator(
                            recognized_functions=self.settings.recognized_functions,
                            auto_zoom_out=self._auto_zoom_out,
                            boundary_stops=self._boundary_stops,
                            structural_stops=self._structural_stops,
                            invisible_operator_stops=self.settings.invisible_operator_stops,
                            language=self._speech_language,
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
            self._announce(
                spoken("Equation editor, professional mode")
                if self.mode == "professional"
                else spoken("Equation editor, linear mode")
            )
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
            over_text = self.mode == "linear" and self._source_rect().Contains(event.GetPosition())
            self.SetCursor(wx.Cursor(wx.CURSOR_IBEAM if over_text else wx.CURSOR_ARROW))
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

        def _on_double_click(self, event: wx.MouseEvent) -> None:
            """A double click in the source selects the word under it (`\\alpha` with its backslash)."""
            if self.mode != "linear" or not self._source_rect().Contains(event.GetPosition()):
                event.Skip()
                return
            position = self._caret_from_point(event.GetPosition())
            source = self.document.source
            for match in re.finditer(r"\\?[A-Za-z0-9_]+|\S", source):
                if match.start() <= position <= match.end() and match.end() > match.start():
                    self.selection_anchor, self.caret = match.start(), match.end()
                    self._dragging = False
                    if self.HasCapture():
                        self.ReleaseMouse()
                    self._announce_selection()
                    self.Refresh()
                    return

        def zoom(self, step: int) -> None:
            """View > Zoom In (+1), Zoom Out (-1), Actual Size (0): the source and the rendering, saved."""
            levels = list(ZOOM_LEVELS)
            current = levels.index(self.settings.equation_zoom) if self.settings.equation_zoom in levels else 4
            index = levels.index(100) if step == 0 else max(0, min(len(levels) - 1, current + step))
            self.settings.equation_zoom = levels[index]
            try:
                save_settings(self.settings)
            except OSError:
                pass  # The zoom still applies; it is only not remembered.
            self._announce(spoken("zoom {percent} percent").format(percent=self.settings.equation_zoom))
            self.Refresh()

        def _zoom_key(self, key: int) -> bool:
            """Cmd+Option+= / - / 0 (Ctrl+Alt elsewhere): Cmd+= is already the subscript template."""
            steps = {
                ord("="): 1,
                ord("+"): 1,
                wx.WXK_NUMPAD_ADD: 1,
                ord("-"): -1,
                wx.WXK_NUMPAD_SUBTRACT: -1,
                ord("0"): 0,
            }
            if key not in steps:
                return False
            self.zoom(steps[key])
            return True

        def _on_capture_lost(self, _event: wx.MouseCaptureLostEvent) -> None:
            self._dragging = False

        def _caret_from_point(self, point: wx.Point) -> int:
            dc = wx.ClientDC(self)
            dc.SetFont(self._source_font())
            return self._caret_from_x(dc, point.x, self._source_origin_x(dc))

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
            width = dc.GetTextExtent(self._shown_source[: self.caret])[0] if self.caret else 0
            return wx.Point(self._source_origin_x(dc) + width, content.y + content.height // 2)

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
                opens_built = self.settings.open_built and self.mode == "linear"
                if opens_built and self.latex and not self._begin_latex_editing():
                    return
                conversion = self._convert_source()
                if opens_built:
                    # Open straight in professional view, MathCAT on the start of the math.
                    self._enter_professional_mode(conversion, error_prefix=spoken("The equation could not be built"))
                    return
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
                self._announce(spoken("The equation could not be read. {error}").format(error=error))

        def _toggle_mode(self, attempts: int = 40) -> None:
            session_log.write("command", "toggle linear/professional")
            if self.mode == "linear" and self._converting and attempts > 0:
                # F2 arrived inside the live preview's RunScript (its nested
                # event loop): wait for that conversion instead of failing
                # with "busy".
                wx.CallLater(30, self._retry_toggle_mode, attempts - 1)
                return
            selection = None if self.latex_document else self._built_selection()
            if selection is not None:
                # As Word's Linear/Professional on a selection: only that part changes.
                self._toggle_selection_linear(*selection)
                return
            self._clear_selection()
            if self.mode == "linear" and self.mathcat is None:
                self._announce(MATHCAT_MISSING)
                return
            # Professional builds everything, linear shows everything linear, as in Word.
            self._linear_runs = ()
            self._script_chain = None
            if self.mode == "linear" and not self.document.source.strip():
                # Nothing to build (and MathCAT cannot even zoom into empty math).
                self._announce(spoken("empty equation"))
                return
            if self.mode == "linear":
                if self.latex and not self._begin_latex_editing():
                    return
                try:
                    conversion = self._convert_source()
                except (UnicodeMathError, RuntimeError, ValueError) as error:
                    self._cancel_latex_editing()
                    self._announce(spoken("Professional mode could not be built. {error}").format(error=error))
                    return
                if 'mathcolor="#F00"' in conversion.mathml:
                    # Nothing parses: building would only show the source in red.
                    self._cancel_latex_editing()
                    self._announce(
                        spoken("cannot be built, {errors}").format(errors=self._errors_summary(total_failure=True))
                    )
                    return
                self._enter_professional_mode(conversion, error_prefix=spoken("Professional mode could not be built"))
            else:
                if self._latex_editing is not None:
                    if not self.end_latex_editing():
                        return
                    self.mode = "linear"
                else:
                    self.mode = "linear"
                    self.remove_extra_spaces()  # As Word's linear format: no space that changes nothing.
                self._update_braille_display()
                self._announce(spoken("linear mode"))
            self.Refresh()

        def _retry_toggle_mode(self, attempts: int) -> None:
            if self and self.mode == "linear":  # Not destroyed, not toggled meanwhile.
                self._toggle_mode(attempts)

        def _enter_professional_mode(self, conversion: ConversionResult, error_prefix: str) -> bool:
            self._clear_selection()  # A linear view selection is not kept: MathCAT starts over.
            self._professional_mathml = conversion.mathml
            try:
                self.mode = "professional"
                self.mathml_document = MathMLDocument.parse(
                    conversion.mathml,
                    recognized_functions=self.settings.recognized_functions,
                )
                if self.mathcat is None:
                    raise RuntimeError(MATHCAT_MISSING)
                self.mathcat.load(conversion.mathml, speak=False)
                self.mathml_document = self.mathcat.structure
                speech = self.mathcat.command("ZoomIn")
                self._sync_mathcat_cursor()
                self._announce(spoken("professional mode, {speech}").format(speech=speech))
                self._start_linear_preparation()
                return True
            except (OSError, RuntimeError, ValueError) as error:
                self.mode = "linear"
                self._cancel_latex_editing()
                self._announce(f"{error_prefix}. {error}")
                return False

        def _begin_latex_editing(self) -> bool:
            """Into the professional view with a LaTeX equation: the source becomes the UnicodeMath it builds as.

            The converter's lineariser writes that UnicodeMath, in the letters typed, so the built view
            edits it as any equation. The linear view's LaTeX and history wait in `_latex_editing`.
            False (and said) when the LaTeX does not build.
            """
            latex = self.document.source
            try:
                mathml = self.convert_unicode_math(latex)
                if mathml_has_parse_error(mathml):
                    raise UnicodeMathError(spoken("the LaTeX has errors"))
                unicodemath = plain_letters(self.unicode_math_from_mathml(mathml))
            except (UnicodeMathError, RuntimeError, ValueError) as error:
                self._announce(spoken("cannot be built, {errors}").format(errors=error))
                return False
            self._latex_editing = _LatexEditing(latex, self.caret, unicodemath, self.history)
            self.document = EquationSource(unicodemath)
            self.caret = len(unicodemath)
            self.history = EditHistory(unicodemath, self.caret)
            return True

        def _cancel_latex_editing(self) -> None:
            """Back to the LaTeX as it was, when the professional view could not open after all."""
            editing, self._latex_editing = self._latex_editing, None
            if editing is not None:
                self.document = EquationSource(editing.latex)
                self.caret = editing.caret
                self.history = editing.history

        def end_latex_editing(self) -> bool:
            """Out of the professional view of a LaTeX equation: the LaTeX as typed if nothing was edited there,
            else the edited equation written again in LaTeX (one undo in the linear view takes that back).

            False (and said) when the edited equation cannot be written in LaTeX: it stays in the professional
            view. True with nothing to do outside it.
            """
            editing = self._latex_editing
            if editing is None:
                return True
            source = self.document.source
            if source == editing.unicodemath:
                latex, caret = editing.latex, editing.caret
            else:
                try:
                    mathml = self.convert_equation(source)
                    if mathml_has_parse_error(mathml):
                        raise UnicodeMathError(spoken("the equation has errors"))
                    latex = within_environment(self.latex_from_mathml(mathml), self.latex_environment, editing.latex)
                except (UnicodeMathError, RuntimeError, ValueError) as error:
                    self._announce(spoken("cannot be written in LaTeX, {error}").format(error=error))
                    return False
                caret = len(latex)
            self._latex_editing = None
            self.history = editing.history
            if latex != editing.latex:
                session_log.write("command", f"LaTeX written again: {latex!r}")
                self.history.push(latex, caret)
            self.document = EquationSource(latex)
            self.caret = caret
            return True

        def _on_key_down(self, event: wx.KeyEvent) -> None:
            if session_log.enabled():
                session_log.write("key", describe_key(event))
            key = event.GetKeyCode()
            command_modifier = event.CmdDown()
            if key not in (wx.WXK_BACK, wx.WXK_DELETE):
                self._armed_removal = None
            if self._completion_key(event, key):
                return
            if command_modifier and event.AltDown() and self._zoom_key(key):
                return
            if key == wx.WXK_F8 and not command_modifier:
                self.show_errors()
                return
            if command_modifier and key in (ord("C"), ord("c")):
                self._copy_equation()
                return
            # Keyboard access to the right-click menu: the Menu key (Windows),
            # or Shift+F10 everywhere, as in other native text fields; both modes.
            if key == wx.WXK_WINDOWS_MENU or (key == wx.WXK_F10 and event.ShiftDown() and not command_modifier):
                self._show_context_menu(self._caret_point())
                return
            if key == wx.WXK_F10 and not event.ShiftDown() and not command_modifier:
                self.toggle_writing()
                return
            if not self.writing_enabled and self._is_edit_key(event, key):
                self._announce_writing_off()
                return
            if self.mode == "linear" and key in (wx.WXK_LEFT, wx.WXK_RIGHT) and word_navigation_down(event):
                self._word_step(-1 if key == wx.WXK_LEFT else 1, extend=event.ShiftDown())
                return
            built = self.mode == "professional" and self.mathcat is not None
            if built and command_modifier and self._built_command_shortcut(event, key):
                return
            # Control+I/S/P/R/L/O (Alt elsewhere): the variants of Cmd+I/S/P/R/L/Shift+O.
            variant_view = self.mode == "linear" or (self.mode == "professional" and self.mathcat is not None)
            if variant_view and template_variant_down(event) and self._insert_for_key(event, "variant"):
                return
            if self.mode == "linear" and command_modifier and self._linear_command_shortcut(event, key):
                return
            if self.mode == "professional" and self._types_into_built_equation(event, key):
                # The character arrives as EVT_CHAR, with its real case.
                event.Skip()
                return
            if self.mode == "professional" or key in _KEYS_HANDLED_ON_KEY_DOWN:
                self._on_char(event)
                return
            event.Skip()

        def _built_command_shortcut(self, event: wx.KeyEvent, key: int) -> bool:
            """Cmd/Ctrl shortcuts in the built equation (cut, paste, undo, redo, select all, templates)."""
            if key in (ord("X"), ord("x")):
                self._cut_node()
            elif key in (ord("V"), ord("v")):
                self._edit_in_built(self._paste_equation, glue=True)
            elif key in (ord("Z"), ord("z")):
                self._built_history("redo" if event.ShiftDown() else "undo")
            elif key in (ord("Y"), ord("y")):
                self._built_history("redo")
            elif key in (ord("A"), ord("a")) and self.writing_enabled:
                self._select_all_built()
            else:
                return self._insert_for_key(event, "command")
            return True

        def _linear_command_shortcut(self, event: wx.KeyEvent, key: int) -> bool:
            """Cmd/Ctrl shortcuts in the linear view (cut, paste, select all, undo, redo, templates)."""
            if key in (ord("X"), ord("x")):
                self._cut_equation()
            elif key in (ord("V"), ord("v")):
                self._paste_equation()
            elif key in (ord("A"), ord("a")):
                self._select_all()
            elif key in (ord("Z"), ord("z")):
                action = "redo" if event.ShiftDown() else "undo"
                state = self.history.redo() if event.ShiftDown() else self.history.undo()
                self._restore_history(state, action)
            elif key in (ord("Y"), ord("y")):
                self._restore_history(self.history.redo(), "redo")
            else:
                return self._insert_for_key(event, "command")
            return True

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

        def toggle_writing(self) -> None:
            """F10: writing mode <-> exploration mode.

            Exploration forbids changing the equation and navigates as the
            settings say (linear or structural); writing always navigates
            linearly, by character, with Option/Ctrl for whole nodes.
            """
            session_log.write("command", "toggle writing mode")
            self.writing_enabled = not self.writing_enabled
            self._armed_removal = None
            self._completion = None
            self._inside_leaf = None
            self._built_caret = None
            self.apply_settings()  # The navigation kind follows the mode.
            self._announce(spoken("writing mode") if self.writing_enabled else spoken("exploration mode"))

        def _announce_writing_off(self) -> None:
            self._announce(spoken("exploration mode, F10 to write"))

        def _writing_off(self) -> bool:
            """For menu edits: True (and say so) when writing is off."""
            if self.writing_enabled:
                return False
            self._announce_writing_off()
            return True

        def _is_edit_key(self, event: wx.KeyEvent, key: int) -> bool:
            """A key that would change the equation (typing, deleting, cut/paste/undo, templates)."""
            if key in (wx.WXK_BACK, wx.WXK_DELETE):
                return True
            if key == wx.WXK_SPACE:
                # Space reads in professional view; with modifiers it reads there too.
                return self.mode == "linear" and not (event.AltDown() or event.CmdDown())
            letters = {event.GetKeyCode(), event.GetUnicodeKey()}
            if event.CmdDown():
                if letters & {ord(c) for c in "XxVvZzYy"}:
                    return True
                character = next((chr(code) for code in letters if 32 < code < 127), "")
                return bool(character) and item_for_key(character, "command", event.ShiftDown()) is not None
            if template_variant_down(event):
                character = next((chr(code) for code in letters if 32 < code < 127), "")
                return bool(character) and item_for_key(character, "variant", event.ShiftDown()) is not None
            if event.RawControlDown():
                return False
            return 32 < key < 127 or event.GetUnicodeKey() > 127

        def insert_item(self, item: InsertItem) -> None:
            """Insert an Insert-menu entry at the caret, or where MathCAT is in professional view."""
            session_log.write("command", f"insert {item.label!r}")
            if self._writing_off():
                return
            if self.latex:
                self._insert_latex_item(item)
                return
            if self.mode == "professional" and self.mathcat is not None and self.mathcat.structure is not None:
                self._edit_in_built(lambda: self._insert_linear(item), glue=True)
                return
            if self.mode != "linear":
                return
            announcement = self._insert_linear(item)
            if announcement:
                self._announce(announcement)

        def _insert_latex_item(self, item: InsertItem) -> None:
            """An Insert entry in LaTeX typed in the linear view: its UnicodeMath template (a matrix, symbol or
            gallery entry chosen first, as always) written in LaTeX by MathCAT, the caret in its first slot."""
            if self.mode != "linear":
                return
            source, caret, history = self.document.source, self.caret, self.history
            self._clear_selection()
            # The template as it is inserted into an empty UnicodeMath equation.
            self.document, self.caret, self.history = EquationSource(""), 0, EditHistory()
            try:
                announcement = self._insert_linear(item)
                template = self.document.source
            finally:
                self.document, self.caret, self.history = EquationSource(source), caret, history
            if not template:
                return  # Its dialog was cancelled.
            try:
                mathml = self.convert_equation(fill_empty_slots(template, self.settings.recognized_functions))
                # An equation number is LaTeX's `\tag{}` (amsmath), which MathCAT does not write.
                latex = "\\tag{}" if ":equation-label" in mathml else self.latex_from_mathml(mathml)
            except (UnicodeMathError, RuntimeError, ValueError):
                self._announce(spoken("not available here"))
                return
            self._replace_linear(*insert_latex(source, caret, latex))
            if announcement:
                self._announce(announcement)

        def _insert_linear(self, item: InsertItem) -> str | None:
            """Insert in the linear source; returns what to announce (the matrix dialog speaks itself)."""
            if item.dialog == "normal_text":
                return self._toggle_normal_text()
            if item.dialog == "symbol":
                return self._insert_symbol()
            if item.dialog == "gallery":
                chosen = self._choose_from_gallery()
                return self._insert_linear(chosen) if chosen is not None else None
            if item.insert is None:
                self._insert_matrix()
                return None
            self._clear_selection()
            edit = self._edit(item.insert)
            self._replace_linear(edit.source, edit.caret)
            return edit.announcement

        def _toggle_normal_text(self) -> str:
            """Normal Text (Cmd+Shift+T): text starts, ends, or the selection changes over (normal_text.py)."""
            edit = toggle_normal_text(self.document.source, self.caret, self._selection_range())
            self._clear_selection()
            self._replace_linear(edit.source, edit.caret)
            return edit.announcement

        def _typing_text(self) -> bool:
            """The caret is in a normal text and Math AutoCorrect stays out of it (the setting), or the
            equation is LaTeX, typed as it is written: no AutoCorrect, completion or building while typing."""
            return self.latex or (
                not self.settings.autocorrect_in_text and in_text(self.document.source, self.caret, self._linear_runs)
            )

        def edit_command(self, command: str) -> None:
            """An Edit-menu command, acting as its shortcut does (only Copy outside linear view)."""
            session_log.write("command", f"edit {command}")
            if command == "copy":
                self._copy_equation()
                return
            if command != "select_all" and self._writing_off():
                return
            if self.mode == "professional" and command in ("undo", "redo") and self.mathcat is not None:
                self._built_history(command)
                return
            if self.mode == "professional" and command == "cut" and self.mathcat is not None:
                self._cut_node()
                return
            if self.mode == "professional" and command == "paste" and self.mathcat is not None:
                self._edit_in_built(self._paste_equation, glue=True)
                return
            if self.mode == "professional" and command == "select_all" and self.mathcat is not None:
                if self.writing_enabled:
                    self._select_all_built()
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

        def remove_extra_spaces(self) -> None:
            """Remove the spaces that change nothing (`space_tidy`), when the setting asks: on save, F2 to linear."""
            if not self.settings.remove_extra_spaces or not self.converter_ready or self._converting:
                return
            if self.latex_document:
                return  # The setting is UnicodeMath's: LaTeX is kept as typed.

            def convert(text: str) -> str | None:
                try:
                    return self.convert_unicode_math(text)
                except (UnicodeMathError, RuntimeError):
                    return None

            tidied, removed = tidy_spaces(self.document.source, convert)
            if removed:
                session_log.write("command", f"removed {len(removed)} extra spaces")
                self._replace_linear(tidied, caret_after_tidy(self.caret, removed))

        def toggle_mode(self) -> None:
            """F2 / View > Professional View: switch between linear and professional view."""
            self._toggle_mode()

        def _restore_history(self, state: EditState | None, action: str) -> None:
            if state is None:
                self._announce(spoken("nothing to undo") if action == "undo" else spoken("nothing to redo"))
                return
            self.document.source = state.source
            self.caret = state.caret
            self._announce(action)
            self.Refresh()

        def _selection_range(self) -> tuple[int, int] | None:
            if self.selection_anchor is None or self.selection_anchor == self.caret:
                return None
            return (min(self.selection_anchor, self.caret), max(self.selection_anchor, self.caret))

        def _clear_selection(self) -> None:
            self.selection_anchor = None
            self._selected_ids = ()

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
                self._announce(spoken("selection cleared"))
                return
            count = selection[1] - selection[0]
            self._announce(
                spoken_n("{count} character selected", "{count} characters selected", count).format(count=count)
            )

        def _select_all(self) -> None:
            if not self.document.source:
                self._announce(spoken("nothing to select"))
                return
            self.selection_anchor = 0
            self.caret = len(self.document.source)
            self._announce_selection()
            self.Refresh()

        def _copy_equation(self) -> None:
            node = self._current_node() if self._built_selection() is None else None
            if node is not None:
                # Professional view: the current node (a whole fraction, a numerator, a symbol).
                start, end, _replacement = self._node_removal(node.identifier)
                text = self.document.source[start:end]
                if set_clipboard_text(text, self._equation_html(text, whole=False)):
                    self._announce(spoken("copied {item}").format(item=spoken(self._node_label(node))))
                else:
                    self._announce(spoken("could not copy"))
                return
            selection = self._selection_range()
            text = self.document.source[selection[0] : selection[1]] if selection else self.document.source
            if not text:
                self._announce(spoken("nothing to copy"))
                return
            if not set_clipboard_text(text, self._equation_html(text, whole=not selection)):
                self._announce(spoken("could not copy"))
                return
            self._announce(spoken("selection copied") if selection else spoken("equation copied"))

        def _cut_equation(self) -> None:
            selection = self._selection_range()
            text = self.document.source[selection[0] : selection[1]] if selection else self.document.source
            if not text:
                self._announce(spoken("nothing to cut"))
                return
            if not set_clipboard_text(text, self._equation_html(text, whole=not selection)):
                self._announce(spoken("could not cut"))
                return
            if selection:
                self._replace_selection("")
                self._announce(spoken("selection cut"))
            else:
                self._replace_linear("", 0)
                self._announce(spoken("equation cut"))

        def _equation_html(self, text: str, whole: bool) -> str | None:
            """The copied source as MathML for the clipboard, so Word and browsers paste it built."""
            try:
                mathml = self.convert_unicode_math(text)
            except (UnicodeMathError, RuntimeError):
                return None
            return equation_html(mathml, text, display=self.display and whole)

        def _paste_equation(self) -> None:
            text = get_clipboard_text()
            mathml = pasted_mathml(text, get_clipboard_html())
            if mathml is not None:
                # A web page's or Word's MathML: its UnicodeMath (or LaTeX), in the letters typed.
                try:
                    if self.latex:
                        text = self.latex_from_mathml(mathml)
                    else:
                        text = plain_letters(self.unicode_math_from_mathml(mathml))
                except (UnicodeMathError, RuntimeError):
                    self._announce(spoken("the pasted MathML could not be converted"))
                    return
            if not text:
                self._announce(spoken("clipboard is empty"))
                return
            # UnicodeMath source renders as a single line; keep only the first
            # line of pasted text rather than corrupting the layout.
            text = text.replace("\r\n", "\n").replace("\r", "\n").split("\n", 1)[0]
            if not text:
                self._announce(spoken("clipboard is empty"))
                return
            if not self._replace_selection(text):
                self._replace_linear(
                    self.document.source[: self.caret] + text + self.document.source[self.caret :],
                    self.caret + len(text),
                )
            self._announce(spoken("equation pasted"))

        def _on_char(self, event: wx.KeyEvent) -> None:
            if session_log.enabled() and event.GetUnicodeKey() > 32:
                session_log.write("char", repr(chr(event.GetUnicodeKey())))
            key = effective_key(event)
            if not self.writing_enabled and self._is_typed_character(event):
                # Key-down already stops these; EVT_CHAR is a second guard.
                self._announce_writing_off()
                return
            if key == wx.WXK_F2:
                self._toggle_mode()
                return
            if self.mode == "professional":
                self._on_built_char(event, key)
                return
            if key == wx.WXK_TAB:
                self._linear_tab(event.ShiftDown())
                return
            if key == wx.WXK_SPACE:
                self._linear_space()
                return
            if key in (wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_UP, wx.WXK_DOWN, wx.WXK_HOME, wx.WXK_END):
                self._linear_move(event, key)
            elif key in (wx.WXK_BACK, wx.WXK_DELETE):
                self._linear_delete(backward=key == wx.WXK_BACK)
            else:
                self._linear_type(event)  # Refreshes as it edits, or lets the key through.
                return
            self.Refresh()

        def _on_built_char(self, event: wx.KeyEvent, key: int) -> None:
            """A key in the built equation: readings, navigation, Tab, and typing into it."""
            if (
                self._preparing
                and key in (wx.WXK_LEFT, wx.WXK_RIGHT)
                and not cell_navigation_down(event)
                and self.mathcat is not None
                and not self.mathcat.linear_position_known
                and self._current_inside() is None
            ):
                self._preparing_announced = True
                self._announce(spoken("still preparing the equation, please wait"))
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
                if cell_navigation_down(event):
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
                plain_space = key == wx.WXK_SPACE and not (event.AltDown() or event.ShiftDown() or event.CmdDown())
                if plain_space and self.writing_enabled and not cell_navigation:
                    # Writing mode: Space types, as in a text field (it once read
                    # after any navigation, so no space could be added once built).
                    # Exploration mode (F10) is for reading: Space reads there.
                    self._edit_built_equation(event)
                    return
                if not cell_navigation and self._mode_arrow(event, key):
                    return
                command = commands.get(key)
                if command is not None:
                    self._inside_leaf = None
                    self._built_caret = None
                    self._clear_built_selection()
                if command in ("ZoomIn", "ZoomOut") and self._linear_now:
                    # Flat reading has no levels: a stray Up/Down only
                    # threw MathCAT off the linear stops. Ignored, silently.
                    return
                if command is not None:
                    self._run_navigation_command(command, cell_navigation)
                    return
                if key == wx.WXK_TAB:
                    self._built_slot(reverse=event.ShiftDown())
                    return
                if (
                    key in (wx.WXK_BACK, wx.WXK_DELETE)
                    and self._built_selection() is None
                    and self._removes_whole_structure()
                ):
                    return
                if key in (wx.WXK_BACK, wx.WXK_DELETE) or self._is_typed_character(event):
                    self._edit_built_equation(event)
                    return

        def _run_navigation_command(self, command: str, cell_navigation: bool) -> None:
            """A MathCAT move in the built equation: by cell, along the linear stops, or by level."""
            try:
                self._highlight_matrix_cell = cell_navigation
                if cell_navigation:
                    speech = self.mathcat.table_command(command)
                elif self._linear_now:
                    speech = self.mathcat.linear_command(command)
                else:
                    # Mathessible's own levels with structure stops or without
                    # (MathCAT's own Left/Right failed in sums and integrals).
                    speech = self.mathcat.structural_command(command)
                self._sync_mathcat_cursor()
                if speech:
                    self._announce(speech)
                self.Refresh()
            except (OSError, RuntimeError, ValueError):
                self._recover_navigation()

        def _linear_tab(self, reverse: bool) -> None:
            """Tab/Shift+Tab in the linear view: a typed control word converted, then the next slot. LaTeX's
            words stay as typed, and its slots are its brace groups."""
            self._clear_selection()
            if self.latex:
                converted = ""
                edit = self._edit(lambda source, caret: move_to_latex_slot(source, caret, reverse))
            else:
                converted = self._convert_word_before_caret()
                edit = self._edit(
                    lambda source, caret: move_to_slot(source, caret, reverse, self.settings.recognized_functions)
                )
            if edit is None:
                self._announce(f"{converted}, {spoken('no slot')}" if converted else spoken("no slot"))
                self.Refresh()
                return
            self.caret = edit.caret
            self._announce(f"{converted}, {edit.announcement}" if converted else edit.announcement)
            self.Refresh()

        def _linear_space(self) -> None:
            """Space in the linear view: an argument box opened, or a control word or shortcut converted, or a space."""
            if self._typing_text():
                # In normal text Space is a space: nothing converts, opens or builds.
                if not self._replace_selection(" "):
                    source = self.document.source
                    self._replace_linear(source[: self.caret] + " " + source[self.caret :], self.caret + 1)
                self._announce(inserted_character(" ", self.symbols))
                return
            if self.settings.convert_on_space and self._selection_range() is None:
                # Space after lim_(...)/log_(...) opens the argument box, as in Word.
                functions = self.settings.recognized_functions
                group = self._edit(lambda source, caret: group_function_argument(source, caret, functions))
                if group is None and self._editing_built and self._at_condition_end():
                    # In the built equation, the end of the condition ("end limit
                    # condition", after ∞) is still inside its ")": Space opens the
                    # argument there too, or goes into the one already open.
                    after = self.caret + 1
                    group = self._edit(lambda source, caret: group_function_argument(source, caret, functions), after)
                    if group is None:
                        inside = self._existing_argument(after)
                        if inside is not None:
                            # Into the argument already there, at its end; the source is unchanged,
                            # so MathCAT is moved here (no rebuild follows).
                            self.caret = inside
                            self.mode = "professional"
                            self._place_after_caret()
                            self._sync_mathcat_cursor()
                            self.mode = "linear"
                            self._announce(f"{spoken('argument')}, {self._insertion_point_here()}")
                            return
                if group is not None:
                    self._replace_linear(group.source, group.caret)
                    self._announce(group.announcement)
                    self._build_as_you_type(f"{spoken('built')}, {group.announcement}")
                    return
            selection = self._selection_range()
            if selection is not None:
                source = self.document.source[: selection[0]] + self.document.source[selection[1] :]
                caret = selection[0]
                self._clear_selection()
            else:
                source, caret = self.document.source, self.caret
            edit = convert_on_space(
                source,
                caret,
                enabled=self.settings.convert_on_space,
                control_words=self._control_words(),
                shortcuts=self._shortcuts(),
            )
            self._replace_linear(edit.source, edit.caret)
            self._announce(edit.announcement)
            self._build_as_you_type(space=True)

        def _linear_move(self, event: wx.KeyEvent, key: int) -> None:
            """Arrows, Home and End in the linear view (Shift extends the selection)."""
            if key == wx.WXK_LEFT:
                self._step_caret(-1, extend=event.ShiftDown())
            elif key == wx.WXK_RIGHT:
                self._step_caret(1, extend=event.ShiftDown())
            elif key in (wx.WXK_UP, wx.WXK_DOWN) and "\n" in self.document.source and not event.ShiftDown():
                # A source on several lines (a .tex align's rows): Up/Down go line by line and read the line.
                target = line_step(self.document.source, self.caret, -1 if key == wx.WXK_UP else 1)
                if target is not None:
                    self._clear_selection()
                    self.caret = target
                    self.Refresh()
                self._announce(line_at(self.document.source, self.caret).strip() or spoken("blank"))
            elif key in (wx.WXK_UP, wx.WXK_DOWN):
                # The linear source is a single line, like a one-line text
                # field: Up/Down read it, Shift+Up/Down select to its start/end.
                if event.ShiftDown():
                    target, label = (0, "start") if key == wx.WXK_UP else (len(self.document.source), "end")
                    self._jump_caret(target, label, extend=True)
                else:
                    self._announce(self.document.source or spoken("blank"))
            elif key == wx.WXK_HOME:
                self._jump_caret(0, "start", extend=event.ShiftDown())
            elif key == wx.WXK_END:
                self._jump_caret(len(self.document.source), "end", extend=event.ShiftDown())

        def _linear_delete(self, backward: bool) -> None:
            """Backspace (backward) or Delete in the linear view, a whole control word in the built one."""
            if backward:
                if self._replace_selection(""):
                    self._announce(spoken("selection deleted"))
                elif self.caret:
                    start, end = self._deletion_span(self.caret, backward=True)
                    deleted = self.document.source[start:end]
                    self._replace_linear(self.document.source[:start] + self.document.source[end:], start)
                    if end - start > 1:  # A whole control word: its symbol, and no completion.
                        self._announce(deleted_character(view_of(deleted).text, self.symbols))
                    else:
                        self._announce(self._offer_completion(deleted_character(deleted, self.symbols)))
            else:
                if self._replace_selection(""):
                    self._announce(spoken("selection deleted"))
                elif self.caret < len(self.document.source):
                    start, end = self._deletion_span(self.caret, backward=False)
                    deleted = self.document.source[start:end]
                    self._replace_linear(self.document.source[:start] + self.document.source[end:], start)
                    self._announce(deleted_character(view_of(deleted).text, self.symbols))

        def _linear_type(self, event: wx.KeyEvent) -> None:
            """A typed character in the linear view, with autocorrect, scripts on function names and shortcuts."""
            codepoint = event.GetUnicodeKey()
            if codepoint not in (wx.WXK_NONE, 0) and codepoint >= 32:
                value = chr(codepoint)
                # Word's autobuild fires on the same characters as control-word
                # conversion: anything but a space or an ASCII letter/digit. Not a
                # script's "^"/"_": it binds tighter than anything before it
                # (`a^b^c`, `a/b^2`), so it ends no operand (UTN #28 sec. 2.3).
                builds = not value.isspace() and not (value.isascii() and value.isalnum()) and value not in "^_"
                if self._typing_text():
                    # Normal text is text: no AutoCorrect, completion or building while typing it. LaTeX is
                    # typed as it is written too, but its control words are offered (`\\fr`: \\frac).
                    if not self._replace_selection(value):
                        self._replace_linear(
                            self.document.source[: self.caret] + value + self.document.source[self.caret :],
                            self.caret + len(value),
                        )
                    said = inserted_character(value, self.symbols)
                    self._announce(self._offer_completion(said) if self.latex else said)
                    return
                if self._selection_range() is None:
                    edit = convert_before_character(
                        self.document.source,
                        self.caret,
                        value,
                        enabled=self.settings.convert_on_space,
                        control_words=self._control_words(),
                    )
                    if edit is not None:
                        self._replace_linear(edit.source, edit.caret)
                        self._announce(f"{edit.announcement}, {inserted_character(value, self.symbols)}")
                        self._after_typed(value, builds)
                        return
                    functions = self.settings.recognized_functions
                    script = script_on_function(self.document.source, self.caret, value, functions)
                    if script is not None:
                        self._replace_linear(script.source, script.caret)
                        self._announce(self._offer_completion(inserted_character(value, self.symbols)))
                        self._after_typed(value, builds)
                        return
                    if self.settings.convert_shortcuts_immediately:
                        edit = convert_shortcut_on_character(self.document.source, self.caret, value, self._shortcuts())
                        if edit is not None:
                            self._replace_linear(edit.source, edit.caret)
                            self._announce(edit.announcement)
                            self._after_typed(value, builds)
                            return
                if not self._replace_selection(value):
                    self._replace_linear(
                        self.document.source[: self.caret] + value + self.document.source[self.caret :],
                        self.caret + len(value),
                    )
                self._announce(self._offer_completion(inserted_character(value, self.symbols)))
                self._after_typed(value, builds)
                return
            event.Skip()
            return

        @staticmethod
        def _is_typed_character(event: wx.KeyEvent) -> bool:
            return (
                event.GetEventType() == wx.wxEVT_CHAR
                and event.GetUnicodeKey() not in (wx.WXK_NONE, 0)
                and (event.GetUnicodeKey() > 32)
            )

        def _insertion_point_here(self) -> str:
            mode, self.mode = self.mode, "professional"
            try:
                return self._insertion_point()
            finally:
                self.mode = mode

        def _at_condition_end(self) -> bool:
            """The caret is right before the ")" closing a `lim_(...)`/`log_(...)` condition."""
            view = view_of(self.document.source)
            index = view.to_view(self.caret)
            if view.text[index : index + 1] != ")":
                return False
            closing = view.to_source(index) + 1
            probe = group_function_argument(view.text[: index + 1], index + 1, self.settings.recognized_functions)
            return probe is not None or self._existing_argument(closing) is not None

        def _existing_argument(self, after: int) -> int | None:
            """Inside the argument box `〖...〗` right after this offset (` \\begin ...`, an integrand's
            `\\of\\begin ...`), at its end; else None."""
            view = view_of(self.document.source)
            index = view.to_view(after)
            if view.text[index : index + 2] not in (" 〖", "▒〖"):
                return None
            depth = 0
            for position in range(index + 1, len(view.text)):
                if view.text[position] == "〖":
                    depth += 1
                elif view.text[position] == "〗":
                    depth -= 1
                    if depth == 0:
                        return view.to_source(position)
            return None

        def _after_typed(self, value: str, builds: bool) -> None:
            """After a character typed in linear handling (whichever way it was inserted).

            A ")" closing `lim_(...)`/`log_(...)` opens the argument box, as
            Space does; then autobuild, if the character is a trigger. Every
            insertion path comes here: `\\infty)` goes through control-word
            conversion first, and was missed when only the plain path did this.
            """
            announcement = "built"
            if value == ")" and self.settings.convert_on_space and self._selection_range() is None:
                functions = self.settings.recognized_functions
                group = self._edit(lambda source, caret: group_function_argument(source, caret, functions))
                if group is not None:
                    if not self.settings.argument_on_closing_paren:
                        # As Word: ")" only closes the condition; Space opens the argument and builds.
                        return
                    self._replace_linear(group.source, group.caret)
                    self._announce(group.announcement)
                    announcement = f"{spoken('built')}, {group.announcement}"
            if builds:
                self._build_as_you_type(announcement)

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

        def _recover_navigation(self) -> None:
            """A navigation command MathCAT failed on: reload it where it was, rather than drop it.

            MathCAT can fail on an intent-only node ("... not found", "no
            speech generated"); that used to switch MathCAT off for good.
            """
            assert self.mathcat is not None
            try:
                self.mathcat.load(self.mathcat.mathml, keep_position=True, speak=False)
                if self.mathcat.structure is None or self.mathcat.structure.node(self.mathcat.current_id) is None:
                    self.mathcat.command("ZoomIn")
                self._sync_mathcat_cursor()
                self._start_linear_preparation()
                self._announce(spoken("cannot move there"))
            except (OSError, RuntimeError, ValueError) as error:
                self.mode = "linear"
                self._update_braille_display()
                self._announce(spoken("MathCAT could not read the equation, linear mode. {error}").format(error=error))
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

        def _autocorrect(self) -> AutoCorrectTable:
            """Math AutoCorrect as one list: the converter's words and Mathessible's shortcuts, with the user's changes."""
            return AutoCorrectTable(
                autocorrect_defaults(), self.settings.math_autocorrect, self.settings.math_autocorrect_removed
            )

        def _literal_words(self) -> tuple[str, ...]:
            """Default control words the user deleted, built as text (off: `removed_words_as_symbols`)."""
            if self.settings.removed_words_as_symbols:
                return ()
            return self._autocorrect().removed_words()

        def _control_words(self) -> dict[str, str]:
            """The control words AutoCorrect converts (without their backslash)."""
            return self._autocorrect().control_words()

        def _shortcuts(self) -> dict[str, str]:
            """The other AutoCorrect entries (`->`, the user's `deg`)."""
            return self._autocorrect().shortcuts()

        def _convert_word_before_caret(self) -> str:
            """Tab after a typed control word (`\\infty`) converts it first, as Space would; returns the symbol or ""."""
            edit = convert_word_before(
                self.document.source, self.caret, self.settings.convert_on_space, self._control_words()
            )
            if edit is None:
                return ""
            self._replace_linear(edit.source, edit.caret)
            return edit.announcement

        def _deletion_span(self, caret: int, backward: bool) -> tuple[int, int]:
            """What one Backspace/Delete removes: a character, or in the built equation a whole control word.

            The built equation shows `\\end ` as one symbol (an invisible
            bracket), so deleting it letter by letter left `\\en`, `\\e`, ...
            in between. In linear view the word is text, edited a letter at a time.
            """
            single = (caret - 1, caret) if backward else (caret, caret + 1)
            if not self._editing_built:
                return single
            view = view_of(self.document.source)
            index = view.to_view(caret)
            if view.to_source(index) != caret:
                return single
            span = (view.to_source(index - 1), caret) if backward and index > 0 else (caret, view.to_source(index + 1))
            return span if span[1] - span[0] > 1 and self.document.source[span[0]] == "\\" else single

        def _replace_linear(self, source: str, caret: int) -> None:
            self.document.source = source
            self.caret = caret
            self.history.push(source, caret)
            self.Refresh()

        def _announce_linear_position(self, moved_right: bool) -> None:
            if not self.document.source:
                self._announce(spoken("start"))
            elif moved_right and self.caret > 0:
                self._announce(character_name(self.document.source[self.caret - 1], self.symbols))
            elif not moved_right and self.caret < len(self.document.source):
                self._announce(character_name(self.document.source[self.caret], self.symbols))
            elif self.caret == 0:
                self._announce(spoken("start"))
            else:
                self._announce(spoken("end"))


else:

    class EquationEditor:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
