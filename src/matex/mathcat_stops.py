"""Linear navigation: one list of stops both ways, built from the structure or
by simulating Right, and the leaf speech it uses.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable

from .mathcat_common import (
    _CONTAINER_REGIONS,
    _FENCES_AND_SEPARATORS,
    _INVISIBLE_OPERATOR_NAMES,
    _LINEAR_SEARCH_BUDGET,
    BoundaryStop,
    _LinearStop,
)
from .math_templates import FUNCTION_SCRIPTS
from .mathcat_common import _INTENT_NODE
from .mathml_model import MathMLNode


class LinearStopsMixin:
    """Methods of `MathCatNavigator` (mathcat.py); relies on its state."""

    __slots__ = ()

    def linear_command(self, command: str) -> str:
        """Right/Left in linear navigation: one list of stops, both ways.

        Right flows into every structure and announces each boundary as a
        stop of its own. Left used to be plain MathCAT MovePrevious, which
        skipped whole structures and said "end ..." while moving backwards;
        now both directions walk the same stops, so Left retraces Right
        exactly, with the same speech at each stop.

        Stops are found by simulating Right from the start of the math. Each
        MathCAT command re-derives the whole expression's intent (about
        70 ms on a deeply nested one), so the list is never built all at
        once: `extend_linear_stops` fills it in the background, and a Right
        past what is known so far discovers just the one next stop.
        """
        if command in ("MoveStart", "MoveEnd"):
            return self._linear_edge(command == "MoveEnd")
        if command not in {"MoveNext", "MovePrevious"}:
            self._linear_index = None
            return self.command_with_boundaries(command)
        index = self._linear_position()
        if index is None:
            # Not on any stop (e.g. after a click on an unusual node): plain step.
            return self._linear_step(command)
        boundary = self._boundary_stop
        if (
            command == "MoveNext"
            and boundary is not None
            and boundary.resume_command == "MoveNext"
            and boundary.speech == "start of math"
            and boundary.current_id == self.current_id
        ):
            # Back from the "start of math" stop onto the first item, not past it.
            self._boundary_stop = self._linear_stops[index].boundary
            self._linear_index = index
            return self._linear_stops[index].speech
        target = index + (1 if command == "MoveNext" else -1)
        if target < 0:
            self._edge_stop(command, self.current_id, "start of math")
            self._linear_index = index
            return "start of math"
        if target >= len(self._linear_stops):
            self.extend_linear_stops(1)
        if target >= len(self._linear_stops):
            target = len(self._linear_stops) - 1
        stop = self._linear_stops[target]
        try:
            self._go_to(stop.node_id)
        except RuntimeError:
            # A stop of another load of this expression: rebuild them here, once.
            self._linear_stops, self._linear_done, self._linear_index = [], False, None
            self._build_bounded_stops()
            return self.linear_command(command) if self._linear_stops else ""
        self._boundary_stop = stop.boundary
        self._linear_index = target
        return stop.speech

    def _linear_edge(self, end: bool) -> str:
        """Home/End: "start of math" / the last stop ("end of math" with structure stops).

        On the stops, as Left/Right are: MathCAT's own MoveStart/MoveEnd
        landed on intent-only nodes of a sum or an integral (no speech, or
        an error that dropped MathCAT).
        """
        if not self._linear_stops:
            self.extend_linear_stops(1)
        if end:
            while self.extend_linear_stops(64):
                pass
        if not self._linear_stops:
            return self.command_with_boundaries("MoveEnd" if end else "MoveStart")
        if not end:
            first = self._linear_stops[0]
            self._go_to(first.node_id)
            self._linear_index = 0
            self._edge_stop("MovePrevious", first.node_id, "start of math")
            return "start of math"
        index = len(self._linear_stops) - 1
        stop = self._linear_stops[index]
        self._go_to(stop.node_id)
        self._boundary_stop = stop.boundary
        self._linear_index = index
        return stop.speech

    @property
    def linear_position_known(self) -> bool:
        """Left/Right from here need no search: the cursor is on a known stop.

        True after arriving by Left/Right from the start; False after a jump
        (Home, End, Up/Down, a click) to somewhere not discovered yet.
        """
        current_id = self.current_id
        if self._linear_index is not None and self._linear_index < len(self._linear_stops):
            if self._linear_stops[self._linear_index].node_id == current_id:
                return True
        return any(stop.node_id == current_id for stop in self._linear_stops)

    @property
    def linear_ready(self) -> bool:
        """Every linear stop is known, so Left/Right need no MathCAT search."""
        return self._linear_done

    def linear_stops_job(self) -> Callable[[], tuple[_LinearStop, ...]]:
        """A function computing this expression's linear stops on another thread.

        It builds its own navigator there: MathCAT keeps all state in
        thread-locals, and the binding releases the GIL, so the UI thread
        stays free. Hand the result back with `adopt_linear_stops`.
        """
        mathml = self.mathml
        navigator_class = type(self)
        settings = (
            self.language,
            self.speech_style,
            self.verbosity,
            self.recognized_functions,
            self.auto_zoom_out,
            self.boundary_stops,
            self.invisible_operator_stops,
            self.decimal_separator,
        )

        def job() -> tuple[_LinearStop, ...]:
            (
                language,
                speech_style,
                verbosity,
                recognized_functions,
                auto_zoom_out,
                boundary_stops,
                invisible_operator_stops,
                decimal_separator,
            ) = settings
            worker = navigator_class(
                language=language,
                speech_style=speech_style,
                verbosity=verbosity,
                recognized_functions=recognized_functions,
                auto_zoom_out=auto_zoom_out,
                boundary_stops=boundary_stops,
                invisible_operator_stops=invisible_operator_stops,
                decimal_separator=decimal_separator,
            )
            worker.load(mathml, speak=False)
            while worker.extend_linear_stops(64):
                pass
            return tuple(worker._linear_stops)

        return job

    def adopt_linear_stops(self, mathml: str, stops: tuple[_LinearStop, ...]) -> bool:
        """Take stops from `linear_stops_job`, unless the expression changed since.

        Any stops already discovered here are a prefix of the same sequence,
        so the current `_linear_index` stays valid.
        """
        if mathml != self.mathml or not stops:
            return False
        if self.structure is None or any(self.structure.node(stop.node_id) is None for stop in stops):
            # The worker's MathCAT canonicalized the same MathML once more and
            # gave the nodes it adds (`f'(x)`'s function application) new ids:
            # those stops point at nothing here. They are built here instead.
            return False
        self._linear_stops = list(stops)
        self._linear_done = True
        return True

    def _linear_position(self) -> int | None:
        current_id = self.current_id
        stops = self._linear_stops
        if self._linear_index is not None and self._linear_index < len(stops):
            if stops[self._linear_index].node_id == current_id:
                return self._linear_index
        # Arrived some other way (Up/Down, Home, End, a click): the first stop
        # there, discovering further stops until it is found -- within a time
        # budget, since that costs one slow MathCAT call per stop. Past it the
        # caller falls back to a plain step and the background fill catches up.
        deadline = time.monotonic() + _LINEAR_SEARCH_BUDGET
        searched = 0
        while time.monotonic() < deadline:
            matches = [index for index in range(searched, len(stops)) if stops[index].node_id == current_id]
            if matches:
                # Boundary stops share the node of the item after them: land
                # on the item itself, not on "start fraction" before it.
                return next((index for index in matches if stops[index].boundary is None), matches[0])
            searched = len(stops)
            if self._linear_done or (not self.extend_linear_stops(1) and len(stops) == searched):
                return self._first_stop_inside(current_id)
        return None

    def _first_stop_inside(self, identifier: str) -> int | None:
        """On a node no stop stands on (a whole structure, an intent-only node of a sum): its first leaf's stop."""
        if self.structure is None:
            return None
        base = _INTENT_NODE.match(identifier)
        node = self.structure.node(base.group(1) if base else identifier)
        if node is None:
            return None
        inside = {
            leaf.identifier
            for leaf in self.structure.find_all(lambda candidate: not candidate.children)
            if leaf is node or any(ancestor is node for ancestor in self.structure.ancestors(leaf.identifier or ""))
        }
        stops = self._linear_stops
        # On a whole structure is at its start: its own "start X" stop, so
        # Right goes on to the first thing inside it.
        own = next(
            (
                index
                for index, stop in enumerate(stops)
                if stop.edge is not None and stop.edge[0] == node.identifier and stop.speech.startswith("start")
            ),
            None,
        )
        first = own if own is not None else next(
            (index for index, stop in enumerate(stops) if stop.node_id in inside), None
        )
        if first is None:
            return None
        stop = stops[first]
        if own is not None:
            position = own
        elif first > 0:
            position = first - 1
        else:
            # Nothing before it: "start of math", so Right reads the first stop.
            self._go_to(stop.node_id)
            self._edge_stop("MovePrevious", stop.node_id, "start of math")
            self._linear_index = 0
            return 0
        self._go_to(stops[position].node_id)
        self._boundary_stop = stops[position].boundary
        return position

    def extend_linear_stops(self, steps: int) -> bool:
        """Build the linear stops if not done yet; always False (all are known after one call).

        Kept with its `steps` argument for the worker-thread preparation
        (`linear_stops_job`), which calls it until it returns False.
        """
        if self._linear_done or self.structure is None or not self.structure.root.identifier:
            self._linear_done = True
            return False
        # Always from the structure. A Right-arrow simulation used to follow
        # MathCAT's own navigation here when structure stops were off, which
        # is wrong in sums and integrals ("in part 1", an "empty" naryand,
        # intent-only nodes it then failed on); the stops are the same, only
        # entering on "start of math" stays the structure-stops setting's.
        self._build_bounded_stops()
        return False

    def _build_bounded_stops(self) -> None:
        """All linear stops at once, from the structure rather than simulated Right.

        Every leaf (identifier, number, operator, ...) MathCAT speaks is a
        stop, and between two leaves each region left gets its own "end X"
        stop (innermost first) and each region entered its own "start X"
        (outermost first), closed by "end ..." stops and "end of math" after
        the last leaf. One ReadCurrent per leaf, ~0.5 ms each.
        """
        structure = self.structure
        assert structure is not None
        saved = (self.current_id, self._boundary_stop, self._ends_announced_at, self._linear_index)
        leaves: list[MathMLNode] = []

        def walk(node: MathMLNode) -> None:
            if node.children:
                # A matrix's own fences read as the whole matrix in MathCAT;
                # "start matrix"/"end matrix" stand for them instead.
                fenced_table = any(child.tag == "mtable" for child in node.children)
                bars = structure.bar_pair_name(node) is not None
                children = node.children
                if node.tag == "mroot" and len(children) == 2:
                    # The index first, as it is said ("cube root of") and written (`√(3&x)`).
                    children = (children[1], children[0])
                for child in children:
                    # A brace, `|x|`'s or `‖x‖`'s bars read as their whole structure;
                    # "start overbrace", "start absolute value" stand for them.
                    if fenced_table and child.tag == "mo" or child.text in ("⏞", "⏟"):
                        continue
                    if bars and child.tag == "mo" and child in (children[0], children[-1]):
                        continue
                    walk(child)
            elif node.identifier:
                leaves.append(node)

        walk(structure.root)
        stops: list[_LinearStop] = []
        previous_entries: tuple[tuple[int, str], ...] = ()
        last_id: str | None = None

        region_nodes: dict[int, str] = {}

        def boundary(speech: str, node_id: str, display_id: str, region: tuple[int, str] | None = None) -> _LinearStop:
            stop = BoundaryStop(speech=speech, pending_speeches=(), resume_command="MoveNext", current_id=node_id)
            edge = None
            if region is not None and region[0] in region_nodes:
                edge = (region_nodes[region[0]], region[1] in _CONTAINER_REGIONS)
            elif region is None and structure.root.identifier and speech == "end of math":
                edge = (structure.root.identifier, True)
            return _LinearStop(node_id, speech, stop, display_id, edge)

        try:
            for leaf in leaves:
                leaf_id = leaf.identifier
                assert leaf_id is not None
                try:
                    self._go_to(leaf_id)
                    speech = self._navigate("ReadCurrent")
                except RuntimeError:
                    speech = " ".join(leaf.content.split())
                if not speech.strip() and leaf.text == "\u00a0":
                    position = structure.table_position(leaf_id)
                    table = structure.node(position.table_id) if position is not None and position.table_id else None
                    if table is not None and structure.table_kind(table) == "equations":
                        continue  # The empty left side of an aligned line ("&=d").
                    # An empty argument (a half-typed integrand) is a place to type, not spacing.
                    speech = "empty"
                if self._skips_invisible_operator(speech):
                    continue
                speech = _INVISIBLE_OPERATOR_NAMES.get(speech.strip(), speech)
                speech = self._leaf_only(leaf, speech)
                # A function name is a single word: "start function name,
                # sine, end function name" would only be noise.
                entries = tuple(
                    entry for entry in self._stop_regions(leaf, leaf_id, region_nodes) if entry[1] != "function name"
                )
                current, previous = set(entries), set(previous_entries)
                for entry in previous_entries:
                    if entry not in current:
                        stops.append(boundary(f"end {entry[1]}", leaf_id, last_id or leaf_id, entry))
                for entry in reversed(entries):
                    if entry not in previous:
                        stops.append(boundary(f"start {entry[1]}", leaf_id, leaf_id, entry))
                stops.append(_LinearStop(leaf_id, speech, None, leaf_id))
                previous_entries, last_id = entries, leaf_id
            if last_id is not None:
                for entry in previous_entries:
                    stops.append(boundary(f"end {entry[1]}", last_id, last_id, entry))
                stops.append(boundary("end of math", last_id, last_id))
        finally:
            current_id, self._boundary_stop, self._ends_announced_at, self._linear_index = saved
            try:
                self._go_to(current_id)
            except RuntimeError:
                pass  # An intent-only node (e.g. "...-fixity-1" after ZoomIn into a sum).
        self._linear_stops = stops
        self._linear_done = True

    def _stop_regions(self, leaf: MathMLNode, leaf_id: str, nodes: dict[int, str]) -> list[tuple[int, str]]:
        """The leaf's regions, innermost first, with matrix rows and cells as regions too.

        A flat "1 0 0 0 1 0" says nothing about a matrix's shape, so each
        row and each cell (named by its column) gets "start"/"end" stops.
        `nodes` collects each region's node id, by region key.
        """
        structure = self.structure
        assert structure is not None
        regions = structure.region_entries(leaf_id)
        entries: list[tuple[int, str]] = []
        for candidate in (leaf,) + structure.ancestors(leaf_id):
            if candidate.identifier:
                nodes[id(candidate)] = candidate.identifier
            entries.extend(entry for entry in regions if entry[0] == id(candidate))
            if candidate.tag in {"mtr", "mtd"} and candidate.identifier:
                parent = structure.parent_by_id.get(candidate.identifier)
                siblings = [child for child in parent.children if child.tag == candidate.tag] if parent else []
                index = next((i for i, child in enumerate(siblings, start=1) if child is candidate), None)
                label = self._table_part_label(candidate, index)
                if label is not None:
                    entries.append((id(candidate), label))
        return entries

    def _leaf_only(self, leaf: MathMLNode, speech: str) -> str:
        """A leaf's own words where MathCAT reads more: "−" of "−x" says "negative x", `ⅆ` its whole term.

        An interval's or a set's parens, brackets, braces and commas read as
        the whole ("the open interval from a to b"); they say their own name,
        as MathCAT reads the character alone (`mathcat_lone`).
        """
        intent = leaf.attributes.get("intent", "")
        if re.fullmatch(r"[A-Za-z][A-Za-z-]*", intent):
            return intent.replace("-", " ")  # `ⅆ` given intent="d" (prepare_for_mathcat).
        text = leaf.text.strip()
        if text in ("−", "-") and speech.startswith("negative "):
            return "negative"
        if leaf.tag == "mo" and text in _FENCES_AND_SEPARATORS and len(speech.split()) > 3:
            return self.character_speech(text)
        if text in FUNCTION_SCRIPTS and len(speech.split()) > 2:
            # `log`/`lim` read the whole "the log base 2" / "the limit as x
            # approaches 0", then the base or condition again: just the name.
            return self.character_speech(text)
        return speech

    def _table_part_label(self, part: MathMLNode, index: int | None) -> str | None:
        """A row/cell region's name: "equation 2" and no columns in an equation array,
        "case 2" with "value"/"condition" in cases, "row 2"/"column 1" in a matrix."""
        structure = self.structure
        if index is None or structure is None:
            return None
        table = part
        while table is not None and table.tag != "mtable":
            table = structure.parent_by_id.get(table.identifier or "")
        kind = structure.table_kind(table) if table is not None else "matrix"
        if part.tag == "mtr":
            return {"equations": f"equation {index}", "cases": f"case {index}"}.get(kind, f"row {index}")
        if kind == "equations":
            return None  # "&" only aligns the lines: its columns mean nothing to a listener.
        if kind == "cases":
            return "value" if index == 1 else "condition"
        return f"column {index}"

    def leaf_speech(self, leaf_id: str) -> str | None:
        """How the linear stops read a leaf by itself, if they have it."""
        for stop in self._linear_stops:
            if stop.node_id == leaf_id and stop.boundary is None:
                return stop.speech
        return None

    def plain_leaf_stop(self) -> str | None:
        """The leaf a linear stop stands on when it is a plain item (typing goes right after it).

        None on a "start X"/"end X"/"start of math" stop, or off the stops.
        """
        if self.structure is None or self._boundary_stop is not None or self._structural_edge is not None:
            return None
        index = self._linear_position()
        if index is None:
            return None
        stop = self._linear_stops[index]
        node = self.structure.node(stop.node_id)
        if stop.boundary is not None or node is None or node.children:
            return None
        return stop.node_id
