"""How the newer structures read in MathCAT, with MateX's fixups (prepare_for_mathcat, flat stops)."""

import unittest

from matex.mathcat import MathCatNavigator

# Converter output for each source.
CONVERTED = {
    "f={■(x&x≥0@-x&x<0)┤": (
        '<math><mi>𝑓</mi><mo>=</mo><mrow intent=":fenced"><mo>{</mo><mtable intent=":array(2,2)"><mtr><mtd>'
        "<mi>𝑥</mi></mtd><mtd><mi>𝑥</mi><mo>≥</mo><mn>0</mn></mtd></mtr><mtr><mtd><mo>−</mo><mi>𝑥</mi></mtd>"
        "<mtd><mi>𝑥</mi><mo>&lt;</mo><mn>0</mn></mtd></mtr></mtable><mo>​</mo></mrow></math>"
    ),
    "⏞(a+b)┴n": (
        '<math><mover><mover><mrow><mi>𝑎</mi><mo>+</mo><mi>𝑏</mi></mrow><mo stretchy="true">⏞</mo></mover>'
        "<mi>𝑛</mi></mover></math>"
    ),
    "∫▒fⅆx": (
        '<math><mrow intent=":nary(,,$naryand)"><mo>∫</mo><mrow arg="naryand"><mi>𝑓</mi><mi> </mi>'
        '<mi intent="ⅆ">𝑑</mi><mi>𝑥</mi></mrow></mrow></math>'
    ),
    "max_(x∈A) f": "<math><msub><mi>max</mi><mrow><mi>𝑥</mi><mo>∈</mo><mi>𝐴</mi></mrow></msub><mi>𝑓</mi></math>",
    "|x|+1": '<math><mrow intent="absolute-value(𝑥)"><mo>|</mo><mi>𝑥</mi><mo>|</mo></mrow><mo>+</mo><mn>1</mn></math>',
    "█(a&=b@&=c)": (
        '<math><mtable intent=":equations" columnspacing="0pt"><mtr><mtd><mi>𝑎</mi></mtd><mtd><mo>=</mo>'
        '<mi>𝑏</mi></mtd></mtr><mtr><mtd><mspace width="0" /></mtd><mtd><mo>=</mo><mi>𝑐</mi></mtd></mtr>'
        "</mtable></math>"
    ),
}


def read(source: str) -> tuple[str, list[str]]:
    """(the whole reading, the flat-reading stops)."""
    navigator = MathCatNavigator(language="en", auto_zoom_out=True, boundary_stops=True)
    navigator.load(CONVERTED[source])
    whole = navigator.command("ReadCurrent")
    navigator.command("ZoomIn")
    stops = []
    for _ in range(40):
        stops.append(navigator.linear_command("MoveNext"))
        if stops[-1] == "end of math":
            break
    return whole, stops


class MathReadingTests(unittest.TestCase):
    def test_cases_read_as_cases(self) -> None:
        whole, stops = read("f={■(x&x≥0@-x&x<0)┤")
        self.assertIn("2 cases; case 1", whole)
        self.assertEqual(stops[2:6], ["start cases", "start case 1", "start value", "x"])
        self.assertIn("start condition", stops)
        self.assertIn("negative", stops)  # "−" alone, not "negative x" then "x".

    def test_an_equation_array_reads_by_equations_without_alignment_columns(self) -> None:
        whole, stops = read("█(a&=b@&=c)")
        self.assertTrue(whole.startswith("2 equations; equation 1"))
        self.assertEqual(stops[:4], ["start equations", "start equation 1", "eigh", "is equal to"])
        self.assertNotIn("empty", stops)
        self.assertFalse(any("column" in stop for stop in stops))

    def test_a_labeled_brace(self) -> None:
        # Needs patches/mathcat/0003 (the labeled-brace rule).
        whole, stops = read("⏞(a+b)┴n")
        self.assertEqual(whole, "eigh plus b, with brace above, labeled n")
        self.assertEqual(stops[:5], ["start overbrace", "eigh", "plus", "b", "start label"])

    def test_the_differential_d_and_max_read_plainly(self) -> None:
        whole, stops = read("∫▒fⅆx")
        self.assertNotIn("double-struck", whole)
        self.assertIn("d", stops)
        whole, stops = read("max_(x∈A) f")
        # Needs patches/mathcat/0003 (no doubled "of").
        self.assertEqual(whole.split(), "the max over x is an element of cap eigh of f".split())
        self.assertIn("start condition", stops)

    def test_bars_frame_their_content(self) -> None:
        whole, stops = read("|x|+1")
        self.assertEqual(whole, "the absolute value of x, plus 1")
        self.assertEqual(stops[:3], ["start absolute value", "x", "end absolute value"])


if __name__ == "__main__":
    unittest.main()
