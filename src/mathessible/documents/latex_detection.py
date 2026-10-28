"""Whether Markdown written elsewhere (GitHub, Pandoc) holds LaTeX equations, though it has no `math: latex`.

Python never reads an equation itself: the converter decides. An equation
speaks for LaTeX when it builds cleanly as LaTeX but not as UnicodeMath
(a parse error, or a control word UnicodeMath does not know left as text:
`\\frac{a}{b}`, `\\mathbb{R}`, `\\begin{pmatrix}`), and for UnicodeMath the
other way round. What both read alike (`a/b`, `\\alpha`, `x^2`) says
nothing. Only equations with a backslash can tell them apart.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from mathessible.documents.front_matter import LATEX, equation_language
from mathessible.documents.markdown_math import find_math_zones
from mathessible.unicodemath import UnicodeMathError, mathml_has_parse_error

# Enough equations to tell, without converting a whole book twice.
_CHECKED = 20
_TAG = re.compile(r"<[^>]*>")


def _builds(convert: Callable[[str, bool], str], equation: str, latex: bool) -> bool:
    try:
        mathml = convert(equation, latex)
    except (UnicodeMathError, RuntimeError, ValueError):
        return False
    return not mathml_has_parse_error(mathml) and "\\" not in _TAG.sub("", mathml)


def has_latex_equations(source: str, convert: Callable[[str, bool], str]) -> bool:
    """True when a document not marked LaTeX holds equations that build only as LaTeX, and none that build only
    as UnicodeMath; `convert(equation, latex)` is the converter (MathML, or `UnicodeMathError`)."""
    if equation_language(source) == LATEX:
        return False
    candidates = [zone.content(source) for zone in find_math_zones(source) if "\\" in zone.content(source)]
    latex_only = unicodemath_only = 0
    for equation in candidates[:_CHECKED]:
        as_latex, as_unicodemath = _builds(convert, equation, True), _builds(convert, equation, False)
        if as_latex and not as_unicodemath:
            latex_only += 1
        elif as_unicodemath and not as_latex:
            unicodemath_only += 1
    return latex_only > 0 and unicodemath_only == 0
