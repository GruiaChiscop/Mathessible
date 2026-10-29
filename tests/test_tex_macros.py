import unittest

from converter_harness import convert_all, has_error, needs_node
from mathessible.documents.tex_macros import (
    LatexMacro,
    document_macros,
    expand_macros,
    expand_markdown_macros,
    find_macros,
)
from mathessible.documents.tex_markdown import tex_to_markdown

PREAMBLE = r"""\documentclass{article}
\newcommand{\R}{\mathbb{R}}
\newcommand\N{\mathbb{N}}
\renewcommand{\vec}[1]{\mathbf{#1}}
\newcommand{\pd}[3][]{\frac{\partial^{#1} #2}{\partial #3^{#1}}}
\def\e{\epsilon}
\def\inner#1#2{\langle #1, #2\rangle}
\DeclareMathOperator{\tr}{tr}
% \newcommand{\R}{\text{commented out}}
\newcommand{\again}{\again}
"""


class FindMacrosTests(unittest.TestCase):
    def test_every_kind_of_definition(self) -> None:
        macros = document_macros(PREAMBLE, tex=True)
        self.assertEqual(macros["R"], LatexMacro(0, None, "\\mathbb{R}"))
        self.assertEqual(macros["N"], LatexMacro(0, None, "\\mathbb{N}"))
        self.assertEqual(macros["vec"], LatexMacro(1, None, "\\mathbf{#1}"))
        self.assertEqual(macros["pd"].parameters, 3)
        self.assertEqual(macros["pd"].default, "")
        self.assertEqual(macros["inner"], LatexMacro(2, None, "\\langle #1, #2\\rangle"))
        self.assertEqual(macros["tr"], LatexMacro(0, None, "\\mathrm{tr}"))

    def test_a_later_definition_wins(self) -> None:
        self.assertEqual(find_macros("\\def\\a{1}\\renewcommand{\\a}{2}")["a"].body, "2")


class ExpandMacrosTests(unittest.TestCase):
    def setUp(self) -> None:
        self.macros = document_macros(PREAMBLE, tex=True)

    def expand(self, latex: str) -> str:
        return expand_macros(latex, self.macros)

    def test_commands_and_their_arguments(self) -> None:
        self.assertEqual(self.expand("x\\in\\R^n"), "x\\in\\mathbb{R}^n")
        self.assertEqual(self.expand("\\vec{v}+\\vec w"), "\\mathbf{v}+\\mathbf{w}")
        self.assertEqual(self.expand("\\inner{u}{v}"), "\\langle u, v\\rangle")
        self.assertEqual(self.expand("\\pd[2]{f}{x}"), "\\frac{\\partial^{2} f}{\\partial x^{2}}")

    def test_a_control_word_is_not_run_into_a_letter(self) -> None:
        self.assertEqual(self.expand("\\e x"), "\\epsilon x")
        self.assertEqual(self.expand("\\R x"), "\\mathbb{R}x")

    def test_a_command_that_expands_into_itself_stops(self) -> None:
        self.assertEqual(self.expand("\\again"), "\\again")

    def test_an_equations_own_definition(self) -> None:
        self.assertEqual(expand_macros("\\newcommand{\\h}{h} \\h+1", {}), " h+1")

    def test_other_commands_are_left(self) -> None:
        self.assertEqual(self.expand("\\frac{a}{b} \\{x\\}"), "\\frac{a}{b} \\{x\\}")


class DocumentTests(unittest.TestCase):
    def test_a_tex_files_preview_has_them_expanded(self) -> None:
        markdown = tex_to_markdown(PREAMBLE + "\\begin{document}\nLet $x\\in\\R$.\n\\end{document}\n")
        self.assertIn("$x\\in\\mathbb{R}$", markdown)

    def test_a_markdown_documents_equations(self) -> None:
        source = "---\nmath: latex\n---\n$\\newcommand{\\R}{\\mathbb{R}}$ Let $x\\in\\R$."
        self.assertEqual(expand_markdown_macros(source), "---\nmath: latex\n---\n$$ Let $x\\in\\mathbb{R}$.")


@needs_node
class ConverterTests(unittest.TestCase):
    def test_expanded_equations_build(self) -> None:
        macros = document_macros(PREAMBLE, tex=True)
        equations = ["x\\in\\R^n", "\\vec{v}", "\\inner{u}{v}", "\\pd{f}{x}", "\\tr A"]
        for result in convert_all([expand_macros(equation, macros) for equation in equations], latex=True):
            self.assertFalse(has_error(result["mathml"]))
            self.assertNotIn("\\", result["mathml"])


if __name__ == "__main__":
    unittest.main()
