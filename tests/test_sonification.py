import math
import unittest

import numpy as np

from mathessible.documents.charts import parse_chart
from mathessible.sonification.graph import (
    GraphExplorer,
    Sound,
    View,
    default_view,
    default_view_for,
    frequency,
    function_chart_at,
    pan,
    scale_note,
)
from mathessible.sonification.synth import Synthesizer, earcon, stereo_gains
from mathessible.ui.graph_explorer import key_digit, key_letter


class GraphModelTests(unittest.TestCase):
    def test_a_function_chart_under_the_caret_is_found(self) -> None:
        source = "Before\n\n```chart\ntype: function\nfunction: x^2\n```\n\nAfter"
        self.assertEqual(function_chart_at(source, source.index("x^2")).functions, ("x^2",))
        self.assertIsNone(function_chart_at(source, 0))
        data = "```chart\ntype: bar\n| x | y |\n|---|---|\n| a | 1 |\n```"
        self.assertIsNone(function_chart_at(data, 10))

    def test_view_pitch_pan_and_discrete_notes(self) -> None:
        view = View(-10, 10, -5, 5)
        self.assertEqual((frequency(-5, view), frequency(5, view)), (100, 1000))
        self.assertIsNone(frequency(6, view))
        self.assertEqual((pan(-10, view), pan(0, view), pan(10, view)), (-1, 0, 1))
        self.assertAlmostEqual(scale_note(100), 130.8127826502993)
        self.assertAlmostEqual(scale_note(1000), 523.2511306011972)
        self.assertEqual(view.moved(right=0.25), View(-5, 15, -5, 5))
        self.assertEqual(view.zoomed(0.5), View(-5, 5, -2.5, 2.5))

    def test_default_view_ignores_a_poles_extreme(self) -> None:
        view = default_view(lambda x: 1 / x if x else math.nan, (-10, 10))
        self.assertEqual((view.x_min, view.x_max), (-10, 10))
        self.assertLess(view.y_min, 0)
        self.assertGreater(view.y_max, 0)
        self.assertLess(view.height, 10)

    def test_a_multi_function_chart_gets_one_view_that_covers_every_curve(self) -> None:
        view = default_view_for((lambda x: x, lambda x: 100 * x), (-1, 1))
        self.assertLessEqual(view.y_min, -50)
        self.assertGreaterEqual(view.y_max, 50)

    def test_explorer_moves_zooms_switches_functions_and_bookmarks(self) -> None:
        chart = parse_chart("type: function\nfunction: x; x^2\nx: -2 .. 2")
        explorer = GraphExplorer(chart)
        before = explorer.x
        explorer.step(1)
        self.assertEqual(explorer.x - before, 0.25)
        self.assertTrue(explorer.zoom(True))
        self.assertTrue(explorer.choose(1))
        explorer.discrete = True
        self.assertTrue(explorer.sound().strike)
        self.assertFalse(explorer.sound().strike)
        self.assertTrue(explorer.bookmark())
        self.assertTrue(any(point.kind == "bookmark" for point in explorer.points()))
        explorer.choose(0)
        self.assertFalse(explorer.bookmarks)
        explorer.choose(1)
        self.assertFalse(explorer.bookmark())

    def test_landmark_navigation_includes_and_wraps_at_view_boundaries(self) -> None:
        explorer = GraphExplorer(parse_chart("type: function\nfunction: x\nx: -2 .. 2"))
        explorer.go_to(0)
        self.assertTrue(explorer.bookmark())
        explorer.go_to(1)
        self.assertEqual(explorer.next_point(1).x, 2)
        self.assertEqual(explorer.next_point(1).x, -2)
        self.assertEqual(explorer.next_point(1).x, 0)


class SynthTests(unittest.TestCase):
    def test_equal_power_pan(self) -> None:
        self.assertAlmostEqual(stereo_gains(-1)[0], 1)
        self.assertAlmostEqual(stereo_gains(-1)[1], 0)
        left, right = stereo_gains(0)
        self.assertAlmostEqual(left, right)
        self.assertAlmostEqual(left * left + right * right, 1)

    def test_earcons_are_generated_not_loaded(self) -> None:
        signal = earcon("edge", 8_000)
        self.assertEqual(signal.ndim, 2)
        self.assertEqual(signal.shape[1], 2)
        self.assertGreater(float(np.max(np.abs(signal))), 0)

    def test_fm_voice_renders_stereo_and_silences(self) -> None:
        synth = Synthesizer(8_000)
        synth.update(Sound(440, -1, False, True))
        signal = synth.render(512)
        self.assertEqual(signal.shape, (512, 2))
        self.assertTrue(np.isfinite(signal).all())
        self.assertGreater(float(np.max(np.abs(signal[:, 0]))), float(np.max(np.abs(signal[:, 1]))))
        synth.silence()
        for _index in range(4):
            silent = synth.render(512)
        self.assertLess(float(np.max(np.abs(silent))), 0.01)

    def test_negative_noise_is_a_centred_background(self) -> None:
        synth = Synthesizer(8_000)
        synth.update(Sound(None, -1, True))
        signal = synth.render(128)
        np.testing.assert_allclose(signal[:, 0], signal[:, 1])

    def test_discrete_mode_uses_a_decaying_plucked_voice(self) -> None:
        synth = Synthesizer(8_000)
        synth.update(Sound(261.63, 0, False, True, True))
        attack = synth.render(512)
        synth.update(Sound(261.63, 0, False, False, True))
        for _index in range(30):
            tail = synth.render(512)
        self.assertGreater(float(np.max(np.abs(attack))), float(np.max(np.abs(tail))))


class KeyTests(unittest.TestCase):
    def test_a_letter_uses_unicode_or_the_platform_key_code(self) -> None:
        self.assertEqual(key_letter(ord("c"), 0), "C")
        self.assertEqual(key_letter(0, ord("v")), "V")
        self.assertEqual(key_letter(0, 314), "")  # Left arrow, not chr(314)'s letter.
        self.assertEqual(key_letter(0, 0), "")
        self.assertEqual(key_digit(ord("3"), 0), "3")
        self.assertEqual(key_digit(0, ord("8")), "8")


if __name__ == "__main__":
    unittest.main()
