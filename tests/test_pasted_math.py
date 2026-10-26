import unittest

from mathessible.editing.pasted_math import pasted_mathml, plain_letters

FRACTION = '<math xmlns="http://www.w3.org/1998/Math/MathML"><mfrac><mi>a</mi><mi>b</mi></mfrac></math>'


class PastedMathmlTests(unittest.TestCase):
    def test_plain_text_is_pasted_as_it_is(self) -> None:
        self.assertIsNone(pasted_mathml("x_1=(-b±√(b^2-4ac))/2", None))  # Word's linear format.
        self.assertIsNone(pasted_mathml("a<b", "<p>a&lt;b</p>"))

    def test_mathml_as_plain_text_is_converted(self) -> None:
        self.assertEqual(pasted_mathml(FRACTION + "\n", None), FRACTION)
        word = '<mml:math xmlns:mml="http://www.w3.org/1998/Math/MathML"><mml:mi>x</mml:mi></mml:math>'
        self.assertEqual(pasted_mathml('<?xml version="1.0"?>\n' + word, None), word)

    def test_a_web_pages_one_equation_is_converted(self) -> None:
        html = f"<html><body><span>{FRACTION}</span></body></html>"
        self.assertEqual(pasted_mathml("a\nb", html), FRACTION)

    def test_several_equations_or_mathessible_own_copy_paste_the_text(self) -> None:
        self.assertIsNone(pasted_mathml("a b", f"<p>{FRACTION} and {FRACTION}</p>"))
        own = '<math xmlns="http://www.w3.org/1998/Math/MathML" display="inline" alttext="a/b&lt;c"><mi>a</mi></math>'
        self.assertIsNone(pasted_mathml("a/b<c", f"<body>{own}</body>"))
        self.assertEqual(pasted_mathml("something else", f"<body>{own}</body>"), own)


class PlainLettersTests(unittest.TestCase):
    def test_italic_letters_become_typed_ones(self) -> None:
        self.assertEqual(plain_letters("𝑥=(−𝑏±√(𝑏²−4𝑎𝑐))/2𝑎"), "x=(−b±√(b²−4ac))/2a")
        self.assertEqual(plain_letters("𝐸=𝑚𝑐²+ℎ𝜈+𝛼"), "E=mc²+hν+α")

    def test_other_alphabets_keep_their_meaning(self) -> None:
        self.assertEqual(plain_letters("𝐱+𝒜+ℝ+𝚤"), "𝐱+𝒜+ℝ+𝚤")


if __name__ == "__main__":
    unittest.main()
