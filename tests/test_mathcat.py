import unittest
from pathlib import Path

from matex.mathcat import MathCatNavigator
from matex.model import EquationDocument


class MathCatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.navigator = MathCatNavigator(language="en")
        self.document = EquationDocument("a/(b+c)")

    def test_expression_speech_comes_from_mathcat(self) -> None:
        speech = self.navigator.load(self.document.mathml)
        self.assertIn("fraction", speech)
        self.assertIn("plus", speech)

    def test_operator_is_reached_by_mathcat_navigation(self) -> None:
        self.navigator.load(self.document.mathml)
        commands = [
            "ZoomIn",     # numerator
            "MoveNext",   # denominator
            "ZoomIn",     # opening parenthesis
            "MoveNext",   # b + c
            "ZoomIn",     # b
            "MoveNext",   # plus
        ]
        speech = ""
        for command in commands:
            speech = self.navigator.command(command)
        self.assertEqual(speech, "plus")
        self.assertEqual(self.navigator.current_path, (1, 0, 1))

    def test_math_edges_are_stops_of_their_own(self) -> None:
        # Left at the start used to leave the cursor on the first item, so
        # Right after "start of math" skipped straight to the second one.
        mathml = "<math><mi>a</mi><mo>+</mo><mi>b</mi></math>"
        for linear in (True, False):
            with self.subTest(linear=linear):
                navigator = MathCatNavigator(language="en", auto_zoom_out=linear)
                navigator.load(mathml)
                step = navigator.linear_command if linear else navigator.command_with_boundaries
                first = navigator.command("ZoomIn")
                self.assertEqual(step("MovePrevious"), "start of math")
                self.assertEqual(step("MovePrevious"), "start of math")
                self.assertEqual(step("MoveNext"), first)
                self.assertEqual(step("MoveNext"), "plus")
                last = step("MoveNext")
                self.assertEqual(step("MoveNext"), "end of math")
                self.assertEqual(step("MovePrevious"), last)
                self.assertEqual(step("MovePrevious"), "plus")

    def test_structure_stops_give_every_structure_a_start_and_an_end(self) -> None:
        mathml = (
            "<math><mfrac><mrow><mi>a</mi><mo>+</mo><mi>b</mi></mrow><mi>c</mi></mfrac>"
            "<mo>=</mo><mn>1</mn></math>"
        )
        navigator = MathCatNavigator(language="en", auto_zoom_out=True, boundary_stops=True)
        navigator.load(mathml)
        navigator.command("ZoomIn")  # Enters on "start of math".
        forward = [navigator.linear_command("MoveNext") for _ in range(14)]
        self.assertEqual(
            forward,
            [
                "start fraction", "start numerator", "eigh", "plus", "b", "end numerator",
                "start denominator", "c", "end denominator", "end fraction",
                "is equal to", "1", "end of math", "end of math",
            ],
        )
        backward = [navigator.linear_command("MovePrevious") for _ in range(14)]
        self.assertEqual(backward, list(reversed(forward[:-2])) + ["start of math", "start of math"])


    def test_invisible_times_is_not_a_linear_stop(self) -> None:
        # Converter output for "3x+1"; MathCAT reads its own invisible times
        # back as the bare U+2062 character, a stop VoiceOver says nothing on.
        navigator = MathCatNavigator(language="en", auto_zoom_out=True, boundary_stops=True)
        navigator.load("<math><mn>3</mn><mi>𝑥</mi><mo>+</mo><mn>1</mn></math>")
        navigator.command("ZoomIn")
        forward = [navigator.linear_command("MoveNext") for _ in range(5)]
        self.assertEqual(forward, ["3", "x", "plus", "1", "end of math"])

    def test_invisible_operator_stops_read_invisible_times_by_name(self) -> None:
        mathml = "<math><mn>3</mn><mi>𝑥</mi><mo>+</mo><mn>1</mn></math>"
        linear = MathCatNavigator(
            language="en", auto_zoom_out=True, boundary_stops=True, invisible_operator_stops=True
        )
        linear.load(mathml)
        linear.command("ZoomIn")
        forward = [linear.linear_command("MoveNext") for _ in range(6)]
        self.assertEqual(forward, ["3", "invisible times", "x", "plus", "1", "end of math"])
        structural = MathCatNavigator(
            language="en", auto_zoom_out=False, structural_stops=True, invisible_operator_stops=True
        )
        structural.load(mathml)
        structural.command("ZoomIn")
        step = structural.structural_command
        self.assertEqual(step("MoveNext"), "3 x")
        self.assertEqual(step("ZoomIn"), "start group")
        forward = [step("MoveNext") for _ in range(4)]
        self.assertEqual(forward, ["3", "invisible times", "x", "end group"])

    def test_structural_stops_frame_each_level(self) -> None:
        mathml = (
            "<math><mfrac><mrow><mi>a</mi><mo>+</mo><mi>b</mi></mrow><mi>c</mi></mfrac>"
            "<mo>=</mo><mn>1</mn></math>"
        )
        navigator = MathCatNavigator(language="en", auto_zoom_out=False, structural_stops=True)
        navigator.load(mathml)
        navigator.command("ZoomIn")  # Enters on "start of math".
        step = navigator.structural_command
        fraction = step("MoveNext")
        self.assertIn("fraction", fraction)
        self.assertEqual(step("MoveNext"), "is equal to")
        self.assertEqual(step("MoveNext"), "1")
        self.assertEqual(step("MoveNext"), "end of math")
        self.assertEqual(step("MovePrevious"), "1")
        for _ in range(2):
            step("MovePrevious")
        self.assertEqual(step("MovePrevious"), "start of math")
        self.assertEqual(step("MoveNext"), fraction)
        self.assertEqual(step("ZoomIn"), "start fraction")
        self.assertEqual(step("MoveNext"), "numerator, eigh plus b")
        self.assertEqual(step("MoveNext"), "denominator, c")
        self.assertEqual(step("MoveNext"), "end fraction")
        self.assertEqual(step("MovePrevious"), "denominator, c")
        self.assertEqual(step("ZoomOut"), fraction)

    def test_structural_stops_name_the_argument_of_a_marked_function(self) -> None:
        # Converter output for "lim_(n→∞) s_n".
        mathml = (
            '<math><mrow intent=":function"><munder><mi>lim</mi><mrow><mi>𝑛</mi><mo>→</mo>'
            "<mi>∞</mi></mrow></munder><mo>⁡</mo><msub><mi>𝑠</mi><mi>𝑛</mi></msub></mrow></math>"
        )
        navigator = MathCatNavigator(language="en", auto_zoom_out=False, structural_stops=True)
        navigator.load(mathml)
        navigator.command("ZoomIn")
        step = navigator.structural_command
        self.assertEqual(step("MoveNext"), "the limit as n approaches infinity")
        self.assertEqual(step("MoveNext"), "argument, s sub n")


    def test_local_mathcat_patches_are_applied(self) -> None:
        # scripts/bootstrap.sh applies patches/mathcat/*.patch; without
        # 0001, every navigation command reloads MathCAT's Unicode table.
        speech = Path(__file__).resolve().parents[1] / "MathCAT" / "src" / "speech.rs"
        self.assertIn(
            'pref_to_string("CheckRuleFiles") != "All";',
            speech.read_text(encoding="utf-8"),
        )

if __name__ == "__main__":
    unittest.main()

