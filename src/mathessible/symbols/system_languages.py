"""The user's preferred languages, from the system, most preferred first ("en-RO", "ro-RO").

Python's locale says "C" in a macOS app started from Finder, so each
system is asked directly: macOS its AppleLanguages list, Windows the
user's locale, elsewhere LANGUAGE and LANG.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys


def parse_apple_languages(output: str) -> list[str]:
    """`defaults read -g AppleLanguages` output, a property list array, as codes."""
    return re.findall(r'"?([A-Za-z]{2,3}(?:-[A-Za-z0-9]+)*)"?\s*[,)\n]', output.split("(", 1)[-1])


def _macos() -> list[str]:
    try:
        output = subprocess.run(
            ["defaults", "read", "-g", "AppleLanguages"], capture_output=True, text=True, timeout=5
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_apple_languages(output)


def _windows() -> list[str]:
    import ctypes

    buffer = ctypes.create_unicode_buffer(85)  # LOCALE_NAME_MAX_LENGTH
    if ctypes.windll.kernel32.GetUserDefaultLocaleName(buffer, len(buffer)):
        return [buffer.value]
    return []


def _environment() -> list[str]:
    languages = os.environ.get("LANGUAGE", "").split(":") + [os.environ.get("LANG", "")]
    return [
        code.split(".")[0].replace("_", "-") for code in languages if code and code.split(".")[0] not in ("C", "POSIX")
    ]


def preferred_languages() -> list[str]:
    """The system's languages, most preferred first; empty when it cannot be told."""
    if sys.platform == "darwin":
        return _macos() or _environment()
    if sys.platform == "win32":
        return _windows() or _environment()
    return _environment()
