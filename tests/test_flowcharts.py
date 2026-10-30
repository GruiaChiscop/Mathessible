import io
import unittest
import zipfile

from mathessible.documents.brf_export import BrfLayout, ascii_braille, braille_lines
from mathessible.documents.docx_export import DocxOptions, docx_document
from mathessible.documents.flowcharts import (
    FlowchartError,
    alternative_text,
    connection_rows,
    draw,
    flowchart_block,
    flowchart_html,
    parse_flowchart,
    tikz_figure,
    tikz_flowchart,
)
from mathessible.documents.html_export import ExportPage, render_markdown
from mathessible.documents.pdf_export import PdfOptions, typst_document
from mathessible.documents.tex_markdown import tex_to_markdown
from mathessible.editing import document_insert

MERMAID = """%% title: Registration
%% description: A person either continues or tries again.
flowchart TD
  start([Start]) --> form[Complete form]
  form --> valid{Valid?}
  valid -->|Yes| finish([Finish])
  valid -->|No| form"""


class ParseTests(unittest.TestCase):
    def test_nodes_shapes_directions_and_labelled_connections(self) -> None:
        flowchart = parse_flowchart(MERMAID)
        self.assertEqual((flowchart.direction, flowchart.title), ("TD", "Registration"))
        self.assertEqual([node.shape for node in flowchart.nodes], ["terminal", "process", "decision", "terminal"])
        self.assertEqual(flowchart.edges[-2].label, "Yes")
        self.assertEqual(connection_rows(flowchart)[-1], "Valid? to Complete form, labelled No")
        self.assertIn("4 nodes and 4 connections", alternative_text(flowchart))

    def test_graph_and_all_directions_are_accepted(self) -> None:
        for direction in ("TB", "BT", "LR", "RL"):
            flowchart = parse_flowchart(f"graph {direction}\n  one(One) --> two[Two]")
            self.assertEqual(flowchart.direction, "TD" if direction == "TB" else direction)

    def test_unknown_mermaid_is_refused_with_its_line(self) -> None:
        for source in (
            "sequenceDiagram\nA->>B: Hello",
            "flowchart TD",
            "flowchart TD\nA -- dotted --> B",
            "flowchart TD\nA[One]\nA[Two]",
        ):
            with self.assertRaises(FlowchartError, msg=source):
                parse_flowchart(source)


class DrawingTests(unittest.TestCase):
    def test_svg_and_png_are_drawn_locally(self) -> None:
        flowchart = parse_flowchart(MERMAID)
        self.assertIn(b"<svg", draw(flowchart))
        self.assertTrue(draw(flowchart, "png").startswith(b"\x89PNG"))

    def test_html_has_the_picture_caption_and_connections(self) -> None:
        html = flowchart_html(MERMAID)
        self.assertIn('src="data:image/svg+xml;base64,', html)
        self.assertIn("<figcaption>Registration</figcaption>", html)
        self.assertIn("Valid? to Finish, labelled Yes", html)
        self.assertIn("flowchart-error", flowchart_html("sequenceDiagram"))


class ExportTests(unittest.TestCase):
    markdown = f"# Process\n\n```mermaid\n{MERMAID}\n```\n"

    def test_preview_and_html_draw_mermaid(self) -> None:
        html = render_markdown(self.markdown, lambda source: source)
        self.assertIn('<figure class="flowchart">', html)
        self.assertNotIn('<code class="language-mermaid">', html)

    def test_pdf_has_an_accessible_flowchart_figure(self) -> None:
        images: dict[str, bytes] = {}
        source = typst_document([ExportPage("Process", self.markdown)], "Process", None, PdfOptions(), images)
        self.assertEqual(list(images), ["flowchart-1.svg"])
        self.assertIn('#figure(image("flowchart-1.svg", alt: "Registration.', source)

    def test_word_has_a_described_picture_and_caption(self) -> None:
        data = docx_document([ExportPage("Process", self.markdown)], "Process", lambda _source: None, DocxOptions())
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertTrue(any(name.startswith("word/media/") for name in archive.namelist()))
            document = archive.read("word/document.xml").decode()
        self.assertIn('descr="Registration.', document)
        self.assertIn('w:val="Caption"', document)

    def test_braille_reads_description_summary_and_connections(self) -> None:
        def letters(text: str) -> str:
            return "".join(chr(0x2801) if character != " " else "⠀" for character in text)

        lines = braille_lines(self.markdown, letters, letters, BrfLayout(cells_per_line=80, lines_per_page=25))
        self.assertGreaterEqual(len([line for line in lines if ascii_braille(line).strip()]), 7)


class InsertionTests(unittest.TestCase):
    def test_markdown_template_is_standard_mermaid_and_places_the_caret(self) -> None:
        block = flowchart_block("Process", "How it works.", "LR")
        source = block.split("\n", 1)[1].rsplit("\n", 1)[0]
        self.assertEqual((parse_flowchart(source).title, parse_flowchart(source).direction), ("Process", "LR"))
        edit = document_insert.flowchart("Text", 4, 4, block, "Process]", False)
        self.assertTrue(edit.source[edit.caret :].startswith("Process]"))

    def test_tikz_keeps_a_mermaid_source_for_preview_and_export(self) -> None:
        figure = tikz_figure("Process", "How it works.")
        self.assertIn("\\begin{tikzpicture}", figure)
        self.assertIn("diamond", figure)
        recovered = tikz_flowchart(figure)
        self.assertIsNotNone(recovered)
        self.assertIn("```mermaid\n%% title: Process", recovered or "")
        markdown = tex_to_markdown("\\documentclass{article}\n\\begin{document}\n" + figure + "\n\\end{document}\n")
        self.assertIn("```mermaid\n%% title: Figure 1: Process", markdown)

    def test_tikz_packages_are_added_once(self) -> None:
        source = "\\documentclass{article}\n\\begin{document}\n\\end{document}\n"
        edit = document_insert.flowchart(
            source, source.index("\\end{document}"), source.index("\\end{document}"), tikz_figure(), "{Process}", True
        )
        edit = document_insert.with_package(edit, "tikz")
        edit = document_insert.with_preamble_line(edit, "\\usetikzlibrary{shapes.geometric}")
        again = document_insert.with_preamble_line(edit, "\\usetikzlibrary{shapes.geometric}")
        self.assertEqual(again.source.count("\\usepackage{tikz}"), 1)
        self.assertEqual(again.source.count("\\usetikzlibrary{shapes.geometric}"), 1)


if __name__ == "__main__":
    unittest.main()
