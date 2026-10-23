from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from .settings import (
    BRAILLE_CODES,
    AppSettings,
    format_math_autocorrect,
    format_recognized_functions,
    parse_math_autocorrect,
    parse_recognized_functions,
)
from .symbol_dictionary import SymbolDictionaryError, available_dictionaries, import_dictionary
from .symbol_download import SymbolDownloadError, download_languages, nvda_languages

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
                label="Use linear navigation in exploration mode (F10; writing mode is always linear)",
            )
            self.linear_navigation.SetName("Linear navigation in exploration mode")
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
                label="Convert control words (for example \\alpha) when Space or punctuation is typed",
            )
            self.convert_on_space.SetName("Convert control words while typing")
            self.convert_on_space.SetValue(settings.convert_on_space)
            self.complete_control_words = wx.CheckBox(
                self,
                label="Suggest control words while one is typed (Up/Down browse, Tab completes)",
            )
            self.complete_control_words.SetName("Suggest control words while typing")
            self.complete_control_words.SetValue(settings.complete_control_words)
            self.decimal_comma = wx.CheckBox(
                self,
                label=(
                    "Decimal comma: 1,5 is a number and a set is written {1, 2, 3}; "
                    "off: decimal point (3.14), and {1,2,3} is a set"
                ),
            )
            self.decimal_comma.SetName("Decimal comma")
            self.decimal_comma.SetValue(settings.decimal_separator == ",")
            self.convert_shortcuts_immediately = wx.CheckBox(
                self,
                label="Convert symbol shortcuts (for example << or ->) as soon as they are typed",
            )
            self.convert_shortcuts_immediately.SetName("Convert symbol shortcuts immediately")
            self.convert_shortcuts_immediately.SetValue(settings.convert_shortcuts_immediately)
            self.open_built = wx.CheckBox(
                self,
                label="Open equations built (professional view), ready to navigate and type into",
            )
            self.open_built.SetName("Open equations built")
            self.open_built.SetValue(settings.open_built)
            self.build_as_you_type = wx.CheckBox(
                self,
                label="Build equations as you type (on Space or a closing bracket, once complete)",
            )
            self.build_as_you_type.SetName("Build equations as you type")
            self.build_as_you_type.SetValue(settings.build_as_you_type)
            self.argument_on_closing_paren = wx.CheckBox(
                self,
                label="Open a function's argument as soon as its parenthesis is closed (instead of on Space)",
            )
            self.argument_on_closing_paren.SetName("Open the argument on the closing parenthesis")
            self.argument_on_closing_paren.SetValue(settings.argument_on_closing_paren)
            self.template_control_words = wx.CheckBox(
                self,
                label="Insert templates as control words (for example \\sum and \\sqrt instead of ∑ and √)",
            )
            self.template_control_words.SetName("Insert templates as control words")
            self.template_control_words.SetValue(settings.template_control_words)
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
            autocorrect_label = wx.StaticText(self, label="&Math AutoCorrect entries")
            self.math_autocorrect = wx.TextCtrl(
                self,
                value=format_math_autocorrect(settings.math_autocorrect),
                style=wx.TE_MULTILINE,
                size=(-1, 90),
            )
            self.math_autocorrect.SetName("Math AutoCorrect entries")
            autocorrect_help = wx.StaticText(
                self,
                label=(
                    "One entry per line: what you type, a space, what it becomes, as in Word's "
                    "Math AutoCorrect. An entry starting with a backslash (\\R ℝ) works like a "
                    "control word; any other (+- ±) is replaced when you type Space after it."
                ),
            )
            autocorrect_help.Wrap(460)
            braille_label = wx.StaticText(self, label="&Braille code (the braille strip under the equation)")
            self.braille_code = wx.Choice(self, choices=[label for _code, label in BRAILLE_CODES])
            self.braille_code.SetName("Braille code")
            codes = [code for code, _label in BRAILLE_CODES]
            self.braille_code.SetSelection(codes.index(settings.braille_code) if settings.braille_code in codes else 0)
            symbols_label = wx.StaticText(self, label="Symbol dictionary (names spoken for symbols)")
            self.symbol_dictionary = wx.Choice(self)
            self.symbol_dictionary.SetName("Symbol dictionary")
            self._fill_dictionaries(settings.symbol_dictionary)
            import_button = wx.Button(self, label="&Import dictionary…")
            import_button.Bind(wx.EVT_BUTTON, self._on_import_dictionary)
            download_button = wx.Button(self, label="&Download NVDA dictionaries…")
            download_button.Bind(wx.EVT_BUTTON, self._on_download_dictionaries)
            symbols_help = wx.StaticText(
                self,
                label=(
                    "Any file in NVDA's symbols.dic format can be imported. NVDA's own "
                    "dictionaries are downloaded from the NVDA project on GitHub."
                ),
            )
            symbols_help.Wrap(460)
            symbols_row = wx.BoxSizer(wx.HORIZONTAL)
            symbols_row.Add(self.symbol_dictionary, 1, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 8)
            symbols_row.Add(import_button, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 8)
            symbols_row.Add(download_button, 0, wx.ALIGN_CENTER_VERTICAL)
            buttons = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)

            sizer.Add(heading, 0, wx.ALL, 12)
            sizer.Add(self.linear_navigation, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            sizer.Add(self.structure_stops, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            sizer.Add(self.invisible_operator_stops, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            sizer.Add(self.convert_on_space, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            sizer.Add(self.complete_control_words, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            sizer.Add(self.decimal_comma, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            sizer.Add(self.convert_shortcuts_immediately, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            sizer.Add(self.open_built, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            sizer.Add(self.build_as_you_type, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            sizer.Add(self.argument_on_closing_paren, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            sizer.Add(self.template_control_words, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            sizer.Add(self.auto_zoom_out, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            sizer.Add(explanation, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
            sizer.Add(functions_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
            sizer.Add(self.recognized_functions, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
            sizer.Add(functions_help, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
            sizer.Add(autocorrect_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
            sizer.Add(self.math_autocorrect, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
            sizer.Add(autocorrect_help, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
            sizer.Add(braille_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
            sizer.Add(self.braille_code, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
            sizer.Add(symbols_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
            sizer.Add(symbols_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
            sizer.Add(symbols_help, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
            if buttons is not None:
                sizer.Add(buttons, 0, wx.ALL | wx.EXPAND, 12)
            self.SetSizerAndFit(sizer)

        def _fill_dictionaries(self, selected: str) -> None:
            self._dictionaries = available_dictionaries()
            self.symbol_dictionary.Set([info.label for info in self._dictionaries])
            identifiers = [info.identifier for info in self._dictionaries]
            self.symbol_dictionary.SetSelection(identifiers.index(selected) if selected in identifiers else 0)

        def _on_import_dictionary(self, _event: wx.CommandEvent) -> None:
            with wx.FileDialog(
                self,
                "Import a symbol dictionary",
                wildcard="NVDA symbol dictionaries (*.dic)|*.dic|All files|*",
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
            ) as dialog:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                path = Path(dialog.GetPath())
            try:
                info = import_dictionary(path)
            except (SymbolDictionaryError, OSError) as error:
                wx.MessageBox(str(error), "Import failed", wx.OK | wx.ICON_ERROR, self)
                return
            self._fill_dictionaries(info.identifier)
            self.symbol_dictionary.SetFocus()

        def _on_download_dictionaries(self, _event: wx.CommandEvent) -> None:
            self._in_background("Listing NVDA's languages…", nvda_languages, self._choose_languages)

        def _choose_languages(self, languages: list[str]) -> None:
            with wx.MultiChoiceDialog(
                self,
                "Choose the languages to download (Space checks one).",
                "Download NVDA dictionaries",
                languages,
            ) as dialog:
                if "en" in languages:
                    dialog.SetSelections([languages.index("en")])
                if dialog.ShowModal() != wx.ID_OK:
                    return
                chosen = [languages[index] for index in dialog.GetSelections()]
            if not chosen:
                return
            self._in_background(
                f"Downloading {len(chosen)} dictionaries…",
                lambda: download_languages(chosen),
                self._downloaded,
            )

        def _downloaded(self, report) -> None:
            selected = self._dictionaries[max(0, self.symbol_dictionary.GetSelection())].identifier
            if report.saved:
                # Select the first one fetched; a language NVDA has no file for is reported.
                selected = report.saved[0].stem
            self._fill_dictionaries(selected)
            message = f"{len(report.saved)} dictionaries downloaded."
            if report.missing:
                message += f" NVDA has no symbol dictionary for: {', '.join(report.missing)}."
            wx.MessageBox(message, "Download NVDA dictionaries", wx.OK | wx.ICON_INFORMATION, self)
            self.symbol_dictionary.SetFocus()

        def _in_background(self, message: str, job: Callable[[], object], done: Callable[[object], None]) -> None:
            """Run a network job off the UI thread behind a pulsing progress dialog."""
            progress = wx.ProgressDialog("Download NVDA dictionaries", message, parent=self, style=wx.PD_APP_MODAL)
            outcome: dict[str, object] = {}

            def work() -> None:
                try:
                    outcome["result"] = job()
                except (SymbolDownloadError, OSError) as error:
                    outcome["error"] = error

            worker = threading.Thread(target=work, daemon=True)
            worker.start()

            def poll() -> None:
                if worker.is_alive():
                    progress.Pulse()
                    wx.CallLater(150, poll)
                    return
                progress.Destroy()
                if "error" in outcome:
                    wx.MessageBox(
                        f"The download failed: {outcome['error']}",
                        "Download NVDA dictionaries",
                        wx.OK | wx.ICON_ERROR,
                        self,
                    )
                    return
                done(outcome["result"])

            wx.CallLater(150, poll)

        def apply(self) -> None:
            selection = self.symbol_dictionary.GetSelection()
            if selection != wx.NOT_FOUND:
                self._settings.symbol_dictionary = self._dictionaries[selection].identifier
            braille = self.braille_code.GetSelection()
            if braille != wx.NOT_FOUND:
                self._settings.braille_code = BRAILLE_CODES[braille][0]
            self._settings.linear_navigation = self.linear_navigation.GetValue()
            self._settings.structure_stops = self.structure_stops.GetValue()
            self._settings.invisible_operator_stops = self.invisible_operator_stops.GetValue()
            self._settings.convert_on_space = self.convert_on_space.GetValue()
            self._settings.complete_control_words = self.complete_control_words.GetValue()
            self._settings.decimal_separator = "," if self.decimal_comma.GetValue() else "."
            self._settings.convert_shortcuts_immediately = self.convert_shortcuts_immediately.GetValue()
            self._settings.open_built = self.open_built.GetValue()
            self._settings.build_as_you_type = self.build_as_you_type.GetValue()
            self._settings.argument_on_closing_paren = self.argument_on_closing_paren.GetValue()
            self._settings.template_control_words = self.template_control_words.GetValue()
            self._settings.auto_zoom_out = self.auto_zoom_out.GetValue()
            self._settings.recognized_functions = parse_recognized_functions(
                self.recognized_functions.GetValue()
            )
            self._settings.math_autocorrect = parse_math_autocorrect(self.math_autocorrect.GetValue())

else:

    class SettingsDialog:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
