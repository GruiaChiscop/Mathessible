from __future__ import annotations

from dataclasses import dataclass, field

from .ast import Atom, Binary, Fraction, Group, Node, Operator, Placeholder, Script, children


@dataclass(frozen=True, slots=True)
class Text:
    value: str
    x: float
    y: float
    scale: float = 1.0


@dataclass(frozen=True, slots=True)
class Line:
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True, slots=True)
class Rect:
    x: float
    y: float
    width: float
    height: float


Primitive = Text | Line


@dataclass(slots=True)
class Layout:
    width: float
    height: float
    baseline: float
    primitives: list[Primitive] = field(default_factory=list)
    boxes: dict[object, Rect] = field(default_factory=dict)


def professional_layout(node: Node) -> Layout:
    return _layout(node)


def _text_width(value: str, scale: float = 1.0) -> float:
    return max(12.0, len(value) * 12.0 * scale)


def _place(target: Layout, child: Layout, index: int, x: float, y: float) -> None:
    for primitive in child.primitives:
        if isinstance(primitive, Text):
            target.primitives.append(Text(primitive.value, primitive.x + x, primitive.y + y, primitive.scale))
        else:
            target.primitives.append(Line(primitive.x1 + x, primitive.y1 + y, primitive.x2 + x, primitive.y2 + y))
    for path, rect in child.boxes.items():
        target.boxes[(index,) + path] = Rect(rect.x + x, rect.y + y, rect.width, rect.height)


def _layout(node: Node) -> Layout:
    if isinstance(node, (Atom, Operator, Placeholder)):
        value = node.value if isinstance(node, (Atom, Operator)) else "□"
        width = _text_width(value)
        return Layout(width, 28, 20, [Text(value, 0, 0)], {(): Rect(0, 0, width, 28)})

    if isinstance(node, Group):
        body = _layout(node.body)
        result = Layout(body.width + 24, body.height, body.baseline)
        result.primitives.extend([Text("(", 0, 0), Text(")", body.width + 12, 0)])
        _place(result, body, 0, 12, 0)
        result.boxes[()] = Rect(0, 0, result.width, result.height)
        return result

    if isinstance(node, Binary):
        left = _layout(node.left)
        right = _layout(node.right)
        op = "" if node.implicit else node.operator.value
        op_width = 8 if not op else _text_width(op) + 8
        baseline = max(left.baseline, right.baseline)
        left_y = baseline - left.baseline
        right_y = baseline - right.baseline
        height = max(left_y + left.height, right_y + right.height)
        result = Layout(left.width + op_width + right.width, height, baseline)
        _place(result, left, 0, 0, left_y)
        if op:
            result.primitives.append(Text(op, left.width + 4, baseline - 20))
            result.boxes[(1,)] = Rect(left.width + 4, baseline - 20, _text_width(op), 28)
            right_index = 2
        else:
            right_index = 1
        _place(result, right, right_index, left.width + op_width, right_y)
        result.boxes[()] = Rect(0, 0, result.width, result.height)
        return result

    if isinstance(node, Fraction):
        numerator = _layout(node.numerator)
        denominator = _layout(node.denominator)
        width = max(numerator.width, denominator.width) + 12
        line_y = numerator.height + 4
        denominator_y = line_y + 6
        result = Layout(width, denominator_y + denominator.height, line_y + 5)
        _place(result, numerator, 0, (width - numerator.width) / 2, 0)
        result.primitives.append(Line(2, line_y, width - 2, line_y))
        _place(result, denominator, 1, (width - denominator.width) / 2, denominator_y)
        result.boxes[()] = Rect(0, 0, result.width, result.height)
        return result

    if isinstance(node, Script):
        parts = children(node)
        base = _layout(parts[0])
        sub = _layout(node.subscript) if node.subscript is not None else None
        sup = _layout(node.superscript) if node.superscript is not None else None
        script_width = max(sub.width if sub else 0, sup.width if sup else 0) * 0.75
        top = (sup.height * 0.65 + 2) if sup else 0
        bottom = (sub.height * 0.65) if sub else 0
        result = Layout(base.width + script_width, top + base.height + bottom, top + base.baseline)
        _place(result, base, 0, 0, top)
        child_index = 1
        if sub is not None:
            scaled = _scale(sub, 0.7)
            _place(result, scaled, child_index, base.width, top + base.baseline)
            child_index += 1
        if sup is not None:
            scaled = _scale(sup, 0.7)
            _place(result, scaled, child_index, base.width, 0)
        result.boxes[()] = Rect(0, 0, result.width, result.height)
        return result

    raise TypeError(type(node))


def _scale(layout: Layout, factor: float) -> Layout:
    result = Layout(layout.width * factor, layout.height * factor, layout.baseline * factor)
    for primitive in layout.primitives:
        if isinstance(primitive, Text):
            result.primitives.append(Text(primitive.value, primitive.x * factor, primitive.y * factor, primitive.scale * factor))
        else:
            result.primitives.append(Line(primitive.x1 * factor, primitive.y1 * factor, primitive.x2 * factor, primitive.y2 * factor))
    for path, rect in layout.boxes.items():
        result.boxes[path] = Rect(rect.x * factor, rect.y * factor, rect.width * factor, rect.height * factor)
    return result
