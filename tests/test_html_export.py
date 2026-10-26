import tempfile
import unittest
from pathlib import Path

from matex.documents.html_export import (
    ExportPage,
    notebook_html,
    preview_update_script,
    render_markdown,
    write_notebook_html,
)


def fake_mathml(source: str) -> str:
    if source == "bad":
        raise ValueError("invalid equation")
    return f"<math><mi>{source}</mi></math>"


class HtmlExportTests(unittest.TestCase):
    def test_renders_markdown_tables_links_and_math(self) -> None:
        source = "# Heading\n\n[Link](https://example.com)\n\n| A | B |\n| - | - |\n| 1 | 2 |\n\n$x+1$\n\n$$a/b$$"

        rendered = render_markdown(source, fake_mathml)

        self.assertIn("<h1>Heading</h1>", rendered)
        self.assertIn('<a href="https://example.com">Link</a>', rendered)
        self.assertIn("<table>", rendered)
        self.assertIn('<span class="math-inline"><math><mi>x+1</mi></math></span>', rendered)
        self.assertIn('<div class="math-display"><math><mi>a/b</mi></math></div>', rendered)

    def test_inline_math_is_inline_although_the_converter_writes_block(self) -> None:
        def block_mathml(source: str) -> str:
            return f'<math display="block"><mi>{source}</mi></math>'

        rendered = render_markdown("Roots of $x$ are\n\n$$y$$", block_mathml)

        self.assertIn('<span class="math-inline"><math display="inline"><mi>x</mi></math></span>', rendered)
        self.assertIn('<div class="math-display"><math display="block"><mi>y</mi></math></div>', rendered)

    def test_code_math_is_untouched_and_invalid_math_has_a_safe_fallback(self) -> None:
        rendered = render_markdown("`$code$` and $bad$ <script>alert(1)</script>", fake_mathml)

        self.assertIn("<code>$code$</code>", rendered)
        self.assertIn('class="math-error"', rendered)
        self.assertIn("$bad$", rendered)
        self.assertNotIn("<script>", rendered)

    def test_malicious_converter_output_falls_back_instead_of_being_embedded(self) -> None:
        def malicious_mathml(source: str) -> str:
            return (
                "<math><semantics><mi>x</mi>"
                '<annotation-xml encoding="text/html">'
                "<script>alert(1)</script></annotation-xml>"
                "</semantics></math>"
            )

        rendered = render_markdown("$x$", malicious_mathml)

        self.assertNotIn("<script>", rendered)

    def test_converter_output_with_disallowed_element_falls_back(self) -> None:
        def unsafe_mathml(source: str) -> str:
            return "<math><mi><foreignObject>x</foreignObject></mi></math>"

        rendered = render_markdown("$x$", unsafe_mathml)

        self.assertIn('class="math-error"', rendered)
        self.assertNotIn("foreignObject", rendered)

    def test_notebook_preserves_page_order_and_escapes_titles(self) -> None:
        rendered = notebook_html(
            "Algebra & Geometry",
            [ExportPage("First <page>", "Text"), ExportPage("Second", "More")],
            fake_mathml,
        )

        self.assertIn("<title>Algebra &amp; Geometry</title>", rendered)
        self.assertIn("First &lt;page&gt;", rendered)
        self.assertLess(rendered.index('id="page-1"'), rendered.index('id="page-2"'))
        self.assertIn('aria-label="Notebook pages"', rendered)

    def test_write_adds_html_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = write_notebook_html(
                Path(directory) / "export",
                "Notebook",
                [ExportPage("Page", "Hello")],
                fake_mathml,
            )

            self.assertEqual(destination.suffix, ".html")
            self.assertTrue(destination.read_text(encoding="utf-8").startswith("<!doctype html>"))

    def test_preview_script_embeds_sanitized_document_as_a_js_string(self) -> None:
        script = preview_update_script(
            "# Title\n\n$x$ and <script>alert(1)</script>", lambda _s: "<math><mi>x</mi></math>"
        )
        self.assertTrue(script.startswith("window.matexSetDocument("))
        self.assertIn("<h1>Title</h1>", script)
        self.assertIn('<span class=\\"math-inline\\"><math><mi>x</mi></math></span>', script)
        self.assertNotIn("<script>", script)
        self.assertIn("Empty document", preview_update_script("  \n", lambda _s: ""))


if __name__ == "__main__":
    unittest.main()
