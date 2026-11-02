from __future__ import annotations

import unittest

from mathessible.documents.pasted_html import has_merged_cells, markdown_from_html


class PasteTests(unittest.TestCase):
    def test_nested_table_inside_wrapper_falls_back(self) -> None:
        self.assertIsNone(
            markdown_from_html("<table><tr><td><div><table><tr><td>Keep this</td></tr></table></div></td></tr></table>")
        )

    def test_merge_warning_uses_cell_attributes_not_text(self) -> None:
        self.assertTrue(has_merged_cells('<td rowspan="2">A</td>'))
        self.assertFalse(has_merged_cells('<td colspan="1">rowspan="2"</td>'))

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

    def test_merged_cells_keep_their_grid_positions(self) -> None:
        self.assertEqual(
            markdown_from_html('<table><tr><td rowspan="2">A</td><td>B</td></tr><tr><td>C</td></tr></table>'),
            "```table\n| A | B |\n| --- | --- |\n| ^ | C |\n```",
        )
        self.assertEqual(
            markdown_from_html('<table><tr><td colspan="2">A</td></tr></table>'),
            "```table\n| A | > |\n| --- | --- |\n```",
        )

    def test_word_math_still_falls_back(self) -> None:
        self.assertIsNone(markdown_from_html("<!--[if gte mso 9]><m:oMath>x</m:oMath><![endif]-->"))

    def test_cocoa_class_styles_and_inline_override(self) -> None:
        self.assertEqual(
            markdown_from_html(
                "<style>p.p1 {font-weight:bold} span.s1 {font-style:italic}</style>"
                '<p class="p1">Title</p><p class="p1" style="font-weight:normal">Plain <span class="s1">italic</span></p>'
            ),
            "**Title**\n\nPlain *italic*",
        )

    def test_code_preserves_spaces_and_markdown_symbols(self) -> None:
        self.assertEqual(markdown_from_html("<pre>  x * y\n    z</pre>"), "```\n  x * y\n    z\n```")

    def test_ordered_list_start_is_preserved(self) -> None:
        self.assertEqual(markdown_from_html('<ol start="3"><li>A</li><li>B</li></ol>'), "3. A\n4. B")

    def test_unsafe_links_and_scripts_are_not_preserved(self) -> None:
        self.assertEqual(markdown_from_html('<script>alert(1)</script><a href="javascript:alert(1)">Hi</a>'), "Hi")

    def test_lists(self) -> None:
        self.assertEqual(markdown_from_html("<ul><li>One</li><li>Two</li></ul>"), "- One\n- Two")
