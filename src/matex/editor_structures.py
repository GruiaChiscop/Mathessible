"""The equation editor's context menu and the edits it offers on structures (matrices, fractions)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .clipboard import get_clipboard_text
from .fraction_styles import FRACTION_STYLES, built_fractions, fraction_at, restyle_fraction
from .math_templates import NARY_LABELS
from .structure_edits import (
    add_nary_limits,
    add_root_index,
    nary_at,
    nary_operators,
    remove_nary_limits,
    remove_root_index,
    root_at,
    roots,
)
from .insert_catalog import INSERT_GROUPS, InsertItem
from .source_view import edit_in_view, in_view, view_of
from .template_source import TemplateEdit
from .matrix_templates import (
    delete_matrix_column,
    delete_matrix_row,
    insert_matrix_column,
    insert_matrix_row,
    insert_matrix_template,
    matrix_cell_caret,
    matrix_count,
    matrix_position_at,
)
from .matrix_dialog import MatrixDialog
from .mathml_model import MathMLDocument, MathMLNode
from .unicodemath import UnicodeMathError, mathml_has_parse_error

try:
    import wx
except ImportError:  # The interface is an optional dependency.
    wx = None


@dataclass(frozen=True, slots=True)
class _StructureKind:
    """How one kind of structure maps between the source and MathCAT's MathML.

    `offsets` lists the offset of every one the converter builds as a node,
    in reading order; `is_node` recognizes those nodes; `at` is the offset
    of the one around a caret (it may be one with no node). Both take the
    symbol text of a `SourceView`.
    """

    offsets: Callable[[str], list[int]]
    is_node: Callable[[MathMLNode], bool]
    at: Callable[[str, int], int | None]

    # Both work on the source view (control words resolved), in source offsets.
    def source_offsets(self, source: str) -> list[int]:
        view = view_of(source)
        return [view.to_source(offset) for offset in self.offsets(view.text)]

    def source_at(self, source: str, caret: int) -> int | None:
        view = view_of(source)
        offset = self.at(view.text, view.to_view(caret))
        return None if offset is None else view.to_source(offset)


def _offset(found: object, attribute: str) -> int | None:
    return None if found is None else getattr(found, attribute)


_FRACTIONS = _StructureKind(
    offsets=lambda source: [fraction.operator for fraction in built_fractions(source)],
    is_node=lambda node: node.tag == "mfrac",
    at=lambda source, caret: _offset(fraction_at(source, caret), "operator"),
)
_ROOTS = _StructureKind(
    offsets=lambda source: [root.sign for root in roots(source)],
    is_node=lambda node: node.tag in {"msqrt", "mroot"},
    at=lambda source, caret: _offset(root_at(source, caret), "sign"),
)
_NARY_OPERATORS = _StructureKind(
    offsets=lambda source: [nary.symbol for nary in nary_operators(source)],
    is_node=lambda node: node.attributes.get("intent", "").startswith(":nary"),
    at=lambda source, caret: _offset(nary_at(source, caret), "symbol"),
)


def append_insert_items(menu: wx.Menu) -> dict[int, InsertItem]:
    """Fill `menu` with the Insert entries, sections apart; returns them by menu id."""
    mac = wx.Platform == "__WXMAC__"
    entries: dict[int, InsertItem] = {}
    for index, group in enumerate(INSERT_GROUPS):
        if index:
            menu.AppendSeparator()
        for entry in group:
            accelerator = entry.accelerator(mac)
            item = menu.Append(wx.ID_ANY, f"{entry.label}\t{accelerator}" if accelerator else entry.label)
            entries[item.GetId()] = entry
    return entries


class StructureActionsMixin:
    """Methods of `EquationEditor` (editor.py); relies on its state."""

    def _show_context_menu(self, position: wx.Point) -> None:
        menu = wx.Menu()
        if self.mode == "linear":
            has_content = bool(self.document.source)
            cut_item = menu.Append(wx.ID_ANY, "Cu&t\tCtrl+X")
            copy_item = menu.Append(wx.ID_ANY, "&Copy\tCtrl+C")
            paste_item = menu.Append(wx.ID_ANY, "&Paste\tCtrl+V")
            menu.AppendSeparator()
            select_all_item = menu.Append(wx.ID_ANY, "Select &All\tCtrl+A")
            menu.AppendSeparator()
            insert_menu = wx.Menu()
            for item_id, entry in append_insert_items(insert_menu).items():
                self.Bind(wx.EVT_MENU, lambda _e, entry=entry: self.insert_item(entry), id=item_id)
            menu.AppendSubMenu(insert_menu, "&Insert")
            cut_item.Enable(has_content)
            copy_item.Enable(has_content)
            paste_item.Enable(get_clipboard_text() is not None)
            select_all_item.Enable(has_content)
            self.Bind(wx.EVT_MENU, lambda _e: self._cut_equation(), cut_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._copy_equation(), copy_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._paste_equation(), paste_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._select_all(), select_all_item)
        # Row/column edits act on the innermost matrix around the caret
        # (linear) or MathCAT's current cell (professional), so the
        # submenu only exists while one of those is in a matrix.
        caret = self._matrix_caret()
        position_in_matrix = in_view(self.document.source, caret, matrix_position_at) if caret is not None else None
        if position_in_matrix is not None:
            matrix_menu = wx.Menu()
            matrix_actions = [
                ("Insert Row &Above", lambda: self._edit(lambda s, c: insert_matrix_row(s, c, below=False), caret)),
                ("Insert Row &Below", lambda: self._edit(lambda s, c: insert_matrix_row(s, c, below=True), caret)),
                ("Insert Column &Left", lambda: self._edit(lambda s, c: insert_matrix_column(s, c, right=False), caret)),
                ("Insert Column &Right", lambda: self._edit(lambda s, c: insert_matrix_column(s, c, right=True), caret)),
                None,
                ("Delete R&ow", lambda: self._edit(delete_matrix_row, caret)),
                ("Delete C&olumn", lambda: self._edit(delete_matrix_column, caret)),
            ]
            for action in matrix_actions:
                if action is None:
                    matrix_menu.AppendSeparator()
                    continue
                label, build = action
                item = matrix_menu.Append(wx.ID_ANY, label)
                self.Bind(wx.EVT_MENU, lambda _e, build=build: self._apply_matrix_edit(build()), item)
            delete_row, delete_column = matrix_menu.GetMenuItems()[-2:]
            delete_row.Enable(position_in_matrix.rows > 1)
            delete_column.Enable(position_in_matrix.columns > 1)
            menu.AppendSubMenu(matrix_menu, "Matri&x")
        fraction_caret = self._structure_offset(_FRACTIONS)
        if fraction_caret is not None:
            fraction_menu = wx.Menu()
            current_style = in_view(self.document.source, fraction_caret, fraction_at).style
            for style in FRACTION_STYLES:
                item = fraction_menu.AppendRadioItem(wx.ID_ANY, f"&{style.capitalize()}")
                item.Check(style == current_style)
                self.Bind(
                    wx.EVT_MENU,
                    lambda _e, style=style: self._apply_fraction_style(fraction_caret, style),
                    item,
                )
            menu.AppendSubMenu(fraction_menu, "&Fraction")
        root_caret = self._structure_offset(_ROOTS)
        if root_caret is not None:
            has_index = in_view(self.document.source, root_caret, root_at).has_index
            root_menu = wx.Menu()
            add_item = root_menu.Append(wx.ID_ANY, "&Add Index")
            remove_item = root_menu.Append(wx.ID_ANY, "&Remove Index")
            add_item.Enable(not has_index)
            remove_item.Enable(has_index)
            self.Bind(wx.EVT_MENU, lambda _e: self._apply_structure_edit(add_root_index, root_caret, _ROOTS), add_item)
            self.Bind(
                wx.EVT_MENU, lambda _e: self._apply_structure_edit(remove_root_index, root_caret, _ROOTS), remove_item
            )
            menu.AppendSubMenu(root_menu, "&Root")
        nary_caret = self._structure_offset(_NARY_OPERATORS)
        if nary_caret is not None:
            view = view_of(self.document.source)
            nary = nary_at(view.text, view.to_view(nary_caret))
            has_limits = nary.has_limits
            label = NARY_LABELS[view.text[nary.symbol]]
            nary_menu = wx.Menu()
            add_item = nary_menu.Append(wx.ID_ANY, "&Add Limits")
            remove_item = nary_menu.Append(wx.ID_ANY, "&Remove Limits")
            add_item.Enable(not has_limits)
            remove_item.Enable(has_limits)
            self.Bind(
                wx.EVT_MENU, lambda _e: self._apply_structure_edit(add_nary_limits, nary_caret, _NARY_OPERATORS), add_item
            )
            self.Bind(
                wx.EVT_MENU,
                lambda _e: self._apply_structure_edit(remove_nary_limits, nary_caret, _NARY_OPERATORS),
                remove_item,
            )
            menu.AppendSubMenu(nary_menu, f"&{label.capitalize()}")
        if menu.GetMenuItemCount():
            menu.AppendSeparator()
        other_view = "Professional" if self.mode == "linear" else "Linear"
        view_item = menu.Append(wx.ID_ANY, f"Switch to {other_view} View\tF2")
        self.Bind(wx.EVT_MENU, lambda _e: self._toggle_mode(), view_item)
        self.PopupMenu(menu, position)
        menu.Destroy()

    def _matrix_caret(self) -> int | None:
        """A source offset in the matrix cell the user is on, if any.

        In professional mode MathCAT's cell is mapped back to the source
        by matrix order: the n-th `mtable` is the n-th `■(`. If the counts
        differ (another construct made a table), no mapping is trusted.
        """
        source = self.document.source
        if self.mode == "linear":
            return self.caret if in_view(source, self.caret, matrix_position_at) is not None else None
        if self.mathcat is None or self.mathcat.structure is None:
            return None
        location = self.mathcat.matrix_location()
        view = view_of(source)
        if location is None or len(self.mathcat.structure.tables()) != matrix_count(view.text):
            return None
        caret = matrix_cell_caret(view.text, *location)
        return None if caret is None else view.to_source(caret)

    def _structure_offset(self, kind: _StructureKind) -> int | None:
        """The source offset of the structure of `kind` the user is on, if any.

        In professional mode MathCAT's innermost node of that kind is mapped
        back by order: the n-th such node is the n-th one in `kind.offsets`.
        If the counts differ (another construct made such a node), no
        mapping is trusted.
        """
        source = self.document.source
        if self.mode == "linear":
            return kind.source_at(source, self.caret)
        structure = self.mathcat.structure if self.mathcat is not None else None
        if structure is None:
            return None
        node = structure.enclosing(self.mathcat.current_id, kind.is_node)
        nodes = structure.find_all(kind.is_node)
        offsets = kind.source_offsets(source)
        if node is None or len(nodes) != len(offsets):
            return None
        return offsets[next(i for i, candidate in enumerate(nodes) if candidate is node)]

    def _apply_fraction_style(self, caret: int, style: str) -> None:
        edit = self._edit(lambda source, at: restyle_fraction(source, at, style), caret)
        if edit is not None and edit.source == self.document.source:
            self._announce(edit.announcement)
            return
        self._apply_edit(edit, _FRACTIONS)

    def _edit(self, build: Callable[[str, int], TemplateEdit | None], caret: int | None = None) -> TemplateEdit | None:
        """Run a template/structure edit on the source, spelled as the settings say."""
        caret = self.caret if caret is None else caret
        return edit_in_view(self.document.source, caret, build, self.settings.template_control_words)

    def _apply_structure_edit(
        self, build: Callable[[str, int], TemplateEdit | None], caret: int, kind: _StructureKind
    ) -> None:
        self._apply_edit(self._edit(build, caret), kind)

    def _apply_edit(self, edit: TemplateEdit | None, kind: _StructureKind) -> None:
        if edit is None:
            self._announce("not available here")
            return
        self._clear_selection()
        self._replace_linear(edit.source, edit.caret)
        self.SetFocus()
        if self.mode != "professional":
            self._announce(edit.announcement)
            return
        try:
            buildable = not mathml_has_parse_error(self.convert_unicode_math(edit.source))
        except (UnicodeMathError, RuntimeError):
            buildable = False
        if not buildable:
            # An empty root index is a parse error until it is typed in.
            self.mode = "linear"
            self._update_braille_display()
            self._announce(f"{edit.announcement}, linear mode")
            self.Refresh()
            return
        self._rebuild_professional_at_caret(edit.announcement, place=lambda: self._place_on(kind))

    def _place_on(self, kind: _StructureKind) -> None:
        """Put MathCAT on the structure of `kind` around the caret (a linear fraction has no node)."""
        self._highlight_matrix_cell = False
        source = self.document.source
        offset = kind.source_at(source, self.caret)
        offsets = kind.source_offsets(source)
        nodes = self.mathcat.structure.find_all(kind.is_node) if self.mathcat.structure is not None else ()
        if offset is None or offset not in offsets or len(nodes) != len(offsets):
            return
        target = nodes[offsets.index(offset)]
        if target.identifier:
            self.mathcat.move_to(target.identifier)

    def _apply_matrix_edit(self, edit: TemplateEdit | None) -> None:
        if edit is None:
            self._announce("not in a matrix")
            return
        self._clear_selection()
        self._replace_linear(edit.source, edit.caret)
        self.SetFocus()
        if self.mode == "professional":
            self._rebuild_professional_at_caret(edit.announcement)
            return
        self._announce(edit.announcement)

    def _rebuild_professional_at_caret(self, announcement: str, place: Callable[[], None] | None = None) -> None:
        """Reload the edited equation and put MathCAT on the caret's cell (or wherever `place` puts it)."""
        try:
            conversion = self._convert_source()
            self._professional_mathml = conversion.mathml
            self.mathml_document = MathMLDocument.parse(
                conversion.mathml,
                recognized_functions=self.settings.recognized_functions,
            )
            if self.mathcat is not None:
                self.mathcat.load(conversion.mathml)
                self.mathml_document = self.mathcat.structure
                if place is not None:
                    place()
                else:
                    position = in_view(self.document.source, self.caret, matrix_position_at)
                    if position is not None:
                        self.mathcat.move_to_cell(position.index, position.row, position.column)
                    self._highlight_matrix_cell = True
                self._sync_mathcat_cursor()
                self._start_linear_preparation()
        except (UnicodeMathError, OSError, RuntimeError, ValueError) as error:
            self.mode = "linear"
            self._update_braille_display()
            self._announce(f"{announcement}. Professional mode could not be rebuilt, linear mode. {error}")
            self.Refresh()
            return
        self._announce(announcement)
        self.Refresh()

    def _insert_matrix(self) -> None:
        if self.mode != "linear":
            return
        rows, columns, fence = self._last_matrix_shape
        dialog = MatrixDialog(self, rows=rows, columns=columns, fence=fence)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                self.SetFocus()
                return
            shape = (dialog.selected_rows, dialog.selected_columns, dialog.selected_fence)
        finally:
            dialog.Destroy()
        self._last_matrix_shape = shape
        edit = self._edit(lambda source, caret: insert_matrix_template(source, caret, *shape))
        self._clear_selection()
        self._replace_linear(edit.source, edit.caret)
        self.SetFocus()
        self._announce(edit.announcement)
