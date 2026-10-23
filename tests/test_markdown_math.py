import unittest

from matex.documents.markdown_math import find_math_zones, math_zone_at


class MarkdownMathTests(unittest.TestCase):
    def test_finds_inline_and_display_equations(self) -> None:
        source = "În triunghi, $a^2+b^2=c^2$.\n\n$$∫_0^1 xⅆx$$"
        zones = find_math_zones(source)
        self.assertEqual([zone.content(source) for zone in zones], ["a^2+b^2=c^2", "∫_0^1 xⅆx"])
        self.assertEqual([zone.display for zone in zones], [False, True])

    def test_ignores_code_escaped_dollars_and_currency(self) -> None:
        source = "`$not_math$` și \\$5, apoi ~~~\n$tot_cod$\n~~~ și $x+1$"
        zones = find_math_zones(source)
        self.assertEqual(len(zones), 1)
        self.assertEqual(zones[0].content(source), "x+1")

    def test_finds_zone_containing_selection(self) -> None:
        source = "Text $a/(b+c)$ final"
        start = source.index("b")
        zone = math_zone_at(source, start)
        self.assertIsNotNone(zone)
        self.assertEqual(zone.content(source), "a/(b+c)")


if __name__ == "__main__":
    unittest.main()
