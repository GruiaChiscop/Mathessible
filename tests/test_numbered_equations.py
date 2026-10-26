import json
import unittest

from converter_harness import convert, needs_node
from mathessible.editing.source_map import anchor_offset, leaf_nodes, map_leaves
from mathessible.mathcat.navigator import MathCatNavigator
from mathessible.unicodemath import decode_conversion


def mathml(source: str) -> str:
    return decode_conversion(json.dumps({"mathml": convert(source)})).mathml


def linear(source: str) -> MathCatNavigator:
    navigator = MathCatNavigator(language="en", auto_zoom_out=True, boundary_stops=True)
    navigator.load(mathml(source))
    navigator.command("ZoomIn")
    return navigator


def stops(navigator: MathCatNavigator) -> list[str]:
    said: list[str] = []
    while not said or said[-1] != "end of math":
        said.append(navigator.linear_command("MoveNext"))
    return said


@needs_node
class NumberedEquationTests(unittest.TestCase):
    """`E=mc^2#(1)`: the converter puts the number in a table cell before the equation (MathML order)."""

    def test_the_source_map_follows_the_source_with_the_number_last(self) -> None:
        source = "E=mc^2#(1)"
        navigator = linear(source)
        spans = map_leaves(source, navigator.structure)
        mapped = [
            source[spans[leaf.identifier].start : spans[leaf.identifier].end]
            for leaf in leaf_nodes(navigator.structure)
            if leaf.identifier in spans
        ]
        self.assertEqual(mapped, ["E", "=", "m", "", "c", "2", "(", "1", ")"])

    def test_the_number_is_one_stop_after_the_equation_with_no_table_stops(self) -> None:
        self.assertEqual(
            stops(linear("E=mc^2#(1)")),
            [
                "cap e",
                "is equal to",
                "m",
                "c",
                "start superscript",
                "2",
                "end superscript",
                "equation number 1",
                "end of math",
            ],
        )
        self.assertEqual(stops(linear("x=1#(1.2)")), ["x", "is equal to", "1", "equation number 1.2", "end of math"])

    def test_typing_on_the_number_goes_into_it(self) -> None:
        for source, typed_at in (("E=mc^2#()", 8), ("E=mc^2#(12)", 10)):
            with self.subTest(source=source):
                navigator = linear(source)
                while not navigator.linear_command("MoveNext").startswith("equation number"):
                    pass
                self.assertEqual(anchor_offset(source, navigator.structure, *navigator.edit_anchor()), typed_at)

    def test_structural_levels_have_the_equation_then_its_number(self) -> None:
        navigator = MathCatNavigator(language="en", auto_zoom_out=False, structural_stops=True)
        navigator.load(mathml("E=mc^2#(1)"))
        navigator.command("ZoomIn")
        said = [navigator.structural_command("MoveNext") for _ in range(5)]
        self.assertEqual(said, ["cap e", "is equal to", "m c squared", "equation number 1", "end of math"])

    def test_a_matrix_still_has_its_rows_and_columns(self) -> None:
        self.assertIn("start row 1", stops(linear("(■(1&0@0&1))")))


if __name__ == "__main__":
    unittest.main()
