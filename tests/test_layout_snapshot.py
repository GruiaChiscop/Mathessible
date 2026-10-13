import unittest

from matex.layout_snapshot import layout_to_svg
from matex.mathml_layout import mathml_layout
from matex.mathml_model import MathMLDocument


class LayoutSnapshotTests(unittest.TestCase):
    def test_svg_contains_equation_primitives_and_selected_node(self) -> None:
        document = MathMLDocument.parse(
            '<math id="root"><mfrac id="fraction"><mi id="x">x</mi>'
            '<mrow id="sum"><mi id="a">a</mi><mo id="plus">+</mo>'
            '<mi id="b">b</mi></mrow></mfrac></math>'
        )

        svg = layout_to_svg(mathml_layout(document), selected="sum")

        self.assertTrue(svg.startswith('<?xml version="1.0"'))
        self.assertIn('<line ', svg)
        self.assertIn('fill="#dbeafe"', svg)
        self.assertIn(">x</text>", svg)
        self.assertIn(">+</text>", svg)
        self.assertIn(">b</text>", svg)

    def test_svg_escapes_math_text(self) -> None:
        document = MathMLDocument.parse('<math id="root"><mo id="less">&lt;</mo></math>')

        svg = layout_to_svg(mathml_layout(document))

        self.assertIn("&lt;</text>", svg)


if __name__ == "__main__":
    unittest.main()
