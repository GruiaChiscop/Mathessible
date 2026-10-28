"""Settings: one panel of tabs, in a window on macOS and a dialog elsewhere.

On macOS settings are a window, as in Mac apps: a change applies (and is
saved) at once, and the window has no OK or Cancel. Elsewhere it is a
dialog with OK, Cancel and Apply. Both hold the same `SettingsPanel`,
its settings grouped in native tabs that screen readers announce.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from mathessible.editing.autocorrect import AutoCorrectTable, autocorrect_defaults, differences
from mathessible.i18n import LANGUAGES, _, ngettext
from mathessible.settings import BRAILLE_CODES, AppSettings
from mathessible.symbols.braille_signs import load_signs, save_signs
from mathessible.symbols.dictionary import SymbolDictionaryError, available_dictionaries, import_dictionary
from mathessible.symbols.download import SymbolDownloadError, download_languages, nvda_languages
from mathessible.ui.autocorrect_dialog import AutoCorrectDialog
from mathessible.ui.braille_signs_dialog import BrailleSignsDialog
from mathessible.ui.export_controls import (
    BrfControls,
    DocxControls,
    FormRows,
    HtmlControls,
    PdfContentControls,
    PdfLayoutControls,
    PdfStandardControl,
)
from mathessible.ui.functions_dialog import RecognizedFunctionsDialog
from mathessible.unicodemath import control_words

try:
    import wx
except ImportError:
    wx = None

_WRAP = 460


def applies_at_once() -> bool:
    """macOS settings are a window whose changes apply at once; elsewhere a dialog with OK/Cancel/Apply."""
    return wx is not None and wx.Platform == "__WXMAC__"


if wx is not None:

    class SettingsPanel(wx.Panel):
        """Every setting, in tabs: Typing, Building, Navigation, Speech, Braille.

        `apply()` writes the controls into the settings. With `on_change`,
        every change calls it straight away (the macOS window); a list edited
        in its own dialog does when that dialog's OK is chosen.
        """

        def __init__(self, parent: wx.Window, settings: AppSettings, on_change: Callable[[], None] | None = None):
            super().__init__(parent)
            self._settings = settings
            self._on_change = on_change
            self._autocorrect = (settings.math_autocorrect, settings.math_autocorrect_removed)
            # The user's own braille signs, per code, until applied (symbols/braille_signs.py).
            self._braille_signs: dict[str, dict[str, str]] = {}
            self._functions = settings.recognized_functions

            self.notebook = wx.Notebook(self)
            self.notebook.SetName(_("Settings categories"))
            self._language_page(self._page(_("Language")), settings)
            self._typing_page(self._page(_("Typing")), settings)
            self._building_page(self._page(_("Building")), settings)
            self._navigation_page(self._page(_("Navigation")), settings)
            self._speech_page(self._page(_("Speech")), settings)
            self._braille_page(self._page(_("Braille")), settings)
            self._pdf_page(self._page("PDF"), settings)
            self._html_page(self._page("HTML"), settings)
            self._docx_page(self._page(_("Word")), settings)
            for index in range(self.notebook.GetPageCount()):
                self.notebook.GetPage(index).GetSizer().AddSpacer(12)  # A margin under the last control.
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(self.notebook, 1, wx.EXPAND)
            self.SetSizer(sizer)

        # Pages

        def _page(self, title: str) -> wx.Panel:
            page = wx.Panel(self.notebook)
            page.SetName(title)
            page.SetSizer(wx.BoxSizer(wx.VERTICAL))
            self.notebook.AddPage(page, title)
            return page

        def _typing_page(self, page: wx.Panel, settings: AppSettings) -> None:
            self.latex_new_documents = self._checkbox(
                page,
                _("Write the equations of new documents and pages in LaTeX"),
                _("Write equations in LaTeX"),
                settings.latex_new_documents,
            )
            self.convert_on_space = self._checkbox(
                page,
                _("Convert control words (for example \\alpha) when Space or punctuation is typed"),
                _("Convert control words while typing"),
                settings.convert_on_space,
            )
            self.complete_control_words = self._checkbox(
                page,
                _("Suggest control words while one is typed (Up/Down browse, Tab completes)"),
                _("Suggest control words while typing"),
                settings.complete_control_words,
            )
            self.convert_shortcuts_immediately = self._checkbox(
                page,
                _(
                    "Convert symbol shortcuts (for example << or ->) as soon as they are typed, in equations and the document"
                ),
                _("Convert symbol shortcuts immediately"),
                settings.convert_shortcuts_immediately,
            )
            self.autocorrect_button = wx.Button(page, label=_("Math &AutoCorrect…"))
            self.autocorrect_button.Bind(wx.EVT_BUTTON, lambda _event: self._edit_autocorrect())
            page.GetSizer().Add(self.autocorrect_button, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
            self._help(
                page,
                _(
                    "Math AutoCorrect is one list, as in Word: the converter's control words, "
                    "Mathessible's shortcuts and your own entries, each one can be changed or deleted."
                ),
            )
            self.removed_words_as_symbols = self._checkbox(
                page,
                _(
                    "Deleted AutoCorrect control words still show as their symbol (off: they stay the text typed, as in Word)"
                ),
                _("Deleted AutoCorrect control words still show as their symbol"),
                settings.removed_words_as_symbols,
            )
            self.autocorrect_in_text = self._checkbox(
                page,
                _("Use Math AutoCorrect in an equation's normal text (control words and shortcuts convert there too)"),
                _("Use Math AutoCorrect in an equation's normal text"),
                settings.autocorrect_in_text,
            )
            self.autocorrect_in_document = self._checkbox(
                page,
                _(
                    "Use Math AutoCorrect in the document too, text and equations alike (as Word's rule outside math regions)"
                ),
                _("Use Math AutoCorrect in the document"),
                settings.autocorrect_in_document,
            )
            self.template_control_words = self._checkbox(
                page,
                _("Insert templates as control words (for example \\sum and \\sqrt instead of ∑ and √)"),
                _("Insert templates as control words"),
                settings.template_control_words,
            )
            self.decimal_comma = self._checkbox(
                page,
                _(
                    "Decimal comma: 1,5 is a number and a set is written {1, 2, 3}; "
                    "off: decimal point (3.14), and {1,2,3} is a set"
                ),
                _("Decimal comma"),
                settings.decimal_separator == ",",
            )
            self.remove_extra_spaces = self._checkbox(
                page,
                _("Remove spaces that change nothing when saving the equation or switching to linear view"),
                _("Remove extra spaces"),
                settings.remove_extra_spaces,
            )

        def _building_page(self, page: wx.Panel, settings: AppSettings) -> None:
            self.build_as_you_type = self._checkbox(
                page,
                _("Build equations as you type (on Space or an operator, what is complete; the rest stays linear)"),
                _("Build equations as you type"),
                settings.build_as_you_type,
            )
            self.announce_built = self._checkbox(
                page,
                _("Say what was built while typing (for example, built fraction)"),
                _("Say what was built"),
                settings.announce_built,
            )
            self.open_built = self._checkbox(
                page,
                _("Open equations built (professional view), ready to navigate and type into"),
                _("Open equations built"),
                settings.open_built,
            )
            self.argument_on_closing_paren = self._checkbox(
                page,
                _("Open a function's argument as soon as its parenthesis is closed (instead of on Space)"),
                _("Open the argument on the closing parenthesis"),
                settings.argument_on_closing_paren,
            )
            self.functions_button = wx.Button(page, label=_("&Recognized Functions…"))
            self.functions_button.Bind(wx.EVT_BUTTON, lambda _event: self._edit_functions())
            page.GetSizer().Add(self.functions_button, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
            self._help(
                page,
                _(
                    "Space after a recognized function (sin, log, lim…) opens its argument, "
                    "and it is navigated as function name and argument, as in Word."
                ),
            )

        def _navigation_page(self, page: wx.Panel, settings: AppSettings) -> None:
            self.linear_navigation = self._checkbox(
                page,
                _("Use linear navigation in exploration mode (F10; writing mode is always linear)"),
                _("Linear navigation in exploration mode"),
                settings.linear_navigation,
            )
            self.structure_stops = self._checkbox(
                page,
                _(
                    'Stop at the start and end of every structure (for example "start fraction", '
                    '"end numerator") and of the math'
                ),
                _("Stop at structure start and end"),
                settings.structure_stops,
            )
            self.invisible_operator_stops = self._checkbox(
                page,
                _("Stop at invisible operators (for example the invisible times in 3x)"),
                _("Stop at invisible operators"),
                settings.invisible_operator_stops,
            )
            self.auto_zoom_out = self._checkbox(
                page,
                _("Leave a structure automatically at its end (for example, from the numerator to the denominator)"),
                _("Leave structures automatically"),
                settings.auto_zoom_out,
            )
            self._help(
                page,
                _(
                    "When enabled, the right arrow enters structures such as fractions "
                    "automatically, so you can read more of an expression without pressing Down."
                ),
            )

        def _speech_page(self, page: wx.Panel, settings: AppSettings) -> None:
            label = wx.StaticText(page, label=_("&Symbol dictionary (names spoken for symbols while typing)"))
            self.symbol_dictionary = wx.Choice(page)
            self.symbol_dictionary.SetName(_("Symbol dictionary"))
            self._fill_dictionaries(settings.symbol_dictionary)
            self.symbol_dictionary.Bind(wx.EVT_CHOICE, lambda _event: self._changed())
            import_button = wx.Button(page, label=_("&Import dictionary…"))
            import_button.Bind(wx.EVT_BUTTON, self._on_import_dictionary)
            download_button = wx.Button(page, label=_("&Download NVDA dictionaries…"))
            download_button.Bind(wx.EVT_BUTTON, self._on_download_dictionaries)
            row = wx.BoxSizer(wx.HORIZONTAL)
            row.Add(self.symbol_dictionary, 1, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 8)
            row.Add(import_button, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 8)
            row.Add(download_button, 0, wx.ALIGN_CENTER_VERTICAL)
            page.GetSizer().Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
            page.GetSizer().Add(row, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)
            self._help(
                page,
                _(
                    "Any file in NVDA's symbols.dic format can be imported. NVDA's own dictionaries "
                    "are downloaded from the NVDA project on GitHub. The built equation is always read by MathCAT."
                ),
            )
            self.name_unknown_symbols = self._checkbox(
                page,
                _("Say symbols MathCAT does not know by their Unicode name (for example, alchemical symbol for air)"),
                _("Name unknown symbols"),
                settings.name_unknown_symbols,
            )

        def _braille_page(self, page: wx.Panel, settings: AppSettings) -> None:
            label = wx.StaticText(page, label=_("&Braille code (the braille strip under the equation)"))
            self.braille_code = wx.Choice(page, choices=[_(label) for _code, label in BRAILLE_CODES])
            self.braille_code.SetName(_("Braille code"))
            codes = [code for code, _label in BRAILLE_CODES]
            self.braille_code.SetSelection(codes.index(settings.braille_code) if settings.braille_code in codes else 0)
            self.braille_code.Bind(wx.EVT_CHOICE, lambda _event: self._changed())
            self.braille_signs_button = wx.Button(page, label=_("Braille si&gns…"))
            self.braille_signs_button.Bind(wx.EVT_BUTTON, lambda _event: self._edit_braille_signs())
            page.GetSizer().Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
            page.GetSizer().Add(self.braille_code, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)
            page.GetSizer().Add(self.braille_signs_button, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
            self._help(
                page,
                _(
                    "Braille signs are your own braille for symbols in the code chosen above, "
                    "for symbols it has no sign for, or to replace its own."
                ),
            )
            heading = wx.StaticText(page, label=_("BRF export (its dialog can change them for one file)"))
            page.GetSizer().Add(heading, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
            rows = FormRows(page, self._changed)
            self.brf = BrfControls(rows, settings)
            rows.finish(page.GetSizer())

        def _docx_page(self, page: wx.Panel, settings: AppSettings) -> None:
            """The Word export's defaults; each export can change them (File > Export > Word Document)."""
            rows = FormRows(page, self._changed)
            self.docx = DocxControls(rows, settings)
            rows.finish(page.GetSizer())

        def _html_page(self, page: wx.Panel, settings: AppSettings) -> None:
            """The HTML export's defaults; each export can change them (File > Export > HTML)."""
            rows = FormRows(page, self._changed)
            self.html = HtmlControls(rows, settings)
            rows.finish(page.GetSizer())

        def _language_page(self, page: wx.Panel, settings: AppSettings) -> None:
            """The interface's language (after a restart) and the speech of equations (at once)."""
            rows = FormRows(page, self._changed)
            interface = (("", _("The system's")), *LANGUAGES)
            self.interface_language = rows.row(
                _("&Interface"), rows.choice(interface, settings.interface_language), _("Interface language")
            )
            speech = (("", _("The interface's")), *LANGUAGES)
            self.speech_language = rows.row(
                _("&Speech of equations"), rows.choice(speech, settings.speech_language), _("Speech language")
            )
            rows.finish(page.GetSizer())
            self._help(
                page,
                _(
                    "The interface changes when Mathessible starts again; the speech of equations at once. "
                    "These are MathCAT's languages. Translations other than English are drafts that a native "
                    "speaker has yet to review."
                ),
            )

        def _pdf_page(self, page: wx.Panel, settings: AppSettings) -> None:
            """The PDF export's defaults; each export can change them (File > Export > PDF)."""
            rows = FormRows(page, self._changed)
            self.pdf_layout = PdfLayoutControls(rows, settings)
            self.pdf_content = PdfContentControls(rows, settings)
            self.pdf_standard = PdfStandardControl(rows, settings)
            self.pdf_author = rows.row(_("Default &author"), rows.text(settings.pdf_author), _("Default author"))
            rows.finish(page.GetSizer())
            self._help(
                page,
                _(
                    "These are the defaults for every PDF; the export's dialog can change them for one PDF, "
                    "and holds the title, watermark and passwords, which are never kept."
                ),
            )

        # Controls

        def _checkbox(self, page: wx.Panel, label: str, name: str, value: bool) -> wx.CheckBox:
            """A checkbox for one setting: its label, the name screen readers announce, its value."""
            checkbox = wx.CheckBox(page, label=label)
            checkbox.SetName(name)
            checkbox.SetValue(value)
            checkbox.Bind(wx.EVT_CHECKBOX, lambda _event: self._changed())
            page.GetSizer().Add(checkbox, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
            return checkbox

        def _help(self, page: wx.Panel, text: str) -> None:
            label = wx.StaticText(page, label=text)
            label.Wrap(_WRAP)
            page.GetSizer().Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)

        def _changed(self) -> None:
            if self._on_change is not None:
                self._on_change()

        # Applying

        def apply(self) -> None:
            selection = self.symbol_dictionary.GetSelection()
            if selection != wx.NOT_FOUND:
                self._settings.symbol_dictionary = self._dictionaries[selection].identifier
            self._apply_pdf()
            interface = (("", ""), *LANGUAGES)
            index = self.interface_language.GetSelection()
            if index != wx.NOT_FOUND:
                self._settings.interface_language = interface[index][0]
            index = self.speech_language.GetSelection()
            if index != wx.NOT_FOUND:
                self._settings.speech_language = interface[index][0]
            self.brf.store(self._settings)
            self.html.store(self._settings)
            self.docx.store(self._settings)
            braille = self.braille_code.GetSelection()
            if braille != wx.NOT_FOUND:
                self._settings.braille_code = BRAILLE_CODES[braille][0]
            for code, signs in self._braille_signs.items():
                save_signs(code, signs)
            self._braille_signs.clear()
            self._settings.linear_navigation = self.linear_navigation.GetValue()
            self._settings.structure_stops = self.structure_stops.GetValue()
            self._settings.invisible_operator_stops = self.invisible_operator_stops.GetValue()
            self._settings.convert_on_space = self.convert_on_space.GetValue()
            self._settings.latex_new_documents = self.latex_new_documents.GetValue()
            self._settings.complete_control_words = self.complete_control_words.GetValue()
            self._settings.decimal_separator = "," if self.decimal_comma.GetValue() else "."
            self._settings.convert_shortcuts_immediately = self.convert_shortcuts_immediately.GetValue()
            self._settings.open_built = self.open_built.GetValue()
            self._settings.build_as_you_type = self.build_as_you_type.GetValue()
            self._settings.announce_built = self.announce_built.GetValue()
            self._settings.autocorrect_in_text = self.autocorrect_in_text.GetValue()
            self._settings.autocorrect_in_document = self.autocorrect_in_document.GetValue()
            self._settings.name_unknown_symbols = self.name_unknown_symbols.GetValue()
            self._settings.remove_extra_spaces = self.remove_extra_spaces.GetValue()
            self._settings.argument_on_closing_paren = self.argument_on_closing_paren.GetValue()
            self._settings.template_control_words = self.template_control_words.GetValue()
            self._settings.auto_zoom_out = self.auto_zoom_out.GetValue()
            self._settings.recognized_functions = self._functions
            self._settings.math_autocorrect, self._settings.math_autocorrect_removed = self._autocorrect
            self._settings.removed_words_as_symbols = self.removed_words_as_symbols.GetValue()

        def _apply_pdf(self) -> None:
            self.pdf_layout.store(self._settings)
            self.pdf_content.store(self._settings)
            self.pdf_standard.store(self._settings)
            self._settings.pdf_author = self.pdf_author.GetValue()

        # Lists edited in their own dialogs

        def _edit_braille_signs(self) -> None:
            """Open the user's signs for the braille code chosen; they are saved when the settings apply."""
            index = self.braille_code.GetSelection()
            code, label = BRAILLE_CODES[index if index != wx.NOT_FOUND else 0]
            signs = self._braille_signs.get(code, load_signs(code))
            try:
                words = control_words()
            except (OSError, ValueError):
                words = {}
            dialog = BrailleSignsDialog(self, label, signs, words)
            try:
                if dialog.ShowModal() == wx.ID_OK:
                    self._braille_signs[code] = dialog.signs
                    self._changed()
            finally:
                dialog.Destroy()
            self.braille_signs_button.SetFocus()

        def _edit_functions(self) -> None:
            """Open the recognized functions; the list is kept until the settings apply."""
            dialog = RecognizedFunctionsDialog(self, self._functions)
            try:
                if dialog.ShowModal() == wx.ID_OK:
                    self._functions = tuple(dialog.functions)
                    self._changed()
            finally:
                dialog.Destroy()
            self.functions_button.SetFocus()

        def _edit_autocorrect(self) -> None:
            """Open the Math AutoCorrect list; its differences from the defaults are kept until applied."""
            defaults = autocorrect_defaults()
            table = AutoCorrectTable(defaults, *self._autocorrect)
            dialog = AutoCorrectDialog(self, defaults, table.entries())
            try:
                if dialog.ShowModal() == wx.ID_OK:
                    self._autocorrect = differences(defaults, dialog.entries)
                    self._changed()
            finally:
                dialog.Destroy()
            self.autocorrect_button.SetFocus()

        # Symbol dictionaries

        def _fill_dictionaries(self, selected: str) -> None:
            self._dictionaries = available_dictionaries()
            self.symbol_dictionary.Set([info.label for info in self._dictionaries])
            identifiers = [info.identifier for info in self._dictionaries]
            self.symbol_dictionary.SetSelection(identifiers.index(selected) if selected in identifiers else 0)

        def _on_import_dictionary(self, _event: wx.CommandEvent) -> None:
            with wx.FileDialog(
                self,
                _("Import a symbol dictionary"),
                wildcard=_("NVDA symbol dictionaries") + " (*.dic)|*.dic|" + _("All files") + "|*",
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
            ) as dialog:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                path = Path(dialog.GetPath())
            try:
                info = import_dictionary(path)
            except (SymbolDictionaryError, OSError) as error:
                wx.MessageBox(str(error), _("Import failed"), wx.OK | wx.ICON_ERROR, self)
                return
            self._fill_dictionaries(info.identifier)
            self._changed()
            self.symbol_dictionary.SetFocus()

        def _on_download_dictionaries(self, _event: wx.CommandEvent) -> None:
            self._in_background(_("Listing NVDA's languages…"), nvda_languages, self._choose_languages)

        def _choose_languages(self, languages: list[str]) -> None:
            with wx.MultiChoiceDialog(
                self,
                _("Choose the languages to download (Space checks one)."),
                _("Download NVDA dictionaries"),
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
                ngettext("Downloading {count} dictionary…", "Downloading {count} dictionaries…", len(chosen)).format(
                    count=len(chosen)
                ),
                lambda: download_languages(chosen),
                self._downloaded,
            )

        def _downloaded(self, report) -> None:
            selected = self._dictionaries[max(0, self.symbol_dictionary.GetSelection())].identifier
            if report.saved:
                # Select the first one fetched; a language NVDA has no file for is reported.
                selected = report.saved[0].stem
            self._fill_dictionaries(selected)
            self._changed()
            count = len(report.saved)
            message = ngettext("{count} dictionary downloaded.", "{count} dictionaries downloaded.", count).format(
                count=count
            )
            if report.missing:
                message += " " + _("NVDA has no symbol dictionary for: {languages}.").format(
                    languages=", ".join(report.missing)
                )
            wx.MessageBox(message, _("Download NVDA dictionaries"), wx.OK | wx.ICON_INFORMATION, self)
            self.symbol_dictionary.SetFocus()

        def _in_background(self, message: str, job: Callable[[], object], done: Callable[[object], None]) -> None:
            """Run a network job off the UI thread behind a pulsing progress dialog."""
            progress = wx.ProgressDialog(_("Download NVDA dictionaries"), message, parent=self, style=wx.PD_APP_MODAL)
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
                        _("The download failed: {error}").format(error=outcome["error"]),
                        _("Download NVDA dictionaries"),
                        wx.OK | wx.ICON_ERROR,
                        self,
                    )
                    return
                done(outcome["result"])

            wx.CallLater(150, poll)

    class SettingsWindow(wx.Frame):
        """macOS: Settings as a window, as Mac apps have; every change applies and is saved at once.

        `on_apply` saves the settings and tells the open windows. Escape or
        Command+W hides it, kept for next time (`show_settings`); it belongs
        to the window it was opened from, so a hidden one never keeps the
        app open after the last document window closes.
        """

        def __init__(self, parent: wx.Window, settings: AppSettings, on_apply: Callable[[], None]):
            super().__init__(parent, title=_("Settings"), style=wx.DEFAULT_FRAME_STYLE & ~wx.MAXIMIZE_BOX)
            self.SetName(_("Settings"))
            self._on_apply = on_apply
            self.panel = SettingsPanel(self, settings, on_change=self._apply)
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(self.panel, 1, wx.EXPAND)
            self.SetSizerAndFit(sizer)
            close = wx.NewIdRef()
            self.Bind(wx.EVT_MENU, lambda _event: self.Close(), id=close)
            self.SetAcceleratorTable(wx.AcceleratorTable([(wx.ACCEL_CMD, ord("W"), close)]))
            self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
            self.Bind(wx.EVT_CLOSE, self._on_close)

        def _apply(self) -> None:
            self.panel.apply()
            self._on_apply()

        def _on_char_hook(self, event: wx.KeyEvent) -> None:
            if event.GetKeyCode() == wx.WXK_ESCAPE:
                self.Close()
                return
            event.Skip()

        def _on_close(self, event: wx.CloseEvent) -> None:
            if not event.CanVeto():
                event.Skip()  # The app is quitting.
                return
            self.Hide()
            event.Veto()  # Kept for next time, where the user left it.

    class SettingsDialog(wx.Dialog):
        """Windows and Linux: Settings as a dialog with OK, Cancel and Apply.

        Apply (and OK) apply the panel and call `on_apply`, which saves and
        tells the open windows; Cancel keeps what was last applied.
        """

        def __init__(self, parent: wx.Window, settings: AppSettings, on_apply: Callable[[], None]):
            super().__init__(parent, title=_("Settings"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
            self.SetName(_("Settings dialog"))
            self._on_apply = on_apply
            self.panel = SettingsPanel(self, settings)
            buttons = wx.StdDialogButtonSizer()
            buttons.AddButton(wx.Button(self, wx.ID_OK))
            buttons.AddButton(wx.Button(self, wx.ID_CANCEL))
            buttons.AddButton(wx.Button(self, wx.ID_APPLY))
            buttons.Realize()
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(self.panel, 1, wx.EXPAND)
            sizer.Add(buttons, 0, wx.ALL | wx.EXPAND, 12)
            self.SetSizerAndFit(sizer)
            self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
            self.Bind(wx.EVT_BUTTON, lambda _event: self._apply(), id=wx.ID_APPLY)

        def _apply(self) -> None:
            self.panel.apply()
            self._on_apply()

        def _on_ok(self, event: wx.CommandEvent) -> None:
            self._apply()
            event.Skip()  # Closes the dialog with wx.ID_OK.

    _window: SettingsWindow | None = None

    def forget_settings_window() -> None:
        """The kept Settings window is rebuilt next time: settings changed elsewhere (Save as Defaults)."""
        global _window
        if _window:
            _window.Destroy()
        _window = None

    def show_settings(parent: wx.Window, settings: AppSettings, on_apply: Callable[[], None]) -> None:
        """Settings, as the platform has them: the one window on macOS, a modal dialog elsewhere."""
        global _window
        if applies_at_once():
            if _window is None or not _window:  # Never opened, or gone with the window it belonged to.
                _window = SettingsWindow(parent, settings, on_apply)
                _window.CentreOnScreen()
            _window.Show()
            _window.Raise()
            _window.panel.notebook.SetFocus()
            return
        dialog = SettingsDialog(parent, settings, on_apply)
        try:
            dialog.ShowModal()
        finally:
            dialog.Destroy()

else:

    class SettingsPanel:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")

    SettingsDialog = SettingsWindow = SettingsPanel  # type: ignore[misc,assignment]

    def show_settings(*args: object, **kwargs: object) -> None:  # type: ignore[misc]
        raise RuntimeError("wxPython is not installed. Run: uv sync")

    def forget_settings_window() -> None:  # type: ignore[misc]
        pass
