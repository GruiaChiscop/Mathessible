import unittest

from matex.layout import Line, Text
from matex.mathml_layout import mathml_layout
from matex.mathml_model import MathMLDocument


class MathMLLayoutTests(unittest.TestCase):
    def test_fraction_radical_and_scripts_have_semantic_boxes(self) -> None:
        document = MathMLDocument.parse(
            """<math id="root"><mfrac id="fraction"><msqrt id="root-sign">
            <mi id="x">x</mi></msqrt><msup id="square"><mi id="y">y</mi>
            <mn id="two">2</mn></msup></mfrac></math>"""
        )
        layout = mathml_layout(document)
        self.assertGreater(layout.height, 60)
        self.assertTrue({"root", "fraction", "root-sign", "x", "square", "y", "two"} <= layout.boxes.keys())
        self.assertTrue(any(isinstance(primitive, Line) for primitive in layout.primitives))
        self.assertTrue(any(isinstance(primitive, Text) and primitive.value == "√" for primitive in layout.primitives))

    def test_matrix_layout_places_every_cell_in_a_grid(self) -> None:
        document = MathMLDocument.parse(
            """<math id="root"><mrow id="fenced"><mo id="open">(</mo><mtable id="matrix">
            <mtr id="row-1"><mtd id="cell-11"><mi id="a">a</mi></mtd>
            <mtd id="cell-12"><mi id="b">b</mi></mtd></mtr>
            <mtr id="row-2"><mtd id="cell-21"><mi id="c">c</mi></mtd>
            <mtd id="cell-22"><mi id="d">d</mi></mtd></mtr>
            </mtable><mo id="close">)</mo></mrow></math>"""
        )
        layout = mathml_layout(document)
        first = layout.boxes["cell-11"]
        right = layout.boxes["cell-12"]
        below = layout.boxes["cell-21"]
        self.assertGreater(right.x, first.x)
        self.assertGreater(below.y, first.y)
        self.assertIn("matrix", layout.boxes)
        self.assertIn("cell-22", layout.boxes)


if __name__ == "__main__":
    unittest.main()
