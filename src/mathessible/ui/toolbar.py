"""The document window's toolbar: the commands a paper is written with, beside the menus that also hold them.

A native toolbar (an NSToolbar on macOS, which VoiceOver reads), each tool
with its label under it and the same command id as its menu item, so it
does what the menu does. Its icons are drawn from text (B, I, H1, ∑) in the
appearance's text colour (ui/theme.py), as there are no stock images for
them; View > Show Toolbar hides it.
"""

from __future__ import annotations

from collections.abc import Sequence

from mathessible.ui.theme import palette

try:
    import wx
except ImportError:
    wx = None

_SIZE = 24


if wx is not None:

    def glyph(text: str, bold: bool = False, italic: bool = False) -> wx.Bitmap:
        """A tool's icon: `text` drawn in the text colour on a transparent square."""
        appearance = wx.SystemSettings.GetAppearance() if hasattr(wx.SystemSettings, "GetAppearance") else None
        colour = wx.Colour(*palette(dark=bool(appearance is not None and appearance.IsDark())).text)
        bitmap = wx.Bitmap(_SIZE, _SIZE)
        dc = wx.MemoryDC(bitmap)
        dc.SetBackground(wx.Brush(wx.BLACK))
        dc.Clear()
        size = 15 if len(text) == 1 else 11
        font = wx.Font(
            size,
            wx.FONTFAMILY_SWISS,
            wx.FONTSTYLE_ITALIC if italic else wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL,
        )
        dc.SetFont(font)
        dc.SetTextForeground(wx.WHITE)
        width, height = dc.GetTextExtent(text)
        dc.DrawText(text, (_SIZE - width) // 2, (_SIZE - height) // 2)
        dc.SelectObject(wx.NullBitmap)
        # The white drawn on black is the icon's alpha, filled with the text colour.
        image = bitmap.ConvertToImage()
        alpha = bytes(image.GetData()[0::3])
        icon = wx.Image(_SIZE, _SIZE)
        icon.SetRGB(wx.Rect(0, 0, _SIZE, _SIZE), colour.Red(), colour.Green(), colour.Blue())
        icon.SetAlpha(alpha)
        return wx.Bitmap(icon)

    def build_toolbar(frame: wx.Frame, tools: Sequence[tuple[int, str, str, dict] | None]) -> wx.ToolBar:
        """The toolbar of `tools`: (command id, label, icon text, glyph options), None for a separator."""
        toolbar = frame.CreateToolBar(wx.TB_HORIZONTAL | wx.TB_TEXT | wx.TB_FLAT)
        toolbar.SetToolBitmapSize((_SIZE, _SIZE))
        for tool in tools:
            if tool is None:
                toolbar.AddSeparator()
                continue
            command, label, text, options = tool
            toolbar.AddTool(command, label, glyph(text, **options), shortHelp=label)
        toolbar.Realize()
        return toolbar
