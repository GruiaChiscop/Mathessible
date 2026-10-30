"""A function's graph explored by ear: what the cursor hears at each x, and what it passes on the way.

The model is AudioFunctions+'s (SONAIRGRAPH, University of Turin), as its
documentation describes it, reimplemented here: the cursor moves along x in
a view of the graph; the function's y there is a tone's pitch, linear from
100 Hz at the view's bottom to 1000 Hz at its top, and x is its place from
left to right (stereo pan). Below the x axis a soft noise plays with it;
where the function is undefined or out of the view there is no tone, and a
sign says so. Moving the cursor, its passing the y axis and the view's edge
each has a sign of its own. In discrete mode y selects one of the chromatic
notes from C3 through C5, struck again each time it changes, so a steep curve
is heard as quick notes and a flat one as a long one. User-created landmarks
are the navigable points of interest.

Nothing here makes sound or knows wx: `GraphExplorer` is the state the
explorer window drives, and `Sound` what the synthesiser is to play.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from mathessible.documents.charts import Chart, ChartError, expression_function, parse_chart
from mathessible.i18n import _

LOWEST, HIGHEST = 100.0, 1000.0  # The tone's pitch at the view's bottom and top, Hz.
STEP = 0.25  # AudioFunctions+'s default stepwise cursor increment.
FLUID_STEP = 0.025  # One keyboard-repeat increment during fluid movement.
ZOOM_IN, ZOOM_OUT = 0.9, 1.1
MOVE = 1.0  # AudioFunctions+ moves the view one coordinate unit (Shift: five).
_DISCRETE_NOTES = 25  # Every semitone from C3 through C5, inclusive.
_C3 = 130.8127826502993
_CHART_BLOCK = re.compile(r"(?ms)^```chart(?:\s+[^\n]*)?\n(?P<chart>.*?)^```[ \t]*$")


@dataclass(frozen=True, slots=True)
class View:
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    def zoomed(self, factor: float, x: bool = True, y: bool = True) -> View:
        """The view enlarged (`factor` < 1: closer) or shrunk around its centre, on one axis or both."""
        x_centre, y_centre = (self.x_min + self.x_max) / 2, (self.y_min + self.y_max) / 2
        x_half, y_half = self.width / 2 * (factor if x else 1), self.height / 2 * (factor if y else 1)
        return View(x_centre - x_half, x_centre + x_half, y_centre - y_half, y_centre + y_half)

    def moved(self, right: float = 0.0, up: float = 0.0) -> View:
        """The view moved by parts of its width and height."""
        dx, dy = right * self.width, up * self.height
        return View(self.x_min + dx, self.x_max + dx, self.y_min + dy, self.y_max + dy)

    def centred(self, x: float) -> View:
        """The view moved so that x is in its middle."""
        return self.moved(right=(x - (self.x_min + self.x_max) / 2) / self.width)


@dataclass(frozen=True, slots=True)
class Point:
    """A landmark or a view boundary the cursor can jump to."""

    kind: str  # "bookmark" or "edge"
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Sound:
    """What is heard at the cursor: a tone (None: no tone, the function undefined or out of the view), where
    it is from left to right (-1 to 1), and whether the noise of negative values plays with it."""

    frequency: float | None
    pan: float
    negative: bool
    strike: bool = False  # Discrete mode: a new note, struck again.
    discrete: bool = False


def function_chart_at(source: str, position: int) -> Chart | None:
    """The function chart fenced around ``position``; data charts and malformed blocks are not explored."""
    position = max(0, min(position, len(source)))
    for found in _CHART_BLOCK.finditer(source):
        if found.start() <= position <= found.end():
            try:
                chart = parse_chart(found.group("chart"))
            except ChartError:
                return None
            return chart if chart.kind == "function" else None
    return None


def default_view(function: Callable[[float], float], x_range: tuple[float, float]) -> View:
    """The view a graph opens in: its x range, and y from the function's values there (the lowest and highest
    of most of them, so that a pole does not flatten the rest), with a margin."""
    return default_view_for((function,), x_range)


def default_view_for(functions: Sequence[Callable[[float], float]], x_range: tuple[float, float]) -> View:
    """A common robust view for every function in a chart, so changing function never makes it silent."""
    start, end = x_range
    if end - start > 100:
        centre = (start + end) / 2
        start, end = centre - 50, centre + 50
    values = sorted(
        y
        for function in functions
        for index in range(401)
        if math.isfinite(y := function(start + (end - start) * index / 400))
    )
    if not values:
        return View(start, end, -10.0, 10.0)
    low, high = values[len(values) // 50], values[-1 - len(values) // 50]
    if high - low < 1e-9:
        low, high = low - 1, high + 1
    margin = (high - low) * 0.1
    low, high = low - margin, high + margin
    if high - low > 100:
        centre = (low + high) / 2
        low, high = centre - 50, centre + 50
    return View(start, end, low, high)


def frequency(y: float, view: View) -> float | None:
    """The tone's pitch for y: linear in the view's height; None when y is out of the view or undefined."""
    if not math.isfinite(y) or not view.y_min <= y <= view.y_max:
        return None
    return LOWEST + (y - view.y_min) / view.height * (HIGHEST - LOWEST)


def pan(x: float, view: View) -> float:
    """Where x is heard: -1 at the view's left edge, 1 at its right."""
    return max(-1.0, min(1.0, -1 + 2 * (x - view.x_min) / view.width))


def scale_note(pitch: float) -> float:
    """Map the continuous 100--1000 Hz range to AudioFunctions+'s C3--C5 chromatic set."""
    normalized = max(0.0, min(1.0, (pitch - LOWEST) / (HIGHEST - LOWEST)))
    index = min(_DISCRETE_NOTES - 1, math.floor(normalized * _DISCRETE_NOTES))
    return _C3 * 2 ** (index / 12)


def passed(points: Sequence[Point], start: float, end: float) -> list[Point]:
    """The points the cursor passes moving from `start` to `end` (the end included, the start not), in the
    order it meets them."""
    low, high = sorted((start, end))
    found = [point for point in points if low < point.x <= high or (point.x == end and start != end)]
    found = [point for point in found if point.x != start]
    return sorted(found, key=lambda point: point.x, reverse=end < start)


@dataclass(slots=True)
class Curve:
    """One function of the graph: its expression as the chart writes it, and its values."""

    expression: str
    function: Callable[[float], float]


class GraphExplorer:
    """The explorer's state: the graph's functions, the one heard, the view, the cursor and the modes."""

    def __init__(self, chart: Chart):
        self.curves = [Curve(expression, expression_function(expression)) for expression in chart.functions]
        self.title = chart.title
        self.current = 0
        self.home = default_view_for([curve.function for curve in self.curves], chart.x_range)
        self.view = self.home
        self.x = (self.view.x_min + self.view.x_max) / 2
        self.discrete = False
        self.sound_on = True
        self._note: float | None = None
        self._bookmarks: list[list[Point]] = [[] for _curve in self.curves]

    @property
    def curve(self) -> Curve:
        return self.curves[self.current]

    @property
    def bookmarks(self) -> list[Point]:
        return self._bookmarks[self.current]

    def y(self, x: float | None = None) -> float:
        return self.curve.function(self.x if x is None else x)

    def points(self) -> list[Point]:
        """The current function's landmarks within the view."""
        return sorted(
            (point for point in self.bookmarks if self.view.x_min <= point.x <= self.view.x_max),
            key=lambda point: point.x,
        )

    def sound(self) -> Sound:
        """What is heard at the cursor now."""
        y = self.y()
        pitch = frequency(y, self.view)
        strike = False
        if pitch is not None and self.discrete:
            pitch = scale_note(pitch)
            strike, self._note = pitch != self._note, pitch
        elif pitch is None:
            self._note = None
        return Sound(pitch, pan(self.x, self.view), math.isfinite(y) and y < 0, strike, self.discrete)

    def step(self, direction: int, fluid: bool = False) -> float:
        """The cursor moved a step left (-1) or right (1), kept in the view; the x it was at."""
        before = self.x
        size = FLUID_STEP if fluid else STEP
        self.x = max(self.view.x_min, min(self.view.x_max, self.x + direction * size))
        return before

    def at_edge(self) -> bool:
        return self.x <= self.view.x_min or self.x >= self.view.x_max

    def go_to(self, x: float) -> float:
        before, self.x = self.x, max(self.view.x_min, min(self.view.x_max, x))
        return before

    def next_point(self, direction: int) -> Point | None:
        """Jump among visible landmarks and view boundaries, wrapping at either end."""
        points = [Point("edge", self.view.x_min, self.y(self.view.x_min)), *self.points()]
        points.append(Point("edge", self.view.x_max, self.y(self.view.x_max)))
        ahead = [point for point in points if (point.x - self.x) * direction > 1e-12]
        point = min(ahead, key=lambda point: abs(point.x - self.x)) if ahead else points[0 if direction > 0 else -1]
        self.x = point.x
        return point

    def bookmark(self) -> bool:
        """Toggle a bookmark at the cursor; True when one was added, False when it was removed."""
        close = next((point for point in self.bookmarks if abs(point.x - self.x) < self.view.width / 10_000), None)
        if close is not None:
            self.bookmarks.remove(close)
            return False
        self.bookmarks.append(Point("bookmark", self.x, self.y()))
        return True

    def set_view(self, view: View) -> bool:
        """The view changed (the cursor kept in it); False when it would be too small or too large to read."""
        if not (0.1 <= view.width <= 100 and 0.1 <= view.height <= 100):
            return False
        self.view = view
        self.x = max(view.x_min, min(view.x_max, self.x))
        return True

    def zoom(self, closer: bool, x: bool = True, y: bool = True) -> bool:
        return self.set_view(self.view.zoomed(ZOOM_IN if closer else ZOOM_OUT, x, y))

    def move_view(self, right: float = 0.0, up: float = 0.0) -> bool:
        return self.set_view(self.view.moved(right, up))

    def reset_view(self) -> None:
        self.set_view(self.home)

    def choose(self, index: int) -> bool:
        if not 0 <= index < len(self.curves):
            return False
        self.current = index
        self._note = None
        return True

    def sweep(self, fraction: float) -> float:
        """The x a playback of the whole view is at, `fraction` (0 to 1) of the way from left to right."""
        return self.view.x_min + self.view.width * max(0.0, min(1.0, fraction))

    def with_view(self, view: View) -> GraphExplorer:
        """A copy at another view (for tests)."""
        copy = object.__new__(GraphExplorer)
        for name in ("curves", "title", "current", "home", "x", "discrete", "sound_on", "_note"):
            setattr(copy, name, getattr(self, name))
        copy._bookmarks = [list(points) for points in self._bookmarks]
        copy.view = replace(view)
        return copy


def number(value: float) -> str:
    """A coordinate as it is said: four significant digits, without a trailing zero ("1.5", "-0.25")."""
    if not math.isfinite(value):
        return _("undefined")
    if abs(value) < 1e-10:
        return "0"
    return f"{value:.4g}".replace("e+0", "e").replace("e-0", "e-")
