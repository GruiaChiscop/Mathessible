"""The equation editor's key conventions, shared by its mixins (platform modifiers)."""

from __future__ import annotations

from .unicodemath import control_words

try:
    import wx
except ImportError:  # The interface is an optional dependency.
    wx = None


def converter_control_words() -> dict[str, str] | None:
    """The converter's control-word table, or None (fallback list) without the submodule."""
    try:
        return control_words()
    except (OSError, ValueError):
        return None

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
