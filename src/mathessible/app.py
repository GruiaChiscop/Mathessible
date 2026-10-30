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

    session_log.start()
    app = wx.App(False)
    # The interface's language, before any window is built (a change needs a restart).
    set_language(interface_language(load_settings().interface_language, preferred_languages()))
    # The home screen, as other editors start with, unless documents are given on the command line.
    frame = MainFrame(home=not sys.argv[1:])
    frame.Centre()
    frame.Show()
    if sys.argv[1:]:
        frame.editor.markdown.SetFocus()
    else:
        frame.home_panel.focus()
    for argument in sys.argv[1:]:  # Documents and notebooks given on the command line.
        frame.open_path(Path(argument))
    wx.CallAfter(offer_recovery, frame)
    app.MainLoop()
    session_log.stop()


if __name__ == "__main__":
    main()
