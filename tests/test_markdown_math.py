import unittest

from matex.documents.markdown_math import find_math_zones, math_zone_at, toggle_display


class MarkdownMathTests(unittest.TestCase):
    def test_finds_inline_and_display_equations(self) -> None:
        source = "In a right triangle, $a^2+b^2=c^2$.\n\n$$∫_0^1 xⅆx$$"
        zones = find_math_zones(source)
        self.assertEqual([zone.content(source) for zone in zones], ["a^2+b^2=c^2", "∫_0^1 xⅆx"])
        self.assertEqual([zone.display for zone in zones], [False, True])

    def test_ignores_code_escaped_dollars_and_currency(self) -> None:
        source = "`$not_math$` and \\$5, then ~~~\n$all_code$\n~~~ and $x+1$"
        zones = find_math_zones(source)
        self.assertEqual(len(zones), 1)
        self.assertEqual(zones[0].content(source), "x+1")

    def test_finds_zone_containing_selection(self) -> None:
        source = "Text $a/(b+c)$ final"
        start = source.index("b")
        zone = math_zone_at(source, start)
        self.assertIsNotNone(zone)
        self.assertEqual(zone.content(source), "a/(b+c)")


class ToggleDisplayTests(unittest.TestCase):
    """Word's Change to Display / Change to Inline on the Markdown source."""

    def toggled(self, source: str, caret: int) -> str:
        zone = math_zone_at(source, caret)
        assert zone is not None
        result = toggle_display(source, zone)
        assert result is not None
        new_source, new_zone = result
        self.assertIn(new_zone, find_math_zones(new_source))
        return new_source

    def test_display_goes_on_a_line_of_its_own(self) -> None:
        self.assertEqual(self.toggled("The roots of $x^2=1$ are ±1.", 15), "The roots of\n$$x^2=1$$\nare ±1.")
        self.assertEqual(self.toggled("$a≠0$.", 1), "$$a≠0$$\n.")
        self.assertEqual(self.toggled("Text\n$x$\nmore", 6), "Text\n$$x$$\nmore")  # Already alone on its line.

    def test_inline_stays_where_it_is(self) -> None:
        self.assertEqual(self.toggled("Text\n$$ x^2 $$\nmore", 8), "Text\n$x^2$\nmore")
        self.assertEqual(self.toggled(self.toggled("a $x$ b", 3), 4), "a\n$x$\nb")  # A soft break: one paragraph.

    def test_what_cannot_be_inline_is_left(self) -> None:
        for source in ("$$$$", "$$a\nb$$", "$$ $$"):
            with self.subTest(source=source):
                zone = math_zone_at(source, 2)
                assert zone is not None
                self.assertIsNone(toggle_display(source, zone))


if __name__ == "__main__":
    unittest.main()
