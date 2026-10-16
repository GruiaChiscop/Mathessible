from __future__ import annotations

import re
import time
from xml.etree import ElementTree
from collections.abc import Callable
from dataclasses import dataclass, field

from .ast import Path, path_from_mathml_id
from .math_templates import ARROWS
from .mathml_model import MathMLDocument, MathMLNode, TablePosition
from .settings import DEFAULT_RECOGNIZED_FUNCTIONS
from .source_map import leaf_nodes


# MathCAT starts some phrases with a separator meant to follow other speech,
# e.g. a matrix row read on its own comes back as "; row 1; a, b".
_LEADING_SEPARATORS = re.compile(r"^[\s;,]+")
# Commands that step forward onto the node after a boundary stop. A stop
# raised by one of them is resumed (the current node read) by either one,
# since both mean "go on into what comes next".
_FORWARD_STEPS = frozenset({"MoveNext", "ZoomIn"})
_DETERMINANT_INTENT = re.compile(r'intent="determinant\(\$([\w-]+)\)"')


@dataclass(frozen=True, slots=True)
class BoundaryStop:
    speech: str
    pending_speeches: tuple[str, ...]
    resume_command: str
    current_id: str
    read_current_on_next_navigation: bool = False


@dataclass(frozen=True, slots=True)
class _LinearStop:
    node_id: str
    speech: str
    boundary: BoundaryStop | None
    # What to highlight: at an "end ..." stop MathCAT is already on the next
    # node, but what was just announced is the structure being left.
    display_id: str
    # A "start X"/"end X" stop: X's node, and whether typing there goes
    # outside it (a whole structure) or inside at its edge (a role, a cell).
    edge: tuple[str, bool] | None = None


# Regions that are whole structures: typing at their "start"/"end" stop goes
# before/after the structure; at a role's ("end numerator") it stays inside.
_CONTAINER_REGIONS = frozenset(
    {"fraction", "square root", "root", "matrix", "determinant", "cases", "equations", "absolute value", "norm", "overbrace", "underbrace"}
)


_MAX_LINEAR_STOPS = 2000
_INVISIBLE_OPERATORS = "\u2061\u2062\u2063\u2064"
# MathCAT reads these back as the bare character, which not every screen
# reader names (function application is spoken as "of", so is not here).
_INVISIBLE_OPERATOR_NAMES = {
    "\u2062": "invisible times",
    "\u2063": "invisible separator",
    "\u2064": "invisible plus",
}
_LINEAR_SEARCH_BUDGET = 0.25  # seconds


@dataclass(slots=True)
class MathCatNavigator:
    """Thin stateful adapter around MathCAT's navigation API."""

    language: str = "en"
    speech_style: str = "SimpleSpeak"
    verbosity: str = "Medium"
    recognized_functions: tuple[str, ...] = DEFAULT_RECOGNIZED_FUNCTIONS
    # MathCAT's AutoZoomOut: at the last item inside a structure the user
    # zoomed into, Right either moves on out of it (True) or stays and says
    # "end of numerator" until the user zooms out (False). Applied on load,
    # since MathCAT preferences are process-wide, not per navigator.
    auto_zoom_out: bool = True
    # Linear navigation only: build the stops from the structure itself, so
    # every structure gets standalone "start X" / "end X" stops and the math
    # its own "start of math" before the first item (see `_build_bounded_stops`).
    boundary_stops: bool = False
    # Structural navigation only: Left/Right walk the items of one level with
    # standalone "start X"/"end X" stops around them, Down/Up change level
    # (see `structural_command`).
    structural_stops: bool = False
    # Invisible times/separator/plus get a stop of their own in both
    # navigation modes, read by name ("invisible times").
    invisible_operator_stops: bool = False
    _native: object = field(init=False, repr=False)
    mathml: str = field(default="", init=False)
    structure: MathMLDocument | None = field(default=None, init=False)
    _boundary_stop: BoundaryStop | None = field(default=None, init=False, repr=False)
    _ends_announced_at: str | None = field(default=None, init=False, repr=False)
    # Linear navigation's stops, in Right-arrow order (see `linear_command`),
    # discovered incrementally from the start of the math. `_linear_frontier`
    # is the simulated cursor state at the last stop found so far.
    _linear_stops: list[_LinearStop] = field(default_factory=list, init=False, repr=False)
    _linear_done: bool = field(default=False, init=False, repr=False)
    _linear_frontier: tuple[str, BoundaryStop | None, str | None] | None = field(
        default=None, init=False, repr=False
    )
    _linear_index: int | None = field(default=None, init=False, repr=False)
    # "start"/"end" while on a structural level's edge stop; the cursor is
    # then on that level's first/last item.
    _structural_edge: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        import matex_mathcat

        self._native = matex_mathcat
        self._native.initialize(self.language, self.speech_style, self.verbosity)

    def load(self, mathml: str, keep_position: bool = False) -> str:
        """Load an expression; `keep_position` puts the cursor back on the
        same node when it still exists (a settings change reloads the same
        MathML, and MathCAT would otherwise start over at the whole math)."""
        previous_id = self.current_id if keep_position and self.structure is not None else None
        self._boundary_stop = None
        self._ends_announced_at = None
        self._linear_stops = []
        self._linear_done = False
        self._linear_frontier = None
        self._linear_index = None
        self._native.preference("AutoZoomOut", "true" if self.auto_zoom_out else "false")
        self.mathml = self._native.set_expression(prepare_for_mathcat(mathml))
        self.structure = MathMLDocument.parse(
            self.mathml,
            recognized_functions=self.recognized_functions,
        )
        speech = _clean_speech(self._native.speak_expression())
        if previous_id is not None and self.structure.node(previous_id) is not None:
            self._native.set_navigation(previous_id, 0)
        return speech

    def command(self, command: str) -> str:
        entering = command == "ZoomIn" and not self._linear_stops and self._at_root()
        self._boundary_stop = None
        self._linear_index = None
        self._structural_edge = None
        if entering and self.structural_stops and self.structure is not None:
            items = self._level_items(self.structure.root)
            if items:
                # Enter on "start of math", reading the whole math.
                speech = _clean_speech(self._native.speak_expression())
                edge = self._structural_enter(self.structure.root, items)
                return speech or edge
        speech = self._navigate(command)
        if entering and self.boundary_stops:
            # Enter on the "start of math" stop: Right then reads the first
            # item (or "start fraction", ...) instead of skipping past it.
            # MathCAT's ZoomIn speech ("in numerator; ...", nothing at all for
            # a sum) would not describe that spot, so read the whole math.
            self.extend_linear_stops(1)
            if self._linear_stops:
                speech = _clean_speech(self._native.speak_expression()) or speech
                first = self._linear_stops[0]
                self._native.set_navigation(first.node_id, 0)
                self._linear_index = 0
                self._edge_stop("MovePrevious", first.node_id, "start of math")
            return speech
        if entering:
            # Zooming in from the whole math is exactly the first linear stop;
            # record it rather than paying a MathCAT call for it again later.
            self._linear_stops.append(_LinearStop(self.current_id, speech, None, self.current_id))
            self._linear_frontier = (self.current_id, None, None)
            self._linear_index = 0
        return speech

    def _at_root(self) -> bool:
        root = self.structure.root.identifier if self.structure is not None else None
        return bool(root) and self.current_id == root

    def _navigate(self, command: str) -> str:
        return _clean_speech(self._native.navigate(command))

    def command_with_boundaries(self, command: str) -> str:
        if self._boundary_stop is not None:
            speech = self._resume_boundary(command)
            if speech is not None:
                return speech

        previous_id = self.current_id
        speech = self._navigate(command)
        held = self._hold_inside_zoomed_group(command, previous_id)
        if held is not None:
            return held
        if self.structure is None or command not in {
            "MoveNext",
            "MovePrevious",
            "MoveStart",
            "MoveEnd",
            "MoveLineStart",
            "MoveLineEnd",
            "ZoomIn",
            "ZoomOut",
        }:
            return speech
        current_id = self.current_id
        if command in {"MoveNext", "MovePrevious"} and current_id == previous_id:
            speech = self._edge_speech(command, current_id, speech)
            if command == "MoveNext":
                speech = self._announce_math_end(current_id, speech)
            if self._boundary_stop is None:
                self._edge_stop(command, current_id, speech)
            return speech
        # Zooming into a structure or out onto it: the user is already on
        # (or was just on) that structure, so its own region is not news.
        ignore_id = previous_id if command == "ZoomIn" else current_id if command == "ZoomOut" else None
        exited = self.structure.exited_regions(previous_id, current_id, ignore_id)
        entered = self.structure.entered_regions(previous_id, current_id, ignore_id)
        boundary_speeches: list[str] = []
        if command in {"MoveNext", "MoveEnd", "MoveLineEnd", "ZoomOut"}:
            boundary_speeches.extend(f"end {label}" for label in exited)
        if command in {"MoveNext", "MovePrevious", "MoveStart", "MoveEnd", "MoveLineStart", "MoveLineEnd", "ZoomIn"}:
            boundary_speeches.extend(f"start {label}" for label in reversed(entered))
        if boundary_speeches:
            self._boundary_stop = BoundaryStop(
                speech=boundary_speeches[0],
                pending_speeches=tuple(boundary_speeches[1:]),
                resume_command=command,
                current_id=current_id,
                read_current_on_next_navigation=True,
            )
            return boundary_speeches[0]
        boundaries = [f"end {label}" for label in exited]
        boundaries.extend(f"start {label}" for label in entered)
        if not boundaries:
            return speech
        boundary = "; ".join(boundaries)
        return f"{boundary}; {speech}" if speech else boundary

    def _hold_inside_zoomed_group(self, command: str, previous_id: str) -> str | None:
        """With auto zoom out off, undo a Left/Right that left a zoomed-into group.

        MathCAT's own AutoZoomOut only stops at the edge of a whole 2D
        structure: from the last item inside a numerator, Right still lands
        in the denominator. The user asked to stay put there until they zoom
        out themselves, so the move is reverted and the edge announced.
        """
        if self.auto_zoom_out or self.structure is None or command not in {"MoveNext", "MovePrevious"}:
            return None
        left = self.structure.left_zoomed_regions(previous_id, self.current_id)
        if not left:
            return None
        self._native.set_navigation(previous_id, 0)
        edge = "end" if command == "MoveNext" else "start"
        speech = f"{edge} of {left[0]}"
        self._edge_stop(command, previous_id, speech)
        return speech

    def _edge_stop(self, command: str, current_id: str, speech: str) -> None:
        """Make an edge Left/Right could not cross ("start of math") a stop of its own.

        MathCAT stays on the node next to the edge, so without this the
        opposite arrow moved on from that node and skipped it: Left at the
        start said "start of math", then Right went straight to the second
        item. Now the opposite arrow comes back to that node and reads it.
        Speech that already names the node ("start of numerator; a") is not
        a separate stop: the node was read, so the opposite arrow moves on.
        """
        if "; " in speech:
            return
        back = "MoveNext" if command == "MovePrevious" else "MovePrevious"
        self._boundary_stop = BoundaryStop(
            speech=speech,
            pending_speeches=(),
            resume_command=back,
            current_id=current_id,
            read_current_on_next_navigation=True,
        )

    def _edge_speech(self, command: str, current_id: str, speech: str) -> str:
        """Patch MathCAT's speech when Left/Right could not move (en rules).

        With AutoZoomOut off, MathCAT's rules (Rules/Languages/en/navigate.yaml)
        say nothing at the very end of the math, read the current node
        instead of "start of math" at the very beginning, and say "end of
        numerator" on Left at the *start* of a numerator (the
        move-previous-no-auto-zoom-at-edge rule reuses 'end of'). Fixed here
        rather than by editing the MathCAT submodule's rules.
        """
        if command == "MoveNext":
            return speech or "end of math"
        if speech.startswith("end of "):
            return "start of " + speech[len("end of "):]
        if (
            self.structure is not None
            and not speech.startswith("start of")
            and self.structure.is_at_math_edge(current_id, end=False)
        ):
            return "start of math"
        return speech

    def _announce_math_end(self, current_id: str, speech: str) -> str:
        """Right at the very end: close every enclosing region before "end of math".

        MathCAT only says "end of math" there, so ending inside a denominator
        never said "end denominator". With AutoZoomOut off, MathCAT stops at
        the structure's own edge instead ("end of denominator") and nothing
        has been left yet, so nothing is added. Announced once per node: a
        further Right just repeats MathCAT's own speech.
        """
        if not self.auto_zoom_out or self.structure is None or current_id == self._ends_announced_at:
            return speech
        self._ends_announced_at = current_id
        speeches = [f"end {label}" for label in self.structure.regions(current_id)]
        if not speeches:
            return speech
        if speech:
            speeches.append(speech)
        self._boundary_stop = BoundaryStop(
            speech=speeches[0],
            pending_speeches=tuple(speeches[1:]),
            resume_command="MoveNext",
            current_id=current_id,
            read_current_on_next_navigation=False,
        )
        return speeches[0]

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
        self._native.set_navigation(stop.node_id, 0)
        self._boundary_stop = stop.boundary
        self._linear_index = target
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
        settings = (
            self.language,
            self.speech_style,
            self.verbosity,
            self.recognized_functions,
            self.auto_zoom_out,
            self.boundary_stops,
            self.invisible_operator_stops,
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
            ) = settings
            worker = MathCatNavigator(
                language=language,
                speech_style=speech_style,
                verbosity=verbosity,
                recognized_functions=recognized_functions,
                auto_zoom_out=auto_zoom_out,
                boundary_stops=boundary_stops,
                invisible_operator_stops=invisible_operator_stops,
            )
            worker.load(mathml)
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
        self._linear_stops = list(stops)
        self._linear_done = True
        self._linear_frontier = None
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
                return None
        return None

    def extend_linear_stops(self, steps: int) -> bool:
        """Discover up to `steps` more linear stops; False once all are known.

        Runs the Right-arrow simulation from the saved frontier and puts the
        real cursor (and boundary state) back afterwards, so it is safe to
        call between key presses, e.g. from an idle timer.
        """
        if self._linear_done or self.structure is None or not self.structure.root.identifier:
            self._linear_done = True
            return False
        if self.boundary_stops:
            self._build_bounded_stops()
            return False
        saved = (self.current_id, self._boundary_stop, self._ends_announced_at, self._linear_index)
        stops = self._linear_stops
        try:
            if not stops:
                self._boundary_stop = None
                self._ends_announced_at = None
                self._native.set_navigation(self.structure.root.identifier, 0)
                speech = self._navigate("ZoomIn")
                stops.append(_LinearStop(self.current_id, speech, None, self.current_id))
                self._linear_frontier = (self.current_id, None, None)
                steps -= 1
            for _ in range(max(0, steps)):
                frontier_id, self._boundary_stop, self._ends_announced_at = self._linear_frontier
                self._native.set_navigation(frontier_id, 0)
                speech = self._linear_step("MoveNext")
                display_id = stops[-1].display_id if speech.startswith("end ") else self.current_id
                stop = _LinearStop(self.current_id, speech, self._boundary_stop, display_id)
                if (stop.node_id == stops[-1].node_id and stop.speech == stops[-1].speech) or len(
                    stops
                ) >= _MAX_LINEAR_STOPS:
                    self._linear_done = True  # Right at the very end only repeats itself.
                    break
                stops.append(stop)
                self._linear_frontier = (self.current_id, self._boundary_stop, self._ends_announced_at)
        finally:
            current_id, self._boundary_stop, self._ends_announced_at, self._linear_index = saved
            self._native.set_navigation(current_id, 0)
        return not self._linear_done

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
        try:
            speech = self._navigate("ReadCurrent")
        except RuntimeError:
            speech = " ".join(node.content.split())
        speech = _INVISIBLE_OPERATOR_NAMES.get(speech.strip(), speech)
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
        if named == "row" and node.identifier:
            table = structure.parent_by_id.get(node.identifier)
            rows = [child for child in table.children if child.tag == "mtr"] if table is not None else []
            if any(row is node for row in rows):
                return f"row {next(i for i, row in enumerate(rows, start=1) if row is node)}"
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

    def _skips_invisible_operator(self, text: str) -> bool:
        if text.strip(_INVISIBLE_OPERATORS + " \t\n"):
            return False
        return not (self.invisible_operator_stops and text.strip() in _INVISIBLE_OPERATOR_NAMES)

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
                for child in node.children:
                    # A brace, `|x|`'s or `‖x‖`'s bars read as their whole structure;
                    # "start overbrace", "start absolute value" stand for them.
                    if fenced_table and child.tag == "mo" or child.text in ("⏞", "⏟"):
                        continue
                    if bars and child.tag == "mo" and child in (node.children[0], node.children[-1]):
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
                    self._native.set_navigation(leaf_id, 0)
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
                self._native.set_navigation(current_id, 0)
            except RuntimeError:
                pass  # An intent-only node (e.g. "...-fixity-1" after ZoomIn into a sum).
        self._linear_stops = stops
        self._linear_done = True
        self._linear_frontier = None

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

    @staticmethod
    def _leaf_only(leaf: MathMLNode, speech: str) -> str:
        """A leaf's own words where MathCAT reads more: "−" of "−x" says "negative x", `ⅆ` its whole term."""
        intent = leaf.attributes.get("intent", "")
        if re.fullmatch(r"[A-Za-z][A-Za-z-]*", intent):
            return intent.replace("-", " ")  # `ⅆ` given intent="d" (prepare_for_mathcat).
        if leaf.text.strip() in ("−", "-") and speech.startswith("negative "):
            return "negative"
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

    def _linear_step(self, command: str) -> str:
        if command != "MoveNext":
            return self.command_with_boundaries(command)
        if self._boundary_stop is not None:
            speech = self._resume_boundary(command, descend=True)
            if speech is not None:
                return speech
        if self._can_zoom_into_current():
            return self.command_with_boundaries("ZoomIn")
        return self.command_with_boundaries(command)

    def _resume_boundary(self, command: str, descend: bool = False) -> str | None:
        if self._boundary_stop is None:
            return None
        boundary = self._boundary_stop
        if command == "ReadCurrent":
            return boundary.speech
        if not self._resumes(boundary, command) or self.current_id != boundary.current_id:
            # A different direction (Left after a stop raised by Right, Home,
            # Up, ...) is a real move away from the boundary, not a request
            # to step onto the node behind it: let the caller execute it.
            self._boundary_stop = None
            return None
        if boundary.pending_speeches:
            self._boundary_stop = BoundaryStop(
                speech=boundary.pending_speeches[0],
                pending_speeches=boundary.pending_speeches[1:],
                resume_command=boundary.resume_command,
                current_id=boundary.current_id,
                read_current_on_next_navigation=boundary.read_current_on_next_navigation,
            )
            return self._boundary_stop.speech
        self._boundary_stop = None
        if not boundary.read_current_on_next_navigation:
            return None
        return self._navigate("ZoomIn") if descend and self._can_zoom_into_current() else self._navigate("ReadCurrent")

    @staticmethod
    def _resumes(boundary: BoundaryStop, command: str) -> bool:
        if command == boundary.resume_command:
            return True
        return command in _FORWARD_STEPS and boundary.resume_command in _FORWARD_STEPS

    def _can_zoom_into_current(self) -> bool:
        if self.structure is None:
            return False
        node = self.structure.node(self.current_id)
        if node is None:
            return False
        return bool(node.children) and node.tag not in {"math", "mi", "mn", "mo", "mtext"}

    def current_context(self) -> str:
        if self._boundary_stop is not None:
            return f"at {self._boundary_stop.speech}"
        if self.structure is None:
            return "at equation"
        parts: list[str] = []
        position = self.current_table_position
        if position is not None:
            parts.append(f"row {position.row}, column {position.column}")
        parts.extend(f"inside {label}" for label in self.structure.regions(self.current_id))
        return "; ".join(parts) if parts else "at equation"

    def read_current_zone(self) -> str:
        if self._boundary_stop is not None:
            return self._boundary_stop.speech
        if self.structure is None:
            return self.command("ReadCurrent")
        description = self.structure.current_region_description(self.current_id)
        if description is not None:
            return description
        return self.command("ReadCurrent")

    def cell_command(self, command: str) -> str:
        if self.current_table_position is None and self.structure is not None:
            cell_id = self.structure.nearest_first_cell(self.current_id)
            if cell_id is not None:
                # Outside every matrix: jump into the nearest one's first
                # cell rather than trying to reach it by zooming, which only
                # ever descends into the node the cursor is already on.
                self._boundary_stop = None
                self._native.set_navigation(cell_id, 0)
                return self._navigate("ReadCellCurrent")
        return self.command(command)

    def move_to_column_boundary(self, end: bool) -> str:
        position = self.current_table_position
        speech = ""
        if position is None:
            speech = self.cell_command("MoveCellNext")
            position = self.current_table_position
        if position is None:
            return speech
        steps = position.row_count - position.row if end else position.row - 1
        command = "MoveCellDown" if end else "MoveCellUp"
        if steps == 0:
            return self.command("ReadCellCurrent")
        for _ in range(steps):
            speech = self.command(command)
        return speech

    def matrix_location(self) -> tuple[int, int, int] | None:
        """(matrix index in reading order, row, column) of the current cell."""
        position = self.current_table_position
        if position is None or position.table_id is None or self.structure is None:
            return None
        index = self.structure.table_index(position.table_id)
        return None if index is None else (index, position.row, position.column)

    def edit_anchor(self) -> tuple[str, str, bool]:
        """Where typing would go: (node id, "before"/"after", outside).

        On a plain item, after it. On a linear "start X"/"end X" stop,
        before/after X: outside a whole structure ("end fraction"), inside
        at the edge of a role or cell ("end numerator"). On a structural
        level's edge, before/after the structure. `outside` asks the source
        offset to step over the structure's own parens too.
        """
        index = self._linear_index
        if index is not None and index < len(self._linear_stops) and self._boundary_stop is not None:
            stop = self._linear_stops[index]
            if stop.edge is not None and self._boundary_stop is stop.boundary:
                side = "before" if stop.speech.startswith("start") else "after"
                return stop.edge[0], side, stop.edge[1]
        if self._structural_edge is not None and self.structure is not None:
            node = self.structure.node(self.current_id)
            parent = self._level_parent(node) if node is not None else None
            side = "before" if self._structural_edge == "start" else "after"
            if parent is not None and parent.identifier:
                return parent.identifier, side, True
            return self.current_id, side, False
        stop = self._boundary_stop
        if stop is not None and stop.speech == "start of math" and self.structure is not None:
            # Before everything, not inside the first numerator or radicand.
            if self.structure.root.identifier:
                return self.structure.root.identifier, "before", True
        if stop is not None and stop.speech.startswith("start"):
            return stop.current_id or self.current_id, "before", False
        if stop is not None and stop.speech.startswith("end"):
            return self.display_id, "after", False
        # After a whole structure (structural navigation stands on one): outside it.
        node = self.structure.node(self.current_id) if self.structure is not None else None
        return self.current_id, "after", bool(node is not None and node.children)

    def move_to(self, identifier: str) -> None:
        """Put MathCAT's cursor on a node, e.g. one clicked in the rendering."""
        self._boundary_stop = None
        self._linear_index = None
        self._structural_edge = None  # Else a level edge left from before still anchors edits.
        self._native.set_navigation(identifier, 0)

    def move_to_cell(self, index: int, row: int, column: int) -> bool:
        if self.structure is None:
            return False
        target = self.structure.cell_target(index, row, column)
        if target is None:
            return False
        self._boundary_stop = None
        self._linear_index = None
        self._native.set_navigation(target, 0)
        return True

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

    def read_line(self, step: int) -> str:
        """Up/Down as in a text field: the previous (-1) or next (1) row of the table the cursor is in, read whole.

        A row is a matrix row, an equation of an equation array, a case.
        The cursor goes to the end of the same column in it. At the first or
        last row, and outside any table (one line), the current line is read
        again without moving.
        """
        if self.structure is None:
            return ""
        position = self.current_table_position
        table = self.structure.node(position.table_id) if position is not None and position.table_id else None
        if position is None or table is None:
            return _clean_speech(self._native.speak_expression())
        rows = [child for child in table.children if child.tag == "mtr"]
        target = position.row + step if 1 <= position.row + step <= len(rows) else position.row
        row = rows[target - 1]
        cells = [child for child in row.children if child.tag == "mtd"]
        if row.identifier is None or not cells:
            return _clean_speech(self._native.speak_expression())
        self._native.set_navigation(row.identifier, 0)
        speech = self._navigate("ReadCurrent")
        cell = cells[min(position.column, len(cells)) - 1]
        inside = [
            leaf
            for leaf in leaf_nodes(self.structure)
            if any(ancestor is cell for ancestor in self.structure.ancestors(leaf.identifier or ""))
        ]
        target_id = inside[-1].identifier if inside else cell.identifier
        self.move_to(target_id or row.identifier)
        return speech

    @property
    def display_id(self) -> str:
        """The node to highlight: `current_id`, except at a linear "end ..." stop."""
        current_id = self.current_id
        if self._linear_index is not None and self._linear_index < len(self._linear_stops):
            stop = self._linear_stops[self._linear_index]
            if stop.node_id == current_id:
                return stop.display_id
        return current_id

    @property
    def current_path(self) -> Path | None:
        identifier = self.current_id
        if identifier == "math-root":
            return ()
        return path_from_mathml_id(identifier)

    @property
    def current_id(self) -> str:
        identifier, _offset = self._native.navigation_id()
        return identifier

    @property
    def current_table_position(self) -> TablePosition | None:
        if self.structure is None:
            return None
        return self.structure.table_position(self.current_id)

    @property
    def current_braille(self) -> str:
        return self._native.navigation_braille()


def prepare_for_mathcat(mathml: str) -> str:
    """Rewrite converter output MathCAT misreads, before it reaches MathCAT.

    UnicodeMathML marks `|■(...)|` as `intent="determinant($a)"` with
    `arg="a"` on the mtable. MathCAT then speaks the table as "2 lines" and
    its cell navigation reads the wrong cell ("row 1, column 1, b"). As a
    plain `:fenced` mrow with no arg, MathCAT infers the determinant itself
    ("the 2 by 2 determinant") and navigates cells correctly.
    """
    for match in list(_DETERMINANT_INTENT.finditer(mathml)):
        argument = re.escape(match.group(1))
        mathml = re.sub(rf'(<mtable\b[^>]*?)\s+arg="{argument}"', r"\1", mathml, count=1)
    mathml = _DETERMINANT_INTENT.sub('intent=":fenced"', mathml)
    # `{■(...)┤` (cases): the converter's ":fenced"/":array" intents hide the
    # piecewise layout; without them MathCAT says "2 cases; case 1; ...".
    mathml = _CASES_INTENTS.sub(r"<mrow><mo>{</mo><mtable", mathml)
    # ...and so does the invisible closing fence `┤` leaves (an `<mo>` holding U+200B).
    mathml = mathml.replace("</mtable><mo>\u200b</mo></mrow>", "</mtable></mrow>")
    # `|x|` carries intent="absolute-value(𝑥)" with the content written into it, so
    # navigating onto x reads the whole thing; MathCAT infers the absolute value itself.
    mathml = _ABSOLUTE_VALUE_INTENT.sub("", mathml)
    # `ⅆ` (\dd) carries intent="ⅆ", read "double-struck italic d"; "d" is what is meant.
    mathml = mathml.replace('intent="ⅆ"', 'intent="d"')
    if any(name in mathml for name in _LARGE_FUNCTIONS) or "⏞" in mathml or "⏟" in mathml:
        mathml = _intent_fixups(mathml)
    return mathml


# max/min/sup/inf with a condition under them read like ∑ ("the max over x of f").
_LARGE_FUNCTIONS = ("max", "min", "sup", "inf", "argmax", "argmin")
_ABSOLUTE_VALUE_INTENT = re.compile(r'\s+intent="absolute-value\([^"$]*\)"')
_CASES_INTENTS = re.compile(r'<mrow intent=":fenced">\s*<mo>\{</mo>\s*<mtable intent=":array\([^)]*\)"')


def _intent_fixups(mathml: str) -> str:
    """Intents the converter does not give (see prepare_for_mathcat); leaves the MathML as is if it does not parse."""
    try:
        root = ElementTree.fromstring(mathml)
    except ElementTree.ParseError:
        return mathml
    changed = False
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        children = list(element)
        if tag in ("msub", "munder") and children and children[0].text in _LARGE_FUNCTIONS and "intent" not in element.attrib:
            element.set("intent", ":largeop")
            changed = True
        if tag in ("mover", "munder") and len(children) == 2 and "intent" not in element.attrib:
            inner = children[0]
            inner_children = list(inner)
            brace = "⏞" if tag == "mover" else "⏟"
            if inner.tag.rsplit("}", 1)[-1] == tag and len(inner_children) == 2 and inner_children[1].text == brace:
                # `⏞(a+b)┴n`: "a plus b, with brace above, labeled n" (MathCAT patch 0003).
                name = "overbrace" if brace == "⏞" else "underbrace"
                element.set("intent", f"{name}($content,$label)")
                inner_children[0].set("arg", "content")
                children[1].set("arg", "label")
                changed = True
    return ElementTree.tostring(root, encoding="unicode") if changed else mathml


def _clean_speech(speech: str) -> str:
    return _LEADING_SEPARATORS.sub("", speech)


def create_mathcat_navigator(
    recognized_functions: tuple[str, ...] = DEFAULT_RECOGNIZED_FUNCTIONS,
    auto_zoom_out: bool = True,
    boundary_stops: bool = False,
    structural_stops: bool = False,
    invisible_operator_stops: bool = False,
) -> MathCatNavigator | None:
    try:
        return MathCatNavigator(
            recognized_functions=recognized_functions,
            auto_zoom_out=auto_zoom_out,
            boundary_stops=boundary_stops,
            structural_stops=structural_stops,
            invisible_operator_stops=invisible_operator_stops,
        )
    except (ImportError, OSError, RuntimeError, ValueError):
        return None
