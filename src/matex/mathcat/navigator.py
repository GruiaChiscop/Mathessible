from __future__ import annotations

import importlib
from dataclasses import dataclass, field

from matex.editing.source_map import leaf_nodes
from matex.mathcat.common import (
    _FORWARD_STEPS,
    _INTENT_NODE,
    _INVISIBLE_OPERATOR_NAMES,
    _INVISIBLE_OPERATORS,
    BoundaryStop,
    _clean_speech,
    _LinearStop,
)
from matex.mathcat.lone import lone_speech, warm_up
from matex.mathcat.mathml_model import MathMLDocument, TablePosition
from matex.mathcat.prepare import prepare_for_mathcat
from matex.mathcat.stops import LinearStopsMixin
from matex.mathcat.structural import StructuralNavigationMixin
from matex.mathcat.tables import TableNavigationMixin
from matex.settings import DEFAULT_RECOGNIZED_FUNCTIONS


@dataclass(slots=True)
class MathCatNavigator(LinearStopsMixin, StructuralNavigationMixin, TableNavigationMixin):
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
    # MathCAT's DecimalSeparator: with "," it reads `1,5` as one number
    # ("1,5"); with "." it took the comma for a thousands separator ("15").
    decimal_separator: str = ","
    # MathCAT's BrailleCode for the braille strip ("Nemeth", "UEB", ...).
    braille_code: str = "Nemeth"
    _native: object = field(init=False, repr=False)
    mathml: str = field(default="", init=False)
    structure: MathMLDocument | None = field(default=None, init=False)
    _boundary_stop: BoundaryStop | None = field(default=None, init=False, repr=False)
    _ends_announced_at: str | None = field(default=None, init=False, repr=False)
    # Linear navigation's stops, in Right-arrow order (see `linear_command`),
    # built from the structure all at once (`_build_bounded_stops`).
    _linear_stops: list[_LinearStop] = field(default_factory=list, init=False, repr=False)
    _linear_done: bool = field(default=False, init=False, repr=False)
    _linear_index: int | None = field(default=None, init=False, repr=False)
    # "start"/"end" while on a structural level's edge stop; the cursor is
    # then on that level's first/last item.
    _structural_edge: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        import matex_mathcat

        self._native = matex_mathcat
        self._native.initialize(self.language, self.speech_style, self.verbosity)
        # MathCAT's start on the lone-character thread, paid now in the background.
        warm_up(self.language, self.speech_style, self.verbosity)

    def character_speech(self, character: str) -> str:
        """MathCAT's reading of one character alone (`mathcat_lone`), in this navigator's language."""
        return lone_speech(character, self.language, self.speech_style, self.verbosity)

    def load(self, mathml: str, keep_position: bool = False, speak: bool = True) -> str:
        """Load an expression; `keep_position` puts the cursor back on the
        same node when it still exists (a settings change reloads the same
        MathML, and MathCAT would otherwise start over at the whole math).

        Returns the whole expression's speech; `speak=False` skips it (a
        third of a reload's time on a long equation) and returns "".
        """
        previous_id = self.current_id if keep_position and self.structure is not None else None
        self._boundary_stop = None
        self._ends_announced_at = None
        self._linear_stops = []
        self._linear_done = False
        self._linear_index = None
        self._native.preference("AutoZoomOut", "true" if self.auto_zoom_out else "false")
        self._native.preference("DecimalSeparator", self.decimal_separator)
        self._native.preference("BrailleCode", self.braille_code)
        self.mathml = self._native.set_expression(prepare_for_mathcat(mathml))
        self.structure = MathMLDocument.parse(
            self.mathml,
            recognized_functions=self.recognized_functions,
        )
        speech = _clean_speech(self._native.speak_expression()) if speak else ""
        if previous_id is not None and self.structure.node(previous_id) is not None:
            self._go_to(previous_id)
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
                self._go_to(first.node_id)
                self._linear_index = 0
                self._edge_stop("MovePrevious", first.node_id, "start of math")
            return speech
        if entering and self.structure is not None and self.structure.node(self.current_id) is None:
            # MathCAT entered a sum or an integral on a node of its intent
            # ("...-fixity-1"), which nothing can go back to: its first item.
            items = self._level_items(self.structure.root)
            if items and items[0].identifier:
                self._go_to(items[0].identifier)
                speech = self._current_reading()
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
        try:
            speech = self._navigate(command)
        except RuntimeError:
            if command not in ("MoveStart", "MoveEnd") or self.structure is None:
                raise
            # MathCAT failed on an intent-only node: the first/last leaf instead.
            leaves = [leaf for leaf in leaf_nodes(self.structure) if leaf.identifier and leaf.text.strip()]
            if not leaves:
                raise
            self._go_to((leaves[-1] if command == "MoveEnd" else leaves[0]).identifier)
            speech = self._current_reading()
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
        if not speech.strip():
            # MathCAT moved onto a node it says nothing for (inside a sum's or
            # an integral's intent): read where it is instead of silence.
            speech = self._current_reading()
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

    def _go_to(self, identifier: str) -> None:
        """Put MathCAT's cursor on a node; an intent-only id goes to the node it came from.

        Zooming into a sum or an integral lands MathCAT on a node of its own
        intent ("<id>-fixity-1", "<id>-indexed-by"), which `set_navigation`
        cannot find again ("not found in MathML"): the stops recorded it,
        and going back to it failed.
        """
        try:
            self._native.set_navigation(identifier, 0)
        except RuntimeError:
            base = _INTENT_NODE.match(identifier)
            if base is None:
                raise
            self._native.set_navigation(base.group(1), 0)

    def _current_reading(self) -> str:
        """The current node read again, else its text: never an empty announcement."""
        try:
            speech = self._navigate("ReadCurrent")
        except RuntimeError:
            speech = ""
        if speech.strip():
            return speech
        node = self.structure.node(self.current_id) if self.structure is not None else None
        text = " ".join(node.content.split()) if node is not None else ""
        return text or "empty"

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
        self._go_to(previous_id)
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
            return "start of " + speech[len("end of ") :]
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

    def _skips_invisible_operator(self, text: str) -> bool:
        if text.strip(_INVISIBLE_OPERATORS + " \t\n"):
            return False
        return not (self.invisible_operator_stops and text.strip() in _INVISIBLE_OPERATOR_NAMES)

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
        at_start = stop is not None and stop.speech == "start of math"
        if at_start and self.structure is not None and self.structure.root.identifier:
            # Before everything, not inside the first numerator or radicand.
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
        self._go_to(identifier)

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


# Said when professional view is asked for without the native MathCAT extension.
MATHCAT_MISSING = "Professional view needs MathCAT, which could not be loaded. Run scripts/bootstrap.sh"


def mathcat_load_error() -> str | None:
    """Why the native MathCAT extension cannot be loaded, or None when it can."""
    try:
        importlib.import_module("matex_mathcat")
    except ImportError as error:
        return str(error)
    return None


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
