"""The equation editor's WebView: the UnicodeMath converter and the visible rendering."""

from __future__ import annotations

import time

from matex.documents.mathml_sanitize import MathMLModelError, sanitize_mathml
from matex.editing.build_repair import literal_repair, literal_text, repair_for_build
from matex.ui.macos_webview import guard_webview_key_equivalents
from matex.unicodemath import (
    ConversionResult,
    StrayScriptResult,
    UnicodeMathError,
    conversion_script,
    decode_conversion,
    highlight_script,
    render_script,
    renderer_page,
)

try:
    import wx
    import wx.html2
except ImportError:  # The interface is an optional dependency.
    wx = None


class EquationRendererMixin:
    """Methods of `EquationEditor` (editor.py); relies on its state."""

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
                "typeof window.matexConvert === 'function' && typeof window.matexRender === 'function'"
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
            self._inside_leaf = None
            self._built_caret = None
            self._highlight_matrix_cell = False
            self._sync_mathcat_cursor()
            self._announce(self.mathcat.command("ReadCurrent"))
        except (OSError, RuntimeError, ValueError):
            return
        self.Refresh()

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
        # A selection highlights its leaves (space-separated ids), else MathCAT's node.
        return ("professional", mathml), " ".join(self._selected_ids) or self.mathml_current_id

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

    @property
    def converter_busy(self) -> bool:
        return self._converting

    @property
    def converter_ready(self) -> bool:
        return self._renderer_ready and self._webview is not None

    def convert_unicode_math(self, source: str) -> str:
        # Control words deleted from Math AutoCorrect stay text, as in Word (every path converts here).
        source = literal_text(source, self._literal_words())
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
            # Results arrive in order, so the conversion's own one is queued
            # behind those strays: wait for it with no-op scripts. But wx 3.2
            # can also hand this conversion's own result to a pending
            # RunScriptAsync: once only our own "null"s come back, it is lost
            # (that dropped correct equations to linear view), so send it again.
            decimal_comma = self.settings.decimal_separator == ","
            conversion = None
            for _send in range(3):
                self._conversion_token += 1
                token = self._conversion_token
                success, value = self._webview.RunScript(conversion_script(source, token, decimal_comma=decimal_comma))
                own_nulls = 0
                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline:
                    if success:
                        try:
                            conversion = decode_conversion(value, token)
                            break
                        except StrayScriptResult:
                            own_nulls = own_nulls + 1 if value.strip() == "null" else 0
                    if own_nulls >= 3:
                        break
                    success, value = self._webview.RunScript("null")
                if conversion is not None:
                    break
            if conversion is None:
                raise UnicodeMathError("the UnicodeMathML converter could not run")
        finally:
            self._converting = False
        self._last_conversion = (source, conversion)  # Its parse error position, for the error list.
        if conversion.error:
            raise UnicodeMathError(conversion.error)
        return conversion.mathml

    def _convert_source(self):
        """Convert the source for building, repaired if it cannot be built as it is (build_repair).

        The linear runs (`self._linear_runs`) are built as linear text.
        `self._repair` records which text was built, so offsets from the
        built equation can be mapped back to the real source.
        """
        source = self.document.source
        # A professional edit checks the build and then rebuilds: one conversion for both.
        literal = self._literal_words()
        runs = self._linear_runs
        key = (source, self.caret, self.settings.decimal_separator, literal, runs)
        if self._built_conversion is not None and self._built_conversion[0] == key:
            self._repair, mathml = self._built_conversion[1], self._built_conversion[2]
            return ConversionResult(mathml=mathml)
        converted: dict[str, str] = {}

        def builds(text: str) -> bool:
            converted[text] = self.convert_unicode_math(text)
            return 'mathcolor="#F00"' not in converted[text]

        repair = repair_for_build(source, builds, self.caret, literal, runs)
        self._repair = repair or literal_repair(source, literal, runs)
        if self._repair.text not in converted:
            builds(self._repair.text)
        self._built_conversion = (key, self._repair, converted[self._repair.text])
        return ConversionResult(mathml=converted[self._repair.text])
