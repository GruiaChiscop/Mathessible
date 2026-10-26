"""Stop wx's web views from taking Cmd+A/C/V/X when they do not have the focus.

wxWidgets 3.2's WKWebView subclass (`WXWKWebView`, src/osx/webview_webkit.mm)
overrides `performKeyEquivalent:` and handles Cmd+A/C/V/X itself, without
checking whether it has the keyboard focus. AppKit offers a Command shortcut
to every view in the key window before the focused one sees it, so the
document preview took Cmd+A from the Markdown editor, and the equation
editor's renderer (never focused) took it from the equation editor.

This replaces that one method so it only runs while the web view, or a view
inside it, is the window's first responder; otherwise it answers NO and the
shortcut reaches the focused control. Nothing else is changed. Remove this
once wxPython ships a wxWidgets with the check.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import sys

_KeyEquivalent = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_installed = False
# The replacement IMP and the original must outlive the process's use of them.
_keep_alive: list[object] = []


def guard_webview_key_equivalents() -> bool:
    """Install the guard once; True when it is in place. A no-op off macOS."""
    global _installed
    if _installed or sys.platform != "darwin":
        return _installed
    objc_path = ctypes.util.find_library("objc")
    if objc_path is None:
        return False
    objc = ctypes.CDLL(objc_path)
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    objc.class_getInstanceMethod.restype = ctypes.c_void_p
    objc.class_getInstanceMethod.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    objc.class_getMethodImplementation.restype = ctypes.c_void_p
    objc.class_getMethodImplementation.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    objc.method_getTypeEncoding.restype = ctypes.c_char_p
    objc.method_getTypeEncoding.argtypes = [ctypes.c_void_p]
    objc.class_replaceMethod.restype = ctypes.c_void_p
    objc.class_replaceMethod.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]

    web_view = objc.objc_getClass(b"WXWKWebView")
    ns_view = objc.objc_getClass(b"NSView")
    if not web_view or not ns_view:
        return False  # wx's WebKit backend is not loaded (wx.html2 not imported).
    selector = objc.sel_registerName(b"performKeyEquivalent:")
    method = objc.class_getInstanceMethod(web_view, selector)
    if not method:
        return False

    # objc_msgSend must be called through a pointer typed for each signature.
    send = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
    send_id = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(send)
    send_bool = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(send)
    window_selector = objc.sel_registerName(b"window")
    first_responder_selector = objc.sel_registerName(b"firstResponder")
    is_kind_selector = objc.sel_registerName(b"isKindOfClass:")
    is_descendant_selector = objc.sel_registerName(b"isDescendantOf:")

    original = _KeyEquivalent(objc.class_getMethodImplementation(web_view, selector))

    def guarded(view: int, command: int, event: int) -> bool:
        window = send_id(view, window_selector)
        responder = send_id(window, first_responder_selector) if window else None
        if (
            responder
            and send_bool(responder, is_kind_selector, ns_view)
            and send_bool(responder, is_descendant_selector, view)
        ):
            return original(view, command, event)
        return False

    replacement = _KeyEquivalent(guarded)
    _keep_alive.extend([original, replacement, send_id, send_bool])
    objc.class_replaceMethod(
        web_view,
        selector,
        ctypes.cast(replacement, ctypes.c_void_p),
        objc.method_getTypeEncoding(method),
    )
    _installed = True
    return True
