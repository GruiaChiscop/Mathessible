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

    def test_google_docs_normal_weight_wrapper_is_not_bold(self) -> None:
        html = (
            '<b style="font-weight:normal;" id="docs-internal-guid-1"><p><span style="font-weight:400">One</span> '
            '<span style="font-weight:700">strong</span></p><p><span>Two</span></p></b>'
        )
        self.assertEqual(markdown_from_html(html), "One **strong**\n\nTwo")

    def test_emphasis_around_blocks_marks_each_paragraph(self) -> None:
        self.assertEqual(markdown_from_html("<b><p>a</p><ul><li>x</li></ul><p>b</p></b>"), "**a**\n\n- x\n\n**b**")

    def test_code_editor_copy_keeps_its_source(self) -> None:
        html = (
            '<div style="white-space: pre;"><div><span>Let $x^2$ be  *a*</span></div><div><br></div>'
            "<div><span>    indented</span></div></div>"
        )
        self.assertEqual(markdown_from_html(html), "Let $x^2$ be  *a*\n\n    indented")

    def test_tildes_are_escaped_and_rules_keep_their_order(self) -> None:
        self.assertEqual(markdown_from_html("<p>~~not~~</p>"), "\\~\\~not\\~\\~")
        html = "<style>p{font-style:italic} .plain{font-style:normal}</style><p class=plain>a</p><p>b</p>"
        self.assertEqual(markdown_from_html(html), "a\n\n*b*")
