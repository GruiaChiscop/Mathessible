import unittest

from matex.build_triggers import build_source_for_trigger, build_trigger_for


class BuildTriggerTests(unittest.TestCase):
    def test_space_at_end_attempts_build_without_becoming_source_text(self) -> None:
        trigger = build_trigger_for("x+1", 3, " ")
        self.assertTrue(trigger.should_attempt)
        self.assertFalse(trigger.include_character)
        self.assertEqual(build_source_for_trigger("x+1", 3, trigger), ("x+1", 3))

    def test_space_in_middle_does_not_attempt_build(self) -> None:
        trigger = build_trigger_for("x+1", 1, " ")
        self.assertFalse(trigger.should_attempt)

    def test_semicolon_at_end_attempts_build_and_is_preserved(self) -> None:
        trigger = build_trigger_for("x+1", 3, ";")
        self.assertTrue(trigger.should_attempt)
        self.assertTrue(trigger.include_character)
        self.assertEqual(build_source_for_trigger("x+1", 3, trigger), ("x+1;", 4))

    def test_comma_after_number_is_not_a_build_trigger(self) -> None:
        trigger = build_trigger_for("3", 1, ",")
        self.assertFalse(trigger.should_attempt)
        self.assertTrue(trigger.include_character)

    def test_comma_after_symbol_attempts_build_and_is_preserved(self) -> None:
        trigger = build_trigger_for("x", 1, ",")
        self.assertTrue(trigger.should_attempt)
        self.assertTrue(trigger.include_character)
        self.assertEqual(build_source_for_trigger("x", 1, trigger), ("x,", 2))

    def test_non_trigger_character_is_ignored(self) -> None:
        trigger = build_trigger_for("x", 1, "+")
        self.assertFalse(trigger.should_attempt)
        self.assertFalse(trigger.include_character)


if __name__ == "__main__":
    unittest.main()
