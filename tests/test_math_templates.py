import unittest

from matex.math_templates import (
    group_function_argument,
    insert_absolute_value_template,
    insert_binomial_template,
    insert_brace_template,
    insert_bracket_template,
    insert_cases_template,
    insert_equation_array_template,
    insert_equation_number_template,
    insert_fraction_template,
    insert_integral_template,
    insert_limit_template,
    insert_logarithm_template,
    insert_nary_operator_template,
    insert_operator_template,
    insert_product_template,
    insert_root_template,
    insert_square_root_template,
    insert_subscript_template,
    insert_sum_template,
    insert_superscript_template,
    move_to_slot,
    script_on_function,
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
        self.assertEqual(edit.source, "x+√〖〗")
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

    def test_the_integrand_is_a_slot_without_a_placeholder(self) -> None:
        # No "()" after "▒" (it would stay visible); the operand itself is the slot.
        self.assertEqual(move_to_slot("∫▒", 2).announcement, "end integral")
        self.assertEqual(move_to_slot("∫▒x dx", 0).announcement, "integrand, x")

    def test_a_typed_integrand_is_read_back_when_tabbing_to_it(self) -> None:
        source = "∫_(0)^(1)▒x^2 dx"
        integrand = move_to_slot(source, 8)
        self.assertEqual((integrand.caret, integrand.announcement), (13, "integrand, x^2"))
        back = move_to_slot(source, len(source), reverse=True)
        self.assertEqual((back.caret, back.announcement), (13, "integrand, x^2"))

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
        self.assertEqual(move_to_slot(source, 10).announcement, "summand, i")

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
        self.assertEqual((edit.source, edit.caret), ("x=lim_() 〖〗", 7))
        self.assertEqual(edit.announcement, "limit template, empty limit condition")
        argument = move_to_slot(edit.source, edit.caret)
        self.assertEqual((argument.caret, argument.announcement), (10, "empty argument"))

    def test_space_after_a_limit_opens_its_argument_as_a_group(self) -> None:
        # As Word's argument box: a fraction typed next stays under the limit.
        edit = group_function_argument("lim_(x→∞)", 9)
        self.assertEqual((edit.source, edit.caret, edit.announcement), ("lim_(x→∞) 〖〗", 11, "empty argument"))
        self.assertEqual(group_function_argument("log_(2)", 7).source, "log_(2) 〖〗")
        self.assertIsNone(group_function_argument("f(x)", 4))
        self.assertIsNone(group_function_argument("lim_(x→∞)〖a〗", 9))

    def test_space_after_a_named_function_opens_its_argument(self) -> None:
        edit = group_function_argument("y=ln", 4, ("ln", "sin"))
        self.assertEqual((edit.source, edit.caret), ("y=ln 〖〗", 6))
        self.assertIsNone(group_function_argument("xln", 3, ("ln",)))  # Part of a longer word.
        self.assertIsNone(group_function_argument("\\sin", 4, ("sin",)))  # A control word.
        self.assertIsNone(group_function_argument("ln", 2))  # Not in the given list.

    def test_space_after_a_radical_sign_opens_its_radicand(self) -> None:
        edit = group_function_argument("a+√", 3)
        self.assertEqual((edit.source, edit.caret, edit.announcement), ("a+√〖〗", 4, "square root, empty radicand"))
        self.assertEqual(group_function_argument("∛", 1).source, "∛〖〗")
        self.assertEqual(move_to_slot("√〖x+1〗+2", 0).announcement, "radicand, x+1")

    def walk_slots(self, edit) -> list[str]:
        announcements, caret = [edit.announcement], edit.caret
        for _ in range(8):
            step = move_to_slot(edit.source, caret)
            if step is None or step.announcement.startswith("end "):
                break
            announcements.append(step.announcement)
            caret = step.caret
        return announcements

    def test_cases_slots_are_values_and_conditions(self) -> None:
        edit = insert_cases_template("f=", 2)
        self.assertEqual(edit.source, "f={■(&@&)┤")
        self.assertEqual(
            self.walk_slots(edit),
            ["cases template, empty value, case 1", "empty condition, case 1", "empty value, case 2", "empty condition, case 2"],
        )
        self.assertEqual(move_to_slot(edit.source, 8).caret, 10)  # Tab out past ")┤".

    def test_equation_array_lines_binomial_and_brackets(self) -> None:
        self.assertEqual(self.walk_slots(insert_equation_array_template("", 0))[1], "empty line 2")
        self.assertEqual(move_to_slot("█(a&=b@&=c)", 0).announcement, "line 1, a&=b")
        self.assertEqual(self.walk_slots(insert_binomial_template("", 0)), ["binomial template, empty top", "empty bottom"])
        self.assertEqual(insert_bracket_template("", 0, "⌊").source, "⌊⌋")
        self.assertEqual(move_to_slot("‖v‖+1", 0).announcement, "value, v")

    def test_box_number_brace_and_large_operators(self) -> None:
        edit = insert_equation_number_template("E=mc^2", 1)
        self.assertEqual((edit.source, edit.caret), ("E=mc^2#()", 8))  # Always at the end.
        self.assertEqual(self.walk_slots(insert_brace_template("", 0)), ["overbrace template, empty content", "empty label"])
        double = insert_nary_operator_template("", 0, "∬", limits=True)
        self.assertEqual(double.announcement, "double integral template, empty lower limit")
        self.assertEqual(move_to_slot("⋃_(i)▒A_i", 3).announcement, "term, A_i")

    def test_any_recognized_function_gets_the_group_and_its_slot(self) -> None:
        # The recognized-functions setting is the only list: a user's own function counts too.
        functions = ("arcsin", "sgn")
        self.assertEqual(group_function_argument("arcsin", 6, functions).source, "arcsin 〖〗")
        self.assertEqual(move_to_slot("sgn 〖x〗", 0, functions=functions).announcement, "argument, x")
        self.assertIsNone(move_to_slot("sgn 〖x〗", 0, functions=("ln",)))

    def test_function_and_logarithm_arguments_are_slots(self) -> None:
        self.assertEqual(move_to_slot("ln(x+1)", 0).announcement, "argument, x+1")
        self.assertEqual(move_to_slot("log_(2) 〖x〗", 6).announcement, "argument, x")
        self.assertEqual(move_to_slot("ln 〖(a)/(b)〗", 0).announcement, "argument, (a)/(b)")

    def test_the_grouped_argument_is_a_slot(self) -> None:
        source = "lim_(n→∞) 〖a_n〗"
        self.assertEqual(move_to_slot(source, 6).announcement, "argument, a_n")
        self.assertEqual(move_to_slot(source, 12).caret, 15)

    def test_logarithm_template_starts_in_the_base(self) -> None:
        edit = insert_logarithm_template("", 0)
        self.assertEqual((edit.source, edit.caret, edit.announcement), ("log_() 〖〗", 5, "logarithm template, empty base"))

    def test_typed_limit_and_logarithm_subscripts_are_slots(self) -> None:
        self.assertEqual(move_to_slot("lim_(n→∞) a_n", 0).announcement, "limit condition, n→∞")
        self.assertEqual(move_to_slot("lim_(n→∞) a_n", 8).announcement, "argument, a_n")
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



class UnparenthesizedScriptArgumentTests(unittest.TestCase):
    """Space after `log_2`, `sin^2`: the argument box, as after `log_(2)` or `ln` (user report)."""

    FUNCTIONS = ("sin", "cos", "log", "ln")

    def test_space_after_a_script_without_parens_opens_the_argument(self) -> None:
        for source, name in (("log_2", "log"), ("log_10", "log"), ("log_a", "log"), ("lim_x", "lim"), ("sin^2", "sin")):
            edit = group_function_argument(source, len(source), self.FUNCTIONS)
            self.assertIsNotNone(edit, source)
            self.assertEqual((edit.source, edit.caret, edit.announcement), (source + " 〖〗", len(source) + 2, f"{name}, empty argument"))

    def test_not_after_a_variable_or_a_glued_argument(self) -> None:
        for source in ("x_2", "a_n", "log_2x"):
            self.assertIsNone(group_function_argument(source, len(source), self.FUNCTIONS), source)

    def test_its_argument_is_a_tab_slot(self) -> None:
        edit = move_to_slot("log_2 〖x〗", 0, False, self.FUNCTIONS)
        self.assertEqual((edit.caret, edit.announcement), (8, "argument, x"))



class LimitInferiorTests(unittest.TestCase):
    def test_space_after_liminf_spells_it_and_opens_the_argument(self) -> None:
        edit = group_function_argument("x+liminf", 8, ("liminf",))
        self.assertEqual((edit.source, edit.caret), ("x+lim\u00a0inf 〖〗", 11))

    def test_a_lim_inf_condition_is_a_slot_and_space_after_it_opens_the_argument(self) -> None:
        source = "lim\u00a0sup_() 〖〗"
        self.assertEqual(move_to_slot(source, 0).announcement, "empty limit condition")
        self.assertEqual(move_to_slot(source, 9).announcement, "empty argument")
        typed = "lim\u00a0inf_(n→∞)"
        self.assertEqual(group_function_argument(typed, len(typed)).source, typed + " 〖〗")



class ScriptOnFunctionTests(unittest.TestCase):
    def test_a_script_after_a_function_and_its_space_goes_on_the_name(self) -> None:
        # UTN #28 sec. 3.5: a script right after a function applies to its name.
        edit = script_on_function("lim ", 4, "_")
        self.assertEqual((edit.source, edit.caret), ("lim_ ", 4))
        self.assertEqual(script_on_function("lim  x", 5, "_").source, "lim_  x")
        self.assertEqual(script_on_function("sin ", 4, "^", ("sin",)).source, "sin^ ")
        self.assertEqual(script_on_function("lim\u00a0inf ", 8, "_").source, "lim\u00a0inf_ ")

    def test_space_after_the_condition_opens_the_argument_before_trailing_spaces(self) -> None:
        source = "lim_(x→∞)  "
        edit = group_function_argument(source, 9)
        self.assertEqual((edit.source, edit.caret), ("lim_(x→∞) 〖〗  ", 11))
        self.assertIsNone(group_function_argument("lim_(x→∞)  x", 9))  # The argument is already there.

    def test_anything_else_is_typed_as_it_is(self) -> None:
        self.assertIsNone(script_on_function("lim", 3, "_"))  # No space: typed right there anyway.
        self.assertIsNone(script_on_function("x ", 2, "_"))
        self.assertIsNone(script_on_function("slim ", 5, "_"))  # Part of a longer word.
        self.assertIsNone(script_on_function("\\sin ", 5, "_", ("sin",)))
        self.assertIsNone(script_on_function("lim ", 4, "+"))


if __name__ == "__main__":
    unittest.main()
