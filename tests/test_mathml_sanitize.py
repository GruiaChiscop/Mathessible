import unittest

from matex.mathml_sanitize import MathMLModelError, sanitize_mathml


class SanitizeMathMLTests(unittest.TestCase):
    def test_passes_through_known_elements_and_attributes(self) -> None:
        source = '<math display="block"><mfrac><mi intent=":numerator">x</mi><mn>2</mn></mfrac></math>'
        self.assertEqual(sanitize_mathml(source), source)

    def test_rejects_non_math_root(self) -> None:
        with self.assertRaises(MathMLModelError):
            sanitize_mathml("<script>alert(1)</script>")

    def test_rejects_disallowed_descendant_elements(self) -> None:
        with self.assertRaises(MathMLModelError):
            sanitize_mathml('<math><mtext><script>alert(1)</script></mtext></math>')

    def test_drops_annotation_children_of_semantics(self) -> None:
        source = (
            "<math><semantics><mi>x</mi>"
            '<annotation-xml encoding="text/html">'
            "<script>alert(1)</script></annotation-xml>"
            "</semantics></math>"
        )
        self.assertEqual(sanitize_mathml(source), "<math><semantics><mi>x</mi></semantics></math>")

    def test_strips_disallowed_attributes_but_keeps_allowed_ones(self) -> None:
        source = '<math><mi onclick="alert(1)" mathvariant="italic" style="color:red">x</mi></math>'
        self.assertEqual(sanitize_mathml(source), '<math><mi mathvariant="italic">x</mi></math>')

    def test_escapes_text_content(self) -> None:
        source = "<math><mtext>1 &lt; 2</mtext></math>"
        self.assertEqual(sanitize_mathml(source), source)


if __name__ == "__main__":
    unittest.main()
