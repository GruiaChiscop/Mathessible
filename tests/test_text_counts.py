import unittest

from mathessible.documents.html_export import markdown_parser
from mathessible.documents.text_counts import counts, current_section

MARKDOWN = (
    "---\nmath: latex\n---\n# Intro\n\nThe **quick** brown fox's tail, $E=mc^2$ and [a link](http://x.org).\n\n"
    "- one\n- [ ] two\n\n```\ncode here\n```\n## Results\nDone."
)


class CountTests(unittest.TestCase):
    def test_words_are_the_texts_an_equation_one(self) -> None:
        self.assertEqual(counts(MARKDOWN).words, 14)
        self.assertEqual(counts("one two").characters, 7)
        self.assertEqual(counts("one two").characters_without_spaces, 6)

    def test_a_tex_file_is_counted_from_its_body(self) -> None:
        tex = "\\documentclass{article}\\begin{document}\\section{Intro} Hello \\emph{world}, $x$.\\end{document}"
        self.assertEqual(counts(tex, tex=True).words, 4)

    def test_the_section_the_caret_is_in(self) -> None:
        self.assertEqual(current_section(MARKDOWN, len(MARKDOWN)), "Results")
        self.assertEqual(current_section(MARKDOWN, 30), "Intro")
        self.assertEqual(current_section("\\section{A} x \\subsection{B} y", 30, tex=True), "B")


class ListExportTests(unittest.TestCase):
    SOURCE = "- [ ] todo\n- [x] done\n\nRing\n: A set\n"

    def test_the_writers_read_tasks_and_definitions_as_what_they_know(self) -> None:
        tokens = markdown_parser().parse(self.SOURCE)
        texts = [child.content for token in tokens if token.type == "inline" for child in token.children]
        self.assertIn("☐", texts)
        self.assertIn("☑", texts)
        self.assertNotIn("dl_open", [token.type for token in tokens])
        self.assertIn("blockquote_open", [token.type for token in tokens])

    def test_html_keeps_them_native(self) -> None:
        html = markdown_parser(native_lists=True).render(self.SOURCE)
        self.assertIn('type="checkbox"', html)
        self.assertIn("<dl>", html)


if __name__ == "__main__":
    unittest.main()
