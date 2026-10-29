import re
import unittest

from converter_harness import convert_all, has_error, needs_node
from mathessible.editing.latex_insert import (
    insert_latex,
    keep_document_commands,
    move_to_latex_slot,
    within_environment,
)
from mathessible.mathcat.latex import equation_latex, tidy_latex
from mathessible.templates.math_templates import fill_empty_slots

GREEK = {
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "zeta",
    "eta",
    "theta",
    "iota",
    "kappa",
    "lambda",
    "mu",
    "nu",
    "xi",
    "pi",
    "rho",
    "sigma",
    "tau",
    "upsilon",
    "phi",
    "chi",
    "psi",
    "omega",
}
needs_mathcat = unittest.skipUnless(
    __import__("importlib").util.find_spec("mathessible_mathcat"), "needs the native MathCAT"
)


class TidyLatexTests(unittest.TestCase):
    def test_binary_operators_are_spaced_on_both_sides(self) -> None:
        self.assertEqual(
            tidy_latex("x =\\frac{ -b \\pm \\sqrt{b^2 -4ac}}{2a}"), "x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}"
        )
        self.assertEqual(tidy_latex("e^{i\\pi} +1 =0"), "e^{i\\pi} + 1 = 0")
        self.assertEqual(tidy_latex("a & =b \\\\ c & -d"), "a & = b \\\\ c & -d")

    def test_a_sign_is_not_a_binary_operator(self) -> None:
        self.assertEqual(tidy_latex("x =-1"), "x = -1")
        self.assertEqual(tidy_latex("f(-x)"), "f(-x)")

    def test_a_texts_spaces_are_kept(self) -> None:
        self.assertEqual(tidy_latex("\\text{if }x \\ge 2"), "\\text{if }x \\ge 2")
        self.assertEqual(tidy_latex("\\text{area} =\\pi r^2"), "\\text{area} = \\pi r^2")
        self.assertEqual(tidy_latex("\\text{a =b} =1"), "\\text{a =b} = 1")


class InsertLatexTests(unittest.TestCase):
    def test_the_caret_goes_into_the_first_empty_slot(self) -> None:
        self.assertEqual(insert_latex("x=", 2, "\\frac{}{}"), ("x=\\frac{}{}", 8))
        self.assertEqual(insert_latex("", 0, "\\sqrt[{}]{}"), ("\\sqrt[{}]{}", 7))

    def test_without_a_slot_the_caret_goes_after_it(self) -> None:
        self.assertEqual(insert_latex("a+b", 2, "\\alpha"), ("a+\\alpha b", 9))
        self.assertEqual(insert_latex("a+", 2, "\\alpha"), ("a+\\alpha", 8))

    def test_a_control_word_is_not_run_into_a_letter(self) -> None:
        self.assertEqual(insert_latex("\\pi", 3, "r"), ("\\pi r", 5))
        self.assertEqual(insert_latex("\\pi", 3, "\\cdot"), ("\\pi\\cdot", 8))
        self.assertEqual(insert_latex("x", 0, "\\alpha"), ("\\alpha x", 7))


class WithinEnvironmentTests(unittest.TestCase):
    def test_an_align_environments_rows_lose_the_aligned_written_around_them(self) -> None:
        written = "\\begin{aligned} a & = b \\\\ c & = d \\end{aligned}"
        typed = "\n  a &= b \\\\\n  c &= d\n"
        self.assertEqual(within_environment(written, "aligned", typed), "\n  a & = b \\\\ c & = d\n")

    def test_a_written_equation_keeps_its_labels_on_their_rows(self) -> None:
        self.assertEqual(keep_document_commands("E = mc^2 + 1", "E=mc^2 \\label{e}"), "E = mc^2 + 1 \\label{e}")
        typed = "a&=b \\label{x}\\\\ c&=d \\nonumber"
        self.assertEqual(
            keep_document_commands("a & = b \\\\ c & = d", typed), "a & = b \\label{x} \\\\ c & = d \\nonumber"
        )

    def test_outside_an_environment_nothing_changes(self) -> None:
        self.assertEqual(within_environment("x = 1", "", " x=1 "), "x = 1")


# Each equation: built from LaTeX, written in LaTeX again by MathCAT, built again.
class LatexSlotTests(unittest.TestCase):
    def slot(self, source: str, caret: int, reverse: bool = False) -> tuple[int, str] | None:
        edit = move_to_latex_slot(source, caret, reverse)
        return None if edit is None else (edit.caret, edit.announcement)

    def test_tab_goes_from_brace_group_to_brace_group(self) -> None:
        self.assertEqual(self.slot("\\frac{}{}", 6), (8, "empty denominator"))
        self.assertEqual(self.slot("\\frac{a}{b}", 10, reverse=True), (7, "numerator, a"))
        self.assertEqual(self.slot("x^{2} + \\sqrt[{}]{}", 0), (4, "superscript, 2"))
        self.assertEqual(self.slot("\\sqrt[{}]{}", 7), (10, "empty radicand"))

    def test_tab_from_the_last_argument_leaves_the_command(self) -> None:
        self.assertEqual(self.slot("\\frac{a}{b}+1", 10), (11, "end fraction"))

    def test_an_environments_name_and_escaped_braces_are_not_slots(self) -> None:
        self.assertEqual(self.slot("\\begin{cases} {} & {} \\end{cases}", 0), (15, "empty group"))
        self.assertIsNone(self.slot("\\left\\{ x \\right\\}", 0))


ROUND_TRIP = [
    "\\frac{a}{b}",
    "\\sum_{i=1}^n i^2",
    "x \\in \\mathbb{R}^n",
    "\\lim_{x\\to 0}\\frac{\\sin x}{x}",
    "\\mathbf{v}\\cdot\\mathbf{w}",
    "f(x)=\\begin{cases}1&x>0\\\\0&x\\le 0\\end{cases}",
    "\\hat{x}+\\vec{v}+\\dot{x}+\\tilde{z}",
    "\\text{if } x\\geq 2",
    "\\alpha+\\beta+\\Gamma",
    "\\sqrt[3]{x^2+y^2}",
    "\\begin{pmatrix}a&b\\\\c&d\\end{pmatrix}",
    "x=\\frac{-b\\pm\\sqrt{b^2-4ac}}{2a}",
    "e^{i\\pi}+1=0",
    "\\binom{n}{k}",
    "\\frac{}{}",
    "\\begin{aligned}a&=b+1\\\\c&=d\\end{aligned}",
    "\\begin{matrix}a&b\\\\c&d\\end{matrix}",
]


@needs_node
@needs_mathcat
class LatexWriterTests(unittest.TestCase):
    def test_mathcat_writes_plain_latex_that_builds_the_same(self) -> None:
        built = [result["mathml"] for result in convert_all(ROUND_TRIP, latex=True)]
        written = equation_latex(built)
        rebuilt = [result["mathml"] for result in convert_all(written, latex=True)]
        for source, latex, before, after in zip(ROUND_TRIP, written, built, rebuilt, strict=True):
            with self.subTest(source=source, latex=latex):
                self.assertIsNotNone(latex)
                self.assertFalse(has_error(after))
                self.assertEqual(after, before)
                # LaTeX's own letters and commands: no math alphanumerics, quotes or hidden markers.
                self.assertIsNone(re.search(r"[\U0001d400-\U0001d7ff\"-]", latex))

    def test_an_align_environment_is_written_back_as_its_rows(self) -> None:
        rows = "a &= b+1 \\\\ c &= d"
        (built,) = convert_all([f"\\begin{{aligned}}{rows}\\end{{aligned}}"], latex=True)
        written = within_environment(equation_latex([built["mathml"]])[0], "aligned", rows)
        self.assertEqual(written, "a & = b + 1 \\\\ c & = d")
        (rebuilt,) = convert_all([f"\\begin{{aligned}}{written}\\end{{aligned}}"], latex=True)
        self.assertEqual(rebuilt["mathml"], built["mathml"])

    def test_what_mathcat_writes(self) -> None:
        sources = ["\\frac{a}{b}", "\\alpha_1", "\\lim_{x\\to 0} f", "\\frac{}{}", "\\text{if } x"]
        written = equation_latex([result["mathml"] for result in convert_all(sources, latex=True)])
        self.assertEqual(written, ["\\frac{a}{b}", "\\alpha_1", "\\lim_{x \\to 0} f", "\\frac{}{}", "\\text{if }x"])

    def test_a_unicode_math_templates_empty_slots_are_empty_braces(self) -> None:
        # Insert in a LaTeX equation writes its UnicodeMath template, whose empty slots are `<mspace width="0"/>`.
        sources = ["()/()", "√〖〗", "x^()", "lim_() 〖〗"]
        written = equation_latex([result["mathml"] for result in convert_all(sources)])
        self.assertEqual(written, ["\\frac{}{}", "\\sqrt{}", "x^{}", "\\lim_{} {}"])

    def test_templates_that_build_only_filled(self) -> None:
        templates = ["√(&)", "(¦)", "‖‖", "()_()", "()^()"]
        filled = [fill_empty_slots(template) for template in templates]
        written = equation_latex([result["mathml"] for result in convert_all(filled)])
        self.assertEqual(written, ["\\sqrt[{}]{}", "\\binom{}{}", "\\Vert {} \\Vert", "{}_{}", "{}^{}"])

    def test_epsilon_norms_and_operator_names(self) -> None:
        sources = ["\\epsilon", "\\|x\\|", "\\left\\lVert x \\right\\rVert", "\\mathrm{tr}\u2061 A"]
        written = equation_latex([result["mathml"] for result in convert_all(sources, latex=True)])
        self.assertEqual(written, ["\\epsilon", "\\Vert x \\Vert", "\\Vert x \\Vert", "\\operatorname{tr}A"])

    def test_spaces_are_written_back_and_a_negative_space_is_no_factorial(self) -> None:
        sources = ["a\\,b", "a\\:b", "a\\;b", "a\\ b", "a~b", "a\\quad b", "a\\!b", "n!"]
        built = [result["mathml"] for result in convert_all(sources, latex=True)]
        self.assertNotIn("!", built[6])
        written = equation_latex(built)
        self.assertEqual(written, ["a\\,b", "a\\:b", "a\\;b", "a\\ b", "a\\ b", "a\\quad b", "ab", "n!"])

    def test_math_alphabets_are_written_in_latex_and_build_back(self) -> None:
        letters = "𝐀𝑥ℎ𝒙𝒜𝓛𝔄𝔸𝕒𝖠𝗮𝚊𝟏𝟙𝜶𝚪𝛂ℝℋ𝓵𝖌𝚤"
        written = equation_latex([f"<math><mi>{letter}</mi></math>" for letter in letters])
        rebuilt = [result["mathml"] for result in convert_all(written, latex=True)]
        for letter, latex, mathml in zip(letters, written, rebuilt, strict=True):
            with self.subTest(letter=letter, latex=latex):
                self.assertIn(f">{letter}<", mathml)

    def test_no_command_latex_lacks(self) -> None:
        import unicodedata

        letters = [chr(code) for code in range(0x1D400, 0x1D800) if unicodedata.name(chr(code), "")]
        written = equation_latex([f"<math><mi>{letter}</mi></math>" for letter in letters])
        commands = {command for latex in written for command in re.findall(r"\\[A-Za-z]+", latex or "")}
        unknown = commands - {
            "\\mathbf",
            "\\mathit",
            "\\boldsymbol",
            "\\mathcal",
            "\\mathscr",
            "\\mathfrak",
            "\\mathbb",
            "\\mathsf",
            "\\mathtt",
            "\\imath",
            "\\jmath",
            "\\partial",
            "\\nabla",
            "\\Digamma",
            "\\digamma",
        }
        greek = {command for command in unknown if command[1:].lower().replace("var", "") in GREEK}
        self.assertNotIn(None, written)
        self.assertEqual(unknown - greek, set())
        self.assertEqual(greek & {"\\Alpha", "\\Beta", "\\Omicron", "\\omicron", "\\Rho", "\\Chi"}, set())

    def test_symbols_are_written_in_latex_and_build_back(self) -> None:
        # amssymb's symbols the converter lacked, a symbol LaTeX has no command for (written as itself),
        # the degree sign, a text symbol and a character MathCAT's tables lack.
        symbols = "⩽⩾∅∴□■≜⟹⪰≔◇⤇∛°¢‑≴⊘∣"
        mathml = [f"<math><mi>x</mi><mo>{symbol}</mo><mi>y</mi></math>" for symbol in symbols]
        written = equation_latex(mathml)
        rebuilt = [result["mathml"] for result in convert_all(written, latex=True)]
        again = equation_latex(rebuilt)
        for symbol, latex, built, second in zip(symbols, written, rebuilt, again, strict=True):
            with self.subTest(symbol=symbol, latex=latex):
                self.assertFalse(has_error(built))
                self.assertIsNone(re.search(r"<mtext>[^<]*\\", built))  # no command left as text
                self.assertEqual(re.sub(r"\s", "", second), re.sub(r"\s", "", latex))
        self.assertEqual(written[11], "x ⤇y")
        self.assertEqual(written[13], "x^{\\circ}y")

    def test_numbers_upright_letters_and_texts(self) -> None:
        sources = ["E=mc^2 \\tag{1}", "\\int f\\,\\mathrm{d}x", "\\text{50\\% off \\& a (b): c}", "\\text{if }x < 0"]
        written = equation_latex([result["mathml"] for result in convert_all(sources, latex=True)])
        self.assertEqual(written, ["E = mc^2 \\tag{1}", "\\int f\\,\\mathrm{d}x", sources[2], sources[3]])

    def test_the_editors_mathcat_is_not_touched(self) -> None:
        import mathessible_mathcat

        mathessible_mathcat.initialize("en", "SimpleSpeak", "Medium")
        mathessible_mathcat.preference("BrailleCode", "Nemeth")
        mathessible_mathcat.set_expression("<math><mi>x</mi></math>")
        self.assertEqual(equation_latex(["<math><mi>y</mi></math>", "<not mathml"]), ["y", None])
        self.assertEqual(mathessible_mathcat.speak_expression().strip(), "x")


if __name__ == "__main__":
    unittest.main()
