"""How the newer structures read in MathCAT, with Mathessible's fixups (prepare_for_mathcat, flat stops)."""

import unittest

from mathessible.mathcat.navigator import MathCatNavigator

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
    "x∈(a,b)": (
        '<math><mi>𝑥</mi><mo>∈</mo><mrow intent=":fenced"><mo>(</mo><mrow><mi>𝑎</mi><mo>,</mo><mi>𝑏</mi>'
        "</mrow><mo>)</mo></mrow></math>"
    ),
    "[0,1)": (
        '<math><mrow intent="closed-open-interval(0,1)"><mo>[</mo><mn>0</mn><mo>,</mo><mn>1</mn>'
        "<mo>)</mo></mrow></math>"
    ),
    "{a,b}": (
        '<math><mrow intent=":fenced"><mo>{</mo><mrow><mi>𝑎</mi><mo>,</mo><mi>𝑏</mi></mrow><mo>}</mo></mrow></math>'
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
    def test_an_h_is_no_planck_constant(self) -> None:
        # The converter's italic h is ℎ (U+210E), which MathCAT named "planck constant".
        navigator = MathCatNavigator(language="en", auto_zoom_out=True)
        navigator.load("<math><mi>𝑓</mi><mo>(</mo><mi>𝑥</mi><mo>+</mo><mi>ℎ</mi><mo>)</mo></math>")
        self.assertNotIn("planck", navigator.command("ReadCurrent"))
        self.assertIn("h", navigator.command("ReadCurrent"))

    def test_a_numbered_aligns_rows_read_with_their_numbers(self) -> None:
        # Converter output for `\\begin{aligned}a&=b &&\\qquad\\text{(1)}\\\\ c&=d\\end{aligned}` (a .tex
        # file's numbered align, as its preview writes it).
        cell = "<mtd>{}</mtd>"
        mathml = (
            '<math><mtable intent=":equations" columnspacing="0pt"><mtr>'
            + cell.format("<mi>𝑎</mi>")
            + cell.format("<mo>=</mo><mi>𝑏</mi>")
            + cell.format('<mspace width="0" />')
            + cell.format('<mspace width="1em" /><mspace width="1em" /><mtext>(1)</mtext>')
            + "</mtr><mtr>"
            + cell.format("<mi>𝑐</mi>")
            + cell.format("<mo>=</mo><mi>𝑑</mi>")
            + "</mtr></mtable></math>"
        )
        navigator = MathCatNavigator(language="en", auto_zoom_out=True)
        navigator.load(mathml)
        self.assertIn("1 with label 1", navigator.command("ReadCurrent"))

    def test_a_log_has_a_base_not_a_subscript(self) -> None:
        # Converter output for "log_2 〖8〗" (user report: "log subscript 2").
        mathml = (
            '<math><mrow intent=":function"><msub><mi>log</mi><mn>2</mn></msub><mo>⁡</mo><mrow intent=":fenced">'
            "<mo></mo><mn>8</mn><mo></mo></mrow></mrow></math>"
        )
        navigator = MathCatNavigator(language="en", auto_zoom_out=True, boundary_stops=True)
        navigator.load(mathml)
        navigator.command("ZoomIn")
        stops = [navigator.linear_command("MoveNext") for _ in range(4)]
        self.assertEqual(stops[1:4], ["start base", "2", "end base"])
        self.assertNotIn("the log base 2", stops[0])  # The name alone; the base follows.
        structural = MathCatNavigator(language="en", auto_zoom_out=False, structural_stops=True)
        structural.load(mathml)
        structural.command("ZoomIn")
        structural.structural_command("MoveNext")
        self.assertEqual(structural.structural_command("ZoomIn"), "start logarithm")
        structural.structural_command("MoveNext")
        self.assertEqual(structural.structural_command("MoveNext"), "base, 2")

    def test_lim_inf_and_lim_sup_read_as_limits(self) -> None:
        # Converter output for "lim inf_(n→∞) a_n" (no-break space, the converter's
        # spelling): an mrow of lim, space, inf; MathCAT patch 0005 names the intent.
        for word, name in (("inf", "inferior"), ("sup", "superior")):
            with self.subTest(word=word):
                mathml = (
                    f"<math><msub><mrow><mi>lim</mi><mo>\u00a0</mo><mi>{word}</mi></mrow><mrow><mi>𝑛</mi>"
                    '<mo stretchy="true">→</mo><mi>∞</mi></mrow></msub><msub><mi>𝑎</mi><mi>𝑛</mi></msub></math>'
                )
                navigator = MathCatNavigator(language="en", auto_zoom_out=True, boundary_stops=True)
                self.assertEqual(navigator.load(mathml), f"the limit {name} as n approaches infinity, of eigh sub n")
                navigator.command("ZoomIn")
                stops = [navigator.linear_command("MoveNext") for _ in range(6)]
                self.assertEqual(
                    stops,
                    [f"lim {word}", "start limit condition", "n", "approaches", "infinity", "end limit condition"],
                )

    def test_lim_sup_without_a_condition_is_applied_to_its_argument(self) -> None:
        # Converter output for "lim sup 〖a_n〗": lim applied to " sup", the argument outside.
        mathml = (
            '<math><mrow intent=":function"><mi>lim</mi><mo>⁡</mo><mo>\u00a0</mo><mi>sup</mi></mrow>'
            '<mrow intent=":fenced"><mo></mo><msub><mi>𝑎</mi><mi>𝑛</mi></msub><mo></mo></mrow></math>'
        )
        navigator = MathCatNavigator(language="en", auto_zoom_out=True, boundary_stops=True)
        self.assertEqual(navigator.load(mathml), "limit superior of eigh sub n")
        navigator.command("ZoomIn")
        self.assertEqual(
            [navigator.linear_command("MoveNext") for _ in range(3)], ["limit superior", "of", "start argument"]
        )

    def test_an_empty_argument_is_said_empty_in_structural_navigation(self) -> None:
        # Converter output for "lim_(n→∞) 〖〗": MathCAT reads the empty group as nothing.
        mathml = '<math display="inline"><mrow intent=":function"><msub><mi>lim</mi><mrow><mi>𝑛</mi><mo stretchy="true">→</mo><mi>∞</mi></mrow></msub><mo>\u2061</mo><mrow intent=":fenced"><mo></mo><mspace width="0" /><mo></mo></mrow></mrow></math>'
        navigator = MathCatNavigator(language="en", auto_zoom_out=False, structural_stops=True)
        navigator.load(mathml)
        navigator.command("ZoomIn")
        navigator.structural_command("MoveNext")
        self.assertEqual(navigator.structural_command("MoveNext"), "argument, empty")

    def test_a_decimal_comma_is_read_as_one_number(self) -> None:
        mathml = (
            '<math><mrow intent=":fenced"><mo>{</mo><mrow><mn>1,5</mn><mo>,</mo><mn>2</mn></mrow>'
            "<mo>}</mo></mrow></math>"
        )
        for separator, number in ((",", "1,5"), (".", "15")):
            navigator = MathCatNavigator(language="en", decimal_separator=separator)
            navigator.load(mathml)
            self.assertIn(f"the set {number} comma", navigator.command("ReadCurrent"))

    def test_interval_and_set_fences_and_commas_read_by_themselves(self) -> None:
        # As MathCAT reads the character alone (mathcat_lone), not the symbol dictionary.
        whole, stops = read("x∈(a,b)")
        self.assertIn("open interval from", whole)
        self.assertEqual(stops[2:7], ["open paren", "eigh", "comma", "b", "close paren"])
        whole, stops = read("[0,1)")
        self.assertIn("closed open interval from 0 to 1", whole)
        self.assertEqual(stops[:5], ["open bracket", "0", "comma", "1", "close paren"])
        _whole, stops = read("{a,b}")
        self.assertEqual(stops[:5], ["open brace", "eigh", "comma", "b", "close brace"])

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
        self.assertEqual(
            whole.split(), ["the", "max", "over", "x", "is", "an", "element", "of", "cap", "eigh", "of", "f"]
        )
        self.assertIn("start condition", stops)

    def test_bars_frame_their_content(self) -> None:
        whole, stops = read("|x|+1")
        self.assertEqual(whole, "the absolute value of x, plus 1")
        self.assertEqual(stops[:3], ["start absolute value", "x", "end absolute value"])


if __name__ == "__main__":
    unittest.main()
