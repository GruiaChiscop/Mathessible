"""Typing aids of the equation editor: control-word completion, symbol search,
and the error list (F8).
"""

from __future__ import annotations

from . import session_log
from .character_speech import character_name
from .completion import Completion, accept_completion, completion_at, symbol_insertion
from .editor_keys import converter_control_words
from .equation_errors import EquationError, find_errors
from .insert_catalog import InsertItem
from .space_conversion import FALLBACK_CONTROL_WORDS
from .unicodemath import UnicodeMathError, code_point_index

try:
    import wx
except ImportError:  # The interface is an optional dependency.
    wx = None


class EditorAssistMixin:
    """Methods of `EquationEditor` (editor.py); relies on its state."""

    def _offer_completion(self, announcement: str) -> str:
        """`announcement`, plus the first suggestion when a control word is being typed (`\\al`)."""
        self._completion = None
        if not self.settings.complete_control_words or self._selection_range() is not None:
            return announcement
        table = converter_control_words() or FALLBACK_CONTROL_WORDS
        completion = completion_at(self.document.source, self.caret, table)
        if completion is None:
            return announcement
        self._completion = (completion, self.document.source)
        return f"{announcement}, {completion.speech(self.symbols.name)}"

    def _current_completion(self) -> Completion | None:
        """The suggestions, if still for this source (and, in linear view, this caret)."""
        if self._completion is None:
            return None
        completion, source = self._completion
        if source != self.document.source or (self.mode == "linear" and self.caret != completion.end):
            self._completion = None
            return None
        return completion

    def _completion_key(self, event: wx.KeyEvent, key: int) -> bool:
        """Up/Down browse the suggestions, Tab takes one; any other key drops them."""
        completion = self._current_completion()
        self._completion = None
        if completion is None or event.ShiftDown() or event.CmdDown() or event.AltDown() or event.RawControlDown():
            return False
        if key in (wx.WXK_DOWN, wx.WXK_UP):
            completion = completion.moved(1 if key == wx.WXK_DOWN else -1)
            self._completion = (completion, self.document.source)
            self._announce(completion.speech(self.symbols.name))
            self.Refresh()
            return True
        if key == wx.WXK_TAB:
            self._accept_completion(completion)
            return True
        return False

    def dismiss_completion(self) -> bool:
        """Escape: close the suggestions (True), so it does not cancel the equation as well."""
        if self._current_completion() is None:
            return False
        self._completion = None
        self._announce("suggestions closed")
        self.Refresh()
        return True

    def _accept_completion(self, completion: Completion) -> None:
        """Tab on a suggestion: the word becomes it (its symbol, when control words convert)."""
        convert = self.settings.convert_on_space
        spoken = completion.current.speech(self.symbols.name)

        def apply() -> str:
            edit = accept_completion(self.document.source, completion, convert)
            self._replace_linear(edit.source, edit.caret)
            return spoken

        if self.mode == "professional" and self.mathcat is not None and self.mathcat.structure is not None:
            self._edit_in_built(apply)
            self._typing_streak = True
            return
        apply()
        self._announce(spoken)
        if convert:
            self._build_as_you_type(f"{spoken}, built")

    def _insert_symbol(self) -> str | None:
        """Insert > Symbol: search control words and symbols by name, insert the chosen one."""
        from .symbol_dialog import SymbolDialog

        if self.mode != "linear":
            return None
        table = converter_control_words() or FALLBACK_CONTROL_WORDS
        dialog = SymbolDialog(self, table, self.symbols.name, self._announce, self._last_symbol_query)
        try:
            chosen = dialog.ShowModal() == wx.ID_OK
            self._last_symbol_query = dialog.query
            suggestion = dialog.selected if chosen else None
        finally:
            dialog.Destroy()
        self.SetFocus()
        if suggestion is None:
            return None
        self._clear_selection()
        edit = symbol_insertion(self.document.source, self.caret, suggestion, self.settings.template_control_words)
        self._replace_linear(edit.source, edit.caret)
        return suggestion.speech(self.symbols.name)

    def _choose_from_gallery(self) -> InsertItem | None:
        """Insert > Structure Gallery: pick a structure; the last category and structure are kept."""
        from .gallery_dialog import GalleryDialog

        if self.mode != "linear":
            return None
        category, structure = self._last_gallery
        dialog = GalleryDialog(self, self._announce, self.settings.template_control_words, category, structure)
        try:
            chosen = dialog.ShowModal() == wx.ID_OK
            self._last_gallery = (dialog.category, dialog.structure)
            item = dialog.selected if chosen else None
        finally:
            dialog.Destroy()
        session_log.write("gallery", f"chose {item.label!r}" if item is not None else "cancelled")
        self.SetFocus()
        return item

    def current_errors(self, total_failure: bool | None = None) -> list[EquationError]:
        """The source's errors (equation_errors); `total_failure` None asks the converter."""
        source = self.document.source
        if total_failure is None:
            try:
                total_failure = 'mathcolor="#F00"' in self.convert_unicode_math(source) if source.strip() else False
            except (UnicodeMathError, RuntimeError):
                total_failure = False
        caret = self.caret if self.mode == "linear" else None
        table = converter_control_words() or FALLBACK_CONTROL_WORDS
        stopped: tuple[int, str | None] | None = None
        if total_failure and (self._last_conversion is None or self._last_conversion[0] != source):
            try:
                self.convert_unicode_math(source)
            except (UnicodeMathError, RuntimeError):
                pass
        if total_failure and self._last_conversion is not None and self._last_conversion[0] == source:
            conversion = self._last_conversion[1]
            if conversion.parse_offset is not None:
                stopped = (code_point_index(source, conversion.parse_offset), conversion.parse_found)
        return find_errors(source, total_failure=total_failure, control_words=table, caret=caret, stopped=stopped)

    def _errors_summary(self, total_failure: bool) -> str:
        """"1 error: unclosed parenthesis, F8 lists errors" for a build that failed."""
        errors = self.current_errors(total_failure)
        if not errors:
            return "no errors found"
        count = len(errors)
        return f"{count} error{'' if count == 1 else 's'}: {errors[0].message}, F8 lists errors"

    def show_errors(self) -> None:
        """F8 (Equation > Errors): the error list; Enter goes to the error and selects it."""
        from .error_dialog import ErrorListDialog

        errors = self.current_errors()
        if not errors:
            self._announce("no errors")
            return
        source = self.document.source
        dialog = ErrorListDialog(self, [error.describe(source) for error in errors])
        try:
            chosen = dialog.selected if dialog.ShowModal() == wx.ID_OK else -1
        finally:
            dialog.Destroy()
        self.SetFocus()
        if 0 <= chosen < len(errors):
            self._go_to_error(errors[chosen])

    def _go_to_error(self, error: EquationError) -> None:
        """Select the error's span: in the built equation if it has nodes there, else in the source."""
        start, end = error.start, max(error.end, error.start + 1)
        end = min(end, len(self.document.source))
        if self.mode == "professional" and self.mathcat is not None and self._leaves_in(start, end):
            self._clear_selection()
            self.caret = end
            self._place_after_caret()
            self._sync_mathcat_cursor()
            self.selection_anchor = start
            self._selected_ids = self._leaves_in(start, end)
            self._announce(f"{error.message}, selected {self._span_speech(start, end)}")
            self.Refresh()
            return
        spoken = " ".join(character_name(c, self.symbols) for c in self.document.source[start:end])
        if self.mode != "linear":
            self.mode = "linear"
            self._update_braille_display()
            spoken = f"linear mode, {spoken}"
        self.selection_anchor, self.caret = start, end
        self._announce(f"{error.message}, selected {spoken}")
        self.Refresh()
