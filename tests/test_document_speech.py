import unittest

from mathessible.mathcat.document_speech import equation_speech, speech_language

FRACTION = "<math><mfrac><mi>a</mi><mi>b</mi></mfrac></math>"


class DocumentSpeechTests(unittest.TestCase):
    def test_a_documents_language_or_english(self) -> None:
        self.assertEqual(speech_language("fr"), "fr")
        self.assertEqual(speech_language("pt-BR"), "pt")
        self.assertEqual(speech_language("zh-Hant-TW"), "zh-TW")
        self.assertEqual(speech_language("ro"), "en")  # MathCAT has no Romanian.
        self.assertEqual(speech_language(""), "en")


@unittest.skipUnless(__import__("importlib").util.find_spec("mathessible_mathcat"), "needs the native MathCAT")
class DocumentSpeechWithMathCatTests(unittest.TestCase):
    def test_equations_are_read_in_the_documents_language_on_a_mathcat_of_their_own(self) -> None:
        import mathessible_mathcat

        mathessible_mathcat.initialize("en", "SimpleSpeak", "Medium")
        mathessible_mathcat.set_expression("<math><mi>x</mi></math>")
        french, broken = equation_speech([FRACTION, "<not mathml"], "fr")
        self.assertIn("sur", french)
        self.assertEqual(broken, "")
        # This thread's MathCAT, as the editor's would be, still speaks English and holds its equation.
        self.assertEqual(mathessible_mathcat.speak_expression().strip(), "x")


if __name__ == "__main__":
    unittest.main()
