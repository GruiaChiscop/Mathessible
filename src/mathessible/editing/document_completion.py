"""Completion in the document's text (`\\fr` offers `\\frac`, `\\ref{` the labels), as in the equation editor.

It is Math AutoCorrect's companion outside math regions, so it works only
while that is on (Settings: "Use Math AutoCorrect in the document"). In a
UnicodeMath document it offers the control words, which convert as
AutoCorrect does. In a LaTeX document it offers what the equation editor's
LaTeX does (`completion.latex_completion_at`: the converter's words, the
document's own `\\newcommand`s, the environments after `\\begin{`); a .tex
file adds LaTeX's text commands and environments (`\\section`, `itemize`),
which have no math of their own. After `\\ref{`, `\\eqref{` and the like
it offers the document's labels, after `\\cite{` its bibliography's keys.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from mathessible.editing.completion import (
    Completion,
    argument_completion_at,
    completion_at,
    latex_completion_at,
)

# LaTeX's commands for a document's text, which the converter (math only) does not know.
TEX_TEXT_COMMANDS = (
    "documentclass",
    "usepackage",
    "title",
    "author",
    "date",
    "maketitle",
    "tableofcontents",
    "part",
    "chapter",
    "section",
    "subsection",
    "subsubsection",
    "paragraph",
    "subparagraph",
    "emph",
    "textbf",
    "textit",
    "texttt",
    "textsc",
    "underline",
    "footnote",
    "item",
    "label",
    "ref",
    "eqref",
    "pageref",
    "cite",
    "nocite",
    "caption",
    "includegraphics",
    "centering",
    "href",
    "url",
    "newcommand",
    "renewcommand",
    "DeclareMathOperator",
    "input",
    "include",
    "bibliography",
    "bibliographystyle",
    "bibitem",
    "newpage",
    "clearpage",
    "noindent",
    "hline",
    "begin",
    "end",
    "verb",
    "today",
    "LaTeX",
    "TeX",
)
TEX_ENVIRONMENTS = (
    "document",
    "abstract",
    "itemize",
    "enumerate",
    "description",
    "quote",
    "quotation",
    "center",
    "flushleft",
    "flushright",
    "figure",
    "table",
    "tabular",
    "verbatim",
    "minipage",
    "thebibliography",
    "equation",
    "equation*",
    "align",
    "align*",
    "gather",
    "gather*",
    "multline",
    "multline*",
    "theorem",
    "lemma",
    "proof",
    "definition",
)
REFERENCE_COMMANDS = ("ref", "eqref", "pageref", "autoref", "cref", "Cref")
CITATION_COMMANDS = ("cite", "citep", "citet", "parencite", "textcite", "autocite", "nocite")


def document_completion_at(
    source: str,
    caret: int,
    *,
    latex: bool,
    tex: bool,
    control_words: Mapping[str, str],
    latex_words: Mapping[str, str],
    environments: Sequence[str],
    labels: Sequence[str] = (),
    keys: Sequence[str] = (),
) -> Completion | None:
    """The suggestions for what is being typed before `caret` in the document's text, or None.

    `latex` is a LaTeX document (`tex`: a .tex file); `control_words` are UnicodeMath's, `latex_words` and
    `environments` LaTeX's (the document's own commands included), `labels` and `keys` its \\label names
    and bibliography keys.
    """
    if not latex:
        return completion_at(source, caret, control_words)
    names = dict.fromkeys(REFERENCE_COMMANDS, labels) | dict.fromkeys(CITATION_COMMANDS, keys)
    argument = argument_completion_at(source, caret, names)
    if argument is not None:
        return argument
    if tex:
        latex_words = {**dict.fromkeys(TEX_TEXT_COMMANDS, ""), **latex_words}
        environments = tuple(dict.fromkeys((*TEX_ENVIRONMENTS, *environments)))
    return latex_completion_at(source, caret, latex_words, environments)
