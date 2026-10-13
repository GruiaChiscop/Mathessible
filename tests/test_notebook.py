import tempfile
import unittest
from pathlib import Path

from matex.notebook import Notebook, NotebookError


class NotebookTests(unittest.TestCase):
    def test_create_write_and_reopen_notebook(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Algebră"
            notebook = Notebook.create(root)
            notebook.write_page(0, "# Ecuații\n\n$x+1=2$")
            notebook.add_page("Matrice", "$$(■(a&b@c&d))$$")

            reopened = Notebook.open(root)
            self.assertEqual(reopened.title, "Algebră")
            self.assertEqual([page.title for page in reopened.pages], ["Page 1", "Matrice"])
            self.assertEqual(reopened.read_page(1), "$$(■(a&b@c&d))$$")

    def test_rename_and_reorder_pages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            notebook = Notebook.create(Path(directory) / "Caiet")
            notebook.add_page("A doua")
            notebook.rename_page(0, "Introducere")
            notebook.move_page(1, 0)
            self.assertEqual([page.title for page in notebook.pages], ["A doua", "Introducere"])

    def test_cannot_delete_last_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            notebook = Notebook.create(Path(directory) / "Caiet")
            with self.assertRaises(NotebookError):
                notebook.delete_page(0)

    def test_delete_removes_page_file_and_keeps_manifest_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Caiet"
            notebook = Notebook.create(root)
            removed = notebook.add_page("Temporară")
            removed_path = root / removed.file
            notebook.delete_page(1)
            self.assertFalse(removed_path.exists())
            self.assertEqual(len(Notebook.open(root).pages), 1)


if __name__ == "__main__":
    unittest.main()
