import tempfile
import unittest
from pathlib import Path

from mathessible.documents.front_matter import LATEX, body, equation_language
from mathessible.documents.markdown_math import find_math_zones
from mathessible.documents.tex_markdown import tex_to_markdown
from mathessible.documents.tex_numbers import tex_numbers

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
        self.assertIn("## 1 Intro", self.body)
        self.assertIn("Some **bold** and *italic* text, 50% off – see [k].[^1]", self.body)

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


NUMBERED = r"""\begin{document}
\section{Intro}\label{s:intro}
\subsection{More}\label{s:more}
\section*{Unnumbered}
See \ref{s:two}, \eqref{eq:e}, \ref{eq:c}, Figure \ref{fig:a}, Table \ref{tab:a}, \cite{knuth,lamport},
\cite[p.~5]{knuth} and \ref{nowhere}.
\begin{equation} E=mc^2 \label{eq:e} \end{equation}
\begin{align} a&=b \\ c&=d \nonumber \\ e&=f \label{eq:c} \end{align}
\begin{figure}[h]\centering\includegraphics[width=5cm]{plot}\caption{A plot of $f$}\label{fig:a}\end{figure}
\begin{table}\caption{Results}\label{tab:a}
\begin{tabular}[t]{l|cr} \hline Name & $x$ & Score \\ \hline Ann & 1 & 9\% \\ \multicolumn{2}{c}{Both} & 10 \\ \hline
\end{tabular}\end{table}
\section{Two}\label{s:two}
\begin{thebibliography}{9}\bibitem{knuth} D. Knuth. \bibitem{lamport} L. Lamport.\end{thebibliography}
\end{document}
"""


class NumberedTexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        Path(self.folder.name, "plot.png").write_bytes(b"")
        self.body = body(tex_to_markdown(NUMBERED, Path(self.folder.name)))

    def test_numbers_as_latex_gives_them(self) -> None:
        numbers = tex_numbers(NUMBERED)
        self.assertEqual(
            numbers.labels,
            {"s:intro": "1", "s:more": "1.1", "eq:e": "1", "eq:c": "3", "fig:a": "1", "tab:a": "1", "s:two": "2"},
        )
        self.assertEqual(numbers.citations, {"knuth": 1, "lamport": 2})

    def test_references_citations_and_headings(self) -> None:
        self.assertIn("See 2, (1), 3, Figure 1, Table 1, [1, 2],\n[1, p.\u00a05] and ??.", self.body)
        self.assertIn("## 1 Intro", self.body)
        self.assertIn("### 1.1 More", self.body)
        self.assertIn("## Unnumbered", self.body)
        self.assertIn("## References\n\n[1] D. Knuth.", self.body)

    def test_an_equations_number_is_its_tag(self) -> None:
        self.assertIn("\\tag{1}$$", self.body)

    def test_a_figure_and_a_table(self) -> None:
        self.assertIn("![A plot of f](plot.png)\n\nFigure 1: A plot of $f$", self.body)
        self.assertIn(
            "Table 1: Results\n\n| Name | $x$ | Score |\n| --- | --- | --- |\n| Ann | 1 | 9% |\n| Both |  | 10 |",
            self.body,
        )


if __name__ == "__main__":
    unittest.main()
