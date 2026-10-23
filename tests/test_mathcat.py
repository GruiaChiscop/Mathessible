import unittest
from pathlib import Path

from matex.mathcat.navigator import MathCatNavigator

# Converter output for "a/(b+c)".
A_OVER_B_PLUS_C = '<math display="inline"><mfrac><mi>𝑎</mi><mrow><mi>𝑏</mi><mo>+</mo><mi>𝑐</mi></mrow></mfrac></math>'


class MathCatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.navigator = MathCatNavigator(language="en")

    def test_expression_speech_comes_from_mathcat(self) -> None:
        speech = self.navigator.load(A_OVER_B_PLUS_C)
        self.assertIn("fraction", speech)
        self.assertIn("plus", speech)

    def test_operator_is_reached_by_mathcat_navigation(self) -> None:
        self.navigator.load(A_OVER_B_PLUS_C)
        commands = [
            "ZoomIn",  # numerator
            "MoveNext",  # denominator
            "ZoomIn",  # b
            "MoveNext",  # plus
        ]
        speech = ""
        for command in commands:
            speech = self.navigator.command(command)
        self.assertEqual(speech, "plus")
        self.assertEqual(self.navigator.structure.node(self.navigator.current_id).text, "+")

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

    def test_linear_unicodemath_syntax_in_braille(self) -> None:
        # Patch 0006: a linear "_" is Nemeth's long dash (omission), and "▒" its control word.
        def braille(mathml: str, code: str) -> str:
            navigator = MathCatNavigator(language="en")
            navigator.braille_code = code
            navigator.load(mathml)
            cells = navigator._native.braille(navigator.structure.root.identifier)
            return "".join(chr(0x2800 + ((ord(cell) - 0x2800) & 0x3F)) for cell in cells)  # No dots 7-8.

        underscore = '<math><mi>x</mi><mo intent=":text">_</mo></math>'
        self.assertEqual(braille(underscore, "Nemeth"), "⠭⠤⠤⠤⠤")
        self.assertEqual(braille(underscore, "UEB"), "⠭⠨⠤")
        naryand = '<math><mi>x</mi><mo intent=":text">▒</mo></math>'
        self.assertEqual(braille(naryand, "Nemeth"), "⠭⠸⠡⠕⠋")
        self.assertEqual(braille(naryand, "UEB"), "⠭⠸⠡⠕⠋")

    def test_a_final_period_is_its_own_stop_not_the_whole_line(self) -> None:
        # MathCAT groups everything before a final "." and read it all on the period.
        mathml = "<math><mi>x</mi><mo>+</mo><mn>1</mn><mo>.</mo></math>"
        navigator = MathCatNavigator(language="en", auto_zoom_out=True, boundary_stops=True)
        navigator.load(mathml)
        navigator.command("ZoomIn")
        forward = [navigator.linear_command("MoveNext") for _ in range(5)]
        self.assertEqual(forward, ["x", "plus", "1", "dot", "end of math"])

    def test_structure_stops_give_every_structure_a_start_and_an_end(self) -> None:
        mathml = "<math><mfrac><mrow><mi>a</mi><mo>+</mo><mi>b</mi></mrow><mi>c</mi></mfrac><mo>=</mo><mn>1</mn></math>"
        navigator = MathCatNavigator(language="en", auto_zoom_out=True, boundary_stops=True)
        navigator.load(mathml)
        navigator.command("ZoomIn")  # Enters on "start of math".
        forward = [navigator.linear_command("MoveNext") for _ in range(14)]
        self.assertEqual(
            forward,
            [
                "start fraction",
                "start numerator",
                "eigh",
                "plus",
                "b",
                "end numerator",
                "start denominator",
                "c",
                "end denominator",
                "end fraction",
                "is equal to",
                "1",
                "end of math",
                "end of math",
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
        linear = MathCatNavigator(language="en", auto_zoom_out=True, boundary_stops=True, invisible_operator_stops=True)
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
        mathml = "<math><mfrac><mrow><mi>a</mi><mo>+</mo><mi>b</mi></mrow><mi>c</mi></mfrac><mo>=</mo><mn>1</mn></math>"
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

    def test_text_above_an_arrow_is_announced_in_both_navigation_modes(self) -> None:
        # Converter output for "a→┴(q) x".
        mathml = '<math><mi>𝑎</mi><mover><mo stretchy="true">→</mo><mi>𝑞</mi></mover><mi>𝑥</mi></math>'
        linear = MathCatNavigator(language="en", auto_zoom_out=True, boundary_stops=True)
        linear.load(mathml)
        linear.command("ZoomIn")
        forward = [linear.linear_command("MoveNext") for _ in range(5)]
        self.assertEqual(forward, ["eigh", "right arrow", "start text above", "q", "end text above"])
        structural = MathCatNavigator(language="en", auto_zoom_out=False, structural_stops=True)
        structural.load(mathml)
        structural.command("ZoomIn")
        step = structural.structural_command
        step("MoveNext")
        step("MoveNext")
        self.assertEqual(step("ZoomIn"), "start arrow")
        self.assertEqual([step("MoveNext") for _ in range(3)], ["base, right arrow", "text above, q", "end arrow"])

    def test_a_root_reads_its_index_before_its_radicand(self) -> None:
        # MathML has the radicand first; "cube root of" and `√(3&x+1)` the index.
        mathml = "<math><mroot><mrow><mi>x</mi><mo>+</mo><mn>1</mn></mrow><mn>3</mn></mroot></math>"
        linear = MathCatNavigator(language="en", auto_zoom_out=True, boundary_stops=True)
        linear.load(mathml)
        linear.command("ZoomIn")
        forward = [linear.linear_command("MoveNext") for _ in range(9)]
        self.assertEqual(
            forward,
            ["start root", "start index", "3", "end index", "start radicand", "x", "plus", "1", "end radicand"],
        )
        self.assertEqual(linear.linear_command("MovePrevious"), "1")
        structural = MathCatNavigator(language="en", auto_zoom_out=False, structural_stops=True)
        structural.load(mathml)
        structural.command("ZoomIn")
        step = structural.structural_command
        step("MoveNext")
        self.assertEqual(step("ZoomIn"), "start root")
        self.assertEqual([step("MoveNext") for _ in range(3)], ["index, 3", "radicand, x plus 1", "end root"])

    def test_flat_reading_frames_matrix_rows_and_cells(self) -> None:
        # Converter output for "(■(1&0@0&1))": "1 0 0 1" alone says nothing about the shape.
        mathml = (
            '<math><mrow intent=":fenced"><mo>(</mo><mtable intent=":array(2,2)"><mtr><mtd><mn>1</mn></mtd>'
            "<mtd><mn>0</mn></mtd></mtr><mtr><mtd><mn>0</mn></mtd><mtd><mn>1</mn></mtd></mtr></mtable>"
            "<mo>)</mo></mrow></math>"
        )
        navigator = MathCatNavigator(language="en", auto_zoom_out=True, boundary_stops=True)
        navigator.load(mathml)
        navigator.command("ZoomIn")
        forward = [navigator.linear_command("MoveNext") for _ in range(10)]
        self.assertEqual(
            forward,
            [
                "start matrix",
                "start row 1",
                "start column 1",
                "1",
                "end column 1",
                "start column 2",
                "0",
                "end column 2",
                "end row 1",
                "start row 2",
            ],
        )
        self.assertEqual(navigator.linear_command("MovePrevious"), "end row 1")

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

    def test_an_empty_naryand_stays_a_node(self) -> None:
        # Needs patches/mathcat/0002 (canonicalize keeps an `arg` whitespace mtext).
        mathml = (
            '<math><mrow intent=":nary(,,$naryand)"><mo>∫</mo><mrow arg="naryand">'
            '<mspace width="0" /></mrow></mrow></math>'
        )
        navigator = MathCatNavigator(language="en")
        navigator.load(mathml)
        leaves = [node.text for node in navigator.structure.by_id.values() if not node.children]
        self.assertIn("\u00a0", leaves)

    def test_local_mathcat_patches_are_applied(self) -> None:
        # scripts/bootstrap.sh applies patches/mathcat/*.patch; without
        # 0001, every navigation command reloads MathCAT's Unicode table.
        speech = Path(__file__).resolve().parents[1] / "MathCAT" / "src" / "speech.rs"
        self.assertIn(
            'pref_to_string("CheckRuleFiles") != "All";',
            speech.read_text(encoding="utf-8"),
        )


class NavigationRobustnessTests(unittest.TestCase):
    """Found by the navigation audit: MathCAT's own moves fail inside sums and integrals."""

    SUM = (
        '<math><mrow intent=":nary($l,𝑛,$naryand)"><munderover><mo>∑</mo><mrow arg="l"><mi>𝑖</mi><mo>=</mo>'
        '<mn>1</mn></mrow><mi>𝑛</mi></munderover><mrow arg="naryand"><mi>𝑖</mi></mrow></mrow></math>'
    )
    INTEGRAL = (
        '<math><mrow intent=":nary(,,$naryand)"><mo>∫</mo><mrow arg="naryand"><mi>𝑓</mi>'
        '<mrow intent=":fenced"><mo>(</mo><mi>𝑥</mi><mo>)</mo></mrow><mi>𝑑</mi><mi>𝑥</mi></mrow></mrow></math>'
    )

    def every_mode(self):
        for options in (
            {"auto_zoom_out": True, "boundary_stops": True},
            {"auto_zoom_out": True},
            {"auto_zoom_out": False, "structural_stops": True},
            {"auto_zoom_out": False},
        ):
            yield options, ("structural" if not options["auto_zoom_out"] else "linear")

    def test_home_end_and_arrows_never_fail_or_go_silent(self) -> None:
        for mathml in (self.SUM, self.INTEGRAL):
            for options, kind in self.every_mode():
                with self.subTest(options=options, mathml=mathml[:40]):
                    navigator = MathCatNavigator(language="en", **options)
                    navigator.load(mathml)
                    navigator.command("ZoomIn")
                    step = navigator.linear_command if kind == "linear" else navigator.structural_command
                    for command in (
                        "MoveEnd",
                        "MoveStart",
                        "MoveNext",
                        "MoveNext",
                        "MoveEnd",
                        "MovePrevious",
                        "MoveNext",
                    ):
                        self.assertTrue(step(command).strip(), command)

    def test_stops_from_the_worker_never_point_at_missing_nodes(self) -> None:
        # The worker's MathCAT re-canonicalizes the MathML: for f'(x) it gave the
        # function application it adds new ids, and Right then failed ("not found").
        import threading

        mathml = (
            '<math><msup><mi>𝑓</mi><mo>′</mo></msup><mrow intent=":fenced"><mo>(</mo><mi>𝑥</mi><mo>)</mo></mrow></math>'
        )
        navigator = MathCatNavigator(language="en", auto_zoom_out=True, boundary_stops=True)
        navigator.load(mathml)
        navigator.command("ZoomIn")
        job, found = navigator.linear_stops_job(), {}
        worker = threading.Thread(target=lambda: found.setdefault("stops", job()))
        worker.start()
        worker.join()
        navigator.adopt_linear_stops(navigator.mathml, found["stops"])
        for _ in range(8):
            navigator.linear_command("MoveNext")
        self.assertTrue(all(navigator.structure.node(stop.node_id) for stop in navigator._linear_stops))

    def test_home_and_end_in_linear_navigation_are_the_math_edges(self) -> None:
        navigator = MathCatNavigator(language="en", auto_zoom_out=True, boundary_stops=True)
        navigator.load(self.SUM)
        navigator.command("ZoomIn")
        self.assertEqual(navigator.linear_command("MoveEnd"), "end of math")
        self.assertEqual(navigator.linear_command("MoveStart"), "start of math")
        self.assertEqual(navigator.linear_command("MoveNext"), "sum")

    def test_without_structure_stops_a_sum_is_walked_from_the_structure(self) -> None:
        # MathCAT's own Right said "in part 1" and an "empty" summand here.
        navigator = MathCatNavigator(language="en", auto_zoom_out=True)
        navigator.load(self.SUM)
        navigator.command("ZoomIn")
        forward = [navigator.linear_command("MoveNext") for _ in range(13)]
        self.assertNotIn("empty", forward)
        self.assertNotIn("in part 1", forward)
        self.assertEqual(forward[:3], ["sum", "start lower limit", "i"])
        self.assertEqual(forward[-1], "end of math")


if __name__ == "__main__":
    unittest.main()
