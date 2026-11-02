from __future__ import annotations

import json
import os
import subprocess
import unittest
from unittest.mock import patch

from mathessible.documents.pandoc import Format, PandocError, PandocMissing, convert, executable, read_html
from mathessible.documents.paste_requirements import inspect_html


class PandocTests(unittest.TestCase):
    def test_missing_is_distinct_from_failed_conversion(self) -> None:
        with patch("mathessible.documents.pandoc.executable", return_value=None), self.assertRaises(PandocMissing):
            read_html("<p>Hello</p>")

    def test_explicit_path_is_respected(self) -> None:
        with (
            patch.dict(os.environ, {"MATHESSIBLE_PANDOC": "/custom/pandoc"}),
            patch("mathessible.documents.pandoc.load_settings") as settings,
            patch("mathessible.documents.pandoc.find_pandoc", return_value=None) as which,
        ):
            settings.return_value.pandoc_path = ""
            self.assertIsNone(executable())
            which.assert_called_once_with("/custom/pandoc")

    @patch("mathessible.documents.pandoc.executable", return_value="/bin/pandoc")
    def test_json_bridge_and_sandbox(self, _program) -> None:
        document = {"pandoc-api-version": [1, 23, 1], "meta": {}, "blocks": []}
        with patch("mathessible.documents.pandoc.subprocess.run") as run:
            run.return_value.stdout = json.dumps(document).encode()
            self.assertEqual(read_html("<p>Text</p>"), document)
            args, kwargs = run.call_args
            self.assertIn("--sandbox", args[0])
            self.assertIn("--fail-if-warnings", args[0])
            self.assertIn("--from=html", args[0])
            self.assertIn("--to=json", args[0])
            self.assertEqual(kwargs["input"], b"<p>Text</p>")
            self.assertEqual(kwargs["timeout"], 10)
            self.assertNotIn("shell", kwargs)

    @patch("mathessible.documents.pandoc.executable", return_value="/bin/pandoc")
    def test_errors_never_echo_clipboard(self, _program) -> None:
        for error in (
            subprocess.TimeoutExpired("pandoc", 10),
            subprocess.CalledProcessError(1, "pandoc", stderr=b"PRIVATE TEXT"),
            OSError("PRIVATE TEXT"),
        ):
            with (
                self.subTest(error=type(error)),
                patch("mathessible.documents.pandoc.subprocess.run", side_effect=error),
            ):
                with self.assertRaises(PandocError) as raised:
                    read_html("PRIVATE TEXT")
                self.assertNotIn("PRIVATE TEXT", str(raised.exception))

    def test_invalid_document_is_rejected(self) -> None:
        for value in ("not json", "[]", '{"blocks": []}'):
            with (
                self.subTest(value=value),
                patch("mathessible.documents.pandoc.convert", return_value=value),
                self.assertRaises(PandocError),
            ):
                read_html("<p>Text</p>")

    def test_large_input_and_arbitrary_options_are_rejected_before_running(self) -> None:
        with patch("mathessible.documents.pandoc.subprocess.run") as run:
            with self.assertRaises(PandocError):
                convert("x" * 2_000_001, Format.HTML, Format.JSON)
            with self.assertRaises(ValueError):
                convert("text", "--filter=program", Format.JSON)
            run.assert_not_called()

    @unittest.skipUnless(executable(), "Optional Pandoc executable is not installed")
    def test_real_reader_preserves_complex_cell_blocks(self) -> None:
        document = read_html('<table><tr><td colspan="2"><p>First</p><p>Second</p></td></tr></table>')
        self.assertEqual(document["blocks"][0]["t"], "Table")
        encoded = json.dumps(document)
        self.assertIn('"First"', encoded)
        self.assertIn('"Second"', encoded)


class PasteRequirementsTests(unittest.TestCase):
    def test_simple_office_content_needs_no_pandoc(self) -> None:
        for html in (
            "<p><b>Text</b></p><ul><li>Item</li></ul>",
            '<table><tr><td colspan="2"><p>One paragraph</p></td></tr></table>',
        ):
            requirements = inspect_html(html)
            self.assertFalse(requirements.pandoc_features)
            self.assertFalse(requirements.unsupported_features)

    def test_complex_cells_and_nested_lists_are_identified(self) -> None:
        self.assertIn(
            "cell_paragraphs",
            inspect_html("<table><tr><td><div><p>A</p><p>B</p></div></td></tr></table>").pandoc_features,
        )
        for body in ("<ul><li>A</li></ul>", "<pre>code</pre>", "A<br>B", "<table></table>"):
            self.assertIn("cell_blocks", inspect_html(f"<table><tr><td>{body}</td></tr></table>").pandoc_features)
        self.assertIn("nested_lists", inspect_html("<ul><li>A<ul><li>B</li></ul></li></ul>").pandoc_features)

    def test_pandoc_is_not_assumed_to_fix_equations_or_images(self) -> None:
        requirements = inspect_html('<!--[if mso]><m:oMath>x</m:oMath><![endif]--><img src="file:///image">')
        self.assertEqual(requirements.unsupported_features, frozenset({"office_equations", "embedded_content"}))
        self.assertFalse(requirements.pandoc_features)
