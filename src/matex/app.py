from __future__ import annotations


def main() -> None:
    try:
        import wx
    except ImportError as error:
        raise SystemExit("wxPython is not installed. Run: uv sync") from error

    from matex import session_log
    from matex.ui.main_frame import MainFrame

    session_log.start()
    app = wx.App(False)
    frame = MainFrame()
    frame.Centre()
    frame.Show()
    frame.editor.markdown.SetFocus()
    app.MainLoop()
    session_log.stop()


if __name__ == "__main__":
    main()
