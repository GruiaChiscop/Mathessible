import unittest
from xml.etree import ElementTree

from converter_harness import convert_all, needs_node
from mathessible.documents.omml_math import M, omml_math

SOURCES = [
    "x=(-b±√(b^2-4ac))/(2a)",
    "∑_(k=1)^n k^2",
    "∫_0^1▒〖x^2 dx〗",
    "lim_(x→∞) 〖1/x〗",
    "sin^2 x",
    "(■(1&0@0&1))",
    "{■(x&x≥0@-x&x<0)┤",
    "√(3&x)",
    "E=mc^2#(1)",
    "█(x+y&=1@x-y&=3)",
    '"if "x>0',
    "x̂",
    "(n¦k)",
    "x⁄y",
    "⏞(a+b)┴n",
    "|x|",
    "□(x)",
]


def tags(xml: str) -> list[str]:
    return [element.tag.removeprefix(f"{{{M}}}") for element in ElementTree.fromstring(xml).iter()]


@needs_node
class OmmlMathTests(unittest.TestCase):
    """The converter's real MathML, as Word's own equation elements."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.omml = {
            source: omml_math(result["mathml"]) for source, result in zip(SOURCES, convert_all(SOURCES), strict=True)
        }

    def has(self, source: str, *expected: str) -> None:
        found = tags(self.omml[source].xml)
        for tag in expected:
            self.assertIn(tag, found, f"{source}: no m:{tag} in {found}")

    def test_every_equation_is_one_well_formed_omath(self) -> None:
        for source, equation in self.omml.items():
            with self.subTest(source=source):
                self.assertEqual(tags(equation.xml)[0], "oMath")

    def test_each_structure_is_words_own(self) -> None:
        self.has("x=(-b±√(b^2-4ac))/(2a)", "f", "num", "den", "rad", "sSup")
        self.has("∑_(k=1)^n k^2", "nary", "sub", "sup")
        self.has("∫_0^1▒〖x^2 dx〗", "nary")
        self.assertNotIn("d", tags(self.omml["∫_0^1▒〖x^2 dx〗"].xml))  # 〖〗 is no delimiter in Word.
        self.has("lim_(x→∞) 〖1/x〗", "func", "fName", "limLow")
        self.has("sin^2 x", "func", "sSup")
        self.has("(■(1&0@0&1))", "d", "m", "mr")
        self.has("{■(x&x≥0@-x&x<0)┤", "d", "m")  # Cases: a matrix in a brace, as Word builds ■.
        self.has("√(3&x)", "rad", "deg")
        self.has("█(x+y&=1@x-y&=3)", "eqArr")
        self.has("x̂", "acc")
        self.has("(n¦k)", "f", "fPr")
        self.has("⏞(a+b)┴n", "groupChr", "limUpp")

    def test_numbers_and_text(self) -> None:
        self.assertEqual(self.omml["E=mc^2#(1)"].number, "(1)")
        self.assertIn("<m:nor/>", self.omml['"if "x>0'].xml)
        self.assertIn("□(x)", self.omml["□(x)"].xml)  # What does not build: its source, as text.
        self.assertIn('<m:t xml:space="preserve">&amp;</m:t>', self.omml["█(x+y&=1@x-y&=3)"].xml)  # Alignment.

    def test_text_is_escaped(self) -> None:
        xml = omml_math('<math><mtext>&lt;w:p&gt; &amp; "</mtext></math>').xml
        self.assertEqual(ElementTree.fromstring(xml).find(f".//{{{M}}}t").text, '<w:p> & "')


if __name__ == "__main__":
    unittest.main()
