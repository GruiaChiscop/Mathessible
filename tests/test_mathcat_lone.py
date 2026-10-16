import unittest

from matex.mathcat import MathCatNavigator
from matex.mathcat_lone import lone_speech, lone_speeches


class LoneSpeechTests(unittest.TestCase):
    def test_characters_read_alone_by_mathcat(self) -> None:
        self.assertEqual(
            lone_speeches("(),"),
            {"(": "open paren", ")": "close paren", ",": "comma"},
        )
        self.assertEqual(lone_speech("4"), "4")
        self.assertEqual(lone_speech(" "), "space")

    def test_the_equation_being_read_is_not_touched(self) -> None:
        # MathCAT keeps one expression per thread; the lone readings use another thread.
        navigator = MathCatNavigator(language="en")
        navigator.load("<math><mi>a</mi><mo>+</mo><mi>b</mi></math>")
        navigator.command("ZoomIn")
        before = navigator.current_id
        self.assertEqual(navigator.character_speech("⟨"), "left angle bracket")
        self.assertEqual(navigator.current_id, before)
        self.assertIn("plus", navigator.command("ReadCurrent") + navigator.load(navigator.mathml))


if __name__ == "__main__":
    unittest.main()
