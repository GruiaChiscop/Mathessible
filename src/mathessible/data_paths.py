"""Platform data locations for Mathessible."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def application_root() -> Path:
    """Where the submodules' files are: the checkout, or a packaged application (PyInstaller's folder)."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def data_directory(
    home: Path | None = None, platform: str | None = None, environ: dict[str, str] | None = None
) -> Path:
    """Resolve paths only; never create directories or migrate during an import."""
    # An explicit home (a test's folder) is the whole answer: APPDATA would still name the real one.
    environ = environ if environ is not None else (os.environ if home is None else {})
    home = home if home is not None else Path.home()
    platform = platform if platform is not None else sys.platform
    if platform == "win32":
        roaming = Path(environ.get("APPDATA", ""))
        if not roaming.is_absolute():
            roaming = home / "AppData" / "Roaming"
        return roaming / "mathessible"
    if platform == "darwin":
        return home / "Library" / "Application Support" / "Mathessible"
    return home / ".mathessible"
