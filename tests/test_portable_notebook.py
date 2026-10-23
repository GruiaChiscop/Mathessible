import tempfile
import unittest
import zipfile
from pathlib import Path

from matex.documents.notebook import Notebook, NotebookError
from matex.documents.portable_notebook import extract_mtex, save_mtex


class PortableNotebookTests(unittest.TestCase):
    def test_round_trip_preserves_pages_and_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            notebook = Notebook.create(base / "sursă", "Analiză matematică")
            notebook.write_page(0, "# Limite\n\n$lim_(x→0) f(x)$")
            notebook.add_page("Integrale", "$$∫_0^1 xⅆx$$")
            archive = save_mtex(notebook, base / "analiză")

            reopened = extract_mtex(archive, base / "destinație")
            self.assertEqual(archive.suffix, ".mtex")
            self.assertEqual(reopened.title, "Analiză matematică")
            self.assertEqual([page.title for page in reopened.pages], ["Page 1", "Integrale"])
            self.assertEqual(reopened.read_page(1), "$$∫_0^1 xⅆx$$")

    def test_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archive = base / "periculos.mtex"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("matex.json", "{}")
                output.writestr("../outside.md", "nu")
            with self.assertRaises(NotebookError):
                extract_mtex(archive, base / "destinație")
            self.assertFalse((base / "outside.md").exists())


if __name__ == "__main__":
    unittest.main()
