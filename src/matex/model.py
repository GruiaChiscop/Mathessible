from __future__ import annotations

from dataclasses import dataclass, field

from .ast import (
    Node,
    Path,
    children,
    deepest_path_at_offset,
    describe,
    node_at_path,
    to_mathml,
    to_unicodemath,
    walk,
)
from .parser import ParseError, parse_unicodemath


@dataclass(slots=True)
class MathCursor:
    path: Path = ()

    def current(self, root: Node) -> Node:
        return node_at_path(root, self.path)

    def move_into(self, root: Node) -> bool:
        if not children(self.current(root)):
            return False
        self.path += (0,)
        return True

    def move_out(self) -> bool:
        if not self.path:
            return False
        self.path = self.path[:-1]
        return True

    def move_next(self, root: Node) -> bool:
        paths = [path for path, _ in walk(root)]
        index = paths.index(self.path)
        if index + 1 >= len(paths):
            return False
        self.path = paths[index + 1]
        return True

    def move_previous(self, root: Node) -> bool:
        paths = [path for path, _ in walk(root)]
        index = paths.index(self.path)
        if index == 0:
            return False
        self.path = paths[index - 1]
        return True


@dataclass(slots=True)
class EquationDocument:
    source: str = "a/(b+c)"
    root: Node = field(init=False)
    cursor: MathCursor = field(default_factory=MathCursor)
    parse_error: str | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        # The toy parser rejects plenty of valid UnicodeMath ("x=(-b±...)");
        # opening such an equation must not crash, same as replace_source.
        try:
            self.root = parse_unicodemath(self.source)
        except ParseError as error:
            self.root = parse_unicodemath("")
            self.parse_error = str(error)

    def replace_source(self, source: str, caret: int | None = None) -> bool:
        self.source = source
        try:
            new_root = parse_unicodemath(source)
        except ParseError as error:
            self.parse_error = str(error)
            return False
        self.root = new_root
        self.parse_error = None
        self.cursor.path = deepest_path_at_offset(new_root, caret if caret is not None else len(source))
        return True

    @property
    def announcement(self) -> str:
        """Temporary fallback until navigation is delegated to MathCAT."""
        return describe(self.cursor.current(self.root))

    @property
    def normalized_source(self) -> str:
        return to_unicodemath(self.root)

    @property
    def mathml(self) -> str:
        return to_mathml(self.root)
