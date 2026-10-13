import unittest

from matex.theme import DARK, LIGHT, contrast_ratio, palette


class ThemeTests(unittest.TestCase):
    def test_contrast_ratio_extremes(self) -> None:
        self.assertAlmostEqual(contrast_ratio((0, 0, 0), (255, 255, 255)), 21.0, places=1)
        self.assertAlmostEqual(contrast_ratio((10, 20, 30), (10, 20, 30)), 1.0)

    def test_text_meets_wcag_aa_on_every_surface(self) -> None:
        for colors in (LIGHT, DARK):
            for surface in (colors.background, colors.panel, colors.selection, colors.highlight_fill):
                self.assertGreaterEqual(contrast_ratio(colors.text, surface), 4.5)
            for surface in (colors.background, colors.panel):
                self.assertGreaterEqual(contrast_ratio(colors.subtle_text, surface), 4.5)

    def test_focus_ring_is_visible_against_the_background(self) -> None:
        # WCAG 1.4.11: user-interface components need 3:1.
        for colors in (LIGHT, DARK):
            self.assertGreaterEqual(contrast_ratio(colors.focus, colors.background), 3.0)
            self.assertGreaterEqual(contrast_ratio(colors.focus, colors.highlight_fill), 3.0)

    def test_palette_follows_the_appearance(self) -> None:
        self.assertIs(palette(dark=True), DARK)
        self.assertIs(palette(dark=False), LIGHT)


if __name__ == "__main__":
    unittest.main()
