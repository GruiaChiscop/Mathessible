from __future__ import annotations

import sys


def main() -> None:
    try:
        import wx
    except ImportError as error:
        raise SystemExit("wxPython is not installed. Run: uv sync") from error

    from pathlib import Path

    from mathessible import session_log
    from mathessible.i18n import interface_language, set_language
    from mathessible.settings import load_settings
    from mathessible.symbols.system_languages import preferred_languages
    from mathessible.ui.main_frame import MainFrame, offer_recovery

    class Application(wx.App):
        def __init__(self) -> None:
            # Documents the Finder asks to open before the first window exists: when it starts the
            # application to open them, wx delivers them while the application is being made.
            self.waiting: list[Path] = []
            super().__init__(False)

        def MacOpenFiles(self, fileNames: list[str]) -> None:  # noqa: N802, N803 (wx's names)
            """Documents opened from the Finder (double-click, Open With, a drop on the Dock icon)."""
            paths = [Path(name) for name in fileNames]
            windows = MainFrame._application_windows()
            session_log.write("open", f"from the Finder: {fileNames}, {len(windows)} window(s)")
            if not windows:
                self.waiting += paths
                return
            for path in paths:
                windows[0].open_path(path)

    session_log.start()
    app = Application()
    # The interface's language, before any window is built (a change needs a restart).
    set_language(interface_language(load_settings().interface_language, preferred_languages()))
    # Documents and notebooks given on the command line or by the Finder.
    paths = [Path(argument) for argument in sys.argv[1:]] + app.waiting
    app.waiting = []
    # The home screen, as other editors start with, unless documents are given.
    frame = MainFrame(home=not paths)
    frame.Centre()
    frame.Show()
    if paths:
        frame.editor.markdown.SetFocus()
    else:
        frame.home_panel.focus()
    # With them, those the Finder sent while the window was being built.
    while paths or app.waiting:
        paths, app.waiting = paths + app.waiting, []
        frame.open_path(paths.pop(0))
    wx.CallAfter(offer_recovery, frame)
    app.MainLoop()
    session_log.stop()


if __name__ == "__main__":
    main()
