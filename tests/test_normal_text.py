import unittest

from converter_harness import convert, has_error, needs_node
from matex.editing.build_repair import PLACEHOLDER, literal_repair, repairs
from matex.editing.normal_text import in_text, text_spans, toggle_normal_text
from matex.templates.insert_catalog import item_for_key


def toggled(source: str, caret: int, selection=None) -> tuple[str, str]:
    """The source with "|" at the new caret, and what is said."""
    edit = toggle_normal_text(source, caret, selection)
    return edit.source[: edit.caret] + "|" + edit.source[edit.caret :], edit.announcement


class TextSpanTests(unittest.TestCase):
    def test_quoted_text_and_an_unclosed_one(self) -> None:
        self.assertEqual(text_spans('"for all "x'), [(1, 9)])
        self.assertEqual(text_spans('x"if'), [(2, 4)])
        self.assertEqual(text_spans('x\\"y'), [])  # An escaped quote is a quote character.

    def test_quotes_typed_in_a_linear_run_delimit_nothing(self) -> None:
        self.assertEqual(text_spans('x"a"', ignored=((1, 4),)), [])

    def test_in_text(self) -> None:
        self.assertTrue(in_text('x"ab"', 2))
        self.assertTrue(in_text('x"ab"', 4))
        self.assertFalse(in_text('x"ab"', 5))
        self.assertFalse(in_text('x"ab"', 1))


class ToggleTests(unittest.TestCase):
    def test_in_math_it_starts_a_text(self) -> None:
        self.assertEqual(toggled("x=", 2), ('x="|"', "normal text"))

    def test_at_the_end_of_a_text_it_goes_back_to_math(self) -> None:
        self.assertEqual(toggled('x="for all "', 11), ('x="for all "|', "math"))
        self.assertEqual(toggled('"ab"', 1), ('|"ab"', "math"))

    def test_in_the_middle_of_a_text_it_splits_it(self) -> None:
        self.assertEqual(toggled('"abcd"', 3), ('"ab"|"cd"', "math"))

    def test_a_selection_in_math_becomes_text(self) -> None:
        self.assertEqual(toggled("a+b", 3, (0, 3)), ('"a+b|"', "normal text, a+b"))

    def test_a_selection_in_a_text_becomes_math(self) -> None:
        self.assertEqual(toggled('"abcdef"', 5, (3, 5)), ('"ab"cd|"ef"', "math, cd"))
        self.assertEqual(toggled('"cd"', 3, (1, 3)), ("cd|", "math, cd"))

    def test_texts_that_come_to_touch_are_joined(self) -> None:
        self.assertEqual(toggled('"ab"x"cd"', 5, (4, 5)), ('"abx|cd"', "normal text, x"))

    def test_the_insert_menu_has_it_on_command_shift_t(self) -> None:
        item = item_for_key("T", "command", True)
        self.assertIsNotNone(item)
        self.assertEqual(item.dialog, "normal_text")


class BuildingTests(unittest.TestCase):
    def test_an_empty_text_gets_a_placeholder(self) -> None:
        self.assertEqual([candidate.text for candidate in repairs('x=""')][-1], f'x="{PLACEHOLDER}"')

    def test_linear_text_is_not_escaped_inside_a_normal_text(self) -> None:
        # Typed into a text, "/" is text already: a backslash there would be text too.
        self.assertEqual(literal_repair('x"a/b"', (), ((2, 5),)).text, 'x"a/b"')
        self.assertEqual(literal_repair('c/"t"', (), ((0, 2),)).text, 'c\\/"t"')


@needs_node
class ConverterTests(unittest.TestCase):
    def test_a_text_maps_back_to_its_source_with_its_spaces(self) -> None:
        # The converter writes a text's spaces as no-break spaces.
        from matex.editing.source_map import leaf_characters, leaf_nodes, map_leaves
        from matex.mathcat.navigator import MathCatNavigator

        source = 'x="for all "y'
        navigator = MathCatNavigator(language="en")
        navigator.load(convert(source))
        spans = map_leaves(source, navigator.structure)
        text = next(leaf for leaf in leaf_nodes(navigator.structure) if leaf.tag == "mtext")
        span = spans[text.identifier]
        self.assertEqual(source[span.start : span.end], "for all ")
        self.assertEqual(leaf_characters(source, spans, navigator.structure, text.identifier), "for all ")

    def test_text_builds_as_mtext_and_an_empty_one_builds_clean(self) -> None:
        no_break = chr(0xA0)
        self.assertIn(f"<mtext>for{no_break}all{no_break}</mtext>", convert('"for all "x'))
        self.assertFalse(has_error(convert(f'x="{PLACEHOLDER}"')))


if __name__ == "__main__":
    unittest.main()
