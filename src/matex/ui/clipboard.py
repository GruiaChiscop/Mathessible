from __future__ import annotations

try:
    import wx
except ImportError:  # The interface is an optional dependency.
    wx = None


def set_clipboard_text(text: str, html: str | None = None) -> bool:
    """Put text on the clipboard, and `html` beside it (equations as MathML, which Word builds)."""
    if not wx.TheClipboard.Open():
        return False
    try:
        if html is None:
            wx.TheClipboard.SetData(wx.TextDataObject(text))
        else:
            data = wx.DataObjectComposite()
            data.Add(wx.TextDataObject(text), preferred=True)
            data.Add(wx.HTMLDataObject(html))
            wx.TheClipboard.SetData(data)
    finally:
        wx.TheClipboard.Close()
    return True


def get_clipboard_text() -> str | None:
    if not wx.TheClipboard.Open():
        return None
    try:
        data = wx.TextDataObject()
        if not wx.TheClipboard.GetData(data):
            return None
    finally:
        wx.TheClipboard.Close()
    return data.GetText()
