from __future__ import annotations

from dataclasses import dataclass


RGB = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class Palette:
    """Colors for the custom-drawn equation editor, per light/dark appearance.

    Text colors are checked against WCAG AA (4.5:1) in the tests; the
    editor's own surfaces sit on the system window background, which is
    assumed to be close to `background` here.
    """

    background: RGB
    text: RGB
    panel: RGB
    subtle_text: RGB
    border: RGB
    focus: RGB
    selection: RGB
    highlight_fill: RGB


LIGHT = Palette(
    background=(255, 255, 255),
    text=(29, 29, 31),
    panel=(242, 242, 245),
    subtle_text=(84, 84, 90),
    border=(188, 188, 194),
    focus=(0, 99, 214),
    selection=(179, 215, 255),
    highlight_fill=(215, 232, 255),
)

DARK = Palette(
    background=(30, 30, 30),
    text=(236, 236, 240),
    panel=(44, 44, 46),
    subtle_text=(188, 188, 196),
    border=(84, 84, 90),
    focus=(90, 162, 255),
    selection=(38, 79, 120),
    highlight_fill=(32, 66, 110),
)


def palette(dark: bool) -> Palette:
    return DARK if dark else LIGHT


def contrast_ratio(first: RGB, second: RGB) -> float:
    """WCAG 2 contrast ratio between two sRGB colors (1.0 to 21.0)."""
    lighter, darker = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def _luminance(color: RGB) -> float:
    def channel(value: int) -> float:
        value_srgb = value / 255
        return value_srgb / 12.92 if value_srgb <= 0.03928 else ((value_srgb + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(value) for value in color)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue
