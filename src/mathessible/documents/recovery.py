"""Recovery of unsaved work after Mathessible closed unexpectedly.

Every open window with unsaved changes writes its text to
`~/.mathessible/recovery/` now and then; saving, reverting or closing the
window removes it. What is left when Mathessible starts, from a process
that is no longer running, was lost in a crash or a power cut and is
offered back.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Recovered:
    kind: str  # "document", "notebook" (a folder) or "portable" (a .msnb file).
    path: str  # The document, notebook folder or .msnb file; "" for an untitled document.
    page: int  # The notebook's page.
    title: str  # What the window was called.
    source: str  # The unsaved text.
    process: int  # The process that wrote it.
    saved_at: float


def recovery_directory() -> Path:
    return Path.home() / ".mathessible" / "recovery"


def write_record(name: str, record: Recovered, directory: Path | None = None) -> None:
    folder = directory or recovery_directory()
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / f"{name}.json.tmp"
    temporary.write_text(json.dumps(asdict(record), ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, folder / f"{name}.json")  # Never half a file.


def delete_record(name: str, directory: Path | None = None) -> None:
    try:
        ((directory or recovery_directory()) / f"{name}.json").unlink()
    except FileNotFoundError:
        pass


def _running(process: int) -> bool:
    try:
        os.kill(process, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def pending_records(directory: Path | None = None) -> list[tuple[str, Recovered]]:
    """Records left by a Mathessible that is no longer running, newest first; unreadable ones are left alone."""
    folder = directory or recovery_directory()
    found: list[tuple[str, Recovered]] = []
    for path in folder.glob("*.json") if folder.is_dir() else ():
        try:
            record = Recovered(**json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            continue
        if record.process != os.getpid() and not _running(record.process):
            found.append((path.stem, record))
    return sorted(found, key=lambda item: item[1].saved_at, reverse=True)


def record_name(window: int) -> str:
    """A name unique to this process's window."""
    return f"{os.getpid()}-{window}"


def now() -> float:
    return time.time()
