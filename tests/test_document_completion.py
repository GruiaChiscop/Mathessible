import unittest

from mathessible.documents.tex_math import NEW_DOCUMENT, NEW_DOCUMENT_CARET
from mathessible.editing.completion import accept_completion, argument_completion_at
from mathessible.editing.document_completion import accept_document_completion, document_completion_at

CONTROL_WORDS = {"alpha": "α", "aleph": "ℵ", "frac": "", "sec": ""}
LATEX_WORDS = {"frac": "", "sec": "", "sqrt": ""}
ENVIRONMENTS = ("pmatrix", "cases")


def complete(source: str, latex: bool = True, tex: bool = False, **names: tuple[str, ...]):
    return document_completion_at(
        source,
        len(source),
        latex=latex,
        tex=tex,
        control_words=CONTROL_WORDS,
        latex_words=LATEX_WORDS,
        environments=ENVIRONMENTS,
        **names,
    )


def words(completion) -> list[str]:
    return [suggestion.word for suggestion in completion.suggestions]


class DocumentCompletionTests(unittest.TestCase):
    def test_a_unicode_math_document_offers_control_words_that_convert(self) -> None:
        completion = complete("Let \\al", latex=False)
        self.assertEqual(words(completion), ["aleph", "alpha"])
        self.assertEqual(accept_completion("Let \\al", completion.moved(1), convert=True).source, "Let α")

    def test_a_latex_document_offers_latex_words_kept_as_words(self) -> None:
        completion = complete("$\\fr")
        self.assertEqual(words(completion), ["frac"])
        self.assertEqual(accept_completion("$\\fr", completion, convert=False).source, "$\\frac")

    def test_a_tex_file_adds_text_commands_and_environments(self) -> None:
        self.assertIn("section", words(complete("\\sec", tex=True)))
        self.assertIsNone(complete("\\sect"))  # A Markdown document's text is no LaTeX.
        completion = complete("\\begin{ite", tex=True)
        self.assertEqual(words(completion), ["itemize"])
        self.assertEqual(
            accept_completion("\\begin{ite", completion, convert=False).source, "\\begin{itemize}\\end{itemize}"
        )

    def test_a_tex_files_preamble_and_document_environment(self) -> None:
        self.assertEqual(words(complete("\\doc", tex=True)), ["documentclass"])
        self.assertEqual(words(complete("\\documentclass{ar", tex=True)), ["article"])
        self.assertEqual(words(complete("\\usepackage[utf8]{inp", tex=True)), ["inputenc"])
        self.assertIn("graphicx", words(complete("\\usepackage{amsmath, gra", tex=True)))
        completion = complete("\\begin{doc", tex=True)
        edit = accept_document_completion("\\begin{doc", completion, convert=False, tex=True)
        self.assertEqual((edit.source, edit.caret), ("\\begin{document}\n\n\\end{document}", 17))
        matrix = complete("\\begin{pm", tex=True)
        self.assertEqual(
            accept_document_completion("\\begin{pm", matrix, False, True).source, "\\begin{pmatrix}\\end{pmatrix}"
        )

    def test_a_new_latex_document_has_its_caret_in_the_body(self) -> None:
        self.assertTrue(NEW_DOCUMENT.startswith("\\documentclass{article}"))
        self.assertEqual(NEW_DOCUMENT[NEW_DOCUMENT_CARET:], "\n\\end{document}\n")

    def test_labels_after_ref_and_keys_after_cite(self) -> None:
        labels, keys = ("eq:energy", "eq:e2", "fig:a"), ("knuth84", "lamport86")
        self.assertEqual(words(complete("see \\eqref{eq:", labels=labels, keys=keys)), ["eq:e2", "eq:energy"])
        completion = complete("\\cite{knuth84, la", labels=labels, keys=keys)
        self.assertEqual(
            accept_completion("\\cite{knuth84, la", completion, convert=False).source, "\\cite{knuth84, lamport86}"
        )

    def test_a_name_in_the_middle_of_a_list_gets_no_brace(self) -> None:
        source = "\\cite{kn, lamport86}"
        completion = argument_completion_at(source, 8, {"cite": ("knuth84",)})
        edit = accept_completion(source, completion, convert=False)
        self.assertEqual((edit.source, edit.caret), ("\\cite{knuth84, lamport86}", 13))


if __name__ == "__main__":
    unittest.main()
