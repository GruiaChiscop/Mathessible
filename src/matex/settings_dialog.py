from __future__ import annotations

from .settings import AppSettings, format_recognized_functions, parse_recognized_functions

try:
    import wx
except ImportError:
    wx = None


if wx is not None:

    class SettingsDialog(wx.Dialog):
        def __init__(self, parent: wx.Window, settings: AppSettings):
            super().__init__(
                parent,
                title="Settings",
                style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            )
            self.SetName("Settings dialog")
            self._settings = settings

            sizer = wx.BoxSizer(wx.VERTICAL)
            heading = wx.StaticText(self, label="Equation editor")
            self.linear_navigation = wx.CheckBox(
                self,
                label="Use linear navigation in professional equation mode",
            )
            self.linear_navigation.SetName("Linear navigation")
            self.linear_navigation.SetValue(settings.linear_navigation)
            self.structure_stops = wx.CheckBox(
                self,
                label=(
                    "Stop at the start and end of every structure "
                    "(for example \"start fraction\", \"end numerator\") and of the math"
                ),
            )
            self.structure_stops.SetName("Stop at structure start and end")
            self.structure_stops.SetValue(settings.structure_stops)
            self.invisible_operator_stops = wx.CheckBox(
                self,
                label="Stop at invisible operators (for example the invisible times in 3x)",
            )
            self.invisible_operator_stops.SetName("Stop at invisible operators")
            self.invisible_operator_stops.SetValue(settings.invisible_operator_stops)
            self.convert_on_space = wx.CheckBox(
                self,
                label="Convert shortcuts when Space is pressed",
            )
            self.convert_on_space.SetName("Convert on Space")
            self.convert_on_space.SetValue(settings.convert_on_space)
            self.auto_zoom_out = wx.CheckBox(
                self,
                label="Leave a structure automatically at its end (for example, from the numerator to the denominator)",
            )
            self.auto_zoom_out.SetName("Leave structures automatically")
            self.auto_zoom_out.SetValue(settings.auto_zoom_out)
            explanation = wx.StaticText(
                self,
                label=(
                    "When enabled, the right arrow enters structures such as fractions "
                    "automatically, so you can read more of an expression without pressing Down."
                ),
            )
            explanation.Wrap(460)
            functions_label = wx.StaticText(self, label="Recognized functions")
            self.recognized_functions = wx.TextCtrl(
                self,
                value=format_recognized_functions(settings.recognized_functions),
            )
            self.recognized_functions.SetName("Recognized functions")
            functions_help = wx.StaticText(
                self,
                label=(
                    "Comma-separated function names. These are used for Word-like "
                    "navigation through function names and arguments."
                ),
            )
            functions_help.Wrap(460)
            buttons = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)

            sizer.Add(heading, 0, wx.ALL, 12)
            sizer.Add(self.linear_navigation, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            sizer.Add(self.structure_stops, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            sizer.Add(self.invisible_operator_stops, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            sizer.Add(self.convert_on_space, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            sizer.Add(self.auto_zoom_out, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            sizer.Add(explanation, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
            sizer.Add(functions_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
            sizer.Add(self.recognized_functions, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
            sizer.Add(functions_help, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
            if buttons is not None:
                sizer.Add(buttons, 0, wx.ALL | wx.EXPAND, 12)
            self.SetSizerAndFit(sizer)

        def apply(self) -> None:
            self._settings.linear_navigation = self.linear_navigation.GetValue()
            self._settings.structure_stops = self.structure_stops.GetValue()
            self._settings.invisible_operator_stops = self.invisible_operator_stops.GetValue()
            self._settings.convert_on_space = self.convert_on_space.GetValue()
            self._settings.auto_zoom_out = self.auto_zoom_out.GetValue()
            self._settings.recognized_functions = parse_recognized_functions(
                self.recognized_functions.GetValue()
            )

else:

    class SettingsDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
