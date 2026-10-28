"""The equation editor's context menu and the edits it offers on structures (matrices, fractions)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from mathessible.editing.source_map import anchor_offset
from mathessible.editing.source_view import edit_in_view, in_view, view_of
from mathessible.i18n import _, spoken
from mathessible.mathcat.mathml_model import MathMLDocument, MathMLNode
from mathessible.templates.fraction_styles import FRACTION_STYLES, built_fractions, fraction_at, restyle_fraction
from mathessible.templates.insert_catalog import INSERT_GROUPS, InsertItem
from mathessible.templates.math_templates import NARY_LABELS
from mathessible.templates.matrix_templates import (
    TABLE_SIGNS,
    delete_matrix_column,
    delete_matrix_row,
    delete_table_row,
    insert_matrix_column,
    insert_matrix_row,
    insert_matrix_template,
    insert_table_row,
    matrix_cell_caret,
    matrix_count,
    table_position_at,
)
from mathessible.templates.structure_edits import (
    ACCENTS,
    BARS,
    BRACKET_NAMES,
    accent_at,
    add_nary_limits,
    add_root_index,
    add_subscript,
    add_superscript,
    bar_at,
    bracket_at,
    change_accent,
    change_brackets,
    encloses_matrix,
    hide_bracket,
    nary_at,
    nary_operators,
    remove_accent,
    remove_bar,
    remove_brackets,
    remove_nary_limits,
    remove_root_index,
    remove_subscript,
    remove_superscript,
    root_at,
    roots,
    script_at,
    switch_bar,
)
from mathessible.templates.template_source import TemplateEdit
from mathessible.ui.clipboard import get_clipboard_text
from mathessible.ui.matrix_dialog import MatrixDialog
from mathessible.unicodemath import UnicodeMathError, mathml_has_parse_error

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


def _menu_label(name: str) -> str:
    """A structure's name (`N_` where it is defined) as a menu item: translated, capitalised, its access key first."""
    label = _(name)
    return f"&{label[:1].upper()}{label[1:]}"


def append_insert_items(menu: wx.Menu) -> dict[int, InsertItem]:
    """Fill `menu` with the Insert entries, sections apart; returns them by menu id."""
    mac = wx.Platform == "__WXMAC__"
    entries: dict[int, InsertItem] = {}
    for index, group in enumerate(INSERT_GROUPS):
        if index:
            menu.AppendSeparator()
        for entry in group:
            accelerator = entry.accelerator(mac)
            label = _(entry.label)
            item = menu.Append(wx.ID_ANY, f"{label}\t{accelerator}" if accelerator else label)
            entries[item.GetId()] = entry
    return entries


class StructureActionsMixin:
    """Methods of `EquationEditor` (editor.py); relies on its state."""

    def _show_context_menu(self, position: wx.Point) -> None:
        menu = wx.Menu()
        self._append_edit_items(menu)
        if not self.latex:  # The structure edits write UnicodeMath.
            self._append_table_menu(menu)
            self._append_fraction_menu(menu)
            self._append_root_menu(menu)
            self._append_nary_menu(menu)
            self._append_caret_structure_menus(menu)
        if menu.GetMenuItemCount():
            menu.AppendSeparator()
        switch = _("Switch to Professional View") if self.mode == "linear" else _("Switch to Linear View")
        view_item = menu.Append(wx.ID_ANY, switch + "\tF2")
        self.Bind(wx.EVT_MENU, lambda _e: self._toggle_mode(), view_item)
        self.PopupMenu(menu, position)
        menu.Destroy()

    def _append_edit_items(self, menu: wx.Menu) -> None:
        """Cut, Copy, Paste, Select All and the Insert submenu, in the linear view."""
        if self.mode != "linear":
            return
        has_content = bool(self.document.source)
        cut_item = menu.Append(wx.ID_ANY, _("Cu&t") + "\tCtrl+X")
        copy_item = menu.Append(wx.ID_ANY, _("&Copy") + "\tCtrl+C")
        paste_item = menu.Append(wx.ID_ANY, _("&Paste") + "\tCtrl+V")
        menu.AppendSeparator()
        select_all_item = menu.Append(wx.ID_ANY, _("Select &All") + "\tCtrl+A")
        if not self.latex:  # The Insert entries are UnicodeMath templates.
            menu.AppendSeparator()
            insert_menu = wx.Menu()
            for item_id, entry in append_insert_items(insert_menu).items():
                self.Bind(wx.EVT_MENU, lambda _e, entry=entry: self.insert_item(entry), id=item_id)
            menu.AppendSubMenu(insert_menu, _("&Insert"))
        cut_item.Enable(has_content)
        copy_item.Enable(has_content)
        paste_item.Enable(get_clipboard_text() is not None)
        select_all_item.Enable(has_content)
        self.Bind(wx.EVT_MENU, lambda _e: self._cut_equation(), cut_item)
        self.Bind(wx.EVT_MENU, lambda _e: self._copy_equation(), copy_item)
        self.Bind(wx.EVT_MENU, lambda _e: self._paste_equation(), paste_item)
        self.Bind(wx.EVT_MENU, lambda _e: self._select_all(), select_all_item)

    def _append_table_menu(self, menu: wx.Menu) -> None:
        """Matrix, Cases or Equations: rows and columns of the table the user is in."""
        # Row/column edits act on the innermost table around the caret
        # (linear) or MathCAT's current cell (professional), so the
        # submenu only exists while one of those is in a table: "Matrix"
        # for a matrix or determinant, "Cases", "Equations" (rows only).
        caret = self._matrix_caret()
        position_in_matrix = in_view(self.document.source, caret, table_position_at) if caret is not None else None
        if position_in_matrix is not None and position_in_matrix.kind in ("cases", "equations"):
            cases = position_in_matrix.kind == "cases"
            rows_menu = wx.Menu()
            above, below, delete = (
                (_("Insert Case &Above"), _("Insert Case &Below"), _("&Delete Case"))
                if cases
                else (_("Insert Equation &Above"), _("Insert Equation &Below"), _("&Delete Equation"))
            )
            rows_actions = [
                (above, lambda: self._edit(lambda s, c: insert_table_row(s, c, below=False), caret)),
                (below, lambda: self._edit(lambda s, c: insert_table_row(s, c, below=True), caret)),
                (delete, lambda: self._edit(delete_table_row, caret)),
            ]
            for label, build in rows_actions:
                item = rows_menu.Append(wx.ID_ANY, label)
                self.Bind(wx.EVT_MENU, lambda _e, build=build: self._apply_matrix_edit(build()), item)
            rows_menu.GetMenuItems()[-1].Enable(position_in_matrix.rows > 1)
            menu.AppendSubMenu(rows_menu, _("&Cases") if cases else _("&Equations"))
        elif position_in_matrix is not None:
            matrix_menu = wx.Menu()
            matrix_actions = [
                (_("Insert Row &Above"), lambda: self._edit(lambda s, c: insert_matrix_row(s, c, below=False), caret)),
                (_("Insert Row &Below"), lambda: self._edit(lambda s, c: insert_matrix_row(s, c, below=True), caret)),
                (
                    _("Insert Column &Left"),
                    lambda: self._edit(lambda s, c: insert_matrix_column(s, c, right=False), caret),
                ),
                (
                    _("Insert Column &Right"),
                    lambda: self._edit(lambda s, c: insert_matrix_column(s, c, right=True), caret),
                ),
                None,
                (_("Delete R&ow"), lambda: self._edit(delete_matrix_row, caret)),
                (_("Delete C&olumn"), lambda: self._edit(delete_matrix_column, caret)),
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
            menu.AppendSubMenu(matrix_menu, _("Matri&x"))

    def _append_fraction_menu(self, menu: wx.Menu) -> None:
        """Fraction: Word's four styles, for the fraction the user is in."""
        fraction_caret = self._structure_offset(_FRACTIONS)
        if fraction_caret is None:
            return
        fraction_menu = wx.Menu()
        current_style = in_view(self.document.source, fraction_caret, fraction_at).style
        for style in FRACTION_STYLES:
            item = fraction_menu.AppendRadioItem(wx.ID_ANY, _menu_label(style))
            item.Check(style == current_style)
            self.Bind(
                wx.EVT_MENU,
                lambda _e, style=style: self._apply_fraction_style(fraction_caret, style),
                item,
            )
        menu.AppendSubMenu(fraction_menu, _("&Fraction"))

    def _append_root_menu(self, menu: wx.Menu) -> None:
        """Root: add or remove the index."""
        root_caret = self._structure_offset(_ROOTS)
        if root_caret is None:
            return
        has_index = in_view(self.document.source, root_caret, root_at).has_index
        root_menu = wx.Menu()
        add_item = root_menu.Append(wx.ID_ANY, _("&Add Index"))
        remove_item = root_menu.Append(wx.ID_ANY, _("&Remove Index"))
        add_item.Enable(not has_index)
        remove_item.Enable(has_index)
        self.Bind(wx.EVT_MENU, lambda _e: self._apply_structure_edit(add_root_index, root_caret, _ROOTS), add_item)
        self.Bind(
            wx.EVT_MENU, lambda _e: self._apply_structure_edit(remove_root_index, root_caret, _ROOTS), remove_item
        )
        menu.AppendSubMenu(root_menu, _("&Root"))

    def _append_nary_menu(self, menu: wx.Menu) -> None:
        """Integral, Sum, Product…: add or remove the limits."""
        nary_caret = self._structure_offset(_NARY_OPERATORS)
        if nary_caret is None:
            return
        view = view_of(self.document.source)
        nary = nary_at(view.text, view.to_view(nary_caret))
        has_limits = nary.has_limits
        label = NARY_LABELS[view.text[nary.symbol]]
        nary_menu = wx.Menu()
        add_item = nary_menu.Append(wx.ID_ANY, _("&Add Limits"))
        remove_item = nary_menu.Append(wx.ID_ANY, _("&Remove Limits"))
        add_item.Enable(not has_limits)
        remove_item.Enable(has_limits)
        self.Bind(
            wx.EVT_MENU,
            lambda _e: self._apply_structure_edit(add_nary_limits, nary_caret, _NARY_OPERATORS),
            add_item,
        )
        self.Bind(
            wx.EVT_MENU,
            lambda _e: self._apply_structure_edit(remove_nary_limits, nary_caret, _NARY_OPERATORS),
            remove_item,
        )
        menu.AppendSubMenu(nary_menu, _menu_label(label))

    def _append_caret_structure_menus(self, menu: wx.Menu) -> None:
        """Word's Script, Brackets, Accent and Bar options for the structure at the caret (or MathCAT's node)."""
        span = self._structure_span()
        if span is None:
            return
        caret = span[0]
        view = view_of(self.document.source)
        at, end = view.to_view(span[0]), view.to_view(span[1])

        def add(submenu: wx.Menu, label: str, build: Callable[[str, int], TemplateEdit | None], enabled: bool = True):
            item = submenu.Append(wx.ID_ANY, label)
            item.Enable(enabled)
            self.Bind(wx.EVT_MENU, lambda _e: self._apply_caret_edit(build, caret), item)

        script = script_at(view.text, at, end)
        if script is not None:
            script_menu = wx.Menu()
            add(script_menu, _("Add &Subscript"), add_subscript, script.subscript is None)
            add(script_menu, _("Add Su&perscript"), add_superscript, script.superscript is None)
            add(script_menu, _("&Remove Subscript"), remove_subscript, script.subscript is not None)
            add(script_menu, _("Remove Superscrip&t"), remove_superscript, script.superscript is not None)
            menu.AppendSubMenu(script_menu, _("&Script"))
        bracket = bracket_at(view.text, at, end)
        if bracket is not None:
            bracket_menu = wx.Menu()
            matrix = encloses_matrix(view.text, bracket)
            current = view.text[bracket.opening]
            for opening, name in BRACKET_NAMES.items():
                if matrix and opening not in "([|":
                    continue  # Other fences leave the matrix loose or misread (‖ is two loose bars).
                item = bracket_menu.AppendRadioItem(wx.ID_ANY, _menu_label(name))
                item.Check(opening == current)
                self.Bind(
                    wx.EVT_MENU,
                    lambda _e, opening=opening: self._apply_caret_edit(
                        lambda source, at: change_brackets(source, at, opening), caret
                    ),
                    item,
                )
            if not matrix and current not in "|‖":
                bracket_menu.AppendSeparator()
                opening_hidden = view.text[bracket.opening] == "├"
                closing_hidden = view.text[bracket.closing] == "┤"
                add(
                    bracket_menu,
                    _("Show &Opening Bracket") if opening_hidden else _("Hide &Opening Bracket"),
                    lambda source, at: hide_bracket(source, at, closing=False),
                )
                add(
                    bracket_menu,
                    _("Show &Closing Bracket") if closing_hidden else _("Hide &Closing Bracket"),
                    lambda source, at: hide_bracket(source, at, closing=True),
                )
            if not matrix:
                bracket_menu.AppendSeparator()
                add(bracket_menu, _("&Remove Brackets"), remove_brackets)
            menu.AppendSubMenu(bracket_menu, _("&Brackets"))
        accent = accent_at(view.text, at, end)
        if accent is not None:
            accent_menu = wx.Menu()
            for mark, name in ACCENTS.items():
                item = accent_menu.AppendRadioItem(wx.ID_ANY, _menu_label(name))
                item.Check(view.text[accent.mark] == mark)
                self.Bind(
                    wx.EVT_MENU,
                    lambda _e, mark=mark: self._apply_caret_edit(
                        lambda source, at: change_accent(source, at, mark), caret
                    ),
                    item,
                )
            accent_menu.AppendSeparator()
            add(accent_menu, _("&Remove Accent"), remove_accent)
            menu.AppendSubMenu(accent_menu, _("&Accent"))
        bar = bar_at(view.text, at, end)
        if bar is not None:
            bar_menu = wx.Menu()
            add(bar_menu, _("Change to &Underbar") if view.text[bar[0]] == "¯" else _("Change to &Overbar"), switch_bar)
            add(bar_menu, _("&Remove Bar"), remove_bar)
            menu.AppendSubMenu(bar_menu, _menu_label(BARS[view.text[bar[0]]]))

    def _structure_span(self) -> tuple[int, int] | None:
        """Where the user is, in the source: the caret, or MathCAT's node's whole span.

        A whole node, not its start: the "+" right after `(a+b)^2` starts
        where the script ends, and is not in it, while the linear caret
        there is (Word's caret right after a structure).
        """
        if self.mode == "linear":
            return self.caret, self.caret
        structure = self.mathcat.structure if self.mathcat is not None else None
        # The highlighted node: on an "end X" stop MathCAT is already on the next one.
        node_id = self.mathcat.display_id if self.mathcat is not None else None
        if (
            structure is None
            or not node_id
            or structure.node(node_id) is None
            or structure.node(node_id) is structure.root
        ):
            return None
        repair = self._built_repair()
        try:
            start = anchor_offset(repair.text, structure, node_id, "before", False)
            end = anchor_offset(repair.text, structure, node_id, "after", False)
        except (KeyError, ValueError):
            return None
        return repair.to_real(start), repair.to_real(max(start, end))

    def _apply_caret_edit(self, build: Callable[[str, int], TemplateEdit | None], caret: int) -> None:
        """A structure edit found by caret (Script, Brackets, Accent, Bar); MathCAT goes to the caret after it."""
        self._apply_edit(self._edit(build, caret), None)

    def _matrix_caret(self) -> int | None:
        """A source offset in the table cell (matrix, case, equation) the user is on, if any.

        In professional mode MathCAT's cell is mapped back to the source
        by table order: the n-th `mtable` is the n-th `■(`/`█(`. If the
        counts differ (another construct made a table), no mapping is trusted.
        """
        source = self.document.source
        if self.mode == "linear":
            return self.caret if in_view(source, self.caret, table_position_at) is not None else None
        if self.mathcat is None or self.mathcat.structure is None:
            return None
        location = self.mathcat.matrix_location()
        view = view_of(source)
        if location is None or len(self.mathcat.structure.tables()) != matrix_count(view.text, TABLE_SIGNS):
            return None
        caret = matrix_cell_caret(view.text, *location, signs=TABLE_SIGNS)
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

    def _apply_edit(self, edit: TemplateEdit | None, kind: _StructureKind | None) -> None:
        if self._writing_off():
            return
        if edit is None:
            self._announce(spoken("not available here"))
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
            self._announce(f"{edit.announcement}, {spoken('linear mode')}")
            self.Refresh()
            return
        place = self._place_after_caret if kind is None else (lambda: self._place_on(kind))
        self._rebuild_professional_at_caret(edit.announcement, place=place)

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
        if self._writing_off():
            return
        if edit is None:
            self._announce(spoken("not in a table"))
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
                self.mathcat.load(conversion.mathml, speak=False)
                self.mathml_document = self.mathcat.structure
                if place is not None:
                    place()
                else:
                    position = in_view(self.document.source, self.caret, table_position_at)
                    if position is not None:
                        self.mathcat.move_to_cell(position.index, position.row, position.column)
                    self._highlight_matrix_cell = True
                self._sync_mathcat_cursor()
                self._start_linear_preparation()
        except (UnicodeMathError, OSError, RuntimeError, ValueError) as error:
            self.mode = "linear"
            self._update_braille_display()
            self._announce(
                spoken("{announcement}. Professional mode could not be rebuilt, linear mode. {error}").format(
                    announcement=announcement, error=error
                )
            )
            self.Refresh()
            return
        if announcement:
            self._announce(announcement)
        self.Refresh()

    def _insert_matrix(self) -> None:
        if self._writing_off():
            return
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
