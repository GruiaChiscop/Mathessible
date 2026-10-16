"""What the MathCAT navigator's parts share: stop types, speech cleanup, table names."""

from __future__ import annotations

import re
from dataclasses import dataclass


# MathCAT starts some phrases with a separator meant to follow other speech,
# e.g. a matrix row read on its own comes back as "; row 1; a, b".
_LEADING_SEPARATORS = re.compile(r"^[\s;,]+")
# Commands that step forward onto the node after a boundary stop. A stop
# raised by one of them is resumed (the current node read) by either one,
# since both mean "go on into what comes next".
_FORWARD_STEPS = frozenset({"MoveNext", "ZoomIn"})


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
# Leaves MathCAT may read as their whole interval or set (see `_leaf_only`).
_FENCES_AND_SEPARATORS = frozenset("()[]{}⟨⟩,;")
# Cell commands as (row, column) steps.
_CELL_STEPS = {
    "MoveCellNext": (0, 1),
    "MoveCellPrevious": (0, -1),
    "MoveCellDown": (1, 0),
    "MoveCellUp": (-1, 0),
}


def _table_names(kind: str) -> tuple[str, str]:
    """What a table's rows and columns are called: (row, column)."""
    return {"cases": ("case", "column"), "equations": ("equation", "column")}.get(kind, ("row", "column"))


def _clean_speech(speech: str) -> str:
    return _LEADING_SEPARATORS.sub("", speech)
