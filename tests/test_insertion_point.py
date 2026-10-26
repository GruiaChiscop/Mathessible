import unittest

from mathessible.editing.insertion_point import describe_insertion_point
from mathessible.editing.source_map import anchor_offset
from mathessible.mathcat.navigator import MathCatNavigator

# Converter output for each source.
CONVERTED = {
    "(1)/(2)+3": "<math><mfrac><mn>1</mn><mn>2</mn></mfrac><mo>+</mo><mn>3</mn></math>",
    "√(x)+1": "<math><msqrt><mi>𝑥</mi></msqrt><mo>+</mo><mn>1</mn></math>",
    "(■(1&2@3&4))": (
        '<math><mrow intent=":fenced"><mo>(</mo><mtable intent=":array(2,2)"><mtr><mtd><mn>1</mn></mtd>'
        "<mtd><mn>2</mn></mtd></mtr><mtr><mtd><mn>3</mn></mtd><mtd><mn>4</mn></mtd></mtr></mtable>"
        "<mo>)</mo></mrow></math>"
    ),
}


def walk(source: str) -> dict[str, tuple[str, str]]:
    """For each flat-reading stop: (what typing there is said to do, the source split at that point)."""
    navigator = MathCatNavigator(language="en", auto_zoom_out=True, boundary_stops=True)
    navigator.load(CONVERTED[source])
    navigator.command("ZoomIn")
    found: dict[str, tuple[str, str]] = {}
    speech = None
    for _ in range(30):
        speech = navigator.linear_command("MoveNext")
        node, side, outside = navigator.edit_anchor()
        offset = anchor_offset(source, navigator.structure, node, side, outside)
        found.setdefault(
            speech,
            (
                describe_insertion_point(navigator.structure, node, side, outside),
                f"{source[:offset]}|{source[offset:]}",
            ),
        )
        if speech == "end of math":
            break
    return found


class InsertionPointTests(unittest.TestCase):
    def test_numerator_and_denominator_edges_are_told_apart(self) -> None:
        stops = walk("(1)/(2)+3")
        self.assertEqual(stops["1"], ("after 1, end of numerator, before 2", "(1|)/(2)+3"))
        self.assertEqual(stops["start denominator"], ("after 1, start of denominator, before 2", "(1)/(|2)+3"))

    def test_a_whole_structure_edge_types_outside_it(self) -> None:
        stops = walk("(1)/(2)+3")
        self.assertEqual(stops["end fraction"], ("after the fraction, before plus", "(1)/(2)|+3"))
        self.assertEqual(stops["start fraction"][1], "|(1)/(2)+3")
        roots = walk("√(x)+1")
        self.assertEqual(roots["start square root"], ("start of math, before the square root", "|√(x)+1"))
        self.assertEqual(roots["end square root"][1], "√(x)|+1")

    def test_matrix_cells_are_named_at_their_edges(self) -> None:
        stops = walk("(■(1&2@3&4))")
        self.assertEqual(stops["1"], ("after 1, end of column 1, before 2", "(■(1|&2@3&4))"))
        self.assertEqual(stops["start column 2"], ("after 1, start of column 2, before 2", "(■(1&|2@3&4))"))
        self.assertEqual(stops["2"][0], "after 2, end of column 2, end of row 1, before 3")

    def test_the_ends_of_the_math(self) -> None:
        stops = walk("√(x)+1")
        self.assertEqual(stops["end of math"], ("end of math", "√(x)+1|"))


if __name__ == "__main__":
    unittest.main()
