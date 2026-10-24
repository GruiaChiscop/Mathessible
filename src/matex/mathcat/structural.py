"""Structural navigation: the items of one level, framed by "start X"/"end X" stops."""

from __future__ import annotations

from matex.mathcat.common import _INVISIBLE_OPERATOR_NAMES, BoundaryStop, _table_names
from matex.mathcat.mathml_model import MathMLNode, is_equation_label, number_last
from matex.templates.math_templates import ARROWS, function_script


class StructuralNavigationMixin:
    """Methods of `MathCatNavigator` (mathcat.py); relies on its state."""

    __slots__ = ()

    def structural_command(self, command: str) -> str:
        """Left/Right/Down/Up in structural navigation with structure stops.

        One level is the items of a structure (a fraction's numerator and
        denominator, a group's terms, ...), framed by standalone stops:
        "start fraction", numerator, denominator, "end fraction". Left/Right
        stay within the level (with AutoZoomOut, past an edge they leave it
        like Up then Left/Right); Down enters the current item on its
        "start ..." stop, Up goes back to the enclosing item.
        """
        structure = self.structure
        node = structure.node(self.current_id) if structure is not None else None
        level_commands = {"MoveNext", "MovePrevious", "ZoomIn", "ZoomOut", "MoveStart", "MoveEnd"}
        if structure is None or node is None or command not in level_commands:
            if command != "ReadCurrent":  # Space re-reads an edge stop without leaving it.
                self._structural_edge = None
            return self.command_with_boundaries(command)
        parent = self._level_parent(node)
        items = self._level_items(parent) if parent is not None else []
        if parent is None or not any(item is node for item in items):
            # MathCAT is somewhere this model has no level for: plain MathCAT.
            self._structural_edge = None
            return self.command_with_boundaries(command)
        index = next(position for position, item in enumerate(items) if item is node)
        edge = self._structural_edge
        if command in ("MoveStart", "MoveEnd"):
            # Home/End: the level's first/last item. MathCAT's own MoveEnd could
            # land on an invisible operator and fail ("no speech generated").
            return self._structural_go(items[0] if command == "MoveStart" else items[-1])
        if command == "ZoomIn":
            children = self._level_items(node)
            if not children:
                return self._structural_edge_speech(edge, parent) if edge else "zoomed in all of the way"
            # On an edge stop too: Down enters the item the cursor is on.
            return self._structural_enter(node, children)
        if command == "ZoomOut":
            outer = self._level_parent(parent)
            if outer is None:
                return "zoomed out all of the way"
            return self._structural_go(parent)
        forward = command == "MoveNext"
        if edge == ("start" if forward else "end"):
            # Back from an edge stop onto the item next to it.
            return self._structural_go(node)
        target = index + (1 if forward else -1)
        if 0 <= target < len(items) and edge is None:
            return self._structural_go(items[target])
        side = "end" if forward else "start"
        if not self.structural_stops:
            # No standalone edge stops: stay on the item and say the edge.
            return self._structural_edge_speech(side, parent)
        if edge == side and self.auto_zoom_out:
            outer = self._level_parent(parent)
            if outer is not None:
                # Past the edge: leave the structure, as Up then Left/Right.
                self._structural_go(parent)
                return self.structural_command(command)
        self._structural_edge = side
        self._boundary_stop = BoundaryStop(
            speech=self._structural_edge_speech(side, parent),
            pending_speeches=(),
            resume_command="MovePrevious" if forward else "MoveNext",
            current_id=node.identifier or "",
            read_current_on_next_navigation=True,
        )
        return self._boundary_stop.speech

    def _structural_enter(self, node: MathMLNode, children: list[MathMLNode]) -> str:
        first = children[0]
        assert first.identifier is not None
        if not self.structural_stops:
            # No "start X" stop: Down goes straight onto the first item, saying where.
            speech = self._structural_go(first)
            return f"{self._structural_edge_speech('start', node)}; {speech}"
        self._go_to(first.identifier)
        self._structural_edge = "start"
        self._boundary_stop = BoundaryStop(
            speech=self._structural_edge_speech("start", node),
            pending_speeches=(),
            resume_command="MoveNext",
            current_id=first.identifier,
            read_current_on_next_navigation=True,
        )
        return self._boundary_stop.speech

    def _structural_go(self, node: MathMLNode) -> str:
        assert node.identifier is not None and self.structure is not None
        self._structural_edge = None
        self._boundary_stop = None
        self._go_to(node.identifier)
        number = self.structure.equation_number(node.identifier)
        if number is not None:
            return number  # "equation number 1", as the linear stops say it.
        position = self.structure.table_position(node.identifier) if node.tag == "mtd" else None
        table = self.structure.node(position.table_id) if position is not None and position.table_id else None
        if position is not None and table is not None:
            # A cell by itself ("condition; x is greater than 0"): MathCAT
            # reads a case's cell as the whole case, and fails on an empty one.
            return self._cell_speech(table, position.row, position.column, vertical=False, move=False)
        try:
            speech = self._navigate("ReadCurrent")
        except RuntimeError:
            speech = " ".join(node.content.split())
        speech = _INVISIBLE_OPERATOR_NAMES.get(speech.strip(), speech)
        if not node.children:
            speech = self._leaf_only(node, speech)
        role = self.structure.semantic_role(node.identifier)
        if role == "base" and function_script(node.content):
            role = None  # `log`/`lim` itself is the name, not a "base" (log's base is its subscript).
        if not role and self.structure.is_function_argument(node):
            role = "argument"
        if not speech.strip():
            speech = "empty"  # An empty argument or slot: MathCAT reads nothing ("argument, ").
        return f"{role}, {speech}" if role else speech

    def _structural_edge_speech(self, side: str, parent: MathMLNode) -> str:
        return f"{side} {self._structure_label(parent)}"

    def _structure_label(self, node: MathMLNode) -> str:
        structure = self.structure
        assert structure is not None
        if structure.root is node:
            return "of math"
        named = {
            "mfrac": "fraction",
            "msqrt": "square root",
            "mroot": "root",
            "mtable": "matrix",
            "mtr": "row",
            "mtd": "cell",
            "msub": "script",
            "msup": "script",
            "msubsup": "script",
            "munder": "script",
            "mover": "script",
            "munderover": "script",
        }.get(node.tag)
        if named == "matrix":
            kind = structure.table_kind(node)  # "cases", "equations", "determinant", "numbered" or "matrix".
            return "numbered equation" if kind == "numbered" else kind
        if node.identifier and (number := structure.equation_number(node.identifier)):
            return number
        if named in ("row", "cell") and node.identifier:
            table = structure.enclosing(node.identifier, lambda candidate: candidate.tag == "mtable")
            if table is not None and structure.table_kind(table) == "numbered":
                return "equation"  # The equation's own row and cell, beside its number.
        if named == "row" and node.identifier:
            table = structure.parent_by_id.get(node.identifier)
            rows = [child for child in table.children if child.tag == "mtr"] if table is not None else []
            if table is not None and any(row is node for row in rows):
                number = next(i for i, row in enumerate(rows, start=1) if row is node)
                return f"{_table_names(structure.table_kind(table))[0]} {number}"
        if named == "script" and node.children and structure.is_large_operator(node.children[0]):
            return "limits"
        if named == "script" and node.children and (script := function_script(node.children[0].content)):
            return script[0]  # "limit", "logarithm": not a script.
        if named == "script" and node.tag in {"mover", "munder", "munderover"} and node.children:
            # An operator with text over/under it (`→┴(x)`): named like its template.
            base = node.children[0]
            text = node.children[1].identifier if len(node.children) > 1 else None
            if base.tag == "mo" and text and structure.semantic_role(text) in {"text above", "text below"}:
                return "arrow" if base.content.strip() in ARROWS else "operator"
        if named:
            return named
        if node.identifier:
            regions = structure.regions(node.identifier)
            if regions:
                return regions[0]
        if node.attributes.get("intent", "").startswith(":fenced"):
            return "parentheses"
        return "group"

    def _level_items(self, node: MathMLNode) -> list[MathMLNode]:
        """The items one level inside `node`, skipping what is never a stop.

        Invisible operators (function application, and invisible times unless
        `invisible_operator_stops`) and a matrix's own fences (MathCAT reads those as the whole matrix) are
        left out, and a lone unlabeled wrapper row is looked through.
        """
        structure = self.structure
        assert structure is not None
        table = self._numbered_table(node)
        if table is not None:
            # `E=mc^2#(1)`: the equation's own items, then its number. The converter's table, its row
            # and the equation's cell all give this one level, so none of them is a level of its own.
            row = table.children[0] if table.children else None
            cells = number_last(row) if row is not None else ()
            equation = [cell for cell in cells if not is_equation_label(cell)]
            label = [cell for cell in cells if is_equation_label(cell)]
            inner = [item for cell in equation for item in self._plain_level_items(cell)]
            return inner + label
        fenced_table = any(child.tag == "mtable" for child in node.children)
        items = [
            child
            for child in node.children
            if child.identifier
            and not (child.tag == "mo" and (fenced_table or self._skips_invisible_operator(child.content)))
        ]
        if node.tag == "mroot" and len(items) == 2:
            items.reverse()  # The index first, as it is said and written.
        if len(items) == 1 and (
            (
                items[0].children
                and items[0].tag in {"mrow", "mstyle", "mpadded", "semantics"}
                and not structure.semantic_role(items[0].identifier or "")
            )
            or self._numbered_table(items[0]) is not None
        ):
            return self._level_items(items[0])
        return items

    def _numbered_table(self, node: MathMLNode) -> MathMLNode | None:
        """The numbered equation's table if `node` is it, its row or the equation's cell (not the number's)."""
        structure = self.structure
        assert structure is not None
        if node.tag not in {"mtable", "mtr", "mtd"} or is_equation_label(node) or not node.identifier:
            return None
        table = structure.enclosing(node.identifier, lambda candidate: candidate.tag == "mtable")
        if table is None or structure.table_kind(table) != "numbered":
            return None
        return table

    def _plain_level_items(self, cell: MathMLNode) -> list[MathMLNode]:
        """The equation cell's items, looked through as any lone wrapper row is."""
        items = [child for child in cell.children if child.identifier]
        if len(items) == 1 and items[0].children and items[0].tag in {"mrow", "mstyle", "mpadded", "semantics"}:
            return self._level_items(items[0])
        return items

    def _level_parent(self, node: MathMLNode) -> MathMLNode | None:
        """The structure whose level `node` is an item of (None for the math itself)."""
        structure = self.structure
        assert structure is not None
        if node.identifier is None:
            return None
        found: MathMLNode | None = None
        for ancestor in structure.ancestors(node.identifier):
            if any(item is node for item in self._level_items(ancestor)):
                # Keep going: a wrapper row is looked through by the
                # structure around it, which owns the level then.
                found = ancestor
            elif found is not None:
                break
        return found
