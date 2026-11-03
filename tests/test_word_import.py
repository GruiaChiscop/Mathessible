from __future__ import annotations

import base64
import io
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from mathessible.documents.docx_import import DocxImportError, import_docx
from mathessible.documents.grid_tables import expand_grid_tables
from mathessible.documents.html_export import markdown_parser
from mathessible.documents.pandoc import executable, html_to_markdown
from mathessible.documents.pandoc_ast import clean, has_math
from mathessible.documents.paste_plan import PasteRoute, paste_route


def _text(words: str) -> list[dict]:
    parts: list[dict] = []
    for word in words.split(" "):
        if parts:
            parts.append({"t": "Space"})
        parts.append({"t": "Str", "c": word})
    return parts


def _document(*blocks: dict) -> dict:
    return {"pandoc-api-version": [1, 23, 1], "meta": {}, "blocks": list(blocks)}


def _image(source: str, description: str) -> dict:
    return {"t": "Image", "c": [["", ["c"], [["width", "1in"]]], _text(description), [source, ""]]}


ATTRIBUTES = ["", ["note"], [["style", "color:red"]]]


class AstTests(unittest.TestCase):
    def test_raw_markup_spans_and_divs_give_way_to_their_text(self) -> None:
        document = _document(
            {"t": "RawBlock", "c": ["html", "<o:p></o:p>"]},
            {"t": "Div", "c": [ATTRIBUTES, [{"t": "Para", "c": [{"t": "Span", "c": [ATTRIBUTES, _text("Kept")]}]}]]},
        )
        self.assertEqual(clean(document)["blocks"], [{"t": "Para", "c": _text("Kept")}])

    def test_words_empty_paragraphs_are_left_out(self) -> None:
        empty = {"t": "Para", "c": [{"t": "Str", "c": "\u00a0"}, {"t": "Space"}]}
        document = _document(empty, {"t": "Para", "c": _text("Text")}, {"t": "Plain", "c": []})
        self.assertEqual(clean(document)["blocks"], [{"t": "Para", "c": _text("Text")}])

    def test_images_are_their_description_unless_placed(self) -> None:
        document = _document({"t": "Para", "c": [_image("file:///clip.png", "A dot")]})
        self.assertEqual(clean(document)["blocks"][0]["c"], _text("A dot"))
        placed = clean(document, lambda source: "media/dot.png")["blocks"][0]["c"][0]
        self.assertEqual(placed["c"][0], ["", [], []])  # Its attributes, which Markdown would show, dropped.
        self.assertEqual(placed["c"][2], ["media/dot.png", ""])

    def test_a_caption_that_repeats_the_description_is_not_repeated(self) -> None:
        figure = {
            "t": "Figure",
            "c": [
                ATTRIBUTES,
                [None, [{"t": "Plain", "c": _text("A dot")}]],
                [{"t": "Plain", "c": [_image("d.png", "A dot")]}],
            ],
        }
        self.assertEqual(clean(_document(figure))["blocks"], [{"t": "Plain", "c": _text("A dot")}])

    def test_math_is_found(self) -> None:
        self.assertTrue(has_math(_document({"t": "Para", "c": [{"t": "Math", "c": [{"t": "InlineMath"}, "x"]}]})))
        self.assertFalse(has_math(_document({"t": "Para", "c": _text("x")})))


class PasteRouteTests(unittest.TestCase):
    def test_routes(self) -> None:
        simple = "<p><b>Bold</b></p><table><tr><td colspan=2>Merged</td></tr></table>"
        blocks = "<table><tr><td><p>One</p><p>Two</p></td></tr></table>"
        self.assertEqual(paste_route(simple, True), PasteRoute.LOCAL)
        self.assertEqual(paste_route(blocks, True), PasteRoute.PANDOC)
        self.assertEqual(paste_route(blocks, False), PasteRoute.NEEDS_PANDOC)
        # Equations are converted by neither: the clipboard's text, as before.
        self.assertEqual(paste_route(blocks + "<math><mi>x</mi></math>", True), PasteRoute.PLAIN)
        self.assertEqual(
            paste_route("<!--[if gte msEquation 12]><m:oMath>x</m:oMath><![endif]-->", True), PasteRoute.PLAIN
        )


def _docx(*entries: tuple[str, bytes]) -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return data.getvalue()


class DocxImportTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def _import(self, document: dict, *entries: tuple[str, bytes]) -> str:
        source = self.root / "In.docx"
        source.write_bytes(_docx(("word/document.xml", b"<w/>"), *entries))
        with (
            patch("mathessible.documents.docx_import.pandoc.read_docx", return_value=document),
            patch("mathessible.documents.docx_import.pandoc.write_markdown", side_effect=lambda value: repr(value)),
        ):
            imported = import_docx(source, self.root / "Out.md")
        return imported.path.read_text(encoding="utf-8")

    def test_pictures_are_copied_and_unsafe_paths_refused(self) -> None:
        document = _document(
            {
                "t": "Para",
                "c": [
                    _image("media/image1.png", "Kept"),
                    _image("../../etc/passwd", "Outside"),
                    _image("/etc/passwd", "Absolute"),
                    _image("media/missing.png", "Missing"),
                ],
            }
        )
        written = self._import(document, ("word/media/image1.png", b"PNG"))
        self.assertEqual((self.root / "Out-media" / "image1.png").read_bytes(), b"PNG")
        self.assertIn("Out-media/image1.png", written)
        for refused in ("Outside", "Absolute", "Missing"):
            self.assertIn(f"'c': '{refused}'", written)  # Its description, not a picture.
        self.assertNotIn("passwd", written)

    def test_word_equations_mark_the_document_latex(self) -> None:
        written = self._import(_document({"t": "Para", "c": [{"t": "Math", "c": [{"t": "InlineMath"}, "x^2"]}]}))
        self.assertTrue(written.startswith("---\nmath: latex\n---\n"))
        self.assertNotIn("math: latex", self._import(_document({"t": "Para", "c": _text("x")})))

    def test_not_a_word_document(self) -> None:
        source = self.root / "In.docx"
        source.write_bytes(b"not a zip")
        with self.assertRaises(DocxImportError):
            import_docx(source, self.root / "Out.md")


DOT = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@unittest.skipUnless(executable(), "Optional Pandoc executable is not installed")
class RealPandocTests(unittest.TestCase):
    def test_pasted_cell_blocks_become_a_grid_table_we_read(self) -> None:
        markdown = html_to_markdown(
            '<table><tr><th colspan="2">Group</th></tr><tr><td><p>One</p><p>Two</p></td>'
            "<td><ul><li>x</li></ul></td></tr></table>"
            '<p><span style="color:red">Red</span> <img src="file:///clip.png" alt="A dot"></p>'
        )
        self.assertTrue(markdown.startswith("+--"))
        self.assertIn("Red A dot", markdown)
        self.assertNotIn("{", markdown)  # No Pandoc attributes, which the editor would show as text.
        html = markdown_parser().render(expand_grid_tables(markdown))
        self.assertIn('<th colspan="2">Group</th>', html)
        self.assertIn("<p>One</p>\n<p>Two</p>", html)

    def test_word_document_with_equation_note_picture_and_merged_table(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "dot.png").write_bytes(DOT)
            table = "+-----+-----+\n| A   | One |\n|     |     |\n|     | Two |\n|     +-----+\n|     | B   |\n+-----+-----+\n"
            source = "Area $x^2$ and a note.[^1]\n\n![A dot](dot.png)\n\n" + table + "\n[^1]: The note.\n"
            (root / "in.md").write_text(source, encoding="utf-8")
            program = shutil.which(executable())
            subprocess.run([program, "in.md", "-o", "in.docx"], cwd=root, check=True, timeout=60)
            imported = import_docx(root / "in.docx", root / "Out.md")
            written = imported.path.read_text(encoding="utf-8")
            self.assertTrue(written.startswith("---\nmath: latex\n---\n"))
            self.assertIn("$x^{2}$", written)
            self.assertIn("[^1]: The note.", written)
            self.assertEqual(len(imported.images), 1)
            self.assertEqual(imported.images[0].read_bytes(), DOT)
            self.assertIn(f"]({imported.images[0].parent.name}/{imported.images[0].name})", written)
            html = markdown_parser().render(expand_grid_tables(written))
            self.assertIn('rowspan="2"', html)
            self.assertIn("<p>One</p>\n<p>Two</p>", html)
