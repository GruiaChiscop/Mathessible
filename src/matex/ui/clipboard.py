from __future__ import annotations

try:
    import wx
except ImportError:  # The interface is an optional dependency.
    wx = None


def set_clipboard_text(text: str) -> bool:
    if not wx.TheClipboard.Open():
        return False
    try:
        wx.TheClipboard.SetData(wx.TextDataObject(text))
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
