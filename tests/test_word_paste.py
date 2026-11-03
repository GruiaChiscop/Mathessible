from __future__ import annotations

import unittest

from mathessible.documents.omml_mathml import mathml_from_omml
from mathessible.documents.paste_plan import PasteRoute, paste_route
from mathessible.documents.pasted_html import markdown_from_html
from mathessible.documents.word_html import plain_word_html, with_word_parts


def _item(text: str, list_id: str, level: int, marker: str) -> str:
    """A list paragraph as Word writes it to the clipboard."""
    return (
        f"<p class=MsoListParagraphCxSpMiddle style='text-indent:-.25in;mso-list:{list_id} level{level} lfo1'>"
        f"<![if !supportLists]><span style='mso-list:Ignore'>{marker}<span style='font:7.0pt \"Times New Roman\"'>"
        f"&nbsp;&nbsp;&nbsp; </span></span><![endif]><span lang=EN-GB>{text}<o:p></o:p></span></p>\n"
    )


# A fragment of Word's clipboard HTML (Word for Windows): lists, a footnote, an equation and a table.
WORD = (
    _item("First", "l1", 1, "-")
    + _item("Second", "l1", 1, "-")
    + "<p class=MsoNormal><o:p>&nbsp;</o:p></p>\n"
    + _item("One", "l2", 1, "1.")
    + _item("Inner", "l2", 2, "a.")
    + _item("Deeper", "l2", 3, "i.")
    + _item("Two", "l2", 1, "2.")
    + _item("Three", "l3", 1, "3)")
    + '<p class=MsoNormal>Some text <a style=\'mso-footnote-id:ftn1\' href="#_ftn1" name="_ftnref1" title="">'
    "<span class=MsoFootnoteReference><span style='mso-special-character:footnote'><![if !supportFootnotes]>"
    "<span class=MsoFootnoteReference>[1]</span><![endif]></span></span></a> and more.<o:p></o:p></p>\n"
    "<p class=MsoNormal><!--[if gte msEquation 12]><m:oMathPara><m:oMath><m:sSup><m:sSupPr><span"
    " style='font-family:\"Cambria Math\"'><m:ctrlPr></m:ctrlPr></span></m:sSupPr><m:e><i><m:r>x</m:r></i></m:e>"
    "<m:sup><i><m:r>2</m:r></i></m:sup></m:sSup><i><m:r>+1</m:r></i></m:oMath></m:oMathPara><![endif]-->"
    '<![if !msEquation]><span><!--[if gte vml 1]><v:shape><v:imagedata src="file:///x.png"/></v:shape>'
    '<![endif]--><![if !vml]><img width=59 height=22 src="file:///x.png"><![endif]></span><![endif]><o:p></o:p></p>\n'
    "<table class=MsoTableGrid><tr><td><p class=MsoNormal>Cell<o:p></o:p></p></td><td>"
    + _item("Listed", "l1", 1, "-")
    + "</td></tr></table>\n"
    "<div style='mso-element:footnote-list'><![if !supportFootnotes]><br clear=all><hr align=left size=1 width=\"33%\">"
    "<![endif]><div style='mso-element:footnote' id=ftn1><p class=MsoFootnoteText><a style='mso-footnote-id:ftn1'"
    ' href="#_ftnref1" name="_ftn1" title=""><span class=MsoFootnoteReference>[1]</span></a> The note.<o:p></o:p>'
    "</p></div></div>"
)


def _pasted(html: str, source: str = "", equation=lambda found: "x^2+1") -> str | None:
    plain, parts = plain_word_html(html)
    markdown = markdown_from_html(plain)
    assert markdown is not None
    return with_word_parts(markdown, parts, source, equation, lambda note: markdown_from_html(note) or "")


class WordHtmlTests(unittest.TestCase):
    def test_lists_footnotes_and_equations(self) -> None:
        pasted = _pasted(WORD)
        self.assertIn("- First\n- Second", pasted)
        # One list each Word list (l2, l3), nested by level, numbered or bulleted by its marker.
        self.assertIn("1. One\n\n   1. Inner\n\n      1. Deeper\n2. Two", pasted)
        # Word's "3)" list starts at 3 (next to the list before, Markdown joins the two).
        self.assertIn("3. Three", pasted)
        self.assertIn("Some text [^1] and more.", pasted)  # The space Word has before the reference.
        self.assertIn("$$x^2+1$$", pasted)
        self.assertTrue(pasted.endswith("[^1]: The note."))
        self.assertNotIn("x.png", pasted)  # The equation's picture for other readers is left out.
        self.assertIn("| Cell | - Listed |", pasted)

    def test_footnote_labels_are_free_in_the_document(self) -> None:
        pasted = _pasted(WORD, source="Before[^1] and[^2].\n\n[^1]: One.\n\n[^2]: Two.")
        self.assertIn("Some text [^3] and more.", pasted)
        self.assertTrue(pasted.endswith("[^3]: The note."))

    def test_an_equation_that_cannot_be_converted_gives_the_clipboards_text(self) -> None:
        self.assertIsNone(_pasted(WORD, equation=lambda found: None))

    def test_word_html_goes_by_the_local_conversion_or_pandoc(self) -> None:
        # Before, its equation made the whole paste the clipboard's text.
        self.assertEqual(paste_route(WORD, True), PasteRoute.PLAIN)
        plain, _ = plain_word_html(WORD)
        self.assertEqual(paste_route(plain, False), PasteRoute.NEEDS_PANDOC)  # Nested lists.

    def test_other_html_is_left_as_it_is(self) -> None:
        html = "<p>Plain <b>text</b></p>"
        self.assertEqual(plain_word_html(html), (html, plain_word_html(html)[1]))
        self.assertEqual(plain_word_html(html)[1].equations, ())


def _math(omml: str) -> str:
    return mathml_from_omml(f"<m:oMath>{omml}</m:oMath>")


def _r(text: str) -> str:
    return f"<m:r><m:t>{text}</m:t></m:r>"


class OmmlTests(unittest.TestCase):
    def test_runs(self) -> None:
        self.assertEqual(
            _math(_r("2x+10.5")),
            '<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mn>2</mn><mi>x</mi><mo>+</mo><mn>10.5</mn></mrow>'
            "</math>",
        )
        upright = '<m:r><m:rPr><m:sty m:val="p"/></m:rPr><m:t>dx</m:t></m:r>'
        self.assertIn("<mi>dx</mi>", _math(upright))

    def test_fractions_and_roots(self) -> None:
        fraction = f"<m:f><m:num>{_r('a')}</m:num><m:den>{_r('b')}</m:den></m:f>"
        self.assertIn("<mfrac><mrow><mi>a</mi></mrow><mrow><mi>b</mi></mrow></mfrac>", _math(fraction))
        linear = f'<m:f><m:fPr><m:type m:val="lin"/></m:fPr><m:num>{_r("a")}</m:num><m:den>{_r("b")}</m:den></m:f>'
        self.assertIn("<mo>/</mo>", _math(linear))
        square = f'<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/><m:e>{_r("x")}</m:e></m:rad>'
        self.assertIn("<msqrt>", _math(square))
        cube = f"<m:rad><m:deg>{_r('3')}</m:deg><m:e>{_r('x')}</m:e></m:rad>"
        self.assertIn("<mroot><mrow><mi>x</mi></mrow><mrow><mn>3</mn></mrow></mroot>", _math(cube))

    def test_scripts_and_large_operators(self) -> None:
        scripts = f"<m:sSubSup><m:e>{_r('x')}</m:e><m:sub>{_r('i')}</m:sub><m:sup>{_r('2')}</m:sup></m:sSubSup>"
        self.assertIn("<msubsup>", _math(scripts))
        total = (
            '<m:nary><m:naryPr><m:chr m:val="∑"/><m:limLoc m:val="undOvr"/></m:naryPr>'
            f"<m:sub>{_r('i=1')}</m:sub><m:sup>{_r('n')}</m:sup><m:e>{_r('i')}</m:e></m:nary>"
        )
        self.assertIn('<munderover><mo largeop="true">∑</mo>', _math(total))
        integral = f"<m:nary><m:sub>{_r('0')}</m:sub><m:sup>{_r('1')}</m:sup><m:e>{_r('f')}</m:e></m:nary>"
        self.assertIn('<msubsup><mo largeop="true">∫</mo>', _math(integral))

    def test_functions_delimiters_and_accents(self) -> None:
        sine = f"<m:func><m:fName>{_r('sin')}</m:fName><m:e>{_r('x')}</m:e></m:func>"
        self.assertIn("<mrow><mi>sin</mi></mrow><mo>⁡</mo>", _math(sine))
        brackets = f'<m:d><m:dPr><m:begChr m:val="["/><m:endChr m:val="]"/></m:dPr><m:e>{_r("a")}</m:e></m:d>'
        self.assertIn('<mo fence="true">[</mo><mrow><mi>a</mi></mrow><mo fence="true">]</mo>', _math(brackets))
        hat = f"<m:acc><m:e>{_r('x')}</m:e></m:acc>"
        self.assertIn('<mover accent="true"><mrow><mi>x</mi></mrow><mo>̂</mo></mover>', _math(hat))
        bar = f'<m:bar><m:barPr><m:pos m:val="top"/></m:barPr><m:e>{_r("x")}</m:e></m:bar>'
        self.assertIn("<mo>¯</mo>", _math(bar))

    def test_matrices_and_several_lines(self) -> None:
        matrix = f"<m:m><m:mr><m:e>{_r('a')}</m:e><m:e>{_r('b')}</m:e></m:mr><m:mr><m:e>{_r('c')}</m:e></m:mr></m:m>"
        self.assertIn("<mtable><mtr><mtd><mrow><mi>a</mi></mrow></mtd><mtd>", _math(matrix))
        lines = mathml_from_omml(f"<m:oMathPara><m:oMath>{_r('a')}</m:oMath><m:oMath>{_r('b')}</m:oMath></m:oMathPara>")
        self.assertEqual(lines.count("<mtr>"), 2)

    def test_text_is_escaped(self) -> None:
        self.assertIn("<mo>&lt;</mo>", _math(_r("a&lt;b")))
        self.assertNotIn("<script", _math(_r("&lt;script&gt;")))


if __name__ == "__main__":
    unittest.main()
