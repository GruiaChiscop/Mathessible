"""Use macOS's local rich-text converter for clipboard RTF, including tables."""

from __future__ import annotations

import subprocess
import sys


def html_from_rtf(data: bytes) -> str | None:
    """Return HTML without temporary files; unsupported platforms keep native paste."""
    if sys.platform != "darwin" or len(data) > 2_000_000 or not data.startswith(b"{\\rtf"):
        return None
    try:
        result = subprocess.run(
            ["/usr/bin/textutil", "-convert", "html", "-format", "rtf", "-stdin", "-stdout"],
            input=data,
            capture_output=True,
            timeout=5,
            check=True,
        )
        return result.stdout.decode("utf-8")
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None
