import io
import math
import unittest
import zipfile

from mathessible.documents.brf_export import BrfLayout, ascii_braille, braille_lines
from mathessible.documents.charts import (
    ChartError,
    alternative_text,
    calculator_expression,
    chart_block,
    chart_html,
    draw,
    expression_function,
    parse_chart,
    pgf_expression,
    pgfplots_chart,
    pgfplots_figure,
    summary,
)
from mathessible.documents.docx_export import DocxOptions, docx_document
from mathessible.documents.html_export import ExportPage
from mathessible.documents.pdf_export import PdfOptions, typst_document
from mathessible.documents.tex_markdown import tex_to_markdown
from mathessible.editing import document_insert

SCORES = "type: bar\ntitle: Scores\ndescription: Ann leads.\n| Name | Score |\n|---|---|\n| Ann | 9 |\n| Bob | 7 |"


def inside(block: str) -> str:
    """A ```chart block's text, without its fence."""
    return block.split("\n", 1)[1].rsplit("\n", 1)[0]


class ExpressionTests(unittest.TestCase):
    def test_a_calculators_expression_is_evaluated(self) -> None:
        self.assertAlmostEqual(expression_function("2x^2 + 1")(3), 19)
        self.assertAlmostEqual(expression_function("sin(π/2)")(0), 1)
        self.assertAlmostEqual(expression_function("(x+1)(x-1)")(2), 3)
        self.assertTrue(math.isnan(expression_function("ln(x)")(-1)))
        self.assertTrue(math.isnan(expression_function("10^x^x")(9)))

    def test_anything_but_arithmetic_is_refused(self) -> None:
        for expression in ("__import__('os')", "x.real", "open(x)", "[x]", "lambda: 1", "y + 1", ""):
            with self.assertRaises(ChartError, msg=expression):
                expression_function(expression)


class ParseTests(unittest.TestCase):
    def test_a_function_graph(self) -> None:
        chart = parse_chart("type: function\ntitle: Waves\nfunction: sin(x); cos(x)\nx: -pi .. pi")
        self.assertEqual((chart.kind, chart.title, chart.functions), ("function", "Waves", ("sin(x)", "cos(x)")))
        self.assertAlmostEqual(chart.x_range[1], math.pi)
        self.assertEqual(summary(parse_chart("type: function\nfunction: x\nx: 0 to 2")).split(",")[0], "Graph of y = x")

    def test_a_chart_of_data(self) -> None:
        chart = parse_chart(SCORES)
        self.assertEqual(chart.labels, ("Ann", "Bob"))
        self.assertEqual(chart.series, (("Score", (9.0, 7.0)),))
        self.assertEqual(summary(chart), "Bar chart of Score, for 2 values of Name: Ann, Bob.")
        self.assertEqual(alternative_text(chart), f"Scores. Ann leads. {summary(chart)}")

    def test_mistakes_are_said(self) -> None:
        for text in (
            "type: cake",
            "type: function\nfunction: x\nx: 3 .. 1",
            "type: bar\n| a | b |\n| c | d |",
            "type: pie\n| a | b |\n| one | -1 |",
            "type: pie\n| a | b | c |\n| one | 1 | 2 |",
        ):
            with self.assertRaises(ChartError, msg=text):
                parse_chart(text)


class DrawingTests(unittest.TestCase):
    def test_svg_and_png(self) -> None:
        chart = parse_chart(SCORES)
        self.assertIn(b"<svg", draw(chart))
        self.assertTrue(draw(chart, "png").startswith(b"\x89PNG"))

    def test_html_has_the_picture_its_text_and_its_data(self) -> None:
        html = chart_html(SCORES)
        self.assertIn('<img src="data:image/svg+xml;base64,', html)
        self.assertIn("Ann leads.", html)
        self.assertIn("<table>", html)
        self.assertIn("chart-error", chart_html("type: cake"))


class ExportTests(unittest.TestCase):
    markdown = f"# Results\n\n```chart\n{SCORES}\n```\n"

    def test_pdf_has_a_figure_with_the_drawn_chart(self) -> None:
        images: dict[str, bytes] = {}
        source = typst_document([ExportPage("Results", self.markdown)], "Results", None, PdfOptions(), images)
        self.assertEqual(list(images), ["chart-1.svg"])
        self.assertIn('#figure(image("chart-1.svg", alt: "Scores. Ann leads.', source)

    def test_word_has_the_picture_described_and_captioned(self) -> None:
        data = docx_document([ExportPage("Results", self.markdown)], "Results", lambda _source: None, DocxOptions())
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertTrue(any(name.startswith("word/media/") for name in archive.namelist()))
            document = archive.read("word/document.xml").decode()
        self.assertIn('descr="Scores. Ann leads.', document)
        self.assertIn('w:val="Caption"', document)

    def test_braille_reads_the_chart_and_its_data(self) -> None:
        def letters(text: str) -> str:
            return "".join(chr(0x2800 + 1) if character != " " else "⠀" for character in text)

        lines = braille_lines(self.markdown, letters, letters, BrfLayout(cells_per_line=80, lines_per_page=25))
        self.assertGreaterEqual(len([line for line in lines if ascii_braille(line).strip()]), 5)


class NewChartTests(unittest.TestCase):
    def test_a_new_markdown_chart_reads_back(self) -> None:
        block = chart_block("line", "Growth", "", "", ("", ""), 2, 2)
        self.assertEqual(parse_chart(inside(block)).series, (("Series 1", (0.0, 0.0)), ("Series 2", (0.0, 0.0))))
        graph = chart_block("function", "", "", "x^2", ("-2", "2"), 0, 0)
        self.assertEqual(parse_chart(inside(graph)).functions, ("x^2",))

    def test_pgfplots_takes_degrees(self) -> None:
        self.assertEqual(pgf_expression("sin(x)"), "sin(deg(x))")
        self.assertEqual(pgf_expression("2x"), "(2*x)")
        self.assertEqual(calculator_expression("sin(deg(x))"), "sin(x)")
        with self.assertRaises(ChartError):
            pgf_expression("open(x)")

    def test_a_pgfplots_figure_is_read_back_as_a_chart(self) -> None:
        figure = pgfplots_figure("function", "Sine", "A wave.", "sin(x)", ("-3", "3"), 0, 0)
        self.assertIn("\\addplot {sin(deg(x))};", figure)
        chart = parse_chart(inside(pgfplots_chart(figure)))
        self.assertEqual((chart.functions, chart.x_range), (("sin(x)",), (-3.0, 3.0)))
        bars = parse_chart(inside(pgfplots_chart(pgfplots_figure("bar", "", "", "", ("", ""), 2, 1))))
        self.assertEqual((bars.kind, bars.labels), ("bar", ("Item1", "Item2")))
        pie = parse_chart(inside(pgfplots_chart(pgfplots_figure("pie", "", "", "", ("", ""), 2, 1))))
        self.assertEqual((pie.kind, pie.labels), ("pie", ("Item1", "Item2")))
        self.assertIsNone(pgfplots_chart("\\includegraphics{plot}"))

    def test_a_function_figure_needs_a_function(self) -> None:
        with self.assertRaises(ChartError):
            pgfplots_figure("function", "", "", "", ("-1", "1"), 0, 0)

    def test_a_tex_files_preview_draws_its_pgfplots(self) -> None:
        figure = pgfplots_figure("function", "Sine", "", "sin(x)", ("-3", "3"), 0, 0)
        markdown = tex_to_markdown(f"\\documentclass{{article}}\n\\begin{{document}}\n{figure}\n\\end{{document}}\n")
        self.assertIn("```chart\ntype: function\ntitle: Figure 1: Sine\nfunction: sin(x)", markdown)

    def test_inserting_puts_the_caret_in_the_data(self) -> None:
        block = chart_block("bar", "", "", "", ("", ""), 1, 1)
        edit = document_insert.chart("Text", 4, 4, block, "Item 1", False)
        self.assertTrue(edit.source[edit.caret :].startswith("Item 1"))
        self.assertTrue(edit.source.startswith("Text\n\n```chart\n"))


if __name__ == "__main__":
    unittest.main()
