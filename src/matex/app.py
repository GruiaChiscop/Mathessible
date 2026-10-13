from __future__ import annotations


def main() -> None:
    try:
        import wx
    except ImportError as error:
        raise SystemExit("wxPython is not installed. Run: uv sync") from error

    from .main_frame import MainFrame

    app = wx.App(False)
    frame = MainFrame()
    frame.Centre()
    frame.Show()
    frame.editor.markdown.SetFocus()
    app.MainLoop()


if __name__ == "__main__":
    main()
