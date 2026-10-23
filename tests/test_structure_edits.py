import unittest

from converter_harness import convert_all, has_error, needs_node
from matex.templates.structure_edits import (
    accent_at,
    add_nary_limits,
    add_root_index,
    add_subscript,
    add_superscript,
    bracket_at,
    brackets,
    change_accent,
    change_brackets,
    hide_bracket,
    nary_at,
    nary_operators,
    remove_accent,
    remove_bar,
    remove_brackets,
    remove_nary_limits,
    remove_root_index,
    remove_subscript,
    remove_superscript,
    root_at,
    roots,
    script_at,
    scripts,
    switch_bar,
)


class RootEditTests(unittest.TestCase):
    def test_roots_are_found_in_reading_order(self) -> None:
        self.assertEqual([root.sign for root in roots("√(√(x))+∛y")], [0, 2, 8])
        self.assertEqual(root_at("√(√(x))", 4).sign, 2)
        self.assertEqual(root_at("√(√(x))", 0).sign, 0)
        self.assertIsNone(root_at("a+b", 1))

    def test_add_index_leaves_the_caret_in_an_empty_index(self) -> None:
        edit = add_root_index("a+√x", 3)
        self.assertEqual((edit.source, edit.caret), ("a+√(&x)", 4))
        self.assertEqual(edit.announcement, "root with index, empty index")
        self.assertEqual(add_root_index("√(x+1)", 3).source, "√(&x+1)")
        self.assertIsNone(add_root_index("√(3&x)", 1))

    def test_remove_index_gives_a_square_root(self) -> None:
        edit = remove_root_index("√(3&x)", 4)
        self.assertEqual((edit.source, edit.caret), ("√〖x〗", 3))
        self.assertEqual(remove_root_index("∛x+1", 1).source, "√x+1")
        self.assertEqual(remove_root_index("∜(y)", 2).source, "√〖y〗")
        self.assertIsNone(remove_root_index("√(x)", 1))

    def test_an_ampersand_inside_a_nested_group_is_not_the_index(self) -> None:
        self.assertFalse(root_at("√((■(1&2)))", 1).has_index)


class NaryEditTests(unittest.TestCase):
    def test_only_built_nary_operators_count(self) -> None:
        # A bare "∑x" is just an operator sign to the converter.
        self.assertEqual([nary.symbol for nary in nary_operators("∫▒∫▒x+∑x+∑_i x_i")], [0, 2, 9])

    def test_the_naryand_after_a_space_belongs_to_the_operator(self) -> None:
        self.assertEqual(nary_at("∑_i x_i", 5).symbol, 0)
        self.assertIsNone(nary_at("∑_(i=1)^n▒i + 1", 12))

    def test_add_limits_starts_in_the_lower_limit(self) -> None:
        edit = add_nary_limits("∫▒x dx", 2)
        self.assertEqual((edit.source, edit.caret), ("∫_()^()▒x dx", 3))
        self.assertEqual(edit.announcement, "integral with limits, empty lower limit")
        self.assertIsNone(add_nary_limits("∫_0^1▒x", 0))

    def test_remove_limits_keeps_the_naryand(self) -> None:
        edit = remove_nary_limits("∫_(0)^(1)▒x dx", 3)
        self.assertEqual((edit.source, edit.caret, edit.announcement), ("∫▒x dx", 2, "integral, limits removed"))
        self.assertEqual(remove_nary_limits("∑_i x_i", 5).source, "∑▒x_i")
        self.assertIsNone(remove_nary_limits("∫▒x", 0))


class ScriptEditTests(unittest.TestCase):
    def test_scripts_are_found_but_not_limits_of_sums_or_lim_conditions(self) -> None:
        self.assertEqual(len(scripts("x_i^2+(a+b)^2")), 2)
        self.assertEqual(scripts("∑_(i=1)^n▒i"), [])
        self.assertEqual(scripts("lim_(x→0) 〖x〗"), [])
        self.assertEqual(script_at("sin^2 x", 1).base_start, 0)  # The whole name is the base.
        self.assertEqual(script_at("e^(x^2)", 4).base_start, 3)  # The innermost.

    def test_subscripts_and_superscripts_are_added_and_removed(self) -> None:
        self.assertEqual(add_subscript("x^2", 0).source, "x_()^2")
        self.assertEqual(add_superscript("x_i", 0).source, "x_i^()")
        self.assertEqual(remove_subscript("x_i^2", 0).source, "x^2")
        self.assertEqual(remove_superscript("x_i^2", 0).source, "x_i")
        self.assertIsNone(add_subscript("x_i", 0))
        self.assertIsNone(remove_superscript("x_i", 0))


class BracketEditTests(unittest.TestCase):
    def test_only_visible_brackets_count(self) -> None:
        self.assertEqual(len(brackets("2(a+b)+f(x)+[0,1)+|x|")), 4)
        for transparent in ("(a)/(b)", "x_(i)", "√(x)"):
            with self.subTest(source=transparent):
                self.assertEqual(brackets(transparent), [])
        self.assertEqual([(b.opening, b.closing) for b in brackets("|()|")], [(0, 3)])  # The bars, not the parens.
        self.assertEqual(len(brackets("(a+b)^2")), 1)  # A script's base keeps its parens.

    def test_brackets_change_hide_and_go(self) -> None:
        self.assertEqual(change_brackets("2(a+b)", 3, "[").source, "2[a+b]")
        self.assertEqual(change_brackets("2(a+b)", 3, "|").source, "2|a+b|")
        self.assertEqual(remove_brackets("2(a+b)", 3).source, "2a+b")
        self.assertEqual(hide_bracket("(a+b)", 1, closing=True).source, "(a+b┤")
        self.assertEqual(hide_bracket("(a+b┤", 1, closing=True).source, "(a+b)")
        self.assertEqual(hide_bracket("(a+b)", 1, closing=False).source, "├a+b)")
        self.assertEqual(bracket_at("(a+b)+1", 5).opening, 0)  # Right after ")" is still on it.

    def test_a_matrix_keeps_its_fence(self) -> None:
        self.assertIsNone(remove_brackets("(■(1&0@0&1))", 3))
        self.assertIsNone(hide_bracket("(■(1&0@0&1))", 3, closing=True))
        self.assertEqual(change_brackets("(■(1&0@0&1))", 3, "[").source, "[■(1&0@0&1)]")


class AccentAndBarEditTests(unittest.TestCase):
    def test_accents_change_and_go(self) -> None:
        self.assertEqual(change_accent("x\u0302+1", 1, "\u20d7").source, "x\u20d7+1")
        self.assertEqual(remove_accent("(a+b)\u20d7", 2).source, "(a+b)")
        self.assertEqual(accent_at("(a+b)\u20d7", 2).base_start, 0)

    def test_bars_switch_and_go(self) -> None:
        self.assertEqual(switch_bar("¯(x+y)", 3).source, "▁(x+y)")
        self.assertEqual(remove_bar("▁(x+y)", 3).source, "x+y")


@needs_node
class EditsBuildTests(unittest.TestCase):
    def test_every_edit_gives_a_source_the_converter_builds(self) -> None:
        sources = [
            add_subscript("x^2", 0).source,
            add_superscript("(a+b)_1", 0).source,
            remove_subscript("x_i^2", 0).source,
            change_brackets("2(a+b)", 3, "⟨").source,
            change_brackets("2(a+b)", 3, "⌈").source,
            hide_bracket("2(a+b)", 3, closing=True).source,
            hide_bracket("2(a+b)", 3, closing=False).source,
            change_accent("x\u0302", 1, "\u0308").source,
            switch_bar("¯(x+y)", 3).source,
        ]
        errors = [
            source for source, result in zip(sources, convert_all(sources), strict=True) if has_error(result["mathml"])
        ]
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
