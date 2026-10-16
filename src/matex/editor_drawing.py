"""Painting the custom-drawn equation editor: source line, chrome, fallback layout."""

from __future__ import annotations

from .layout import Line, Text, professional_layout
from .mathml_layout import mathml_layout
from .theme import Palette

try:
    import wx
except ImportError:  # The interface is an optional dependency.
    wx = None


class EditorDrawingMixin:
    """Methods of `EquationEditor` (editor.py); relies on its state."""

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
        if self.writing_enabled:
            navigation = "writing mode (F10 explores)"
        else:
            kind = "linear" if self.settings.linear_navigation else "structural"
            navigation = f"exploration mode, {kind} navigation (F10 writes)"
        return (
            f"Professional mode — {navigation}; Space reads; "
            "Shift+Space context; Alt+Space zone; F2 source"
        )

    def _suggestions_text(self) -> str:
        """The control-word suggestions around the current one, for the line under the source."""
        completion = self._current_completion()
        if completion is None:
            return ""
        first = max(0, min(completion.index - 1, len(completion.suggestions) - 4))
        shown = completion.suggestions[first : first + 4]
        words = [
            f"[\\{s.word} {s.symbol}]" if first + offset == completion.index else f"\\{s.word}"
            for offset, s in enumerate(shown)
        ]
        return f"{'  '.join(words)}  ({completion.index + 1} of {len(completion.suggestions)}; Tab completes)"

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
            suggestions = self._suggestions_text()
            if suggestions:
                dc.SetFont(self._ui_font(12))
                dc.SetTextForeground(self._colour(colors.text))
                dc.DrawText(suggestions, source.right - 2 - dc.GetTextExtent(suggestions).width, source.bottom + 7)
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
