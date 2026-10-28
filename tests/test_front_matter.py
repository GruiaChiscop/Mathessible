import unittest

from mathessible.documents.front_matter import (
    LATEX,
    UNICODEMATH,
    HeaderFooter,
    body,
    equation_language,
    header_and_footer,
    with_equation_language,
    with_header_and_footer,
)


class FrontMatterTests(unittest.TestCase):
    def test_the_header_and_footer_are_read_and_the_body_follows(self) -> None:
        source = '---\nheader: Calculus notes\nfooter: "Chapter 2: limits"\ntitle: Kept\n---\n# Limits\n'
        self.assertEqual(header_and_footer(source), HeaderFooter("Calculus notes", "Chapter 2: limits"))
        self.assertEqual(body(source), "# Limits\n")

    def test_a_document_that_only_starts_with_a_rule_has_no_front_matter(self) -> None:
        for source in ("---\n\nText\n\n---\n", "---\n---\n", "---\nheader: never closed\n", "# Title\n"):
            with self.subTest(source=source):
                self.assertEqual(body(source), source)
                self.assertEqual(header_and_footer(source), HeaderFooter())

    def test_writing_keeps_the_other_keys_and_quotes_what_yaml_would_misread(self) -> None:
        source = "---\ntitle: Kept\nheader: Old\n---\nText\n"
        written = with_header_and_footer(source, "Notes: draft", "Page 'two'")
        self.assertEqual(written, "---\nheader: \"Notes: draft\"\nfooter: Page 'two'\ntitle: Kept\n---\nText\n")
        self.assertEqual(header_and_footer(written), HeaderFooter("Notes: draft", "Page 'two'"))
        self.assertEqual(with_header_and_footer("Text\n", "", ""), "Text\n")
        self.assertEqual(with_header_and_footer("---\nheader: A\n---\nText\n", "", ""), "Text\n")
        self.assertEqual(with_header_and_footer("Text\n", "#1", ""), '---\nheader: "#1"\n---\nText\n')

    def test_math_latex_marks_a_latex_document(self) -> None:
        self.assertEqual(equation_language("---\nmath: latex\n---\n$\\frac{a}{b}$\n"), LATEX)
        self.assertEqual(equation_language("---\nmath: LaTeX\nheader: H\n---\n"), LATEX)
        self.assertEqual(equation_language("$a/b$\n"), UNICODEMATH)
        self.assertEqual(equation_language("---\nmath: unicodemath\n---\n"), UNICODEMATH)
        marked = with_equation_language("---\nheader: H\n---\nText\n", LATEX)
        self.assertEqual(marked, "---\nmath: latex\nheader: H\n---\nText\n")
        self.assertEqual(with_equation_language(marked, UNICODEMATH), "---\nheader: H\n---\nText\n")
        self.assertEqual(with_equation_language("Text\n", UNICODEMATH), "Text\n")
        self.assertEqual(header_and_footer(with_header_and_footer(marked, "A", "")).header, "A")
        self.assertEqual(equation_language(with_header_and_footer(marked, "A", "")), LATEX)  # Kept.


if __name__ == "__main__":
    unittest.main()
