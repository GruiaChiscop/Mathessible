import unittest

from matex.mathcat import MathCatNavigator
from matex.source_map import inside_leaf, leaf_at, leaf_characters, leaf_nodes, map_leaves

# Converter output for each source (UnicodeMathML with MateX's options).
CONVERTED = {
    "2x+1": "<math><mn>2</mn><mi>𝑥</mi><mo>+</mo><mn>1</mn></math>",
    "\\sum_(i=1)^n\\of i": (
        '<math><mrow intent=":nary($l,𝑛,$naryand)"><munderover><mo>∑</mo><mrow arg="l"><mi>𝑖</mi>'
        '<mo>=</mo><mn>1</mn></mrow><mi>𝑛</mi></munderover><mrow arg="naryand"><mi>𝑖</mi></mrow></mrow></math>'
    ),
    "(■(1&@&4))": (
        '<math><mrow intent=":fenced"><mo>(</mo><mtable intent=":array(2,2)"><mtr><mtd><mn>1</mn></mtd>'
        '<mtd><mspace width="0" /></mtd></mtr><mtr><mtd><mspace width="0" /></mtd><mtd><mn>4</mn></mtd>'
        "</mtr></mtable><mo>)</mo></mrow></math>"
    ),
    "f'(x)": (
        '<math><msup><mi>𝑓</mi><mo>′</mo></msup><mrow intent=":fenced"><mo>(</mo><mi>𝑥</mi>'
        "<mo>)</mo></mrow></math>"
    ),
    "()/()": '<math><mfrac><mspace width="0" /><mspace width="0" /></mfrac></math>',
    "a<=b": "<math><mi>𝑎</mi><mo>≤</mo><mi>𝑏</mi></math>",
    "x+4345": "<math><mi>𝑥</mi><mo>+</mo><mn>4345</mn></math>",
    "\\alpha+sin x": (
        "<math><mi>𝛼</mi><mo>+</mo><mi>sin</mi><mo>&#x2061;</mo><mi>𝑥</mi></math>"
    ),
    "√(3&x)": "<math><mroot><mi>𝑥</mi><mn>3</mn></mroot></math>",
    "∛x": "<math><mroot><mi>𝑥</mi><mn>3</mn></mroot></math>",
    "x\\hat": '<math><mover accent="true"><mi>𝑥</mi><mo>&#x302;</mo></mover></math>',
    "∬_D▒f dA": (
        '<math><mrow intent=":nary(𝐷,,$naryand)"><msub><mo>∬</mo><mi>𝐷</mi></msub><mrow arg="naryand">'
        "<mi>𝑓</mi></mrow></mrow><mi>𝑑</mi><mi>𝐴</mi></math>"
    ),
}


def aligned(source: str) -> list[tuple[str, str, int]]:
    """(leaf text, the source it maps to, its start) for each leaf, in reading order."""
    navigator = MathCatNavigator(language="en")
    navigator.load(CONVERTED[source])
    spans = map_leaves(source, navigator.structure)
    return [
        (leaf.text, source[spans[leaf.identifier].start : spans[leaf.identifier].end], spans[leaf.identifier].start)
        for leaf in leaf_nodes(navigator.structure)
    ]


class SourceMapTests(unittest.TestCase):
    def test_leaves_map_to_their_characters_and_invisible_ones_to_nothing(self) -> None:
        # MathCAT adds the invisible times; it sits where the two factors meet.
        self.assertEqual(aligned("2x+1"), [("2", "2", 0), ("⁢", "", 1), ("𝑥", "x", 1), ("+", "+", 2), ("1", "1", 3)])

    def test_control_words_map_to_their_symbol_leaf(self) -> None:
        self.assertEqual(
            aligned("\\sum_(i=1)^n\\of i"),
            [("∑", "\\sum", 0), ("𝑖", "i", 6), ("=", "=", 7), ("1", "1", 8), ("𝑛", "n", 11), ("𝑖", "i", 16)],
        )

    def test_empty_cells_and_slots_sit_between_their_separators(self) -> None:
        cells = aligned("(■(1&@&4))")
        self.assertEqual([start for _text, _source, start in cells], [0, 3, 5, 6, 7, 8])
        self.assertEqual([start for _text, _source, start in aligned("()/()")], [1, 4])

    def test_rewritten_spellings_are_matched(self) -> None:
        self.assertEqual(aligned("a<=b")[1], ("≤", "<=", 1))
        self.assertEqual(aligned("f'(x)")[1], ("′", "'", 1))

    def test_a_root_index_comes_first_as_in_the_source(self) -> None:
        # MathML puts the index last; a cube root's index is its sign.
        self.assertEqual(aligned("√(3&x)"), [("3", "3", 2), ("𝑥", "x", 4)])
        self.assertEqual(aligned("∛x"), [("3", "∛", 0), ("𝑥", "x", 1)])

    def test_accents_and_double_integrals_are_matched(self) -> None:
        self.assertEqual(aligned("x\\hat")[1][1], "\\hat")
        self.assertEqual(aligned("∬_D▒f dA")[0], ("∬", "∬", 0))

    def test_leaf_at_finds_the_leaf_under_or_before_an_offset(self) -> None:
        navigator = MathCatNavigator(language="en")
        navigator.load(CONVERTED["2x+1"])
        spans = map_leaves("2x+1", navigator.structure)
        texts = {identifier: navigator.structure.node(identifier).text for identifier in spans}
        self.assertEqual(texts[leaf_at(spans, 2)], "+")
        self.assertEqual(texts[leaf_at(spans, 4)], "1")
        self.assertEqual(texts[leaf_at(spans, 0)], "2")
        self.assertIsNone(leaf_at({}, 0))


class LeafCharacterTests(unittest.TestCase):
    def characters(self, source: str) -> dict[str, str | None]:
        navigator = MathCatNavigator(language="en")
        navigator.load(CONVERTED[source])
        spans = map_leaves(source, navigator.structure)
        return {
            leaf.text: leaf_characters(source, spans, navigator.structure, leaf.identifier)
            for leaf in leaf_nodes(navigator.structure)
        }

    def test_numbers_and_names_can_be_stepped_through(self) -> None:
        self.assertEqual(self.characters("x+4345")["4345"], "4345")
        self.assertEqual(self.characters("\\alpha+sin x")["sin"], "sin")

    def test_single_characters_control_words_and_respellings_cannot(self) -> None:
        self.assertIsNone(self.characters("x+4345")["𝑥"])
        self.assertIsNone(self.characters("\\alpha+sin x")["𝛼"])
        self.assertIsNone(self.characters("a<=b")["≤"])

    def test_inside_leaf_only_strictly_inside(self) -> None:
        navigator = MathCatNavigator(language="en")
        navigator.load(CONVERTED["x+4345"])
        spans = map_leaves("x+4345", navigator.structure)
        found = inside_leaf(spans, 4)
        self.assertIsNotNone(found)
        self.assertEqual(found[1], 2)
        self.assertIsNone(inside_leaf(spans, 2))
        self.assertIsNone(inside_leaf(spans, 6))


if __name__ == "__main__":
    unittest.main()
