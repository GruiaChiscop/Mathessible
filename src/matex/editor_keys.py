"""The equation editor's key conventions, shared by its mixins (platform modifiers)."""

from __future__ import annotations

try:
    import wx
except ImportError:  # The interface is an optional dependency.
    wx = None


def word_navigation_down(event: wx.KeyEvent) -> bool:
    """The word-navigation modifier: Option on macOS, Ctrl elsewhere."""
    return event.AltDown() if wx.Platform == "__WXMAC__" else event.ControlDown()


def template_variant_down(event: wx.KeyEvent) -> bool:
    """The template-variant modifier (limits, n-th root): physical Control on macOS, Alt elsewhere.

    Not Option on macOS: Option+S/P/I type ß, π and a dead key there
    (the same reason the equation shortcut is Control+=).
    """
    if wx.Platform == "__WXMAC__":
        return event.RawControlDown() and not event.CmdDown() and not event.AltDown()
    return event.AltDown() and not event.ControlDown()


def cell_navigation_down(event: wx.KeyEvent) -> bool:
    """The matrix-cell modifier: Command+Option on macOS, Ctrl+Alt elsewhere."""
    # CmdDown() is Command on macOS and Ctrl elsewhere.
    return event.CmdDown() and event.AltDown()


def effective_key(event: wx.KeyEvent) -> int:
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


def describe_key(event: wx.KeyEvent) -> str:
    """A key press as text for the session log: "Cmd+Shift+G", "Option+Left", "F2"."""
    mac = wx.Platform == "__WXMAC__"
    parts = []
    if event.RawControlDown() and mac:
        parts.append("Control")
    if event.CmdDown():
        parts.append("Cmd" if mac else "Ctrl")
    if event.AltDown():
        parts.append("Option" if mac else "Alt")
    if event.ShiftDown():
        parts.append("Shift")
    code = event.GetKeyCode()
    names = {
        wx.WXK_LEFT: "Left",
        wx.WXK_RIGHT: "Right",
        wx.WXK_UP: "Up",
        wx.WXK_DOWN: "Down",
        wx.WXK_HOME: "Home",
        wx.WXK_END: "End",
        wx.WXK_BACK: "Backspace",
        wx.WXK_DELETE: "Delete",
        wx.WXK_RETURN: "Return",
        wx.WXK_NUMPAD_ENTER: "Enter",
        wx.WXK_TAB: "Tab",
        wx.WXK_ESCAPE: "Escape",
        wx.WXK_SPACE: "Space",
        wx.WXK_PAGEUP: "PageUp",
        wx.WXK_PAGEDOWN: "PageDown",
        wx.WXK_MENU: "Menu",
    }
    if code in names:
        name = names[code]
    elif wx.WXK_F1 <= code <= wx.WXK_F24:
        name = f"F{code - wx.WXK_F1 + 1}"
    elif 32 < code < 127:
        name = chr(code)
    else:
        name = f"key {code}"
    return "+".join(parts + [name])
