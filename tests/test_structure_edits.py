import unittest

from matex.structure_edits import (
    add_nary_limits,
    add_root_index,
    nary_at,
    nary_operators,
    remove_nary_limits,
    remove_root_index,
    root_at,
    roots,
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
        self.assertEqual((edit.source, edit.caret), ("√(x)", 3))
        self.assertEqual(remove_root_index("∛x+1", 1).source, "√x+1")
        self.assertEqual(remove_root_index("∜(y)", 2).source, "√(y)")
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


if __name__ == "__main__":
    unittest.main()
