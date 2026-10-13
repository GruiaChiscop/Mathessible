import tempfile
import unittest
from pathlib import Path

from matex.document_io import markdown_path, read_markdown, write_markdown


class DocumentIOTests(unittest.TestCase):
    def test_adds_markdown_extension_when_missing(self) -> None:
        self.assertEqual(markdown_path("caiet").name, "caiet.md")
        self.assertEqual(markdown_path("caiet.markdown").name, "caiet.markdown")

    def test_round_trip_preserves_unicode_math_exactly(self) -> None:
        source = "# Analiză\r\n\r\n$$∫_0^∞▒f(x)ⅆx$$\r\n"
        with tempfile.TemporaryDirectory() as directory:
            path = write_markdown(Path(directory) / "analiza", source)
            self.assertEqual(path.name, "analiza.md")
            self.assertEqual(read_markdown(path), source)


if __name__ == "__main__":
    unittest.main()
