import unittest

from mathessible.documents.front_matter import LATEX, body, equation_language
from mathessible.documents.markdown_math import find_math_zones
from mathessible.documents.tex_markdown import tex_to_markdown

DOCUMENT = r"""\documentclass{article}
\usepackage{amsmath} % a comment with $math$
\title{Notes on \emph{limits}}
\author{A. Student}
\begin{document}
\maketitle
\section{Intro}\label{s:intro}
Some \textbf{bold} and \textit{italic} text, 50\% off -- see \cite{k}.\footnote{A note costing \$5.}
\begin{itemize}
  \item First, $x_1$
  \item Second
  \begin{enumerate}
    \item nested
  \end{enumerate}
\end{itemize}
Use \verb|a_b| or \href{https://example.org}{a link}.
\begin{verbatim}
raw *text* $not math$
\end{verbatim}
\unknowncommand{kept text} and a_b*star.
\begin{align}
  f(x) &= (x+1)^2 \\
       &= x^2+2x+1
\end{align}
\end{document}
"""


class TexToMarkdownTests(unittest.TestCase):
    def setUp(self) -> None:
        self.markdown = tex_to_markdown(DOCUMENT)
        self.body = body(self.markdown)

    def test_its_equations_are_latex(self) -> None:
        self.assertEqual(equation_language(self.markdown), LATEX)
        equations = [zone.content(self.body) for zone in find_math_zones(self.body)]
        self.assertEqual(equations[0], "x_1")
        self.assertEqual(equations[1], "\\begin{aligned}f(x) &= (x+1)^2 \\\\\n       &= x^2+2x+1\\end{aligned}")

    def test_title_sections_and_styles(self) -> None:
        self.assertIn("# Notes on *limits*\n\nA. Student", self.body)
        self.assertIn("## Intro", self.body)
        self.assertIn("Some **bold** and *italic* text, 50% off – see k.[^1]", self.body)

    def test_footnotes_go_at_the_end(self) -> None:
        self.assertTrue(self.body.rstrip().endswith("[^1]: A note costing \\$5."))

    def test_lists(self) -> None:
        self.assertIn("\n\n- First, $x_1$\n- Second\n  1. nested\n\nUse", self.body)

    def test_verbatim_links_and_unknown_commands(self) -> None:
        self.assertIn("Use `a_b` or [a link](https://example.org).", self.body)
        self.assertIn("```\nraw *text* $not math$\n```", self.body)
        self.assertIn("kept text and a\\_b\\*star.", self.body)

    def test_the_preamble_and_comments_are_not_text(self) -> None:
        self.assertNotIn("amsmath", self.body)
        self.assertNotIn("comment", self.body)
        self.assertNotIn("s:intro", self.body)

    def test_a_file_without_a_document_environment(self) -> None:
        self.assertEqual(body(tex_to_markdown("Just $x$ here.")), "Just $x$ here.\n")


if __name__ == "__main__":
    unittest.main()
