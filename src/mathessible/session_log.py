"""An optional log of a test session: keys, speech, menu commands, editor state, errors.

On only when the environment has MATHESSIBLE_LOG=1 (or a file path in it), so a
user's test can be read back afterwards: the screen reader's own speech is
not in it, only what Mathessible says. Writes to ~/.mathessible/logs/session-<time>.log.
Never raises: a log that cannot be written is simply not written.
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path
from types import TracebackType

_path: Path | None = None
_started = 0.0


def enabled() -> bool:
    return _path is not None


def start(environment: dict[str, str] | None = None) -> Path | None:
    """Open the log if MATHESSIBLE_LOG asks for one; returns its path, or None."""
    global _path, _started
    value = (environment if environment is not None else os.environ).get("MATHESSIBLE_LOG", "")
    if not value or value == "0":
        return None
    if value == "1":
        path = Path.home() / ".mathessible" / "logs" / time.strftime("session-%Y%m%d-%H%M%S.log")
    else:
        path = Path(value).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    except OSError:
        return None
    _path, _started = path, time.monotonic()
    previous = sys.excepthook

    def hook(kind: type[BaseException], error: BaseException, trace: TracebackType | None) -> None:
        write("error", "".join(traceback.format_exception(kind, error, trace)).rstrip())
        previous(kind, error, trace)

    sys.excepthook = hook
    write("start", f"Mathessible session, pid {os.getpid()}")
    return path


def write(kind: str, text: str) -> None:
    if _path is None:
        return
    line = f"{time.monotonic() - _started:9.3f} {kind:7} {text}".replace("\n", "\n" + " " * 18)
    try:
        with _path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
    except OSError:
        pass


def stop() -> None:
    global _path
    write("stop", "")
    _path = None
