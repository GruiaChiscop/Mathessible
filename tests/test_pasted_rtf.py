from __future__ import annotations

import sys
import unittest

from mathessible.documents.pasted_html import markdown_from_html
from mathessible.documents.pasted_rtf import html_from_rtf


class RichTextPasteTests(unittest.TestCase):
    def test_non_rtf_is_rejected(self) -> None:
        self.assertIsNone(html_from_rtf(b"plain text"))

    @unittest.skipUnless(sys.platform == "darwin", "Requires Apple's textutil")
    def test_native_rtf_formatting(self) -> None:
        html = html_from_rtf(rb"{\rtf1\ansi Hello \b bold\b0\par Next}")
        self.assertIsNotNone(html)
        self.assertEqual(markdown_from_html(html), "Hello **bold**\n\nNext")

    @unittest.skipUnless(sys.platform == "darwin", "Requires Apple's textutil")
    def test_native_rtf_table(self) -> None:
        html = html_from_rtf(
            rb"{\rtf1\ansi "
            rb"\trowd\cellx2000\cellx4000\intbl Name\cell Value\cell\row "
            rb"\trowd\cellx2000\cellx4000\intbl A\cell 42\cell\row}"
        )
        self.assertIsNotNone(html)
        self.assertEqual(markdown_from_html(html), "| Name | Value |\n| --- | --- |\n| A | 42 |")
