import unittest

from matex.mathcat import MathCatNavigator
from matex.node_edits import NodeSpan, node_span, removal

# Converter output for each source.
CONVERTED = {
    "(a+b)/(c+d)+1": (
        "<math><mfrac><mrow><mi>𝑎</mi><mo>+</mo><mi>𝑏</mi></mrow><mrow><mi>𝑐</mi><mo>+</mo><mi>𝑑</mi>"
        "</mrow></mfrac><mo>+</mo><mn>1</mn></math>"
    ),
    "(■(a&2@3&4))": (
        '<math><mrow intent=":fenced"><mo>(</mo><mtable intent=":array(2,2)"><mtr><mtd><mi>𝑎</mi></mtd>'
        "<mtd><mn>2</mn></mtd></mtr><mtr><mtd><mn>3</mn></mtd><mtd><mn>4</mn></mtd></mtr></mtable><mo>)</mo>"
        "</mrow></math>"
    ),
    "lim_(n→∞) 〖a_n〗": (
        '<math><mrow intent=":function"><munder><mi>lim</mi><mrow><mi>𝑛</mi><mo stretchy="true">→</mo>'
        '<mi>∞</mi></mrow></munder><mo>⁡</mo><mrow intent=":fenced"><mo></mo><msub><mi>𝑎</mi><mi>𝑛</mi>'
        "</msub><mo></mo></mrow></mrow></math>"
    ),
}


def removed(source: str, pick) -> str:
    """The source with the first node `pick(document, node)` accepts removed."""
    navigator = MathCatNavigator(language="en")
    navigator.load(CONVERTED[source])
    document = navigator.structure
    node = next(node for node in document.by_id.values() if pick(document, node))
    span, replacement = removal(source, document, node.identifier)
    return source[: span.start] + replacement + source[span.end :]


class NodeEditTests(unittest.TestCase):
    def test_a_whole_fraction_goes_with_its_parens(self) -> None:
        self.assertEqual(removed("(a+b)/(c+d)+1", lambda d, n: n.tag == "mfrac"), "+1")

    def test_an_emptied_slot_is_kept(self) -> None:
        numerator = lambda d, n: d.semantic_role(n.identifier) == "numerator"  # noqa: E731
        self.assertEqual(removed("(a+b)/(c+d)+1", numerator), "()/(c+d)+1")
        argument = lambda d, n: n.tag == "msub"  # noqa: E731
        self.assertEqual(removed("lim_(n→∞) 〖a_n〗", argument), "lim_(n→∞) 〖〗")

    def test_matrix_cells_empty_and_rows_go_with_a_separator(self) -> None:
        self.assertEqual(removed("(■(a&2@3&4))", lambda d, n: n.tag == "mtd"), "(■(&2@3&4))")
        self.assertEqual(removed("(■(a&2@3&4))", lambda d, n: n.tag == "mtr"), "(■(3&4))")

    def test_the_span_of_the_math_is_everything(self) -> None:
        navigator = MathCatNavigator(language="en")
        navigator.load(CONVERTED["(a+b)/(c+d)+1"])
        root = navigator.structure.root
        self.assertEqual(node_span("(a+b)/(c+d)+1", navigator.structure, root.identifier), NodeSpan(0, 13))


if __name__ == "__main__":
    unittest.main()
