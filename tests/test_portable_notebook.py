import tempfile
import unittest
import zipfile
from pathlib import Path

from mathessible.documents.notebook import Notebook, NotebookError
from mathessible.documents.portable_notebook import extract_portable, save_portable


class PortableNotebookTests(unittest.TestCase):
    def test_round_trip_preserves_pages_and_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            notebook = Notebook.create(base / "source", "Analyse mathématique")
            notebook.write_page(0, "# Limite\n\n$lim_(x→0) f(x)$")
            notebook.add_page("Integrale", "$$∫_0^1 xⅆx$$")
            archive = save_portable(notebook, base / "analyse")

            reopened = extract_portable(archive, base / "destination")
            self.assertEqual(archive.suffix, ".mathessible")
            self.assertEqual(reopened.title, "Analyse mathématique")
            self.assertEqual([page.title for page in reopened.pages], ["Page 1", "Integrale"])
            self.assertEqual(reopened.read_page(1), "$$∫_0^1 xⅆx$$")

    def test_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archive = base / "periculos.mathessible"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("mathessible.json", "{}")
                output.writestr("../outside.md", "no")
            with self.assertRaises(NotebookError):
                extract_portable(archive, base / "destination")
            self.assertFalse((base / "outside.md").exists())


if __name__ == "__main__":
    unittest.main()
