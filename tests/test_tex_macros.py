import unittest

from converter_harness import convert_all, has_error, needs_node
from mathessible.documents.tex_macros import (
    LatexMacro,
    document_macros,
    expand_macros,
    expand_markdown_macros,
    find_macros,
    fold_macros,
    macro_sample,
)
from mathessible.documents.tex_markdown import tex_to_markdown
from mathessible.mathcat.latex import equation_latex

needs_mathcat = unittest.skipUnless(
    __import__("importlib").util.find_spec("mathessible_mathcat"), "needs the native MathCAT"
)

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
        self.assertEqual(macros["tr"], LatexMacro(0, None, "tr", operator=True))

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

    def test_an_operator_is_applied_as_a_function_after_its_scripts(self) -> None:
        self.assertEqual(self.expand("\\tr A"), "\\mathrm{tr}\u2061 A")
        macros = find_macros("\\DeclareMathOperator*{\\argmax}{arg\\,max}")
        self.assertEqual(expand_macros("\\argmax\\limits_{x} f", macros), "\\mathrm{argmax}_{x}\u2061 f")
        self.assertEqual(expand_macros("\\operatorname{rank} M", {}), "\\mathrm{rank}\u2061 M")

    def test_other_commands_are_left(self) -> None:
        self.assertEqual(self.expand("\\frac{a}{b} \\{x\\}"), "\\frac{a}{b} \\{x\\}")


class FoldMacrosTests(unittest.TestCase):
    def setUp(self) -> None:
        self.macros = document_macros(PREAMBLE, tex=True)
        # As MathCAT writes the samples' expansions.
        self.written = {"R": "\\mathbb R", "vec": "\\mathbf Q", "e": "\\epsilon", "inner": "\\langle Q, W \\rangle"}

    def test_samples(self) -> None:
        self.assertEqual(macro_sample("vec", self.macros["vec"]), "\\vec{Q}")
        self.assertEqual(macro_sample("pd", self.macros["pd"]), "\\pd[Q]{W}{K}")
        self.assertIsNone(macro_sample("tr", self.macros["tr"]))

    def test_bodies_become_their_commands_again(self) -> None:
        folded = fold_macros("\\mathbf v \\in \\mathbb R^n", self.macros, self.written)
        self.assertEqual(folded, "\\vec{v} \\in \\R^n")
        self.assertEqual(
            fold_macros("\\langle u, \\mathbf{xy} \\rangle", self.macros, self.written), "\\inner{u}{\\vec{xy}}"
        )

    def test_an_operator_and_a_command_before_a_letter(self) -> None:
        self.assertEqual(fold_macros("\\operatorname{tr}A = \\epsilon x", self.macros, self.written), "\\tr A = \\e x")

    def test_a_control_word_is_not_folded_inside_a_longer_one(self) -> None:
        self.assertEqual(fold_macros("\\epsilonx", self.macros, self.written), "\\epsilonx")


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


@needs_node
@needs_mathcat
class RoundTripTests(unittest.TestCase):
    def test_an_equation_written_again_by_mathcat_keeps_the_documents_commands(self) -> None:
        macros = document_macros(PREAMBLE + "\\newcommand{\\norm}[1]{\\left\\| #1 \\right\\|}", tex=True)
        samples = {name: macro_sample(name, macro) for name, macro in macros.items()}
        samples = {name: sample for name, sample in samples.items() if sample is not None and name != "again"}
        built = convert_all([expand_macros(sample, macros) for sample in samples.values()], latex=True)
        written = dict(zip(samples, equation_latex([result["mathml"] for result in built]), strict=True))
        equations = ["\\vec{v} \\in \\R^n", "\\pd{f}{x} + \\tr A = 0", "\\inner{u}{\\vec{v}} = \\e x", "\\norm{x}"]
        mathml = [result["mathml"] for result in convert_all([expand_macros(e, macros) for e in equations], latex=True)]
        folded = [fold_macros(latex, macros, written) for latex in equation_latex(mathml)]
        self.assertEqual(
            folded, ["\\vec{v} \\in \\R^n", "\\pd{f}{x} + \\tr A = 0", "\\inner{u}{\\vec{v}} = \\e x", "\\norm{x}"]
        )
        rebuilt = convert_all([expand_macros(latex, macros) for latex in folded], latex=True)
        self.assertEqual([result["mathml"] for result in rebuilt], mathml)


if __name__ == "__main__":
    unittest.main()
