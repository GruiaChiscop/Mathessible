import unittest

from matex.math_templates import (
    MatrixPosition,
    built_fractions,
    fraction_at,
    restyle_fraction,
    delete_matrix_column,
    delete_matrix_row,
    insert_absolute_value_template,
    insert_matrix_column,
    insert_matrix_row,
    matrix_cell_caret,
    matrix_count,
    matrix_position_at,
    insert_fraction_template,
    insert_integral_template,
    insert_limit_template,
    insert_logarithm_template,
    insert_matrix_template,
    insert_operator_template,
    insert_product_template,
    insert_root_template,
    insert_square_root_template,
    insert_subscript_template,
    insert_sum_template,
    insert_superscript_template,
    move_to_slot,
)


class MathTemplateTests(unittest.TestCase):
    def test_fraction_template_places_caret_in_numerator(self) -> None:
        edit = insert_fraction_template("x+", 2)
        self.assertEqual(edit.source, "x+()/()")
        self.assertEqual(edit.caret, 3)
        self.assertEqual(edit.announcement, "fraction template, empty numerator")

    def test_tab_moves_between_fraction_slots_and_exits_fraction(self) -> None:
        source = "()/()"
        denominator = move_to_slot(source, 1)
        self.assertIsNotNone(denominator)
        self.assertEqual(denominator.caret, 4)
        self.assertEqual(denominator.announcement, "empty denominator")

        exit_edit = move_to_slot(source, denominator.caret)
        self.assertIsNotNone(exit_edit)
        self.assertEqual(exit_edit.caret, 5)
        self.assertEqual(exit_edit.announcement, "end fraction")

    def test_shift_tab_moves_to_previous_empty_slot(self) -> None:
        edit = move_to_slot("()/()", 4, reverse=True)
        self.assertIsNotNone(edit)
        self.assertEqual(edit.caret, 1)
        self.assertEqual(edit.announcement, "empty numerator")

    def test_no_empty_slots_returns_none(self) -> None:
        self.assertIsNone(move_to_slot("x+1", 0))

    def test_square_root_template_places_caret_in_radicand(self) -> None:
        edit = insert_square_root_template("x+", 2)
        self.assertEqual(edit.source, "x+√()")
        self.assertEqual(edit.caret, 4)
        self.assertEqual(edit.announcement, "square root template, empty radicand")

    def test_tab_exits_square_root_template(self) -> None:
        source = "√()"
        exit_edit = move_to_slot(source, 2)
        self.assertIsNotNone(exit_edit)
        self.assertEqual(exit_edit.caret, 3)
        self.assertEqual(exit_edit.announcement, "end square root")

    def test_square_root_and_fraction_slots_are_distinguished_when_adjacent(self) -> None:
        source = "√()/()"
        radicand = move_to_slot(source, 0)
        self.assertIsNotNone(radicand)
        self.assertEqual(radicand.caret, 2)
        self.assertEqual(radicand.announcement, "empty radicand")

        denominator = move_to_slot(source, radicand.caret)
        self.assertIsNotNone(denominator)
        self.assertEqual(denominator.caret, 5)
        self.assertEqual(denominator.announcement, "empty denominator")

    def test_subscript_template_places_caret_in_base(self) -> None:
        edit = insert_subscript_template("x+", 2)
        self.assertEqual(edit.source, "x+()_()")
        self.assertEqual(edit.caret, 3)
        self.assertEqual(edit.announcement, "subscript template, empty base")

    def test_tab_moves_from_base_to_subscript_and_exits(self) -> None:
        source = "()_()"
        subscript = move_to_slot(source, 1)
        self.assertIsNotNone(subscript)
        self.assertEqual(subscript.caret, 4)
        self.assertEqual(subscript.announcement, "empty subscript")

        exit_edit = move_to_slot(source, subscript.caret)
        self.assertIsNotNone(exit_edit)
        self.assertEqual(exit_edit.caret, 5)
        self.assertEqual(exit_edit.announcement, "end scripts")

    def test_superscript_template_places_caret_in_base(self) -> None:
        edit = insert_superscript_template("x+", 2)
        self.assertEqual(edit.source, "x+()^()")
        self.assertEqual(edit.caret, 3)
        self.assertEqual(edit.announcement, "superscript template, empty base")

    def test_tab_moves_from_base_to_superscript(self) -> None:
        superscript = move_to_slot("()^()", 1)
        self.assertIsNotNone(superscript)
        self.assertEqual(superscript.caret, 4)
        self.assertEqual(superscript.announcement, "empty superscript")

    def test_subscript_template_reuses_a_preceding_letter_as_the_base(self) -> None:
        edit = insert_subscript_template("x", 1)
        self.assertEqual(edit.source, "x_()")
        self.assertEqual(edit.caret, 3)
        self.assertEqual(edit.announcement, "subscript template, empty subscript")

    def test_superscript_template_reuses_a_preceding_closing_bracket_as_the_base(self) -> None:
        edit = insert_superscript_template("(a+b)", 5)
        self.assertEqual(edit.source, "(a+b)^()")
        self.assertEqual(edit.caret, 7)
        self.assertEqual(edit.announcement, "superscript template, empty superscript")

    def test_subscript_and_fraction_slots_are_distinguished_when_adjacent(self) -> None:
        # base_subscript / denominator: the subscript is nested inside the
        # fraction's numerator, not itself the numerator.
        source = "()_()/()"
        base = move_to_slot(source, 0)
        self.assertIsNotNone(base)
        self.assertEqual(base.announcement, "empty base")

        subscript = move_to_slot(source, base.caret)
        self.assertIsNotNone(subscript)
        self.assertEqual(subscript.announcement, "empty subscript")

        denominator = move_to_slot(source, subscript.caret)
        self.assertIsNotNone(denominator)
        self.assertEqual(denominator.announcement, "empty denominator")

    def test_absolute_value_template_places_caret_in_value(self) -> None:
        edit = insert_absolute_value_template("x+", 2)
        self.assertEqual(edit.source, "x+|()|")
        self.assertEqual(edit.caret, 4)
        self.assertEqual(edit.announcement, "absolute value template, empty value")

    def test_tab_exits_absolute_value_template_past_the_closing_bar(self) -> None:
        exit_edit = move_to_slot("|()|", 2)
        self.assertIsNotNone(exit_edit)
        self.assertEqual(exit_edit.caret, 4)
        self.assertEqual(exit_edit.announcement, "end absolute value")

    def test_absolute_value_followed_by_a_fraction_slot_is_still_a_denominator(self) -> None:
        # Textual siblings with different delimiters back to back: the old
        # fixed-window detection expected ")/(" and missed "|/(".
        source = "|()|/()"
        value = move_to_slot(source, 0)
        self.assertIsNotNone(value)
        self.assertEqual(value.announcement, "empty value")

        denominator = move_to_slot(source, value.caret)
        self.assertIsNotNone(denominator)
        self.assertEqual(denominator.caret, 6)
        self.assertEqual(denominator.announcement, "empty denominator")

    def test_tab_visits_a_filled_numerator_then_the_denominator(self) -> None:
        numerator = move_to_slot("(a+b)/()", 0)
        self.assertIsNotNone(numerator)
        self.assertEqual(numerator.caret, 4)
        self.assertEqual(numerator.announcement, "numerator, a+b")
        denominator = move_to_slot("(a+b)/()", numerator.caret)
        self.assertIsNotNone(denominator)
        self.assertEqual(denominator.caret, 7)
        self.assertEqual(denominator.announcement, "empty denominator")

    def test_shift_tab_returns_to_a_slot_after_it_was_filled(self) -> None:
        # Type in the numerator, Tab to the denominator, type, Shift+Tab back.
        source = "(ab)/(c)"
        numerator = move_to_slot(source, 7, reverse=True)
        self.assertIsNotNone(numerator)
        self.assertEqual(numerator.caret, 3)
        self.assertEqual(numerator.announcement, "numerator, ab")
        self.assertIsNone(move_to_slot(source, numerator.caret, reverse=True))
        denominator = move_to_slot(source, numerator.caret)
        self.assertIsNotNone(denominator)
        self.assertEqual(denominator.caret, 7)
        self.assertEqual(denominator.announcement, "denominator, c")
        exit_edit = move_to_slot(source, denominator.caret)
        self.assertIsNotNone(exit_edit)
        self.assertEqual((exit_edit.caret, exit_edit.announcement), (8, "end fraction"))

    def test_shift_tab_from_the_middle_of_a_slot_goes_to_the_previous_one(self) -> None:
        edit = move_to_slot("√(x)+|(yz)|", 8, reverse=True)
        self.assertIsNotNone(edit)
        self.assertEqual((edit.caret, edit.announcement), (3, "radicand, x"))

    def test_a_function_argument_is_not_a_numerator_or_base(self) -> None:
        self.assertIsNone(move_to_slot("f(x)/2", 0))
        self.assertIsNone(move_to_slot("f(x)^2", 0))

    def test_absolute_value_nested_in_a_fraction_numerator_is_distinguished_from_the_denominator(self) -> None:
        # The reachable-in-practice case: Ctrl+/ then Ctrl+\ while still
        # inside the numerator slot nests one template inside the other,
        # rather than placing them as textual siblings.
        fraction = insert_fraction_template("", 0)
        nested = insert_absolute_value_template(fraction.source, fraction.caret)
        self.assertEqual(nested.source, "(|()|)/()")
        self.assertEqual(nested.announcement, "absolute value template, empty value")

        denominator = move_to_slot(nested.source, nested.caret)
        self.assertIsNotNone(denominator)
        self.assertEqual(denominator.announcement, "empty denominator")

    def test_integral_template_places_caret_after_the_naryand_marker(self) -> None:
        edit = insert_integral_template("x=", 2)
        self.assertEqual(edit.source, "x=∫▒")
        self.assertEqual(edit.caret, 4)
        self.assertEqual(edit.announcement, "integral template")

    def test_integral_template_has_no_tab_able_slot(self) -> None:
        # There is deliberately no empty-slot placeholder for the integrand
        # (see insert_integral_template's docstring) — Tab finds nothing.
        self.assertIsNone(move_to_slot("∫▒", 2))

    def test_typing_after_the_integral_template_produces_the_integrand(self) -> None:
        edit = insert_integral_template("", 0)
        typed = edit.source[: edit.caret] + "x" + edit.source[edit.caret :]
        self.assertEqual(typed, "∫▒x")

    def test_sum_template_places_caret_after_the_naryand_marker(self) -> None:
        edit = insert_sum_template("", 0)
        self.assertEqual(edit.source, "∑▒")
        self.assertEqual(edit.caret, 2)
        self.assertEqual(edit.announcement, "sum template")

    def test_product_template_places_caret_after_the_naryand_marker(self) -> None:
        edit = insert_product_template("", 0)
        self.assertEqual(edit.source, "∏▒")
        self.assertEqual(edit.caret, 2)
        self.assertEqual(edit.announcement, "product template")


    def test_integral_with_limits_starts_in_the_lower_limit(self) -> None:
        edit = insert_integral_template("x=", 2, limits=True)
        self.assertEqual(edit.source, "x=∫_()^()▒")
        self.assertEqual(edit.caret, 5)
        self.assertEqual(edit.announcement, "integral template, empty lower limit")

    def test_tab_walks_the_limits_then_lands_on_the_naryand(self) -> None:
        source = "∫_()^()▒"
        upper = move_to_slot(source, 3)
        self.assertEqual((upper.caret, upper.announcement), (6, "empty upper limit"))
        naryand = move_to_slot(source, upper.caret)
        self.assertEqual((naryand.caret, naryand.announcement), (8, "empty integrand"))

    def test_limits_of_a_typed_sum_are_slots_and_not_scripts(self) -> None:
        source = "∑_(i=1)^(n)▒i"
        lower = move_to_slot(source, 0)
        self.assertEqual((lower.caret, lower.announcement), (6, "lower limit, i=1"))
        self.assertEqual(move_to_slot(source, 13, reverse=True).announcement, "upper limit, n")
        self.assertEqual(move_to_slot(source, 10).announcement, "summand")

    def test_sum_and_product_with_limits(self) -> None:
        self.assertEqual(insert_sum_template("", 0, limits=True).source, "∑_()^()▒")
        self.assertEqual(insert_product_template("", 0, limits=True).announcement, "product template, empty lower limit")

    def test_a_lower_limit_alone_exits_past_the_naryand_marker(self) -> None:
        self.assertEqual(move_to_slot("∑_(k)▒", 4).caret, 6)

    def test_ordinary_scripts_are_not_limits(self) -> None:
        self.assertEqual(move_to_slot("x_(i)^(2)", 3).announcement, "superscript, 2")

    def test_root_template_starts_in_the_index(self) -> None:
        edit = insert_root_template("x=", 2)
        self.assertEqual((edit.source, edit.caret, edit.announcement), ("x=√(&)", 4, "root template, empty index"))

    def test_tab_goes_from_the_index_to_the_radicand_and_out(self) -> None:
        radicand = move_to_slot("√(&)", 2)
        self.assertEqual((radicand.caret, radicand.announcement), (3, "empty radicand"))
        out = move_to_slot("√(&)", radicand.caret)
        self.assertEqual((out.caret, out.announcement), (4, "end root"))

    def test_filled_root_slots_are_announced_with_their_content(self) -> None:
        self.assertEqual(move_to_slot("√(3&x+1)", 0).announcement, "index, 3")
        self.assertEqual(move_to_slot("√(3&x+1)", 3).announcement, "radicand, x+1")

    def test_a_square_root_is_still_a_single_radicand(self) -> None:
        self.assertEqual(move_to_slot("√(x)", 0).announcement, "radicand, x")

    def test_a_root_inside_a_matrix_cell_keeps_both_apart(self) -> None:
        source = "(■(√(3&x)&2))"
        # The root's "&" does not split the cell; its slots sit inside cell 1.
        self.assertEqual(move_to_slot(source, 4).announcement, "index, 3")
        self.assertEqual(move_to_slot(source, 6).announcement, "radicand, x")
        self.assertEqual(move_to_slot(source, 8).announcement, "cell, row 1, column 2, 2")

    def test_limit_template_starts_in_the_condition_and_tabs_to_the_argument(self) -> None:
        edit = insert_limit_template("x=", 2)
        self.assertEqual((edit.source, edit.caret), ("x=lim_() ", 7))
        self.assertEqual(edit.announcement, "limit template, empty limit condition")
        argument = move_to_slot(edit.source, edit.caret)
        self.assertEqual((argument.caret, argument.announcement), (9, "empty argument"))

    def test_logarithm_template_starts_in_the_base(self) -> None:
        edit = insert_logarithm_template("", 0)
        self.assertEqual((edit.source, edit.caret, edit.announcement), ("log_() ", 5, "logarithm template, empty base"))

    def test_typed_limit_and_logarithm_subscripts_are_slots(self) -> None:
        self.assertEqual(move_to_slot("lim_(n→∞) a_n", 0).announcement, "limit condition, n→∞")
        self.assertEqual(move_to_slot("lim_(n→∞) a_n", 8).announcement, "argument")
        self.assertEqual(move_to_slot("log_(2) x", 0).announcement, "base, 2")

    def test_a_word_ending_in_lim_is_not_a_limit(self) -> None:
        self.assertEqual(move_to_slot("clim_(1)", 6).announcement, "end scripts")

    def test_operator_template_puts_text_above_an_arrow(self) -> None:
        edit = insert_operator_template("a", 1)
        self.assertEqual((edit.source, edit.caret), ("a→┴() ", 4))
        self.assertEqual(edit.announcement, "arrow template, empty text above")
        after = move_to_slot(edit.source + "b", edit.caret)
        self.assertEqual((after.caret, after.announcement), (6, "end arrow"))

    def test_operator_template_below_and_with_another_operator(self) -> None:
        below = insert_operator_template("", 0, above=False)
        self.assertEqual((below.source, below.announcement), ("→┬() ", "arrow template, empty text below"))
        equals = insert_operator_template("", 0, operator="=")
        self.assertEqual((equals.source, equals.announcement), ("=┴() ", "operator template, empty text above"))

    def test_text_below_and_above_one_operator_are_both_slots(self) -> None:
        source = "a→┬(y)┴(x) b"
        below = move_to_slot(source, 0)
        self.assertEqual(below.announcement, "text below, y")
        above = move_to_slot(source, below.caret)
        self.assertEqual(above.announcement, "text above, x")
        self.assertEqual(move_to_slot(source, above.caret).caret, 11)
        self.assertEqual(move_to_slot(source, above.caret, reverse=True).announcement, "text below, y")

    def test_fraction_at_finds_the_innermost_fraction_with_its_operands(self) -> None:
        outer = fraction_at("x=(a+b)/c+1", 4)
        self.assertEqual((outer.start, outer.end, outer.style), (2, 9, "stacked"))
        inner = fraction_at("(x/2)/y", 2)
        self.assertEqual((inner.operator, inner.start, inner.end), (2, 1, 4))
        self.assertEqual(fraction_at("(x/2)/y", 0).operator, 5)
        function = fraction_at("f(x)/√(2)", 0)
        self.assertEqual((function.start, function.end), (0, 9))
        self.assertIsNone(fraction_at("a+b", 1))

    def test_restyle_fraction_swaps_the_operator(self) -> None:
        self.assertEqual(restyle_fraction("x=a/b+1", 3, "skewed").source, "x=a⁄b+1")
        self.assertEqual(restyle_fraction("(x/2)/y", 0, "small").source, "(x/2)⊘y")
        self.assertEqual(restyle_fraction("a⊘b", 0, "stacked").announcement, "stacked fraction")
        self.assertIsNone(restyle_fraction("a+b", 1, "linear"))

    def test_linear_fraction_keeps_visible_parens_around_groups(self) -> None:
        # The converter drops the parens of a linear fraction's operands.
        edit = restyle_fraction("(a+b)/(c+d)", 2, "linear")
        self.assertEqual((edit.source, edit.caret), ("((a+b))∕((c+d))", 3))
        self.assertEqual(restyle_fraction("(x)/2", 0, "linear").source, "(x)∕2")
        back = restyle_fraction(edit.source, edit.caret, "stacked")
        self.assertEqual((back.source, back.caret), ("(a+b)/(c+d)", 2))

    def test_built_fractions_skip_linear_ones_and_count_binomials(self) -> None:
        styles = [fraction.style for fraction in built_fractions("(n¦k)/2+a∕b")]
        self.assertEqual(styles, ["stacked", "no bar"])

    def test_matrix_template_has_empty_cells_and_caret_in_the_first(self) -> None:
        edit = insert_matrix_template("A=", 2, rows=2, columns=3)
        self.assertEqual(edit.source, "A=(■(&&@&&))")
        self.assertEqual(edit.caret, 5)
        self.assertEqual(edit.announcement, "2 by 3 matrix template, empty cell, row 1, column 1")

    def test_matrix_template_fences(self) -> None:
        self.assertEqual(insert_matrix_template("", 0, 2, 2, fence="none").source, "■(&@&)")
        self.assertEqual(insert_matrix_template("", 0, 2, 2, fence="brackets").source, "[■(&@&)]")
        determinant = insert_matrix_template("", 0, 2, 2, fence="bars")
        self.assertEqual(determinant.source, "|■(&@&)|")
        self.assertEqual(determinant.announcement, "2 by 2 determinant template, empty cell, row 1, column 1")

    def test_matrix_template_rejects_bad_sizes_and_fences(self) -> None:
        with self.assertRaises(ValueError):
            insert_matrix_template("", 0, 0, 2)
        with self.assertRaises(ValueError):
            insert_matrix_template("", 0, 2, 11)
        with self.assertRaises(ValueError):
            insert_matrix_template("", 0, 2, 2, fence="double bars")

    def test_tab_walks_matrix_cells_row_by_row_then_exits_past_the_fence(self) -> None:
        source = "(■(&@&))+x"
        expected = [
            (4, "empty cell, row 1, column 2"),
            (5, "empty cell, row 2, column 1"),
            (6, "empty cell, row 2, column 2"),
        ]
        caret = 3
        for position, announcement in expected:
            edit = move_to_slot(source, caret)
            self.assertIsNotNone(edit)
            self.assertEqual((edit.caret, edit.announcement), (position, announcement))
            caret = edit.caret
        exit_edit = move_to_slot(source, caret)
        self.assertIsNotNone(exit_edit)
        self.assertEqual(exit_edit.caret, 8)
        self.assertEqual(exit_edit.announcement, "end matrix")

    def test_shift_tab_walks_matrix_cells_backwards(self) -> None:
        edit = move_to_slot("■(&@&)", 5, reverse=True)
        self.assertIsNotNone(edit)
        self.assertEqual(edit.caret, 4)
        self.assertEqual(edit.announcement, "empty cell, row 2, column 1")

    def test_tab_and_shift_tab_visit_filled_matrix_cells(self) -> None:
        source = "■(a&@x&)"
        edit = move_to_slot(source, 3)
        self.assertIsNotNone(edit)
        self.assertEqual((edit.caret, edit.announcement), (4, "empty cell, row 1, column 2"))
        edit = move_to_slot(source, edit.caret)
        self.assertIsNotNone(edit)
        self.assertEqual((edit.caret, edit.announcement), (6, "cell, row 2, column 1, x"))
        back = move_to_slot(source, 7, reverse=True)
        self.assertIsNotNone(back)
        self.assertEqual((back.caret, back.announcement), (6, "cell, row 2, column 1, x"))
        first = move_to_slot(source, 4, reverse=True)
        self.assertIsNotNone(first)
        self.assertEqual((first.caret, first.announcement), (3, "cell, row 1, column 1, a"))

    def test_determinant_cells_exit_past_the_closing_bar(self) -> None:
        exit_edit = move_to_slot("|■()|", 3)
        self.assertIsNotNone(exit_edit)
        self.assertEqual(exit_edit.caret, 5)
        self.assertEqual(exit_edit.announcement, "end determinant")

    def test_fraction_inside_a_matrix_cell_does_not_split_cells(self) -> None:
        # The "&" belongs to the matrix; the "()/()" slots are the fraction's.
        fraction = insert_fraction_template("■(&)", 2)
        self.assertEqual(fraction.source, "■(()/()&)")
        denominator = move_to_slot(fraction.source, fraction.caret)
        self.assertIsNotNone(denominator)
        self.assertEqual(denominator.announcement, "empty denominator")
        next_cell = move_to_slot(fraction.source, denominator.caret)
        self.assertIsNotNone(next_cell)
        self.assertEqual(next_cell.caret, 8)
        self.assertEqual(next_cell.announcement, "empty cell, row 1, column 2")

    def test_nested_matrix_cells_are_numbered_within_their_own_matrix(self) -> None:
        source = "■(■(&)&)"
        inner = move_to_slot(source, 4)
        self.assertIsNotNone(inner)
        self.assertEqual(inner.caret, 5)
        self.assertEqual(inner.announcement, "empty cell, row 1, column 2")
        outer = move_to_slot(source, inner.caret)
        self.assertIsNotNone(outer)
        self.assertEqual(outer.caret, 7)
        self.assertEqual(outer.announcement, "empty cell, row 1, column 2")


    def test_matrix_position_reports_the_caret_cell_and_shape(self) -> None:
        # "(■(a&b@c&d))": "d" is at index 9.
        self.assertEqual(matrix_position_at("(■(a&b@c&d))", 9), MatrixPosition(2, 2, 2, 2, 0))
        self.assertIsNone(matrix_position_at("x+(■(a&b))", 1))

    def test_matrix_position_uses_the_innermost_matrix(self) -> None:
        source = "■(■(x&y@z&w)&b)"
        self.assertEqual(matrix_position_at(source, 4), MatrixPosition(1, 1, 2, 2, 1))
        self.assertEqual(matrix_position_at(source, 14), MatrixPosition(1, 2, 1, 2, 0))

    def test_insert_row_below_and_above(self) -> None:
        below = insert_matrix_row("(■(a&b@c&d))", 3, below=True)
        self.assertIsNotNone(below)
        self.assertEqual(below.source, "(■(a&b@&@c&d))")
        self.assertEqual(below.caret, 7)
        self.assertEqual(below.announcement, "inserted row 2, 3 by 2 matrix, empty cell, row 2, column 1")
        above = insert_matrix_row("(■(a&b@c&d))", 3, below=False)
        self.assertIsNotNone(above)
        self.assertEqual(above.source, "(■(&@a&b@c&d))")
        self.assertEqual(above.caret, 3)

    def test_insert_column_right_and_left_keeps_the_caret_row(self) -> None:
        right = insert_matrix_column("[■(a&b@c&d)]", 7, right=True)
        self.assertIsNotNone(right)
        self.assertEqual(right.source, "[■(a&&b@c&&d)]")
        self.assertEqual(right.caret, 10)
        self.assertEqual(right.announcement, "inserted column 2, 2 by 3 matrix, empty cell, row 2, column 2")
        left = insert_matrix_column("[■(a&b@c&d)]", 7, right=False)
        self.assertIsNotNone(left)
        self.assertEqual(left.source, "[■(&a&b@&c&d)]")

    def test_insert_column_pads_a_ragged_row(self) -> None:
        edit = insert_matrix_column("■(a&b&c@d)", 6, right=True)
        self.assertIsNotNone(edit)
        self.assertEqual(edit.source, "■(a&b&c&@d&&&)")

    def test_delete_row_and_column(self) -> None:
        row = delete_matrix_row("(■(a&b@c&d))", 9)
        self.assertIsNotNone(row)
        self.assertEqual(row.source, "(■(a&b))")
        self.assertEqual(row.caret, 5)
        self.assertEqual(row.announcement, "deleted row 2, 1 by 2 matrix, row 1, column 2")
        column = delete_matrix_column("|■(a&b@c&d)|", 3)
        self.assertIsNotNone(column)
        self.assertEqual(column.source, "|■(b@d)|")
        self.assertEqual(column.caret, 3)
        self.assertEqual(column.announcement, "deleted column 1, 2 by 1 determinant, row 1, column 1")

    def test_the_last_row_or_column_cannot_be_deleted(self) -> None:
        self.assertIsNone(delete_matrix_row("■(a&b)", 2))
        self.assertIsNone(delete_matrix_column("■(a@b)", 2))
        self.assertIsNone(insert_matrix_row("a+b", 1))

    def test_editing_a_nested_matrix_leaves_the_outer_one_alone(self) -> None:
        edit = insert_matrix_row("■(■(x&y)&b)", 4)
        self.assertIsNotNone(edit)
        self.assertEqual(edit.source, "■(■(x&y@&)&b)")

    def test_cells_with_nested_groups_are_kept_whole(self) -> None:
        edit = delete_matrix_column("■((a)/(b)&c)", 10)
        self.assertIsNotNone(edit)
        self.assertEqual(edit.source, "■((a)/(b))")

    def test_matrix_cells_are_found_by_matrix_index_row_and_column(self) -> None:
        source = "[■(1&2@3&4)]+■(■(x&y@z)&b)"
        self.assertEqual(matrix_count(source), 3)
        self.assertEqual(matrix_cell_caret(source, 0, 2, 2), 9)
        self.assertEqual(matrix_cell_caret(source, 2, 2, 1), 21)
        # A short row gives its last cell; a missing matrix or row gives None.
        self.assertEqual(matrix_cell_caret(source, 2, 2, 2), 21)
        self.assertIsNone(matrix_cell_caret(source, 3, 1, 1))
        self.assertIsNone(matrix_cell_caret(source, 0, 3, 1))
        self.assertEqual(matrix_position_at(source, 21), MatrixPosition(2, 1, 2, 2, 2))

if __name__ == "__main__":
    unittest.main()
