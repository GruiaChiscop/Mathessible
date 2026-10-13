import unittest

from matex.model import EquationDocument


class ModelTests(unittest.TestCase):
    def test_semantic_navigation(self) -> None:
        document = EquationDocument("a/(b+c)")
        self.assertIn("fraction", document.announcement)
        self.assertTrue(document.cursor.move_into(document.root))
        self.assertEqual(document.announcement, "a")
        self.assertTrue(document.cursor.move_next(document.root))
        self.assertIn("group", document.announcement)
        self.assertTrue(document.cursor.move_into(document.root))
        self.assertIn("b plus c", document.announcement)
        self.assertTrue(document.cursor.move_next(document.root))
        self.assertEqual(document.announcement, "b")
        self.assertTrue(document.cursor.move_next(document.root))
        self.assertEqual(document.announcement, "plus")

    def test_cursor_maps_from_source_offset(self) -> None:
        document = EquationDocument("x+1")
        self.assertTrue(document.replace_source("a/(b+c)", caret=4))
        self.assertEqual(document.announcement, "plus")

    def test_invalid_replacement_keeps_source_for_further_editing(self) -> None:
        document = EquationDocument("x+1")
        self.assertFalse(document.replace_source(")"))
        self.assertEqual(document.source, ")")
        self.assertEqual(document.normalized_source, "x+1")
        self.assertIsNotNone(document.parse_error)


    def test_unparsable_source_opens_without_raising(self) -> None:
        document = EquationDocument("x=(-b±√(b^2-4ac))/(2a)")
        self.assertEqual(document.source, "x=(-b±√(b^2-4ac))/(2a)")
        self.assertIsNotNone(document.parse_error)

if __name__ == "__main__":
    unittest.main()
