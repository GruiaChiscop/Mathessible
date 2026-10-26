import unittest

import typst

from converter_harness import convert_all, needs_node
from mathessible.documents.typst_math import typst_math

# UnicodeMath, and the Typst math its MathML becomes.
EXPECTED = {
    "x=(-b±√(b^2-4ac))/(2a)": "x = frac(− b ± sqrt(attach(b, t: 2) − 4 a c), 2 a)",
    "∑_(k=1)^n k^2": "attach(limits(∑), b: k = 1, t: n) attach(k, t: 2)",
    "∫_0^1▒〖x^2 dx〗": "attach(∫, b: 0, t: 1) attach(x, t: 2) d x",
    "lim_(x→∞) 〖1/x〗": 'attach(limits(op("lim")), b: x → ∞) frac(1, x)',
    "sin^2 x": 'attach(op("sin"), t: 2) x',
    "(■(1&0@0&1))": 'mat(delim: "(", 1, 0; 0, 1)',
    "{■(x&x≥0@-x&x<0)┤": "cases(x & x ≥ 0, − x & x \\< 0)",
    "√(3&x)": "root(3, x)",
    "█(x+y&=1@x-y&=3)": "x + y & = 1 \\ x − y & = 3",
    '"if "x>0': '"if\u00a0" x \\> 0',  # The converter's no-break space, kept.
    "(n¦k)": "binom(n, k)",
    "1,5+2": '"1,5" + 2',
    "|x|": "lr(| x |)",
    "x⁄y": "x \\/ y",
    "⏞(a+b)┴n": "overbrace(a + b, n)",
    "f(x)": "f lr(\\( x \\))",
}


@needs_node
class TypstMathTests(unittest.TestCase):
    """The converter's real MathML, as Typst math that Typst compiles."""

    @classmethod
    def setUpClass(cls) -> None:
        sources = [*EXPECTED, "E=mc^2#(1)", "□(x)", "x̂+ȳ"]
        cls.mathml = {source: result["mathml"] for source, result in zip(sources, convert_all(sources), strict=True)}

    def compiles(self, math: str) -> None:
        typst.compile(f"#math.equation(block: true, ${math}$)".encode())

    def test_each_structure_and_typst_compiles_it(self) -> None:
        for source, expected in EXPECTED.items():
            with self.subTest(source=source):
                equation = typst_math(self.mathml[source])
                self.assertEqual(equation.math, expected)
                self.compiles(equation.math)

    def test_an_equation_number_is_kept_apart(self) -> None:
        equation = typst_math(self.mathml["E=mc^2#(1)"])
        self.assertEqual((equation.math, equation.number), ("E = m attach(c, t: 2)", "(1)"))

    def test_what_does_not_build_is_its_source_as_text(self) -> None:
        self.assertEqual(typst_math(self.mathml["□(x)"]).math, '"□(x)"')

    def test_text_cannot_reach_typst_code(self) -> None:
        math = typst_math('<math><mtext>#panic("x") $ \\ "</mtext><mo>#</mo></math>').math
        self.assertEqual(math, '"#panic(\\"x\\") $ \\\\ \\"" \\#')
        self.compiles(math)


if __name__ == "__main__":
    unittest.main()
