"""The equation editor's WebView: the UnicodeMath converter and the visible rendering."""

from __future__ import annotations

import json
import time
from collections.abc import Callable

from mathessible.documents.mathml_sanitize import MathMLModelError, sanitize_mathml
from mathessible.documents.tex_macros import expand_macros
from mathessible.editing.build_repair import literal_repair, literal_text, repair_for_build
from mathessible.i18n import _
from mathessible.mathcat.latex import equation_latex
from mathessible.ui.macos_webview import guard_webview_key_equivalents
from mathessible.unicodemath import (
    ConversionResult,
    StrayScriptResult,
    UnicodeMathError,
    caret_script,
    conversion_script,
    decode_conversion,
    decode_from_mathml,
    from_mathml_script,
    highlight_script,
    render_script,
    renderer_page,
    zoom_script,
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
                self._webview.AddScriptMessageHandler("mathessible")
                self._webview.Bind(wx.html2.EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED, self._on_renderer_click)
            self._webview.SetPage(page, base_url)
        except (FileNotFoundError, RuntimeError) as error:
            self._renderer_error = str(error)

    def _on_renderer_loaded(self, event: wx.html2.WebViewEvent) -> None:
        if self._webview is not None:
            success, value = self._webview.RunScript(
                "typeof window.mathessibleConvert === 'function' && typeof window.mathessibleRender === 'function'"
            )
            self._renderer_ready = success and value.strip().lower() == "true"
            if not self._renderer_ready:
                self._renderer_error = _("the UnicodeMathML engine did not initialize")
            else:
                # LOADED can fire for an earlier, blank page first.
                self._renderer_error = None
                self._rendered_zoom = None  # A new page starts at 100%.
                if self._pending_read:
                    wx.CallAfter(self.read_expression)
            self.Refresh()
        event.Skip()

    def _on_renderer_focus(self, event: wx.FocusEvent) -> None:
        wx.CallAfter(self.SetFocus)
        event.Skip()

    def _on_renderer_click(self, event: wx.html2.WebViewEvent) -> None:
        """The mouse on the rendered equation (the page's JSON point): placing the caret, selecting."""
        self.SetFocus()
        if self.mode != "professional" or self.mathcat is None or self.mathcat.structure is None:
            return
        try:
            point = json.loads(event.GetString())
        except ValueError:
            return
        if isinstance(point, dict):
            self._pointer(point)

    def _schedule_renderer_sync(self) -> None:
        if not self._renderer_sync_pending:
            self._renderer_sync_pending = True
            wx.CallAfter(self._sync_renderer)

    def _renderer_target(self) -> tuple[tuple[str, str] | None, tuple[str | None, bool], dict | None]:
        """What the renderer should show now: ((mode, MathML), (highlighted ids, as a selection), caret)."""
        nothing = (None, False)
        if self.mode == "linear":
            if not self.document.source:
                return ("linear", ""), nothing, None
            try:
                mathml = self.convert_unicode_math(self.document.source)
            except (UnicodeMathError, RuntimeError, ValueError):
                return ("linear", ""), nothing, None
            return ("linear", mathml), nothing, None
        mathml = self.mathcat.mathml if self.mathcat is not None else self._professional_mathml
        if not mathml:
            return None, nothing, None
        if self._selected_ids:
            return ("professional", mathml), (" ".join(self._selected_ids), True), None
        if self.writing_enabled:
            # Writing: a text field's caret where typing goes, no box around the element read.
            return ("professional", mathml), nothing, self._caret_spec()
        return ("professional", mathml), (self.mathml_current_id, False), None

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
        target, highlight, caret = self._renderer_target() if self._renderer_ready else (None, (None, False), None)
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
            self._rendered_caret = None
        if highlight != self._rendered_highlight:
            webview.RunScriptAsync(highlight_script(*highlight))
            self._rendered_highlight = highlight
        if self._zoom() != self._rendered_zoom:
            webview.RunScriptAsync(zoom_script(self._zoom()))
            self._rendered_zoom = self._zoom()
            self._rendered_caret = None  # The caret moves with what it stands by.
        if caret != self._rendered_caret:
            webview.RunScriptAsync(caret_script(caret))
            self._rendered_caret = caret
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
        """The equation being edited (or one like it) as MathML: in its document's language (`self.latex`), a
        .tex environment's rows built as its `latex_environment` (align's as `aligned`), the document's own
        commands (`latex_macros`) expanded."""
        if self.latex:
            source = expand_macros(source, self.latex_macros)
        if self.latex and self.latex_environment:
            source = f"\\begin{{{self.latex_environment}}}{source}\\end{{{self.latex_environment}}}"
        return self.convert_equation(source, self.latex)

    def convert_equation(self, source: str, latex: bool = False) -> str:
        """An equation as MathML, UnicodeMath or (`latex`) LaTeX; raises `UnicodeMathError`."""
        if not latex:
            # Control words deleted from Math AutoCorrect stay text, as in Word (every path converts here).
            source = literal_text(source, self._literal_words())
        decimal_comma = self.settings.decimal_separator == ","
        conversion = self._run_converter(
            lambda token: conversion_script(source, token, decimal_comma=decimal_comma, latex=latex),
            decode_conversion,
        )
        self._last_conversion = (source, conversion)  # Its parse error position, for the error list.
        if conversion.error:
            raise UnicodeMathError(conversion.error)
        return conversion.mathml

    def latex_from_mathml(self, mathml: str) -> str:
        """An equation's MathML as LaTeX, written by MathCAT (`mathcat.latex`); raises `UnicodeMathError`."""
        latex = equation_latex([mathml], self.settings.decimal_separator)[0]
        if latex is None:
            raise UnicodeMathError(_("the equation could not be written in LaTeX"))
        return latex

    def unicode_math_from_mathml(self, mathml: str) -> str:
        """Pasted MathML as UnicodeMath, by the converter's own lineariser; raises `UnicodeMathError`."""
        return self._run_converter(lambda token: from_mathml_script(mathml, token), decode_from_mathml)

    def _run_converter[T](self, script: Callable[[int], str], decode: Callable[[str, int], T]) -> T:
        """Run one converter script synchronously and decode its own result (`script(token)`)."""
        if not self._renderer_ready or self._webview is None:
            reason = self._renderer_error or _("the UnicodeMathML converter is still loading")
            raise UnicodeMathError(reason)
        if self._converting:
            # RunScript spins a nested event loop: a conversion started
            # from inside it (a timer, a deferred call) would receive the
            # outer one's result. Refuse instead; callers already handle
            # a failed conversion.
            raise UnicodeMathError(_("the UnicodeMathML converter is busy"))
        self._converting = True
        try:
            # RunScript takes whichever script result arrives first, e.g.
            # an earlier RunScriptAsync's (mathessibleRender/mathessibleHighlight).
            # Results arrive in order, so the conversion's own one is queued
            # behind those strays: wait for it with no-op scripts. But wx 3.2
            # can also hand this conversion's own result to a pending
            # RunScriptAsync: once only our own "null"s come back, it is lost
            # (that dropped correct equations to linear view), so send it again.
            conversion = None
            for _send in range(3):
                self._conversion_token += 1
                token = self._conversion_token
                success, value = self._webview.RunScript(script(token))
                own_nulls = 0
                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline:
                    if success:
                        try:
                            conversion = decode(value, token)
                            break
                        except StrayScriptResult:
                            own_nulls = own_nulls + 1 if value.strip() == "null" else 0
                    if own_nulls >= 3:
                        break
                    success, value = self._webview.RunScript("null")
                if conversion is not None:
                    break
            if conversion is None:
                raise UnicodeMathError(_("the UnicodeMathML converter could not run"))
        finally:
            self._converting = False
        return conversion

    def _convert_source(self):
        """Convert the source for building, repaired if it cannot be built as it is (build_repair).

        The linear runs (`self._linear_runs`) are built as linear text.
        `self._repair` records which text was built, so offsets from the
        built equation can be mapped back to the real source.
        """
        source = self.document.source
        if self.latex:
            # LaTeX is built as it is: the repairs and linear runs are UnicodeMath's.
            self._repair = literal_repair(source, frozenset(), ())
            return ConversionResult(mathml=self.convert_unicode_math(source))
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
