import unittest

from converter_harness import convert, has_error, needs_node
from matex.editing.build_repair import literal_repair, repairs
from matex.editing.edit_history import EditHistory
from matex.editing.linear_runs import (
    build_on_space,
    build_run,
    built_structure,
    edit_between,
    escape_insertions,
    script_steps,
    shift_runs,
    split_candidates,
    toggle_selection,
    typed,
)
from matex.editing.source_map import leaf_nodes, map_leaves


def linear_text(source: str, runs) -> str:
    return literal_repair(source, (), runs).text


class EscapeTests(unittest.TestCase):
    def test_build_up_operators_in_a_run_are_escaped(self) -> None:
        self.assertEqual(linear_text("a/b+c/", ((5, 6),)), "a/b+c\\/")
        self.assertEqual(linear_text("x^2+(y_1", ((4, 8),)), "x^2+\\(y\\_1")

    def test_letters_digits_and_ordinary_operators_are_left_alone(self) -> None:
        self.assertEqual(escape_insertions("a+b=c", ((0, 5),)), [])

    def test_what_is_already_escaped_and_control_words_are_left_alone(self) -> None:
        self.assertEqual(linear_text("\\(a\\alpha", ((0, 9),)), "\\(a\\alpha")
        self.assertEqual(linear_text("\\\\(", ((0, 3),)), "\\\\\\(")

    def test_a_run_opening_the_equation_is_not_taken_for_latex(self) -> None:
        # The converter reads a leading "\\(" as LaTeX's "\\( ... \\)" and fails.
        self.assertEqual(linear_text("(a+", ((0, 3),)), "\u200b\\(a+")
        self.assertEqual(linear_text("  [a", ((0, 4),)), "  \u200b\\[a")
        self.assertEqual(linear_text("x(a", ((1, 3),)), "x\\(a")

    def test_a_name_is_kept_apart_from_an_escaped_character(self) -> None:
        # Else "log" takes the linear "_" for its argument ("the log of under bar").
        self.assertEqual(linear_text("x+log_", ((5, 6),)), "x+log\u2062\\_")
        self.assertEqual(linear_text("sin (", ((4, 5),)), "sin \u2062\\(")
        self.assertEqual(linear_text("c/", ((1, 2),)), "c\\/")

    def test_repairs_do_not_close_what_a_run_opens(self) -> None:
        # "(a+" is linear: no ")" is added to build it.
        self.assertEqual([candidate.text for candidate in repairs("x+(a+", runs=((2, 5),))], ["x+\\(a+"])


class RunBookkeepingTests(unittest.TestCase):
    def test_edit_between(self) -> None:
        self.assertEqual(edit_between("ab", "acb"), (1, 0, 1))
        self.assertEqual(edit_between("abc", "ac"), (1, 1, 0))
        self.assertEqual(edit_between("\\alpha", "α"), (0, 6, 1))
        # "a" typed after "a": put where the caret is.
        self.assertEqual(edit_between("aa", "aaa", caret=2), (1, 0, 1))

    def test_typing_grows_the_run_it_touches_or_starts_one(self) -> None:
        self.assertEqual(typed((), 3, 0, 1), ((3, 4),))
        self.assertEqual(typed(((3, 4),), 4, 0, 1), ((3, 5),))
        self.assertEqual(typed(((3, 5),), 3, 0, 1), ((3, 6),))
        self.assertEqual(typed(((3, 5),), 0, 0, 1), ((0, 1), (4, 6)))

    def test_deleting_shrinks_a_run_and_drops_an_empty_one(self) -> None:
        self.assertEqual(typed(((3, 5),), 4, 1, 0), ((3, 4),))
        self.assertEqual(typed(((3, 4),), 3, 1, 0), ())
        self.assertEqual(typed(((3, 4),), 0, 1, 0), ((2, 3),))

    def test_other_edits_move_runs_or_drop_the_ones_they_touch(self) -> None:
        self.assertEqual(shift_runs(((3, 5),), 0, 0, 2), ((5, 7),))
        self.assertEqual(shift_runs(((3, 5),), 5, 0, 2), ((3, 5),))
        self.assertEqual(shift_runs(((3, 5),), 4, 0, 2), ())
        self.assertEqual(shift_runs(((3, 5),), 2, 2, 0), ())

    def test_f2_on_a_selection_makes_it_linear_or_builds_the_linear_text_in_it(self) -> None:
        self.assertEqual(toggle_selection((), 2, 9), (((2, 9),), True))
        self.assertEqual(toggle_selection(((0, 1),), 2, 9), (((0, 1), (2, 9)), True))
        # Touching linear text: every run it touches builds, nothing else changes.
        self.assertEqual(toggle_selection(((2, 9), (12, 14)), 0, 3), (((12, 14),), False))
        self.assertEqual(toggle_selection(((2, 9), (12, 14)), 5, 13), ((), False))

    def test_split_candidates_longest_built_part_first(self) -> None:
        self.assertEqual(split_candidates("a/b+c/d", (4, 7)), [7, 5, 4])
        self.assertEqual(split_candidates("(a+", (0, 3)), [3, 0])


@needs_node
class BuildRunTests(unittest.TestCase):
    def built(self, source: str, run: tuple[int, int], others=()) -> tuple:
        runs = tuple(sorted((run, *others)))
        return build_run(source, runs, run, lambda candidate: convert(linear_text(source, candidate)))

    def test_what_is_complete_builds_and_the_rest_stays_linear(self) -> None:
        self.assertEqual(self.built("a/b+c/", (0, 6)), ((5, 6),))
        self.assertEqual(self.built("x^", (0, 2)), ((1, 2),))

    def test_a_complete_run_builds_whole(self) -> None:
        self.assertEqual(self.built("a/b+c/d ", (5, 8)), ())
        self.assertEqual(self.built("x^2 ", (1, 4)), ())

    def test_an_open_bracket_keeps_everything_after_it_linear(self) -> None:
        self.assertEqual(self.built("x+(a+", (0, 5)), ((2, 5),))
        self.assertEqual(self.built("(a+", (0, 3)), ((0, 3),))

    def test_an_error_outside_the_run_does_not_stop_it_building(self) -> None:
        # "1/" stays broken before; "x^2 " still builds.
        self.assertEqual(self.built("1/ + x^2 ", (5, 9)), ())

    def test_linear_text_is_ordinary_tokens_with_no_error(self) -> None:
        mathml = convert(linear_text("a/b+c/", ((5, 6),)))
        self.assertFalse(has_error(mathml))
        self.assertIn("<mfrac>", mathml)
        self.assertIn('intent=":text"', mathml)


class BuiltStructureTests(unittest.TestCase):
    def test_the_new_structure_is_named_outermost_first(self) -> None:
        before = "<math><mi>c</mi><mo>/</mo><mi>d</mi></math>"
        after = "<math><mfrac><msup><mi>c</mi><mn>2</mn></msup><mi>d</mi></mfrac></math>"
        self.assertEqual(built_structure(before, after), "fraction")

    def test_limits_on_an_n_ary_sign_are_named_by_the_sign(self) -> None:
        before = "<math><mo>∫</mo><mi>x</mi></math>"
        after = '<math><msubsup id="s"><mo id="o">∫</mo><mn>0</mn><mn>1</mn></msubsup><mi>x</mi></math>'
        self.assertEqual(built_structure(before, after), "integral")
        self.assertEqual(built_structure(before, after.replace("∫", "∑")), "sum")

    def test_nothing_new_is_none(self) -> None:
        fraction = "<math><mfrac><mi>a</mi><mi>b</mi></mfrac><mo>+</mo><mi>c</mi></math>"
        self.assertIsNone(built_structure(fraction, fraction.replace("<mi>c</mi>", "<mi>c</mi><mi>d</mi>")))

    def test_a_second_one_of_a_kind_counts(self) -> None:
        one = "<math><mfrac><mi>a</mi><mi>b</mi></mfrac></math>"
        two = "<math><mfrac><mi>a</mi><mi>b</mi></mfrac><mfrac><mi>c</mi><mi>d</mi></mfrac></math>"
        self.assertEqual(built_structure(one, two), "fraction")


class HistoryTests(unittest.TestCase):
    def test_undo_right_after_a_build_brings_the_linear_run_back(self) -> None:
        history = EditHistory("c/d")
        history.push("c/d ", 4)
        history.set_runs(((0, 4),))
        history.push("c/d ", 4, ())  # The build: same source, nothing linear.
        state = history.undo()
        self.assertEqual((state.source, state.runs), ("c/d ", ((0, 4),)))
        self.assertEqual(history.undo().source, "c/d")


@needs_node
class TypingTests(unittest.TestCase):
    """Typing character by character as the editor does: runs grow, and a trigger builds."""

    def type_text(self, text: str, source: str = "", runs=()) -> list[tuple[str, tuple]]:
        steps = []
        for character in text:
            caret = len(source)
            source += character
            runs = typed(runs, caret, 0, 1)
            if character == " " or not (character.isascii() and character.isalnum() or character in "^_"):
                run = next(run for run in runs if run[0] <= len(source) <= run[1])
                runs = build_run(source, runs, run, lambda candidate, s=source: convert(linear_text(s, candidate)))
            steps.append((source, runs))
        return steps

    def test_a_fraction_builds_on_the_space_after_its_denominator(self) -> None:
        steps = dict(self.type_text("a/b+c/d "))
        self.assertEqual(steps["a/"], ((1, 2),))  # "a" built, "/" linear.
        self.assertEqual(steps["a/b"], ((1, 3),))  # A letter is no trigger.
        self.assertEqual(steps["a/b+"], ())  # "+" ends the denominator: the fraction builds.
        self.assertEqual(steps["a/b+c/"], ((5, 6),))
        self.assertEqual(steps["a/b+c/d "], ())

    def test_brackets_stay_linear_until_closed_and_ended(self) -> None:
        steps = dict(self.type_text("(a+b)/2 "))
        self.assertEqual(steps["(a+"], ((0, 3),))
        self.assertEqual(steps["(a+b)"], ())  # A complete group builds.
        self.assertEqual(steps["(a+b)/"], ((5, 6),))
        self.assertEqual(steps["(a+b)/2 "], ())

    def test_a_script_builds_one_space_at_a_time(self) -> None:
        steps = dict(self.type_text("x^2 "))
        self.assertEqual(steps["x^"], ((0, 2),))  # "^" builds nothing: it binds what comes after.
        self.assertEqual(steps["x^2 "], ())


class ScriptStepTests(unittest.TestCase):
    def test_a_chain_of_the_same_script_builds_innermost_first(self) -> None:
        self.assertEqual(script_steps("a^b^c ", (0, 6)), [3])
        self.assertEqual(script_steps("a^b^c^d ", (0, 8)), [5, 3])
        self.assertEqual(script_steps("x_i_j ", (0, 6)), [3])

    def test_a_subscript_with_a_superscript_is_one_structure(self) -> None:
        self.assertEqual(script_steps("a_1^2 ", (0, 6)), [])
        self.assertEqual(script_steps("a^(b+1)^c ", (0, 10)), [])


@needs_node
class SpaceBuildTests(unittest.TestCase):
    """Space builds one script of a chain at a time, as Word does (UTN #28 sec. 2.3)."""

    def space(self, source: str, runs, run, below=None):
        return build_on_space(source, runs, run, lambda candidate: convert(linear_text(source, candidate)), below)

    def test_two_spaces_build_a_to_the_b_to_the_c(self) -> None:
        runs, step = self.space("a^b^c ", ((0, 6),), (0, 6))
        self.assertEqual((runs, step), (((0, 3),), 3))  # b^c built, "a^" still linear.
        self.assertIn("<msup><mi>𝑏</mi><mi>𝑐</mi></msup>", convert(linear_text("a^b^c ", runs)))
        # The second Space goes on from the chain's start: all of it builds.
        runs, step = self.space("a^b^c  ", ((0, 7),), (0, 7), below=3)
        self.assertEqual((runs, step), ((), None))

    def test_one_script_builds_whole(self) -> None:
        self.assertEqual(self.space("x^2 ", ((0, 4),), (0, 4)), ((), None))
        self.assertEqual(self.space("a_1^2 ", ((0, 6),), (0, 6)), ((), None))

    def test_an_operator_builds_the_whole_chain(self) -> None:
        source = "a^b^c+"
        built = build_run(source, ((0, 6),), (0, 6), lambda candidate: convert(linear_text(source, candidate)))
        self.assertEqual(built, ())


@needs_node
class LinearRunReadingTests(unittest.TestCase):
    def test_the_source_map_skips_the_escapes(self) -> None:
        from matex.mathcat.navigator import MathCatNavigator

        source = "a/b+c/d"
        repair = literal_repair(source, (), ((5, 7),))
        navigator = MathCatNavigator(language="en")
        navigator.load(convert(repair.text))
        spans = map_leaves(repair.text, navigator.structure)
        mapped = [
            source[repair.to_real(spans[leaf.identifier].start) : repair.to_real(spans[leaf.identifier].end)]
            for leaf in leaf_nodes(navigator.structure)
            if leaf.identifier in spans
        ]
        self.assertEqual(mapped, ["a", "b", "+", "c", "/", "d"])

    def test_a_function_name_before_linear_text_takes_no_argument(self) -> None:
        from matex.mathcat.navigator import MathCatNavigator

        navigator = MathCatNavigator(language="en")
        speech = navigator.load(convert(linear_text("x+log_", ((5, 6),))))
        self.assertEqual(speech, "x plus the log under bar")

    def test_mathcat_reads_linear_text_as_its_characters(self) -> None:
        from matex.mathcat.navigator import MathCatNavigator

        navigator = MathCatNavigator(language="en")
        speech = navigator.load(convert(linear_text("a/b+c/", ((5, 6),))))
        self.assertIn("eigh over b", speech)
        self.assertIn("c divided by", speech)


if __name__ == "__main__":
    unittest.main()
