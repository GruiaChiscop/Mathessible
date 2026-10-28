import unittest

from mathessible.documents.tex_math import find_tex_math_zones, tex_math_zone_at, toggle_tex_display

DOCUMENT = r"""\documentclass{article}
\usepackage{amsmath} % for align: $not math$
\begin{document}
Euler: $e^{i\pi}+1=0$ and \(a/b\); it costs \$5.
\[ \frac{a}{b} \]
$$x^2$$
\begin{equation}
  E = mc^2 \label{eq:e}
\end{equation}
\begin{align*}
  a &= b \\
  c &= d
\end{align*}
\begin{verbatim}
$not math$ \[ nor this \]
\end{verbatim}
\verb|$x$| and \begin{math}y\end{math}.
\end{document}
"""


class FindTexMathZonesTests(unittest.TestCase):
    def test_every_kind_of_equation(self) -> None:
        zones = find_tex_math_zones(DOCUMENT)
        found = [(zone.content(DOCUMENT).strip(), zone.display, zone.environment) for zone in zones]
        self.assertEqual(
            found,
            [
                ("e^{i\\pi}+1=0", False, ""),
                ("a/b", False, ""),
                ("\\frac{a}{b}", True, ""),
                ("x^2", True, ""),
                ("E = mc^2 \\label{eq:e}", True, ""),
                ("a &= b \\\\\n  c &= d", True, "aligned"),
                ("y", False, ""),
            ],
        )

    def test_the_marks_are_the_zones_own(self) -> None:
        marks = [zone.marks(DOCUMENT) for zone in find_tex_math_zones(DOCUMENT)]
        self.assertEqual(marks[1], ("\\(", "\\)"))
        self.assertEqual(marks[4], ("\\begin{equation}", "\\end{equation}"))
        self.assertEqual(marks[5], ("\\begin{align*}", "\\end{align*}"))

    def test_inline_math_does_not_cross_a_paragraph(self) -> None:
        self.assertEqual(find_tex_math_zones("a $b\n\nc$ d"), [])

    def test_alignat_columns_are_not_content(self) -> None:
        source = "\\begin{alignat}{2} x &= 1 \\end{alignat}"
        (zone,) = find_tex_math_zones(source)
        self.assertEqual(zone.content(source), " x &= 1 ")

    def test_zone_at(self) -> None:
        caret = DOCUMENT.index("mc^2")
        self.assertEqual(tex_math_zone_at(DOCUMENT, caret).environment, "")
        self.assertIsNone(tex_math_zone_at(DOCUMENT, DOCUMENT.index("costs")))


class ToggleTexDisplayTests(unittest.TestCase):
    def test_inline_becomes_display_in_place_and_back(self) -> None:
        source = "Then $x+1$ holds."
        (zone,) = find_tex_math_zones(source)
        displayed, new_zone = toggle_tex_display(source, zone)
        self.assertEqual(displayed, "Then \\[x+1\\] holds.")
        self.assertEqual(new_zone.content(displayed), "x+1")
        self.assertEqual(toggle_tex_display(displayed, new_zone)[0], source)

    def test_aligned_rows_cannot_be_inline(self) -> None:
        source = "\\begin{align}a&=b\\\\c&=d\\end{align}"
        (zone,) = find_tex_math_zones(source)
        self.assertIsNone(toggle_tex_display(source, zone))


if __name__ == "__main__":
    unittest.main()
