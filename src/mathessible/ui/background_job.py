"""A slow job (a download, a Pandoc conversion) on a worker thread, behind a native progress window."""

from __future__ import annotations

import threading
from collections.abc import Callable

from mathessible.documents.optional_tools import ToolError
from mathessible.documents.pandoc import PandocError
from mathessible.i18n import _

try:
    import wx
except ImportError:  # The interface is an optional dependency.
    wx = None


def run_job(
    parent: object,
    title: str,
    job: Callable[[threading.Event, Callable[[int], None]], object],
    done: Callable[[object], None],
    failed: Callable[[str], None] | None = None,
    errors: tuple[type[Exception], ...] = (),
) -> None:
    """`job(cancel, report)` on a worker, `report(percent)` turning the pulsing bar into a percentage; then,
    on the GUI thread, `done(result)` or `failed(message)` (by default a message box). Nothing is called
    after Cancel, or once `parent` is gone. `errors`: the job's own exceptions, reported as failures too."""
    cancel = threading.Event()
    outcome: dict[str, object] = {}
    progress = wx.ProgressDialog(
        title, _("Working…"), maximum=100, parent=parent, style=wx.PD_APP_MODAL | wx.PD_CAN_ABORT
    )

    def report(percent: int) -> None:
        outcome["percent"] = percent

    def work() -> None:
        try:
            outcome["result"] = job(cancel, report)
        except (ToolError, PandocError, OSError, *errors) as error:
            outcome["error"] = str(error)

    worker = threading.Thread(target=work, daemon=True)
    worker.start()

    def poll() -> None:
        if worker.is_alive():
            message = _("Cancelling after the current operation…") if cancel.is_set() else _("Working…")
            percent = outcome.get("percent")
            if percent is None or percent >= 90:  # Unpacking and checking have no percentage.
                keep, _skip = progress.Pulse(message)
            else:
                keep, _skip = progress.Update(percent, message)
            if not keep:
                cancel.set()
            wx.CallLater(150, poll)
            return
        progress.Destroy()
        if not parent or cancel.is_set():
            return
        if "error" in outcome or "result" not in outcome:  # Or the job stopped on an unexpected error.
            message = str(outcome.get("error", ""))
            if failed is not None:
                failed(message)
            else:
                wx.MessageBox(
                    _("The operation failed: {error}").format(error=message), title, wx.OK | wx.ICON_ERROR, parent
                )
        else:
            done(outcome["result"])

    wx.CallLater(150, poll)
