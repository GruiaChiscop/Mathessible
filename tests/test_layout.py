import unittest

from matex.layout import professional_layout
from matex.parser import parse_unicodemath


class LayoutTests(unittest.TestCase):
    def test_fraction_layout_contains_semantic_boxes(self) -> None:
        layout = professional_layout(parse_unicodemath("a/(b+c)"))
        self.assertGreater(layout.height, 50)
        self.assertIn((), layout.boxes)
        self.assertIn((0,), layout.boxes)
        self.assertIn((1,), layout.boxes)


if __name__ == "__main__":
    unittest.main()
