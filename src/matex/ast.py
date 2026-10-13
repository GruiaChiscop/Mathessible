from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Iterator, TypeAlias


@dataclass(frozen=True, slots=True)
class Atom:
    value: str
    span: tuple[int, int]


@dataclass(frozen=True, slots=True)
class Placeholder:
    span: tuple[int, int]


@dataclass(frozen=True, slots=True)
class Operator:
    value: str
    span: tuple[int, int]


@dataclass(frozen=True, slots=True)
class Group:
    body: "Node"
    span: tuple[int, int]


@dataclass(frozen=True, slots=True)
class Binary:
    operator: Operator
    left: "Node"
    right: "Node"
    span: tuple[int, int]
    implicit: bool = False


@dataclass(frozen=True, slots=True)
class Fraction:
    numerator: "Node"
    denominator: "Node"
    span: tuple[int, int]


@dataclass(frozen=True, slots=True)
class Script:
    base: "Node"
    subscript: "Node | None"
    superscript: "Node | None"
    span: tuple[int, int]


Node: TypeAlias = Atom | Operator | Placeholder | Group | Binary | Fraction | Script
Path: TypeAlias = tuple[int, ...]


def children(node: Node) -> tuple[Node, ...]:
    if isinstance(node, Group):
        return (node.body,)
    if isinstance(node, Binary):
        if node.implicit:
            return (node.left, node.right)
        return (node.left, node.operator, node.right)
    if isinstance(node, Fraction):
        return (node.numerator, node.denominator)
    if isinstance(node, Script):
        result: list[Node] = [node.base]
        if node.subscript is not None:
            result.append(node.subscript)
        if node.superscript is not None:
            result.append(node.superscript)
        return tuple(result)
    return ()


def node_at_path(root: Node, path: Path) -> Node:
    current = root
    for index in path:
        current = children(current)[index]
    return current


def walk(root: Node, path: Path = ()) -> Iterator[tuple[Path, Node]]:
    yield path, root
    for index, child in enumerate(children(root)):
        yield from walk(child, path + (index,))


def deepest_path_at_offset(root: Node, offset: int) -> Path:
    best: Path = ()
    for path, node in walk(root):
        start, end = node.span
        if start <= offset <= end and len(path) >= len(best):
            best = path
    return best


def describe(node: Node) -> str:
    if isinstance(node, Atom):
        return node.value
    if isinstance(node, Operator):
        names = {
            "+": "plus",
            "-": "minus",
            "=": "equals",
            "⇒": "implies",
            "*": "times",
            "×": "times",
            "·": "times",
        }
        return names.get(node.value, node.value)
    if isinstance(node, Placeholder):
        return "empty slot"
    if isinstance(node, Group):
        return f"group, {describe(node.body)}"
    if isinstance(node, Binary):
        return f"{describe(node.left)} {describe(node.operator)} {describe(node.right)}"
    if isinstance(node, Fraction):
        return f"fraction, numerator {describe(node.numerator)}, denominator {describe(node.denominator)}"
    if isinstance(node, Script):
        parts = [describe(node.base)]
        if node.subscript is not None:
            parts.append(f"subscript {describe(node.subscript)}")
        if node.superscript is not None:
            parts.append(f"to the power of {describe(node.superscript)}")
        return ", ".join(parts)
    raise TypeError(type(node))


def to_unicodemath(node: Node) -> str:
    if isinstance(node, Atom):
        return node.value
    if isinstance(node, Operator):
        return node.value
    if isinstance(node, Placeholder):
        return "□"
    if isinstance(node, Group):
        return f"({to_unicodemath(node.body)})"
    if isinstance(node, Binary):
        op = "" if node.implicit else node.operator.value
        return f"{to_unicodemath(node.left)}{op}{to_unicodemath(node.right)}"
    if isinstance(node, Fraction):
        return f"{to_unicodemath(node.numerator)}/{to_unicodemath(node.denominator)}"
    if isinstance(node, Script):
        result = to_unicodemath(node.base)
        if node.subscript is not None:
            result += "_" + _script_text(node.subscript)
        if node.superscript is not None:
            result += "^" + _script_text(node.superscript)
        return result
    raise TypeError(type(node))


def _script_text(node: Node) -> str:
    text = to_unicodemath(node)
    return text if isinstance(node, (Atom, Group)) else f"({text})"


def to_mathml(node: Node) -> str:
    body = _to_mathml(node, ())
    return f'<math id="math-root" xmlns="http://www.w3.org/1998/Math/MathML">{body}</math>'


def mathml_id(path: Path) -> str:
    return "m-root" if not path else "m-" + "-".join(str(part) for part in path)


def path_from_mathml_id(identifier: str) -> Path | None:
    if identifier == "m-root":
        return ()
    if not identifier.startswith("m-"):
        return None
    try:
        return tuple(int(part) for part in identifier[2:].split("-"))
    except ValueError:
        return None


def _to_mathml(node: Node, path: Path) -> str:
    identifier = mathml_id(path)
    if isinstance(node, Atom):
        tag = "mn" if node.value.replace(".", "", 1).isdigit() else "mi"
        return f'<{tag} id="{identifier}">{escape(node.value)}</{tag}>'
    if isinstance(node, Operator):
        return f'<mo id="{identifier}">{escape(node.value)}</mo>'
    if isinstance(node, Placeholder):
        return f'<mi id="{identifier}" intent=":blank">□</mi>'
    if isinstance(node, Group):
        body = _to_mathml(node.body, path + (0,))
        return f'<mrow id="{identifier}"><mo>(</mo>{body}<mo>)</mo></mrow>'
    if isinstance(node, Binary):
        left = _to_mathml(node.left, path + (0,))
        if node.implicit:
            right = _to_mathml(node.right, path + (1,))
            operator = "<mo>⁢</mo>"
        else:
            operator = _to_mathml(node.operator, path + (1,))
            right = _to_mathml(node.right, path + (2,))
        return f'<mrow id="{identifier}">{left}{operator}{right}</mrow>'
    if isinstance(node, Fraction):
        numerator = _to_mathml(node.numerator, path + (0,))
        denominator = _to_mathml(node.denominator, path + (1,))
        return f'<mfrac id="{identifier}">{numerator}{denominator}</mfrac>'
    if isinstance(node, Script):
        base = _to_mathml(node.base, path + (0,))
        if node.subscript is not None and node.superscript is not None:
            subscript = _to_mathml(node.subscript, path + (1,))
            superscript = _to_mathml(node.superscript, path + (2,))
            return f'<msubsup id="{identifier}">{base}{subscript}{superscript}</msubsup>'
        if node.subscript is not None:
            subscript = _to_mathml(node.subscript, path + (1,))
            return f'<msub id="{identifier}">{base}{subscript}</msub>'
        if node.superscript is not None:
            superscript = _to_mathml(node.superscript, path + (1,))
            return f'<msup id="{identifier}">{base}{superscript}</msup>'
        return base
    raise TypeError(type(node))
