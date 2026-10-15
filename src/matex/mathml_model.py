from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr

from .settings import DEFAULT_RECOGNIZED_FUNCTIONS


class MathMLModelError(ValueError):
    pass


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


# Presentation MathML 3 elements. Anything else (script, foreignObject, svg,
# annotation-xml with embedded markup, ...) is rejected rather than passed
# through, since converted equations end up embedded verbatim in exported
# HTML documents.
ALLOWED_MATHML_TAGS = frozenset(
    {
        "math",
        "mrow",
        "mfrac",
        "msqrt",
        "mroot",
        "mstyle",
        "merror",
        "mpadded",
        "mphantom",
        "mfenced",
        "menclose",
        "msub",
        "msup",
        "msubsup",
        "munder",
        "mover",
        "munderover",
        "mmultiscripts",
        "mprescripts",
        "none",
        "mtable",
        "mtr",
        "mlabeledtr",
        "mtd",
        "maction",
        "mi",
        "mn",
        "mo",
        "mtext",
        "ms",
        "mglyph",
        "mspace",
        "semantics",
    }
)

SCRIPT_TAGS = frozenset({"msub", "msup", "msubsup", "munder", "mover", "munderover", "mmultiscripts"})

# Presentation attributes plus the accessibility-only "intent"/"arg" pair
# MathCAT relies on. Deliberately excludes anything a browser treats as a
# behavior or resource hook (href, src, style, on*, xlink:*).
ALLOWED_MATHML_ATTRIBUTES = frozenset(
    {
        "id",
        "class",
        "dir",
        "intent",
        "arg",
        "mathvariant",
        "mathsize",
        "mathcolor",
        "mathbackground",
        "displaystyle",
        "scriptlevel",
        "display",
        "fence",
        "separator",
        "separators",
        "stretchy",
        "symmetric",
        "largeop",
        "movablelimits",
        "accent",
        "accentunder",
        "lspace",
        "rspace",
        "minsize",
        "maxsize",
        "form",
        "open",
        "close",
        "notation",
        "actiontype",
        "selection",
        "linethickness",
        "align",
        "rowalign",
        "columnalign",
        "columnlines",
        "rowlines",
        "rowspacing",
        "columnspacing",
        "columnspan",
        "rowspan",
        "frame",
        "framespacing",
        "equalrows",
        "equalcolumns",
        "side",
        "width",
        "height",
        "depth",
        "voffset",
        "subscriptshift",
        "superscriptshift",
    }
)


def sanitize_mathml(source: str) -> str:
    """Validate converter output against a MathML allow-list and re-serialize it.

    Exported HTML embeds this string directly, so it must never be trusted
    as-is: a bug in the third-party UnicodeMath-to-MathML converter (or a
    crafted equation) could otherwise smuggle script/foreignObject/annotation
    content into a document users open in a browser.
    """
    try:
        root = ElementTree.fromstring(source.strip())
    except ElementTree.ParseError as error:
        raise MathMLModelError(f"Invalid MathML: {error}") from error
    if _local_name(root.tag) != "math":
        raise MathMLModelError("Expected a MathML document with a <math> root element")
    return _serialize_safe(root)


def _serialize_safe(element: ElementTree.Element) -> str:
    tag = _local_name(element.tag)
    if tag not in ALLOWED_MATHML_TAGS:
        raise MathMLModelError(f"Disallowed MathML element: {tag}")
    attributes = "".join(
        f" {name}={quoteattr(value)}"
        for name, value in element.attrib.items()
        if name in ALLOWED_MATHML_ATTRIBUTES
    )
    # Only the first child of <semantics> is the visible presentation form;
    # annotation/annotation-xml siblings are dropped rather than validated.
    children = list(element)[:1] if tag == "semantics" else list(element)
    parts = [escape(element.text)] if element.text else []
    for child in children:
        parts.append(_serialize_safe(child))
        if child.tail:
            parts.append(escape(child.tail))
    return f"<{tag}{attributes}>{''.join(parts)}</{tag}>"


@dataclass(frozen=True, slots=True)
class MathMLNode:
    tag: str
    identifier: str | None
    text: str
    attributes: dict[str, str]
    children: tuple["MathMLNode", ...]

    @property
    def content(self) -> str:
        return self.text + "".join(child.content for child in self.children)


@dataclass(frozen=True, slots=True)
class TablePosition:
    row: int
    column: int
    row_count: int
    column_count: int
    table_id: str | None
    cell_id: str | None


@dataclass(slots=True)
class MathMLDocument:
    root: MathMLNode
    by_id: dict[str, MathMLNode]
    parent_by_id: dict[str, MathMLNode]
    recognized_functions: frozenset[str]

    @classmethod
    def parse(
        cls,
        mathml: str,
        recognized_functions: tuple[str, ...] = DEFAULT_RECOGNIZED_FUNCTIONS,
    ) -> "MathMLDocument":
        try:
            element = ElementTree.fromstring(mathml.strip())
        except ElementTree.ParseError as error:
            raise MathMLModelError(f"Invalid MathML: {error}") from error
        by_id: dict[str, MathMLNode] = {}
        parent_by_id: dict[str, MathMLNode] = {}

        def build(current: ElementTree.Element) -> MathMLNode:
            children = tuple(build(child) for child in current)
            node = MathMLNode(
                tag=_local_name(current.tag),
                identifier=current.get("id"),
                text=current.text or "",
                attributes=dict(current.attrib),
                children=children,
            )
            if node.identifier:
                if node.identifier in by_id:
                    raise MathMLModelError(f"Duplicate MathML id: {node.identifier}")
                by_id[node.identifier] = node
            for child in children:
                if child.identifier:
                    parent_by_id[child.identifier] = node
            return node

        root = build(element)
        return cls(
            root=root,
            by_id=by_id,
            parent_by_id=parent_by_id,
            recognized_functions=frozenset(name.lower() for name in recognized_functions),
        )

    def node(self, identifier: str) -> MathMLNode | None:
        return self.by_id.get(identifier)

    def contains_tag(self, tag: str) -> bool:
        return self.root.tag == tag or any(node.tag == tag for node in self.by_id.values())

    def ancestors(self, identifier: str) -> tuple[MathMLNode, ...]:
        result: list[MathMLNode] = []
        current_id = identifier
        while current_id in self.parent_by_id:
            parent = self.parent_by_id[current_id]
            result.append(parent)
            if parent.identifier is None:
                break
            current_id = parent.identifier
        return tuple(result)

    def semantic_role(self, identifier: str) -> str | None:
        node = self.node(identifier)
        parent = self.parent_by_id.get(identifier)
        if node is None or parent is None:
            return None
        try:
            index = parent.children.index(node)
        except ValueError:
            return None
        special_role = self._special_script_role(parent, index)
        if special_role is not None:
            return special_role
        roles = {
            "mfrac": ("numerator", "denominator"),
            "msub": ("base", "subscript"),
            "msup": ("base", "superscript"),
            "msubsup": ("base", "subscript", "superscript"),
            "mroot": ("radicand", "index"),
            "munder": ("base", "underscript"),
            "mover": ("base", "overscript"),
            "munderover": ("base", "underscript", "overscript"),
        }
        parent_roles = roles.get(parent.tag, ())
        return parent_roles[index] if index < len(parent_roles) else None

    def regions(self, identifier: str) -> tuple[str, ...]:
        return tuple(label for _key, label in self._region_entries(identifier))

    def region_entries(self, identifier: str) -> tuple[tuple[int, str], ...]:
        """`regions` with each region's identity: (key, label), innermost first."""
        return self._region_entries(identifier)

    def _region_entries(self, identifier: str) -> tuple[tuple[int, str], ...]:
        """(node identity, label) for every region the node is in, innermost first.

        Keyed by node identity, not by label, so two nested fractions are two
        separate regions: leaving the inner one's numerator is still "end
        numerator" while inside the outer one's. A structural container
        (fraction, root, matrix) only counts once the node is strictly
        *inside* it — standing on a whole fraction is not being in it — while
        a role (numerator, subscript, argument, ...) belongs to the node that
        fills it, so standing on the denominator is being in the denominator.
        """
        node = self.node(identifier)
        if node is None:
            return ()
        chain = (node,) + self.ancestors(identifier)
        entries: list[tuple[int, str]] = []
        for candidate in chain:
            key = id(candidate)
            if self._is_function_name(candidate):
                entries.append((key, "function name"))
            structural_region = self._structural_region_name(candidate)
            if structural_region is not None and candidate is not node:
                entries.append((key, structural_region))
            if candidate.attributes.get("arg") == "naryand":
                entries.append((key, self._nary_region_name(candidate)))
            role = candidate.identifier and self.semantic_role(candidate.identifier)
            if role in {
                "numerator",
                "denominator",
                "radicand",
                "subscript",
                "superscript",
                "lower limit",
                "upper limit",
                "limit condition",
                "text above",
                "text below",
            }:
                entries.append((key, role))
            if self._is_function_argument(candidate):
                entries.append((key, "argument"))
        return tuple(dict.fromkeys(entries))

    def exited_regions(self, previous_id: str, current_id: str, ignore_id: str | None = None) -> tuple[str, ...]:
        """Regions left by moving from previous_id to current_id, innermost first.

        `ignore_id` names a node whose own regions are not announced — the
        structure just zoomed into or out of, which the user already knows
        they are entering or standing on.
        """
        current = set(self._region_entries(current_id))
        ignored = self._ignored_key(ignore_id)
        return tuple(
            label for key, label in self._region_entries(previous_id) if (key, label) not in current and key != ignored
        )

    def entered_regions(self, previous_id: str, current_id: str, ignore_id: str | None = None) -> tuple[str, ...]:
        previous = set(self._region_entries(previous_id))
        ignored = self._ignored_key(ignore_id)
        return tuple(
            label for key, label in self._region_entries(current_id) if (key, label) not in previous and key != ignored
        )

    def left_zoomed_regions(self, previous_id: str, current_id: str) -> tuple[str, ...]:
        """Regions exited that the previous node was strictly *inside*, innermost first.

        Moving from the whole numerator to the denominator is a sibling step
        (the numerator node itself held the role); moving from the last item
        *inside* the numerator to the denominator is leaving a group the user
        zoomed into.
        """
        previous = self.node(previous_id)
        current = set(self._region_entries(current_id))
        return tuple(
            label
            for key, label in self._region_entries(previous_id)
            if (key, label) not in current and key != id(previous)
        )

    def _ignored_key(self, identifier: str | None) -> int | None:
        node = self.node(identifier) if identifier is not None else None
        return id(node) if node is not None else None

    def current_region_description(self, identifier: str) -> str | None:
        position = self.table_position(identifier)
        if position is not None and position.cell_id is not None:
            cell = self.node(position.cell_id)
            if cell is not None:
                return f"cell row {position.row}, column {position.column}, {self._readable_content(cell)}"

        node = self.node(identifier)
        if node is None:
            return None
        for candidate in (node,) + self.ancestors(identifier):
            if candidate.attributes.get("arg") == "naryand":
                return f"{self._nary_region_name(candidate)}, {self._readable_content(candidate)}"
            role = candidate.identifier and self.semantic_role(candidate.identifier)
            if role in {
                "numerator",
                "denominator",
                "radicand",
                "subscript",
                "superscript",
                "lower limit",
                "upper limit",
                "limit condition",
            }:
                return f"{role}, {self._readable_content(candidate)}"
            if self._is_function_name(candidate):
                return f"function name, {self._readable_content(candidate)}"
            if self._is_function_argument(candidate):
                return f"argument, {self._readable_content(candidate)}"
            structural_region = self._structural_region_name(candidate)
            if structural_region is not None:
                return f"{structural_region}, {self._readable_content(candidate)}"
        return None

    def _structural_region_name(self, node: MathMLNode) -> str | None:
        return {
            "mfrac": "fraction",
            "msqrt": "square root",
            "mroot": "root",
            "mtable": "matrix",
        }.get(node.tag)

    def _special_script_role(self, parent: MathMLNode, index: int) -> str | None:
        if parent.tag in {"msub", "munder"} and index == 1:
            base = parent.children[0] if parent.children else None
            if base is not None and self._is_limit_operator(base):
                return "limit condition"
            if base is not None and self._is_large_operator(base):
                return "lower limit"
        if parent.tag == "msup" and index == 1:
            base = parent.children[0] if parent.children else None
            if base is not None and self._is_large_operator(base):
                return "upper limit"
        if parent.tag == "msubsup":
            base = parent.children[0] if parent.children else None
            if base is not None and self._is_limit_operator(base):
                return "limit condition" if index == 1 else None
            if base is not None and self._is_large_operator(base):
                if index == 1:
                    return "lower limit"
                if index == 2:
                    return "upper limit"
        if parent.tag == "munderover":
            base = parent.children[0] if parent.children else None
            if base is not None and self._is_large_operator(base):
                if index == 1:
                    return "lower limit"
                if index == 2:
                    return "upper limit"
        if parent.tag in {"mover", "munder", "munderover"} and index > 0:
            # An operator with text over/under it (`→┴(x)`, `=┴(def)`).
            base = parent.children[0] if parent.children else None
            if base is not None and base.tag == "mo" and not self._is_large_operator(base):
                above = parent.tag == "mover" or index == 2
                return "text above" if above else "text below"
        return None

    def is_function_argument(self, node: MathMLNode) -> bool:
        return self._is_function_argument(node)

    def is_large_operator(self, node: MathMLNode) -> bool:
        return self._is_large_operator(node)

    def _is_large_operator(self, node: MathMLNode) -> bool:
        content = self._normalized_text(node)
        return any(symbol in content for symbol in "∫∬∭∮∯∰∱∲∳∑∏")

    def _is_limit_operator(self, node: MathMLNode) -> bool:
        return self._normalized_text(node) == "lim"

    def _readable_content(self, node: MathMLNode) -> str:
        text = " ".join(node.content.split())
        return text or "empty"

    def _nary_region_name(self, node: MathMLNode) -> str:
        if node.identifier is None:
            return "n-ary argument"
        for ancestor in self.ancestors(node.identifier):
            if ":nary" in ancestor.attributes.get("intent", ""):
                operator = ancestor.children[0].content if ancestor.children else ""
                if any(symbol in operator for symbol in "∫∬∭∮∯∰∱∲∳"):
                    return "integrand"
                if "∑" in operator:
                    return "summand"
                if "∏" in operator:
                    return "factor"
        return "n-ary argument"

    def _is_argument(self, node: MathMLNode) -> bool:
        if node.identifier is None:
            return False
        parent = self.parent_by_id.get(node.identifier)
        if parent is None:
            return False
        if ":function" in parent.attributes.get("intent", "") or self._has_recognized_function(parent):
            return True
        try:
            index = parent.children.index(node)
        except ValueError:
            return False
        if index == 0:
            return False
        previous = parent.children[index - 1]
        return previous.tag in {"mi", "msub", "msup", "msubsup"}

    def _is_function_name(self, node: MathMLNode) -> bool:
        return node.tag == "mi" and self._normalized_text(node) in self.recognized_functions

    def _is_function_argument(self, node: MathMLNode) -> bool:
        if node.attributes.get("intent", "").startswith(":fenced") and self._is_argument(node):
            return True
        if node.identifier is None:
            return False
        parent = self.parent_by_id.get(node.identifier)
        if parent is None:
            return False
        return self._function_argument_index(parent) == self._child_index(parent, node)

    def _has_recognized_function(self, node: MathMLNode) -> bool:
        return self._function_name_index(node) is not None

    def _function_name_index(self, node: MathMLNode) -> int | None:
        # A script's base is not applied to its scripts: in ln² the 2 is a
        # superscript, and the whole msup is the function name of its row.
        if node.tag in SCRIPT_TAGS:
            return None
        # The converter marks every function application it recognizes
        # (lim, max, ... -- not just the user's list): the head comes first.
        if ":function" in node.attributes.get("intent", "") and node.children:
            return 0
        for index, child in enumerate(node.children):
            if self._is_function_name(child) or self._is_scripted_function_name(child):
                return index
        return None

    def _is_scripted_function_name(self, node: MathMLNode) -> bool:
        return node.tag in SCRIPT_TAGS and bool(node.children) and self._is_function_name(node.children[0])

    def _function_argument_index(self, node: MathMLNode) -> int | None:
        name_index = self._function_name_index(node)
        if name_index is None:
            return None
        for index in range(name_index + 1, len(node.children)):
            child = node.children[index]
            if child.tag == "mo" and child.content in {"⁡", "(", ")"}:
                continue
            return index
        return None

    def _child_index(self, parent: MathMLNode, child: MathMLNode) -> int | None:
        try:
            return parent.children.index(child)
        except ValueError:
            return None

    def _normalized_text(self, node: MathMLNode) -> str:
        return "".join(node.content.split()).lower()

    def is_at_math_edge(self, identifier: str, end: bool) -> bool:
        """True when nothing comes after (end) / before (start) the node, at any level."""
        node = self.node(identifier)
        if node is None:
            return False
        current = node
        for parent in self.ancestors(identifier):
            if not parent.children:
                return False
            edge_child = parent.children[-1] if end else parent.children[0]
            if edge_child is not current:
                return False
            current = parent
        return True

    def nearest_first_cell(self, identifier: str) -> str | None:
        """Navigation target for the first cell of the matrix nearest to a node.

        On a matrix row (or the matrix itself) that is the row's (matrix's)
        own first cell. Otherwise the first matrix starting at or after the
        node in reading order wins (a matrix inside the node counts as after
        it), else the last one before it. The id returned is the cell's
        content, not the `mtd`: MathCAT reports "not in table" for cell
        commands issued while its cursor sits on an `mtd` itself.
        """
        node = self.node(identifier)
        for candidate in ((node,) if node is not None else ()) + self.ancestors(identifier):
            if candidate.tag == "mtr":
                return self._first_cell_target((candidate,))
            if candidate.tag == "mtable":
                return self._first_cell_target(candidate.children)
        order: list[MathMLNode] = []

        def walk(current: MathMLNode) -> None:
            order.append(current)
            for child in current.children:
                walk(child)

        walk(self.root)
        position = next((index for index, current in enumerate(order) if current.identifier == identifier), 0)
        tables = [(index, current) for index, current in enumerate(order) if current.tag == "mtable"]
        after = [table for index, table in tables if index >= position]
        before = [table for index, table in tables if index < position]
        table = after[0] if after else before[-1] if before else None
        return self._first_cell_target(table.children) if table is not None else None

    @staticmethod
    def _first_cell_target(rows: tuple[MathMLNode, ...]) -> str | None:
        for row in rows:
            cells = [child for child in row.children if child.tag == "mtd"]
            if not cells:
                continue
            return MathMLDocument._cell_target(cells[0])
        return None

    @staticmethod
    def _cell_target(cell: MathMLNode) -> str | None:
        content = cell.children[0] if len(cell.children) == 1 else None
        if content is not None and content.identifier:
            return content.identifier
        return cell.identifier

    def tables(self) -> tuple[MathMLNode, ...]:
        """Every `mtable`, in reading order (an outer one before those inside it)."""
        found: list[MathMLNode] = []

        def walk(current: MathMLNode) -> None:
            if current.tag == "mtable":
                found.append(current)
            for child in current.children:
                walk(child)

        walk(self.root)
        return tuple(found)

    def table_index(self, table_id: str) -> int | None:
        for index, table in enumerate(self.tables()):
            if table.identifier == table_id:
                return index
        return None

    def cell_target(self, table_index: int, row: int, column: int) -> str | None:
        """Navigation target for a cell, by 1-based row/column; a short row gives its last cell."""
        tables = self.tables()
        if not 0 <= table_index < len(tables):
            return None
        rows = [child for child in tables[table_index].children if child.tag == "mtr"]
        if not 1 <= row <= len(rows):
            return None
        cells = [child for child in rows[row - 1].children if child.tag == "mtd"]
        if not cells:
            return None
        return self._cell_target(cells[min(column, len(cells)) - 1])

    def table_position(self, identifier: str) -> TablePosition | None:
        node = self.node(identifier)
        if node is None:
            return None
        cell = node if node.tag == "mtd" else None
        current_id = identifier
        while cell is None and current_id in self.parent_by_id:
            parent = self.parent_by_id[current_id]
            if parent.tag == "mtd":
                cell = parent
                break
            if parent.identifier is None:
                return None
            current_id = parent.identifier
        if cell is None or cell.identifier is None:
            return None
        row = self.parent_by_id.get(cell.identifier)
        if row is None or row.tag != "mtr" or row.identifier is None:
            return None
        table = self.parent_by_id.get(row.identifier)
        if table is None or table.tag != "mtable":
            return None
        rows = tuple(child for child in table.children if child.tag == "mtr")
        cells = tuple(child for child in row.children if child.tag == "mtd")
        return TablePosition(
            row=rows.index(row) + 1,
            column=cells.index(cell) + 1,
            row_count=len(rows),
            column_count=max(
                (len(tuple(child for child in table_row.children if child.tag == "mtd")) for table_row in rows),
                default=0,
            ),
            table_id=table.identifier,
            cell_id=cell.identifier,
        )
