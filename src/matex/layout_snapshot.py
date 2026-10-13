from __future__ import annotations

from html import escape

from .layout import Layout, Line, Text


def layout_to_svg(layout: Layout, selected: object | None = None, padding: float = 10) -> str:
    """Return a deterministic SVG preview of a professional equation layout."""
    width = layout.width + padding * 2
    height = layout.height + padding * 2
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{_number(width)}" '
            f'height="{_number(height)}" viewBox="0 0 {_number(width)} {_number(height)}">'
        ),
        '<rect width="100%" height="100%" fill="white"/>',
    ]

    selected_box = layout.boxes.get(selected)
    if selected_box is not None:
        parts.append(
            f'<rect x="{_number(selected_box.x + padding)}" '
            f'y="{_number(selected_box.y + padding)}" '
            f'width="{_number(selected_box.width)}" height="{_number(selected_box.height)}" '
            'rx="3" fill="#dbeafe" stroke="#2563eb" stroke-width="1"/>'
        )

    for primitive in layout.primitives:
        if isinstance(primitive, Text):
            font_size = 20 * primitive.scale
            baseline = primitive.y + padding + font_size
            parts.append(
                f'<text x="{_number(primitive.x + padding)}" y="{_number(baseline)}" '
                f'font-family="Cambria Math, STIX Two Math, serif" '
                f'font-size="{_number(font_size)}">{escape(primitive.value)}</text>'
            )
        elif isinstance(primitive, Line):
            parts.append(
                f'<line x1="{_number(primitive.x1 + padding)}" '
                f'y1="{_number(primitive.y1 + padding)}" '
                f'x2="{_number(primitive.x2 + padding)}" '
                f'y2="{_number(primitive.y2 + padding)}" '
                'stroke="black" stroke-width="1.5" stroke-linecap="round"/>'
            )

    parts.append("</svg>")
    return "\n".join(parts)


def _number(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")
