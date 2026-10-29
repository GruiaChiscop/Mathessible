import tempfile
import unittest
from pathlib import Path

from mathessible.documents.bibtex import document_bibliography, entry_text, parse_bib
from mathessible.documents.front_matter import body
from mathessible.documents.tex_markdown import tex_to_markdown

BIB = r"""@string{tug = "TUGboat"}
@book{knuth84,
  author = {Knuth, Donald E.},
  title = {The {\TeX}book},
  publisher = {Addison-Wesley},
  year = 1984,
}
@article{lamport86,
  author = "Leslie Lamport and Anne Other",
  title = {On \LaTeX},
  journal = tug,
  volume = {7},
  pages = {1--10},
  year = {1986}
}
@comment{ignored}
@inproceedings{aaron,
  author = {Aaron, Zed},
  title = {First},
  booktitle = {Proc. of Things},
  year = 2000
}
@misc{uncited, title = {Never cited}}
"""


def document(style: str) -> str:
    return (
        "\\documentclass{article}\\begin{document}\nKnuth \\cite{knuth84}, then \\cite{lamport86, aaron}.\n"
        f"\\bibliographystyle{{{style}}}\n\\bibliography{{refs}}\n\\end{{document}}\n"
    )


class BibtexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        Path(self.folder.name, "refs.bib").write_text(BIB, encoding="utf-8")

    def test_entries_strings_and_comments(self) -> None:
        entries = parse_bib(BIB)
        self.assertEqual(sorted(entries), ["aaron", "knuth84", "lamport86", "uncited"])
        self.assertEqual(entries["lamport86"].fields["journal"], "TUGboat")
        self.assertEqual(entries["knuth84"].fields["year"], "1984")
        self.assertEqual(
            entry_text(entries["knuth84"]), "Donald E. Knuth. \\emph{The {\\TeX}book}. Addison-Wesley. 1984."
        )

    def test_plain_sorts_by_author_and_unsrt_keeps_the_citation_order(self) -> None:
        plain = document_bibliography(document("plain"), Path(self.folder.name))
        unsrt = document_bibliography(document("unsrt"), Path(self.folder.name))
        self.assertEqual([entry.key for entry in plain.entries], ["aaron", "knuth84", "lamport86"])
        self.assertEqual([entry.key for entry in unsrt.entries], ["knuth84", "lamport86", "aaron"])

    def test_citations_and_references_in_the_preview(self) -> None:
        text = body(tex_to_markdown(document("plain"), Path(self.folder.name)))
        self.assertIn("Knuth [2], then [3, 1].", text)
        self.assertIn("## References\n\n[1] Zed Aaron. First. *Proc. of Things*. 2000.", text)
        self.assertNotIn("Never cited", text)

    def test_without_the_file_the_keys_are_shown(self) -> None:
        self.assertIn("[knuth84]", body(tex_to_markdown(document("plain"), Path(self.folder.name, "elsewhere"))))


if __name__ == "__main__":
    unittest.main()
