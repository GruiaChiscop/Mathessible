import unittest

from converter_harness import convert_all, needs_node
from mathessible.documents.latex_detection import has_latex_equations
from mathessible.documents.markdown_math import find_math_zones
from mathessible.unicodemath import UnicodeMathError


def real_converter(source: str):
    """The converter for every equation of `source`, both ways, as the editor's `convert_equation` (errors raise)."""
    equations = [zone.content(source) for zone in find_math_zones(source)]
    built = {latex: dict(zip(equations, convert_all(equations, latex=latex), strict=True)) for latex in (False, True)}

    def convert(equation: str, latex: bool) -> str:
        result = built[latex][equation]
        if result.get("error"):
            raise UnicodeMathError(result["error"])
        return result["mathml"]

    return convert


@needs_node
class LatexDetectionTests(unittest.TestCase):
    def check(self, source: str) -> bool:
        return has_latex_equations(source, real_converter(source))

    def test_markdown_from_github_or_pandoc_is_latex(self) -> None:
        self.assertTrue(self.check("Euler: $e^{i\\pi}+1=0$, and $$\\frac{a}{b}$$"))
        self.assertTrue(self.check("$x \\in \\mathbb{R}^n$ and $\\begin{pmatrix}a&b\\\\c&d\\end{pmatrix}$"))
        self.assertTrue(self.check("$\\hat{x}$ or $\\binom{n}{k}$, $\\text{if } x > 0$"))

    def test_unicodemath_is_not(self) -> None:
        source = (
            "$a/(b+c)$, $\\sqrt(x+1)$, $■(a&b@c&d)$, $\\alpha+β$, $∑_(i=1)^n i$, "
            '$\\matrix(a&b)$, $"area"=πr^2$, $\\int_0^1 f(x)dx$, $x \\le 2$'
        )
        self.assertFalse(self.check(source))

    def test_what_both_read_alike_says_nothing(self) -> None:
        self.assertFalse(self.check("$a/b$, $x^2$, $\\alpha+\\beta$, $\\sin x$"))
        self.assertFalse(self.check("No equations at all."))

    def test_a_document_marked_latex_is_not_asked_again(self) -> None:
        self.assertFalse(self.check("---\nmath: latex\n---\n$\\frac{a}{b}$"))

    def test_a_unicodemath_equation_that_needs_unicodemath_wins(self) -> None:
        convert = real_converter("$\\frac{a}{b}$ $\\sqrt(x)$")
        verdicts = {"\\frac{a}{b}": (True, False), "\\sqrt(x)": (False, True)}  # (as LaTeX, as UnicodeMath)

        def mixed(equation: str, latex: bool) -> str:
            if not verdicts[equation][0 if latex else 1]:
                raise UnicodeMathError("does not build")
            return convert(equation, latex)

        self.assertFalse(has_latex_equations("$\\frac{a}{b}$ $\\sqrt(x)$", mixed))


if __name__ == "__main__":
    unittest.main()
