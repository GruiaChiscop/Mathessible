from __future__ import annotations

import unittest

from mathessible.documents.pasted_html import markdown_from_html


class PasteTests(unittest.TestCase):
    def test_word_table_preserves_cells_and_formatting(self) -> None:
        result = markdown_from_html(
            "<html><head><style>p {color:red}</style></head><body><table><tbody>"
            "<tr><td><p>Name</p></td><td><p>Value</p></td></tr>"
            "<tr><td><p><b>A</b></p></td><td><p>1 | 2</p></td></tr>"
            "</tbody></table></body></html>"
        )
        self.assertEqual(result, "| Name | Value |\n| --- | --- |\n| **A** | 1 \\| 2 |")

    def test_blocks_and_inline_styles(self) -> None:
        self.assertEqual(
            markdown_from_html('<h2>Title</h2><p>Hello <span style="font-weight: bold">world</span></p>'),
            "## Title\n\nHello **world**",
        )

    def test_plain_text_fallback_for_merged_cells_and_word_math(self) -> None:
        self.assertIsNone(markdown_from_html('<table><tr><td colspan="2">A</td></tr></table>'))
        self.assertIsNone(markdown_from_html("<!--[if gte mso 9]><m:oMath>x</m:oMath><![endif]-->"))

    def test_unsafe_links_and_scripts_are_not_preserved(self) -> None:
        self.assertEqual(markdown_from_html('<script>alert(1)</script><a href="javascript:alert(1)">Hi</a>'), "Hi")

    def test_lists(self) -> None:
        self.assertEqual(markdown_from_html("<ul><li>One</li><li>Two</li></ul>"), "- One\n- Two")
