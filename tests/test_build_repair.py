import unittest

from mathessible.editing.build_repair import PLACEHOLDER, BuildRepair, repair_for_build, repairs


def text_of(source: str, accepted: int) -> str:
    """The repaired text of the `accepted`-th candidate (0: the source itself)."""
    return list(repairs(source))[accepted].text


class RepairCandidatesTests(unittest.TestCase):
    def test_a_buildable_source_is_its_own_first_candidate(self) -> None:
        self.assertEqual(text_of("a+b", 0), "a+b")
        self.assertEqual(len(list(repairs("a+b"))), 1)

    def test_missing_arguments_get_a_zero_width_placeholder(self) -> None:
        self.assertEqual(text_of("∫▒", 1), "∫▒" + PLACEHOLDER)
        self.assertEqual(text_of("∫▒ dx", 1), "∫▒" + PLACEHOLDER + " dx")
        self.assertEqual(text_of("√(&x)", 1), "√(" + PLACEHOLDER + "&x)")
        self.assertEqual(text_of("√(&)", 1), "√(" + PLACEHOLDER + "&" + PLACEHOLDER + ")")
        # Control words too: "\\of " resolves to "▒" with its space.
        self.assertEqual(text_of("\\int\\of ", 1), "\\int\\of " + PLACEHOLDER)

    def test_what_is_left_open_is_closed_at_the_end(self) -> None:
        self.assertEqual(text_of("(■(1&2@", 1), "(■(1&2@))")
        self.assertEqual(text_of('"abc', 1), '"abc"')
        self.assertEqual(text_of("|x", 1), "|x|")

    def test_a_backslash_just_typed_before_a_separator_is_built_literal(self) -> None:
        # "1&x \\@&": the "\\" would escape the case's "@" until a letter follows.
        source = "{■(1&x \\@&)┤"
        caret = source.index("@")
        candidate = next(repairs(source, caret))
        self.assertEqual(candidate.text, "{■(1&x \\\\@&)┤")
        self.assertEqual(candidate.to_real(caret + 1), caret)
        # Not once a letter follows, not for an escaped backslash, not away from the caret.
        self.assertEqual(next(repairs("x \\i@", 4)).text, "x \\i@")
        self.assertEqual(next(repairs("x\\\\@", 3)).text, "x\\\\@")
        self.assertEqual(next(repairs("\\(a)", 4)).text, "\\(a)")

    def test_the_first_candidate_that_builds_is_used(self) -> None:
        def builds(text: str) -> bool:
            return PLACEHOLDER in text or text == "a"

        self.assertEqual(repair_for_build("a", builds).text, "a")
        self.assertEqual(repair_for_build("∫▒", builds).text, "∫▒" + PLACEHOLDER)
        self.assertIsNone(repair_for_build("a+b)", builds))


class RepairOffsetsTests(unittest.TestCase):
    def test_offsets_map_between_the_source_and_the_repaired_text(self) -> None:
        repair = list(repairs("√(&)"))[1]  # "√(Z&Z)" with Z the placeholder.
        self.assertEqual([repair.to_real(offset) for offset in range(len(repair.text) + 1)], [0, 1, 2, 2, 3, 3, 4])
        self.assertEqual([repair.to_repaired(offset) for offset in range(len(repair.source) + 1)], [0, 1, 2, 4, 6])

    def test_no_repair_maps_offsets_to_themselves(self) -> None:
        repair = BuildRepair("a+b", "a+b")
        self.assertEqual((repair.to_real(2), repair.to_repaired(2)), (2, 2))


if __name__ == "__main__":
    unittest.main()
