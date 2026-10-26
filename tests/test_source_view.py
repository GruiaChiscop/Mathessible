import unittest

from mathessible.editing.source_view import edit_in_view, spell_with_control_words, view_of
from mathessible.templates.fraction_styles import restyle_fraction
from mathessible.templates.math_templates import (
    insert_integral_template,
    insert_limit_template,
    insert_operator_template,
    insert_square_root_template,
    insert_sum_template,
    move_to_slot,
)
from mathessible.templates.matrix_templates import insert_matrix_row, insert_matrix_template
from mathessible.templates.structure_edits import add_nary_limits, remove_nary_limits, remove_root_index


class SourceViewTests(unittest.TestCase):
    def test_control_words_resolve_with_one_trailing_space(self) -> None:
        view = view_of("\\sum_(i)\\of x")
        self.assertEqual(view.text, "∑_(i)▒x")
        # Offsets inside "\\of " count as before its "▒".
        self.assertEqual([view.to_view(offset) for offset in (0, 2, 4, 8, 10, 11, 12, 13)], [0, 0, 1, 5, 5, 5, 6, 7])
        self.assertEqual(view.to_source(5), 8)
        self.assertEqual(view.to_source(len(view.text)), len(view.source))

    def test_unknown_words_and_symbols_are_left_alone(self) -> None:
        self.assertEqual(view_of("\\nosuchword+√x").text, "\\nosuchword+√x")

    def test_spelling_adds_a_space_only_where_a_word_would_run_on(self) -> None:
        self.assertEqual(spell_with_control_words("∫▒", 2), ("\\int\\of ", 8))
        self.assertEqual(spell_with_control_words("√()", 2), ("\\sqrt()", 6))
        self.assertEqual(spell_with_control_words("⁄", None, "b"), ("\\sdiv ", None))


class EditInViewTests(unittest.TestCase):
    def edit(self, source: str, caret: int, build, control_words: bool = True):
        edit = edit_in_view(source, caret, build, control_words)
        return edit.source, edit.caret

    def test_templates_are_written_as_control_words(self) -> None:
        self.assertEqual(self.edit("", 0, insert_integral_template), ("\\int\\of\\begin \\end ", 14))
        self.assertEqual(
            self.edit("x=", 2, lambda s, c: insert_sum_template(s, c, limits=True)),
            ("x=\\sum_()^()\\of\\begin \\end ", 8),
        )
        self.assertEqual(self.edit("a", 1, insert_square_root_template), ("a\\sqrt\\begin \\end ", 13))
        self.assertEqual(self.edit("a", 1, insert_operator_template), ("a\\rightarrow\\above() ", 19))
        self.assertEqual(self.edit("A=", 2, lambda s, c: insert_matrix_template(s, c, 2, 2)), ("A=(\\matrix(&@&))", 11))

    def test_symbols_when_the_setting_is_off(self) -> None:
        self.assertEqual(self.edit("", 0, insert_integral_template, control_words=False), ("∫▒〖〗", 3))

    def test_slots_are_found_in_control_word_source(self) -> None:
        self.assertEqual(self.edit("\\int_()^()\\of x", 5, move_to_slot), ("\\int_()^()\\of x", 6))
        upper = edit_in_view("\\int_()^()\\of x", 6, move_to_slot, True)
        self.assertEqual((upper.caret, upper.announcement), (9, "empty upper limit"))
        naryand = edit_in_view("\\int_()^()\\of x", 9, move_to_slot, True)
        self.assertEqual((naryand.caret, naryand.announcement), (15, "integrand, x"))

    def test_structure_edits_keep_the_rest_of_the_spelling(self) -> None:
        self.assertEqual(self.edit("\\sqrt(3&x)+√y", 8, remove_root_index)[0], "\\sqrt\\begin x\\end+√y")
        self.assertEqual(self.edit("\\int_(0)^(1)\\of x dx", 7, remove_nary_limits), ("\\int\\of x dx", 8))
        self.assertEqual(self.edit("\\int\\of x", 2, add_nary_limits), ("\\int_()^()\\of x", 6))
        self.assertEqual(self.edit("(a+b)/c", 1, lambda s, c: restyle_fraction(s, c, "skewed"))[0], "(a+b)\\sdiv c")
        self.assertEqual(self.edit("\\matrix(1&2@3&4)", 9, insert_matrix_row)[0], "\\matrix(1&2@&@3&4)")

    def test_a_word_right_before_an_insertion_does_not_swallow_it(self) -> None:
        self.assertEqual(self.edit("\\alpha", 6, insert_limit_template)[0], "\\alpha lim_() \\begin \\end ")


if __name__ == "__main__":
    unittest.main()
