import unittest

from matex.equation_errors import find_errors

TABLE = {"alpha": "α", "sqrt": "√", "of": "▒", "int": "∫"}


def errors(source: str, **options) -> list[tuple[int, int, str]]:
    return [(error.start, error.end, error.message) for error in find_errors(source, **options)]


class EquationErrorTests(unittest.TestCase):
    def test_unbalanced_brackets(self) -> None:
        self.assertEqual(errors("(a+b"), [(0, 1, "unclosed parenthesis")])
        self.assertEqual(
            errors("a)/(b"), [(1, 2, "closing parenthesis without an opening one"), (3, 4, "unclosed parenthesis")]
        )
        self.assertEqual(errors("■(1&2"), [(1, 2, "unclosed parenthesis")])
        # Mixed fences pair up, as in UnicodeMath: intervals and cases.
        self.assertEqual(errors("[0,1)"), [])
        self.assertEqual(errors("{■(1&x>0@0&x<0)┤"), [])

    def test_quotes(self) -> None:
        self.assertEqual(errors('"abc'), [(0, 1, "text not closed: missing quote")])
        self.assertEqual(errors('"a(b"'), [])  # Brackets inside text are text.

    def test_operators_missing_an_operand(self) -> None:
        self.assertEqual(errors("a/"), [(1, 2, "fraction without denominator")])
        self.assertEqual(errors("(/b)"), [(1, 2, "fraction without numerator")])
        self.assertEqual(errors("x^ "), [(1, 2, "superscript without anything after ^")])
        self.assertEqual(errors("(x_)"), [(2, 3, "subscript without anything after _")])
        self.assertEqual(errors("∫▒"), [(1, 2, "empty integrand or argument")])
        self.assertEqual(errors("x^2+y_i"), [])

    def test_control_words_map_to_their_source(self) -> None:
        source = "\\int\\of "
        self.assertEqual(errors(source), [(4, 8, "empty integrand or argument")])
        self.assertEqual(errors("\\sqrt(&x)"), [(0, 7, "root without an index")])

    def test_unknown_commands_but_not_the_one_being_typed(self) -> None:
        self.assertEqual(errors("\\alpha+\\beta", control_words=TABLE), [(7, 12, "unknown command \\beta")])
        self.assertEqual(errors("x+\\al", control_words=TABLE, caret=5), [])

    def test_bars_only_when_nothing_parses_and_a_last_resort(self) -> None:
        self.assertEqual(errors("P(A|B)"), [])
        self.assertEqual(errors("|x", total_failure=True), [(0, 1, "absolute value bar without its pair")])
        self.assertEqual(errors("a@@b", total_failure=True), [(0, 4, "the equation cannot be read")])

    def test_where_the_parser_stopped_explains_the_rest(self) -> None:
        self.assertEqual(
            errors("a&b", total_failure=True, stopped=(1, "&")), [(1, 2, "& outside a matrix or equation array")]
        )
        self.assertEqual(errors("a=+%", total_failure=True, stopped=(3, "%")), [(3, 4, "cannot continue with %")])
        self.assertEqual(errors("x+∫▒", total_failure=True, stopped=(4, None)), [(3, 4, "empty integrand or argument")])
        self.assertEqual(errors("x+ ", total_failure=True, stopped=(3, None)), [(1, 2, "the equation ends too early")])
        # Already explained there: not reported twice.
        self.assertEqual(
            errors("a+b)", total_failure=True, stopped=(3, ")")),
            [(3, 4, "closing parenthesis without an opening one")],
        )

    def test_description(self) -> None:
        error = find_errors("1+(a+b")[0]
        self.assertEqual(error.describe("1+(a+b"), "unclosed parenthesis, at character 3: 1+(a+b")


if __name__ == "__main__":
    unittest.main()
