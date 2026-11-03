"""Name a control for the screen reader when it has no visible label next to it, like Edit Table's cells.

wx 3.2 gives a text field no name of its own: on macOS `set_accessibility_label` sets AppKit's
`accessibilityLabel` on the control's view and, for a multiline text field (an NSScrollView), on the text
view inside it, which is the one that takes the focus; on Windows it answers MSAA's name (what NVDA reads)
through a `wx.Accessible` that leaves everything else to the standard control.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import sys
from functools import cache

try:
    import wx
except ImportError:
    wx = None


@cache
def _runtime() -> tuple | None:
    objc_path = ctypes.util.find_library("objc")
    if objc_path is None:
        return None
    objc = ctypes.CDLL(objc_path)
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    # objc_msgSend must be called through a pointer typed for each signature.
    send = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
    send_id = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(send)
    send_with_text = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)(send)
    send_with_id = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(send)
    send_bool = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(send)
    return objc, send_id, send_with_text, send_with_id, send_bool


if wx is not None:

    class _Named(wx.Accessible):
        def __init__(self, control: wx.Window, label: str):
            super().__init__(control)
            self.label = label

        def GetName(self, childId: int) -> tuple[int, str]:  # noqa: N802 (wx's name)
            if childId == wx.ACC_SELF:
                return wx.ACC_OK, self.label
            return wx.ACC_NOT_IMPLEMENTED, ""


def set_accessibility_label(control: wx.Window, label: str) -> None:
    control.SetName(label)
    if wx is None:
        return
    if sys.platform == "win32":
        control.SetAccessible(_Named(control, label))
        return
    if sys.platform != "darwin" or (runtime := _runtime()) is None:
        return
    objc, send_id, send_with_text, send_with_id, send_bool = runtime
    view = control.GetHandle()
    if not view:
        return
    text = send_with_text(
        objc.objc_getClass(b"NSString"), objc.sel_registerName(b"stringWithUTF8String:"), label.encode()
    )
    views = [view]
    document_view = objc.sel_registerName(b"documentView")
    if send_bool(view, objc.sel_registerName(b"respondsToSelector:"), document_view):
        inner = send_id(view, document_view)
        if inner:
            views.append(inner)
    for each in views:
        send_with_id(each, objc.sel_registerName(b"setAccessibilityLabel:"), text)
