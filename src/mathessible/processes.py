"""Whether another process is still running, without touching it."""

from __future__ import annotations

import os
import sys


def running(process: int) -> bool:
    """True while the process exists. On Windows `os.kill(process, 0)` would end it, so it is asked instead."""
    if process <= 0:
        return False
    if sys.platform == "win32":
        return _running_on_windows(process)
    try:
        os.kill(process, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # It exists, under another user.
    except OSError:
        return False
    return True


def _running_on_windows(process: int) -> bool:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    query_limited_information, access_denied, still_active = 0x1000, 5, 259
    handle = kernel32.OpenProcess(query_limited_information, False, process)
    if not handle:
        return ctypes.get_last_error() == access_denied
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True
        return code.value == still_active
    finally:
        kernel32.CloseHandle(handle)
