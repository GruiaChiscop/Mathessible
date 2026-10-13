from __future__ import annotations

from .layout import Layout, Line, Rect, Text
from .mathml_model import MathMLDocument, MathMLNode


LEAF_TAGS = {"mi", "mn", "mo", "mtext", "ms", "mglyph"}
INVISIBLE_OPERATORS = {"⁡", "⁢", "⁣", "⁤", "\u2061", "\u2062", "\u2063", "\u2064"}


def mathml_layout(document: MathMLDocument) -> Layout:
    return _layout(document.root)


def _text_width(value: str, scale: float = 1.0) -> float:
    return max(8.0, len(value) * 12.0 * scale)


def _box(layout: Layout, node: MathMLNode) -> None:
    if node.identifier:
        layout.boxes[node.identifier] = Rect(0, 0, layout.width, layout.height)


def _place(target: Layout, child: Layout, x: float, y: float) -> None:
    for primitive in child.primitives:
        if isinstance(primitive, Text):
            target.primitives.append(Text(primitive.value, primitive.x + x, primitive.y + y, primitive.scale))
        else:
            target.primitives.append(Line(primitive.x1 + x, primitive.y1 + y, primitive.x2 + x, primitive.y2 + y))
    for identifier, rect in child.boxes.items():
        target.boxes[identifier] = Rect(rect.x + x, rect.y + y, rect.width, rect.height)


def _layout(node: MathMLNode) -> Layout:
    if node.tag in LEAF_TAGS:
        value = node.content.strip()
        if value in INVISIBLE_OPERATORS:
            result = Layout(5, 28, 20)
        else:
            value = value or "□"
            width = _text_width(value)
            result = Layout(width, 28, 20, [Text(value, 0, 0)])
        _box(result, node)
        return result

    if node.tag == "mspace":
        result = Layout(8, 28, 20)
        _box(result, node)
        return result

    if node.tag == "mfrac" and len(node.children) >= 2:
        numerator = _layout(node.children[0])
        denominator = _layout(node.children[1])
        width = max(numerator.width, denominator.width) + 14
        line_y = numerator.height + 4
        denominator_y = line_y + 7
        result = Layout(width, denominator_y + denominator.height, line_y + 5)
        _place(result, numerator, (width - numerator.width) / 2, 0)
        result.primitives.append(Line(2, line_y, width - 2, line_y))
        _place(result, denominator, (width - denominator.width) / 2, denominator_y)
        _box(result, node)
        return result

    if node.tag in {"msqrt", "mroot"} and node.children:
        body = _layout(node.children[0])
        index = _scale(_layout(node.children[1]), 0.55) if node.tag == "mroot" and len(node.children) > 1 else None
        radical_width = 19
        index_width = index.width if index else 0
        top = 5
        result = Layout(index_width + radical_width + body.width + 4, body.height + top, body.baseline + top)
        if index:
            _place(result, index, 0, 0)
        radical_x = index_width
        result.primitives.append(Text("√", radical_x, top, 1.15))
        body_x = radical_x + radical_width
        _place(result, body, body_x, top)
        result.primitives.append(Line(body_x - 1, top, result.width, top))
        _box(result, node)
        return result

    if node.tag in {"msub", "msup", "msubsup"} and node.children:
        base = _layout(node.children[0])
        sub_node = node.children[1] if node.tag in {"msub", "msubsup"} and len(node.children) > 1 else None
        sup_index = 2 if node.tag == "msubsup" else 1
        sup_node = node.children[sup_index] if node.tag in {"msup", "msubsup"} and len(node.children) > sup_index else None
        sub = _scale(_layout(sub_node), 0.7) if sub_node else None
        sup = _scale(_layout(sup_node), 0.7) if sup_node else None
        script_width = max(sub.width if sub else 0, sup.width if sup else 0)
        top = sup.height + 1 if sup else 0
        bottom = sub.height * 0.8 if sub else 0
        result = Layout(base.width + script_width, top + base.height + bottom, top + base.baseline)
        _place(result, base, 0, top)
        if sup:
            _place(result, sup, base.width, 0)
        if sub:
            _place(result, sub, base.width, top + base.baseline)
        _box(result, node)
        return result

    if node.tag in {"munder", "mover", "munderover"} and node.children:
        base = _layout(node.children[0])
        under_node = node.children[1] if node.tag in {"munder", "munderover"} and len(node.children) > 1 else None
        over_index = 2 if node.tag == "munderover" else 1
        over_node = node.children[over_index] if node.tag in {"mover", "munderover"} and len(node.children) > over_index else None
        under = _scale(_layout(under_node), 0.72) if under_node else None
        over = _scale(_layout(over_node), 0.72) if over_node else None
        width = max(base.width, under.width if under else 0, over.width if over else 0)
        top = over.height + 2 if over else 0
        bottom = under.height + 2 if under else 0
        result = Layout(width, top + base.height + bottom, top + base.baseline)
        if over:
            _place(result, over, (width - over.width) / 2, 0)
        _place(result, base, (width - base.width) / 2, top)
        if under:
            _place(result, under, (width - under.width) / 2, top + base.height + 2)
        _box(result, node)
        return result

    if node.tag == "mtable":
        return _table_layout(node)

    return _horizontal_layout(node)


def _horizontal_layout(node: MathMLNode) -> Layout:
    children = [_layout(child) for child in node.children]
    if not children:
        value = node.content.strip() or "□"
        result = Layout(_text_width(value), 28, 20, [Text(value, 0, 0)])
        _box(result, node)
        return result
    gap = 3
    baseline = max(child.baseline for child in children)
    positions = [baseline - child.baseline for child in children]
    height = max(y + child.height for y, child in zip(positions, children))
    width = sum(child.width for child in children) + gap * (len(children) - 1)
    result = Layout(width, height, baseline)
    x = 0.0
    for child, y in zip(children, positions):
        _place(result, child, x, y)
        x += child.width + gap
    _box(result, node)
    return result


def _table_layout(node: MathMLNode) -> Layout:
    rows = [row for row in node.children if row.tag == "mtr"]
    cell_nodes = [[cell for cell in row.children if cell.tag == "mtd"] for row in rows]
    cell_layouts = [[_layout(cell) for cell in row] for row in cell_nodes]
    column_count = max((len(row) for row in cell_layouts), default=0)
    column_widths = [
        max((row[index].width for row in cell_layouts if index < len(row)), default=20) + 16
        for index in range(column_count)
    ]
    row_heights = [max((cell.height for cell in row), default=28) + 12 for row in cell_layouts]
    width = sum(column_widths)
    height = sum(row_heights)
    result = Layout(width, height, height / 2 + 10)
    y = 0.0
    for row_node, nodes, layouts, row_height in zip(rows, cell_nodes, cell_layouts, row_heights):
        x = 0.0
        for index, (cell_node, cell) in enumerate(zip(nodes, layouts)):
            cell_x = x + (column_widths[index] - cell.width) / 2
            cell_y = y + (row_height - cell.height) / 2
            _place(result, cell, cell_x, cell_y)
            if cell_node.identifier:
                result.boxes[cell_node.identifier] = Rect(x, y, column_widths[index], row_height)
            x += column_widths[index]
        if row_node.identifier:
            result.boxes[row_node.identifier] = Rect(0, y, width, row_height)
        y += row_height
    _box(result, node)
    return result


def _scale(layout: Layout, factor: float) -> Layout:
    result = Layout(layout.width * factor, layout.height * factor, layout.baseline * factor)
    for primitive in layout.primitives:
        if isinstance(primitive, Text):
            result.primitives.append(
                Text(primitive.value, primitive.x * factor, primitive.y * factor, primitive.scale * factor)
            )
        else:
            result.primitives.append(
                Line(
                    primitive.x1 * factor,
                    primitive.y1 * factor,
                    primitive.x2 * factor,
                    primitive.y2 * factor,
                )
            )
    for identifier, rect in layout.boxes.items():
        result.boxes[identifier] = Rect(
            rect.x * factor,
            rect.y * factor,
            rect.width * factor,
            rect.height * factor,
        )
    return result
