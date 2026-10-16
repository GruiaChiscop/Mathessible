"""Structural navigation: the items of one level, framed by "start X"/"end X" stops.
"""

from __future__ import annotations

from .math_templates import ARROWS
from .mathcat_common import _INVISIBLE_OPERATOR_NAMES, BoundaryStop, _table_names
from .mathml_model import MathMLNode


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
        if structure is None or node is None or command not in {"MoveNext", "MovePrevious", "ZoomIn", "ZoomOut"}:
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
        self._native.set_navigation(first.identifier, 0)
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
        self._native.set_navigation(node.identifier, 0)
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
        if not role and self.structure.is_function_argument(node):
            role = "argument"
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
            return structure.table_kind(node)  # "cases", "equations", "determinant" or "matrix".
        if named == "row" and node.identifier:
            table = structure.parent_by_id.get(node.identifier)
            rows = [child for child in table.children if child.tag == "mtr"] if table is not None else []
            if table is not None and any(row is node for row in rows):
                number = next(i for i, row in enumerate(rows, start=1) if row is node)
                return f"{_table_names(structure.table_kind(table))[0]} {number}"
        if named == "script" and node.children and structure.is_large_operator(node.children[0]):
            return "limits"
        if named == "script" and node.tag in {"mover", "munder", "munderover"} and node.children:
            # An operator with text over/under it (`→┴(x)`): named like its template.
            base = node.children[0]
            if base.tag == "mo" and len(node.children) > 1 and node.children[1].identifier:
                if structure.semantic_role(node.children[1].identifier) in {"text above", "text below"}:
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
        fenced_table = any(child.tag == "mtable" for child in node.children)
        items = [
            child
            for child in node.children
            if child.identifier
            and not (child.tag == "mo" and (fenced_table or self._skips_invisible_operator(child.content)))
        ]
        if (
            len(items) == 1
            and items[0].children
            and items[0].tag in {"mrow", "mstyle", "mpadded", "semantics"}
            and not structure.semantic_role(items[0].identifier or "")
        ):
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
