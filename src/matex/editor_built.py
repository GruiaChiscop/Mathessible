"""Editing and moving in the built equation (professional view): where typing goes,
character and node steps, selection, whole-node edits, rebuilding.
"""

from __future__ import annotations

from collections.abc import Callable

from .build_repair import BuildRepair
from .character_speech import character_name
from .clipboard import set_clipboard_text
from .editor_keys import word_navigation_down
from .insertion_point import describe_insertion_point, node_name
from .math_templates import move_to_slot
from .node_edits import removal
from .source_map import anchor_offset, inside_leaf, leaf_before, leaf_characters, leaf_nodes, map_leaves
from .unicodemath import UnicodeMathError, mathml_has_parse_error

try:
    import wx
except ImportError:  # The interface is an optional dependency.
    wx = None


class BuiltEditingMixin:
    """Methods of `EquationEditor` (editor.py); relies on its state."""

    def _read_character(self, character: str) -> str:
        """One character as MathCAT reads it alone: reading the built equation is MathCAT's, not the dictionary's."""
        if self.mathcat is None:
            return character_name(character, self.symbols)
        return self.mathcat.character_speech(character)

    def _current_node(self):
        """MathCAT's node in professional view, unless it is the math itself."""
        structure = self.mathcat.structure if self.mathcat is not None else None
        if self.mode != "professional" or structure is None:
            return None
        node = structure.node(self.mathcat.current_id)
        return None if node is None or node is structure.root else node

    def _node_label(self, node) -> str:
        """How a node is named when copied, cut or deleted: by its role if it fills one ("the numerator")."""
        role = self.mathcat.structure.semantic_role(node.identifier) if node.children else None
        return f"the {role}" if role else node_name(node, self._read_character)

    def _node_removal(self, node_id: str) -> tuple[int, int, str]:
        """(start, end, replacement) in real-source terms for removing a built node."""
        repair = self._built_repair()
        span, replacement = removal(repair.text, self.mathcat.structure, node_id)
        return repair.to_real(span.start), repair.to_real(span.end), replacement

    def _removes_whole_structure(self) -> bool:
        """Backspace/Delete on a whole structure: the first press asks, the second deletes.

        On a single character (the usual case in flat reading) it is not
        handled here and deletes that character, as in linear view.
        """
        node = self._current_node()
        if node is None or not node.children:
            return False
        name = self._node_label(node)
        if self._armed_removal != node.identifier:
            self._armed_removal = node.identifier
            self._announce(f"{name}, press again to delete it")
            return True
        self._armed_removal = None
        self._remove_node(node.identifier, f"deleted {name}")
        return True

    def _remove_node(self, node_id: str, announcement: str) -> None:
        start, end, replacement = self._node_removal(node_id)
        source = self.document.source
        caret = start + (1 if replacement else 0)
        self._clear_selection()
        self._replace_linear(source[:start] + replacement + source[end:], caret)
        self._finish_built_edit(announcement)

    def _cut_node(self) -> None:
        if self._built_selection() is not None:
            self._edit_in_built(self._cut_equation)
            return
        node = self._current_node()
        if node is None:
            self._cut_equation()
            return
        start, end, _replacement = self._node_removal(node.identifier)
        if not set_clipboard_text(self.document.source[start:end]):
            self._announce("could not cut")
            return
        self._remove_node(node.identifier, f"cut {self._node_label(node)}")

    def _types_into_built_equation(self, event: wx.KeyEvent, key: int) -> bool:
        """A key that types a character into the built equation (not a shortcut or navigation)."""
        if self.mathcat is None or event.CmdDown() or event.RawControlDown() or key == wx.WXK_SPACE:
            return False
        return 32 < key < 127 or event.GetUnicodeKey() > 127

    def _edit_built_equation(self, event: wx.KeyEvent) -> None:
        """Type, Backspace or Delete in professional mode, as if in the source.

        The key is handled exactly as in linear mode (autocorrect,
        history, speech) at MathCAT's position; see `_edit_in_built`.
        """
        def handle_key() -> None:
            self._on_char(event)  # Announces the character itself.

        typed = chr(event.GetUnicodeKey()) if self._is_typed_character(event) else ""
        # A letter, digit, group or control word glued to a structure joins it.
        self._edit_in_built(handle_key, glue=bool(typed) and (typed.isalnum() or typed in '(\\"'))
        self._typing_streak = True

    def _insertion_point(self) -> str:
        assert self.mathcat is not None
        if self.mathcat.structure is None:
            return "equation"
        if self._built_selection() is not None:
            return self._selection_speech()
        inside = self._current_inside()
        if inside is not None:
            _leaf, count, characters, _mathml = inside
            return f"inside {characters}, after {characters[:count]}, before {characters[count:]}"
        node_id, side, outside = self.mathcat.edit_anchor()
        described = describe_insertion_point(self.mathcat.structure, node_id, side, outside, self._read_character)
        remembered = self._remembered_caret()
        if remembered is not None and self.document.source[remembered - 1 : remembered] == " ":
            return f"after space, {described}"  # A space has no node of its own.
        return described

    def _remembered_caret(self) -> int | None:
        """The caret left by the last professional-view edit, if nothing has moved since."""
        remembered = self._built_caret
        if remembered is None or self.mathcat is None:
            return None
        source, caret, mathml = remembered
        if source != self.document.source or mathml != self.mathcat.mathml:
            self._built_caret = None
            return None
        return caret

    def _current_inside(self) -> tuple[str, int, str, str] | None:
        """The caret between a leaf's characters, if MathCAT is still on that leaf of this equation."""
        inside = self._inside_leaf
        if inside is None or self.mathcat is None:
            return None
        if self.mathcat.mathml != inside[3] or self.mathcat.current_id != inside[0]:
            self._inside_leaf = None
            return None
        return inside

    def _leaf_characters(self, leaf: str | None) -> str | None:
        if leaf is None or self.mathcat is None or self.mathcat.structure is None:
            return None
        repair = self._built_repair()
        spans = map_leaves(repair.text, self.mathcat.structure)
        return leaf_characters(repair.text, spans, self.mathcat.structure, leaf)

    def _mode_arrow(self, event: wx.KeyEvent, key: int) -> bool:
        """The arrows that depend on the mode, in professional view; False for the usual handling.

        Up/Down (writing, or linear exploration) go to the previous/next
        row and read it, as in a text field. In writing mode Left/Right
        move by character, inside "12" too, and Option+Left/Right
        (Ctrl elsewhere) by node.
        """
        assert self.mathcat is not None
        if self.writing_enabled and event.ShiftDown() and not event.CmdDown():
            if key in (wx.WXK_LEFT, wx.WXK_RIGHT):
                self._extend_built_selection(1 if key == wx.WXK_RIGHT else -1, word_navigation_down(event))
                return True
            if key in (wx.WXK_HOME, wx.WXK_END):
                self._extend_built_selection_to(0 if key == wx.WXK_HOME else len(self.document.source))
                return True
        if event.CmdDown() or event.ShiftDown():
            return False
        if key in (wx.WXK_LEFT, wx.WXK_RIGHT) and self._built_selection() is not None:
            self._collapse_built_selection(at_end=key == wx.WXK_RIGHT)
            return True
        if key in (wx.WXK_UP, wx.WXK_DOWN, wx.WXK_LEFT, wx.WXK_RIGHT):
            self._built_caret = None  # Navigating: MathCAT says where typing goes again.
            self._clear_built_selection()
        if key in (wx.WXK_UP, wx.WXK_DOWN):
            if not self._linear_now:
                return False  # Structural exploration: Up/Down change level.
            self._typing_streak = False
            self._inside_leaf = None
            speech = self.mathcat.read_line(-1 if key == wx.WXK_UP else 1)
        elif key in (wx.WXK_LEFT, wx.WXK_RIGHT) and self.writing_enabled:
            self._typing_streak = False
            step = 1 if key == wx.WXK_RIGHT else -1
            speech = self._node_step(step) if word_navigation_down(event) else self._character_step(step)
        else:
            return False
        self._highlight_matrix_cell = False
        inside = self._inside_leaf
        self._sync_mathcat_cursor()
        self._inside_leaf = inside
        if speech:
            self._announce(speech)
        self.Refresh()
        return True

    def _built_selection(self) -> tuple[int, int] | None:
        """The selection in professional view, as real-source offsets."""
        if self.mode != "professional":
            return None
        return self._selection_range()

    def _clear_built_selection(self) -> None:
        if self.mode == "professional" and (self.selection_anchor is not None or self._selected_ids):
            self.selection_anchor = None
            self._selected_ids = ()

    def _extend_built_selection(self, step: int, by_node: bool) -> None:
        """Shift+Left/Right (Option too: by node) in writing mode: select as in a text field.

        Says what was passed and whether it is now selected or not.
        """
        assert self.mathcat is not None
        before = self.caret if self._built_selection() is not None else self._built_offset()
        anchor = self.selection_anchor if self._built_selection() is not None else before
        self._built_caret = None
        if by_node:
            self._node_step(step)
        else:
            self._character_step(step)
        inside = self._inside_leaf
        self._sync_mathcat_cursor()
        self._inside_leaf = inside
        self._set_built_selection(anchor, self._built_offset(), before)

    def _extend_built_selection_to(self, offset: int) -> None:
        """Shift+Home/End: select to the start/end of the equation."""
        assert self.mathcat is not None
        before = self.caret if self._built_selection() is not None else self._built_offset()
        anchor = self.selection_anchor if self._built_selection() is not None else before
        self.caret = offset
        self._place_after_caret()
        self._sync_mathcat_cursor()
        self._set_built_selection(anchor, offset, before)

    def _set_built_selection(self, anchor: int, caret: int, before: int) -> None:
        self.selection_anchor, self.caret = anchor, caret
        passed = self._span_speech(min(before, caret), max(before, caret))
        grew = abs(caret - anchor) > abs(before - anchor)
        self._selected_ids = self._leaves_in(*sorted((anchor, caret)))
        if anchor == caret:
            self.selection_anchor = None
            self._announce(f"{passed}, unselected" if passed else "selection cleared")
        elif passed:
            self._announce(f"{passed}, {'selected' if grew else 'unselected'}")
        else:
            self._announce(self._selection_speech())
        self.Refresh()

    def _collapse_built_selection(self, at_end: bool) -> None:
        """Left/Right with a selection: to its start/end, as in a text field."""
        selection = self._built_selection()
        assert selection is not None
        self.caret = selection[1] if at_end else selection[0]
        self._clear_built_selection()
        self._place_after_caret()
        self._sync_mathcat_cursor()
        self._announce(self._insertion_point())
        self.Refresh()

    def _select_all_built(self) -> None:
        """Cmd+A in professional view's writing mode: the whole equation."""
        source = self.document.source
        if not source:
            self._announce("nothing to select")
            return
        self.selection_anchor, self.caret = 0, len(source)
        self._selected_ids = self._leaves_in(0, len(source))
        self._announce(f"selected {self._span_speech(0, len(source))}")
        self.Refresh()

    def _selection_speech(self) -> str:
        selection = self._built_selection()
        return f"selected {self._span_speech(*selection)}" if selection else "nothing selected"

    def _leaves_in(self, start: int, end: int) -> tuple[str, ...]:
        """The leaves with characters between two real-source offsets."""
        if self.mathcat is None or self.mathcat.structure is None or start >= end:
            return ()
        repair = self._built_repair()
        spans = map_leaves(repair.text, self.mathcat.structure)
        low, high = repair.to_repaired(start), repair.to_repaired(end)
        return tuple(
            leaf.identifier
            for leaf in leaf_nodes(self.mathcat.structure)
            if leaf.identifier in spans
            and spans[leaf.identifier].start < high
            and spans[leaf.identifier].end > low
        )

    def _span_speech(self, start: int, end: int) -> str:
        """A source span read leaf by leaf ("x plus 1"); part of a leaf ("12" of "4123") by its characters."""
        if self.mathcat is None or self.mathcat.structure is None or start >= end:
            return ""
        repair = self._built_repair()
        spans = map_leaves(repair.text, self.mathcat.structure)
        low, high = repair.to_repaired(start), repair.to_repaired(end)
        words: list[str] = []
        for leaf in leaf_nodes(self.mathcat.structure):
            span = spans.get(leaf.identifier or "")
            if span is None or span.start >= span.end or span.start >= high or span.end <= low:
                continue
            if span.start >= low and span.end <= high:
                words.append(self.mathcat.leaf_speech(leaf.identifier) or self._read_character(leaf.text))
            else:
                part = repair.text[max(span.start, low) : min(span.end, high)]
                words.extend(self._read_character(character) for character in part)
        if not words:
            # Only what has no node of its own: spaces, a fraction's parens.
            words = [self._read_character(character) for character in self.document.source[start:end]]
        return " ".join(word for word in words if word)

    def _node_step(self, step: int) -> str:
        """Option/Ctrl+Left/Right in writing mode: a whole node, from inside one too."""
        assert self.mathcat is not None
        inside = self._current_inside()
        self._inside_leaf = None
        if inside is not None and step > 0:
            return self.mathcat.command("ReadCurrent")  # To the end of the leaf: its own stop.
        return self.mathcat.linear_command("MoveNext" if step > 0 else "MovePrevious")

    def _step_back(self) -> str:
        """The stop before; landing after "12" reads its last character, as the caret is right after it."""
        assert self.mathcat is not None
        speech = self.mathcat.linear_command("MovePrevious")
        characters = self._leaf_characters(self.mathcat.plain_leaf_stop())
        return self._read_character(characters[-1]) if characters else speech

    def _character_step(self, step: int) -> str:
        """Left/Right in writing mode: one character, reading the one before the caret.

        A one-character leaf is a stop as before; through a longer one
        ("4345", "sin") the caret goes character by character, MathCAT
        staying on the leaf's own stop (after it).
        """
        assert self.mathcat is not None
        inside = self._current_inside()
        self._inside_leaf = None
        if inside is not None:
            leaf, count, characters, mathml = inside
            count += step
            if 0 < count < len(characters):
                self._inside_leaf = (leaf, count, characters, mathml)
                return self._read_character(characters[count - 1])
            if count == len(characters):
                return self._read_character(characters[-1])
            return self._step_back()  # Before the leaf: the stop before it.
        if step < 0:
            leaf = self.mathcat.plain_leaf_stop()
            characters = self._leaf_characters(leaf)
            if leaf is not None and characters:
                self._inside_leaf = (leaf, len(characters) - 1, characters, self.mathcat.mathml)
                return self._read_character(characters[-2])
            return self._step_back()
        speech = self.mathcat.linear_command("MoveNext")
        leaf = self.mathcat.plain_leaf_stop()
        characters = self._leaf_characters(leaf)
        if leaf is not None and characters:
            self._inside_leaf = (leaf, 1, characters, self.mathcat.mathml)
            return self._read_character(characters[0])
        return speech

    def _build_as_you_type(self, announcement: str = "built") -> None:
        """Word's autobuild: build the equation once its source converts with no error.

        Called after Space or a closing bracket in linear view. An incomplete
        source ("a/") stays linear; typing goes on in professional view.
        """
        source = self.document.source
        if (
            not self.settings.build_as_you_type
            or self._editing_built
            or self.mode != "linear"
            or self.mathcat is None
            or not source.strip()
            or self._converting
        ):
            return
        try:
            mathml = self.convert_unicode_math(source)
        except (UnicodeMathError, RuntimeError):
            return
        if mathml_has_parse_error(mathml):
            return
        self._clear_selection()
        self.mode = "professional"
        self._typing_streak = True
        self._update_braille_display()
        self._rebuild_professional_at_caret(announcement, place=self._place_after_caret)

    def _built_offset(self, glue: bool = False) -> int:
        """The source offset of MathCAT's position (`edit_anchor`, `source_map`).

        With `glue` (something that would join an operand is about to be
        typed) at the outer edge of a structure, a space is put between:
        UnicodeMath joins `(1)/(2)x` into the denominator and `x(1)/(2)`
        into the numerator, while `(1)/(2) x` and `x (1)/(2)` stay apart.
        """
        assert self.mathcat is not None and self.mathcat.structure is not None
        source = self.document.source
        repair = self._built_repair()
        inside = self._current_inside()
        if inside is not None:
            # Between a leaf's characters ("4|2"): never at a structure's edge.
            span = map_leaves(repair.text, self.mathcat.structure).get(inside[0])
            if span is not None:
                return repair.to_real(span.start + inside[1])
        node_id, side, outside = self.mathcat.edit_anchor()
        offset = repair.to_real(anchor_offset(repair.text, self.mathcat.structure, node_id, side, outside))
        remembered = self._remembered_caret()
        if remembered is not None and remembered != offset:
            return remembered  # Right after "x ": past the space MathCAT has no node for.
        if not (glue and outside and self._joins_structure(node_id, side)):
            return offset
        if side == "after" and 0 < offset and source[offset - 1] != " ":
            self.document.replace_source(source[:offset] + " " + source[offset:], offset + 1)
            return offset + 1
        if side == "before" and offset < len(source) and source[offset] != " ":
            self.document.replace_source(source[:offset] + " " + source[offset:], offset)
        return offset

    def _built_repair(self) -> BuildRepair:
        """The text the built equation came from, if it is still this source's."""
        source = self.document.source
        return self._repair if self._repair.source == source else BuildRepair(source, source)

    def _joins_structure(self, node_id: str, side: str) -> bool:
        """Whether typing next to this edge would run into a structure (a whole one, or the math's first/last)."""
        structure = self.mathcat.structure if self.mathcat is not None else None
        if structure is None:
            return False
        node = structure.node(node_id)
        if node is not structure.root:
            return True
        leaves = [leaf for leaf in leaf_nodes(structure) if leaf.text not in "\u2061\u2062\u2063\u2064"]
        if not leaves:
            return False
        edge = leaves[-1] if side == "after" else leaves[0]
        return bool(structure.region_entries(edge.identifier or ""))

    def _edit_in_built(self, action: Callable[[], str | None], glue: bool = False) -> None:
        """Run a linear-mode edit at MathCAT's position, then rebuild the equation.

        `action` runs in linear mode with the caret on that offset and may
        announce on its own or return what to announce after rebuilding.
        """
        source = self.document.source
        if self._built_selection() is None:
            self._clear_selection()
            self.caret = self._built_offset(glue)
        # Else the linear handling replaces the selection (typing, Backspace, paste, cut).
        self._selected_ids = ()
        self.mode = "linear"
        self._editing_built = True
        try:
            announcement = action() or ""
        finally:
            self._editing_built = False
        if self.document.source == source:
            self.mode = "professional"
            if announcement:
                self._announce(announcement)
            self.Refresh()
            return
        self._finish_built_edit(announcement)

    def _finish_built_edit(self, announcement: str) -> None:
        """Rebuild after an edit made from professional mode, MathCAT on the caret's node.

        A source that converts only to a total failure (a bare "∫▒") stays
        in linear view; partial errors ("a/") stay built.
        """
        if not self.document.source.strip():
            self.mode = "linear"
            self._update_braille_display()
            self._announce(f"{announcement}, empty, linear mode" if announcement else "empty, linear mode")
            self.Refresh()
            return
        try:
            mathml = self._convert_source().mathml
        except (UnicodeMathError, RuntimeError):
            mathml = 'mathcolor="#F00"'
        if 'mathcolor="#F00"' in mathml:
            # Not even a repair builds (an extra ")"): keep typing in linear view.
            self.mode = "linear"
            self._update_braille_display()
            summary = self._errors_summary(total_failure=True)
            self._announce(f"{announcement}, linear mode, {summary}" if announcement else f"linear mode, {summary}")
            self.Refresh()
            return
        self.mode = "professional"
        self._update_braille_display()
        self._rebuild_professional_at_caret(announcement, place=self._place_after_caret)

    def _built_slot(self, reverse: bool) -> None:
        """Tab/Shift+Tab in professional mode: the next template slot, no rebuild needed."""
        self.caret = self._built_offset()
        edit = self._edit(lambda source, caret: move_to_slot(source, caret, reverse, self.settings.recognized_functions))
        if edit is None:
            self._announce("no slot")
            return
        self.caret = edit.caret
        self._place_after_caret()
        self._sync_mathcat_cursor()
        self._announce(edit.announcement)
        self.Refresh()

    def _built_history(self, action: str) -> None:
        """Undo/redo from professional mode: restore the source, then rebuild there."""
        state = self.history.undo() if action == "undo" else self.history.redo()
        if state is None:
            self._announce(f"nothing to {action}")
            return
        self.document.replace_source(state.source, state.caret)
        self.caret = state.caret
        self._finish_built_edit(action)

    def _place_after_caret(self) -> None:
        """Put MathCAT on the leaf holding the character before the caret (the start of the math at 0)."""
        assert self.mathcat is not None and self.mathcat.structure is not None
        self._highlight_matrix_cell = False
        repair = self._built_repair()
        spans = map_leaves(repair.text, self.mathcat.structure)
        caret = repair.to_repaired(self.caret)
        leaf = leaf_before(spans, caret, self.mathcat.structure)
        self._inside_leaf = None
        self._built_caret = (self.document.source, self.caret, self.mathcat.mathml)
        if leaf is None:
            self.mathcat.command("ZoomIn")
            return
        self.mathcat.move_to(leaf)
        found = inside_leaf(spans, caret)
        characters = leaf_characters(repair.text, spans, self.mathcat.structure, leaf)
        if found is not None and found[0] == leaf and characters:
            # Typed into the middle of "12": the caret stays between its characters.
            self._inside_leaf = (leaf, found[1], characters, self.mathcat.mathml)
