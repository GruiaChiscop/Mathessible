import unittest

from matex.ast import Fraction, Operator, Script, describe, to_mathml, to_unicodemath, walk
from matex.parser import parse_unicodemath


class ParserTests(unittest.TestCase):
    def test_fraction_and_group(self) -> None:
        root = parse_unicodemath("a/(b+c)")
        self.assertIsInstance(root, Fraction)
        self.assertEqual(to_unicodemath(root), "a/(b+c)")
        self.assertIn("numerator a", describe(root))
        self.assertIn("<mfrac ", to_mathml(root))

    def test_subscript_and_superscript(self) -> None:
        root = parse_unicodemath("x_1^2")
        self.assertIsInstance(root, Script)
        self.assertEqual(to_unicodemath(root), "x_1^2")
        self.assertIn("<msubsup ", to_mathml(root))

    def test_incomplete_expression_has_placeholder(self) -> None:
        root = parse_unicodemath("a/")
        self.assertIsInstance(root, Fraction)
        self.assertIn("empty slot", describe(root))

    def test_autocorrect_alias(self) -> None:
        root = parse_unicodemath(r"\alpha=>\infty")
        self.assertEqual(to_unicodemath(root), "α⇒∞")

    def test_explicit_operator_is_navigable(self) -> None:
        root = parse_unicodemath("b+c")
        values = [node.value for _, node in walk(root) if isinstance(node, Operator)]
        self.assertEqual(values, ["+"])


if __name__ == "__main__":
    unittest.main()
