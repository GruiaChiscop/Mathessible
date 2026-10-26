import unittest

from converter_harness import convert, needs_node
from matex.documents.clipboard_html import document_html, equation_html


@needs_node
class ClipboardHtmlTests(unittest.TestCase):
    """Word builds an equation from MathML in the clipboard's HTML."""

    def test_an_equation_is_namespaced_mathml_with_its_source(self) -> None:
        html = equation_html(convert("a/b<c"), "a/b<c", display=False)
        assert html is not None
        self.assertIn('<math xmlns="http://www.w3.org/1998/Math/MathML" display="inline" alttext="a/b&lt;c">', html)
        self.assertIn("<mfrac>", html)
        self.assertEqual(html.count("display="), 1)
        self.assertIn('display="block"', equation_html(convert("x"), "x", display=True) or "")

    def test_what_does_not_build_has_no_html(self) -> None:
        self.assertIsNone(equation_html(convert("a/"), "a/", display=False))

    def test_a_document_keeps_its_text_and_builds_its_equations(self) -> None:
        html = document_html("The roots of $x^2=1$ are\n\n$$x=±1$$\n\nand $a/$.", convert)
        assert html is not None
        self.assertIn("The roots of", html)
        self.assertIn(
            '<span class="math-inline"><math xmlns="http://www.w3.org/1998/Math/MathML" display="inline"', html
        )
        self.assertIn('<math xmlns="http://www.w3.org/1998/Math/MathML" display="block"', html)
        self.assertIn('class="math-error"', html)  # `a/` stays its source.
        self.assertIsNone(document_html("No equations here.", convert))


if __name__ == "__main__":
    unittest.main()
