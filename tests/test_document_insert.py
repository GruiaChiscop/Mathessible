import unittest

from mathessible.documents.tex_math import NEW_DOCUMENT, NEW_DOCUMENT_CARET
from mathessible.editing import document_insert as insert


def parts(edit) -> tuple[str, str]:
    """The text before the caret and after it."""
    return edit.source[: edit.caret], edit.source[edit.caret :]


class MarkdownInsertTests(unittest.TestCase):
    def test_a_heading_replaces_the_lines_own(self) -> None:
        self.assertEqual(parts(insert.heading("Intro\ntext", 2, 2, 2, False)), ("## Intro", "\ntext"))
        self.assertEqual(insert.heading("## Old\n", 3, 3, 3, False).source, "### Old\n")

    def test_lists_and_quotations_mark_the_selected_lines(self) -> None:
        self.assertEqual(insert.list_items("a\nb\nc", 0, 5, False, False).source, "- a\n- b\n- c")
        self.assertEqual(insert.list_items("- a\n- b", 0, 7, True, False).source, "1. a\n2. b")
        self.assertEqual(insert.quotation("one\n\ntwo", 0, 8, False).source, "> one\n>\n> two")

    def test_blocks_go_on_lines_of_their_own(self) -> None:
        self.assertEqual(parts(insert.code_block("text\n", 5, 5, False)), ("text\n\n```\n", "\n```\n"))
        self.assertEqual(insert.horizontal_rule("para", 4, 4, False).source, "para\n\n---\n")
        self.assertEqual(insert.image("", 0, 0, "plot.png", "A plot", False).source, "![A plot](plot.png)\n")

    def test_a_link_is_the_selection(self) -> None:
        self.assertEqual(
            insert.link("see here", 4, 8, "here", "https://a.org/x y", False).source, "see [here](https://a.org/x%20y)"
        )

    def test_a_table_to_fill_in(self) -> None:
        edit = insert.table("Text\n", 5, 5, 3, 2, True, False)
        self.assertEqual(edit.source, "Text\n\n|   |   |\n| --- | --- |\n|   |   |\n|   |   |\n")
        self.assertEqual(edit.source[edit.caret - 2 : edit.caret], "| ")


class ListsAndFormatTests(unittest.TestCase):
    def test_task_and_definition_lists(self) -> None:
        self.assertEqual(insert.task_list("buy milk\n- [x] call", 0, 20, False).source, "- [ ] buy milk\n- [x] call")
        self.assertEqual(parts(insert.definition_list("Ring\nField", 0, 10, False)), ("Ring\n: ", "\n\nField\n: "))
        self.assertEqual(parts(insert.definition_list("Ring", 0, 0, True))[0], "\\begin{description}\n  \\item[Ring] ")
        tasks = insert.task_list(NEW_DOCUMENT, NEW_DOCUMENT_CARET, NEW_DOCUMENT_CARET, True).source
        self.assertIn("\\usepackage{amssymb}", tasks)
        self.assertIn("\\item[$\\square$]", tasks)

    def test_formatting_marks_and_unmarks(self) -> None:
        self.assertEqual(insert.formatted("a word b", 2, 6, "bold", False).source, "a **word** b")
        self.assertEqual(insert.formatted("a **word** b", 4, 8, "bold", False).source, "a word b")
        self.assertEqual(insert.formatted("a **word** b", 2, 10, "bold", False).source, "a word b")
        self.assertEqual(parts(insert.formatted("a  b", 2, 2, "italic", False)), ("a *", "* b"))
        self.assertEqual(insert.formatted("a word b", 2, 6, "italic", True).source, "a \\emph{word} b")
        self.assertEqual(insert.formatted("a \\emph{word} b", 8, 12, "italic", True).source, "a word b")
        struck = insert.formatted(NEW_DOCUMENT, NEW_DOCUMENT_CARET, NEW_DOCUMENT_CARET, "strikethrough", True)
        self.assertIn("\\usepackage[normalem]{ulem}", struck.source)


class TexInsertTests(unittest.TestCase):
    def test_sections_lists_and_quotations(self) -> None:
        self.assertEqual(insert.heading("Intro\n", 2, 2, 1, True).source, "\\section{Intro}\n")
        self.assertEqual(parts(insert.heading("", 0, 0, 2, True)), ("\\subsection{", "}"))
        self.assertEqual(
            insert.list_items("a\nb", 0, 3, True, True).source,
            "\\begin{enumerate}\n  \\item a\n  \\item b\n\\end{enumerate}\n",
        )
        self.assertIn("\\begin{quote}\nwords\n\\end{quote}", insert.quotation("words", 0, 5, True).source)

    def test_a_link_and_an_image_load_their_package(self) -> None:
        edit = insert.with_package(
            insert.link(NEW_DOCUMENT, NEW_DOCUMENT_CARET, NEW_DOCUMENT_CARET, "x", "https://a.org", True), "hyperref"
        )
        self.assertIn("\\usepackage{amsmath}\n\\usepackage{hyperref}\n", edit.source)
        self.assertTrue(edit.source[: edit.caret].endswith("\\href{https://a.org}{x}"))
        self.assertEqual(insert.with_package(edit, "hyperref").source, edit.source)  # Loaded once.
        figure = insert.image("", 0, 0, "plot.png", "A plot", True).source
        self.assertIn("\\includegraphics[width=\\linewidth]{plot.png}\n  \\caption{A plot}", figure)

    def test_a_tabular_to_fill_in(self) -> None:
        source = insert.table("", 0, 0, 2, 3, True, True).source
        self.assertTrue(source.startswith("\\begin{tabular}{lll}\n\\hline\n"))
        self.assertEqual(source.count("\\\\"), 2)
        self.assertTrue(source.rstrip().endswith("\\end{tabular}"))


if __name__ == "__main__":
    unittest.main()
