import unittest

from matex.editing.edit_history import EditHistory


class EditHistoryTests(unittest.TestCase):
    def test_undo_and_redo_restore_source_and_caret(self) -> None:
        history = EditHistory("x", 1)
        history.push("x+", 2)
        history.push("x+1", 3)
        self.assertEqual(history.undo().source, "x+")
        self.assertEqual(history.undo().caret, 1)
        self.assertEqual(history.redo().source, "x+")

    def test_new_edit_discards_redo_branch(self) -> None:
        history = EditHistory("a", 1)
        history.push("ab", 2)
        history.undo()
        history.push("ac", 2)
        self.assertFalse(history.can_redo)
        self.assertEqual(history.current.source, "ac")

    def test_reset_starts_a_new_equation_history(self) -> None:
        history = EditHistory("old", 3)
        history.push("older", 5)
        history.reset("new", 3)
        self.assertFalse(history.can_undo)
        self.assertEqual(history.current.source, "new")


if __name__ == "__main__":
    unittest.main()
