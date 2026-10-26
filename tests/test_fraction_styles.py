import unittest

from mathessible.templates.fraction_styles import (
    built_fractions,
    fraction_at,
    restyle_fraction,
)


class FractionStyleTests(unittest.TestCase):
    def test_fraction_at_finds_the_innermost_fraction_with_its_operands(self) -> None:
        outer = fraction_at("x=(a+b)/c+1", 4)
        self.assertEqual((outer.start, outer.end, outer.style), (2, 9, "stacked"))
        inner = fraction_at("(x/2)/y", 2)
        self.assertEqual((inner.operator, inner.start, inner.end), (2, 1, 4))
        self.assertEqual(fraction_at("(x/2)/y", 0).operator, 5)
        function = fraction_at("f(x)/√(2)", 0)
        self.assertEqual((function.start, function.end), (0, 9))
        self.assertIsNone(fraction_at("a+b", 1))

    def test_restyle_fraction_swaps_the_operator(self) -> None:
        self.assertEqual(restyle_fraction("x=a/b+1", 3, "skewed").source, "x=a⁄b+1")
        self.assertEqual(restyle_fraction("(x/2)/y", 0, "small").source, "(x/2)⊘y")
        self.assertEqual(restyle_fraction("a⊘b", 0, "stacked").announcement, "stacked fraction")
        self.assertIsNone(restyle_fraction("a+b", 1, "linear"))

    def test_linear_fraction_keeps_visible_parens_around_groups(self) -> None:
        # The converter drops the parens of a linear fraction's operands.
        edit = restyle_fraction("(a+b)/(c+d)", 2, "linear")
        self.assertEqual((edit.source, edit.caret), ("((a+b))∕((c+d))", 3))
        self.assertEqual(restyle_fraction("(x)/2", 0, "linear").source, "(x)∕2")
        back = restyle_fraction(edit.source, edit.caret, "stacked")
        self.assertEqual((back.source, back.caret), ("(a+b)/(c+d)", 2))

    def test_built_fractions_skip_linear_ones_and_count_binomials(self) -> None:
        styles = [fraction.style for fraction in built_fractions("(n¦k)/2+a∕b")]
        self.assertEqual(styles, ["stacked", "no bar"])


if __name__ == "__main__":
    unittest.main()
