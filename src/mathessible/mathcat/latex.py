"""Equations written as LaTeX by MathCAT, for a LaTeX document's equations rewritten from MathML.

MathCAT's LaTeX braille code is plain LaTeX (`\\frac{a}{b}`, `x \\in
\\mathbb R^n`, `\\begin{pmatrix}`), written from the built equation as
MathCAT understands it. Sargent's `MathMLtoTeX` writes math alphanumerics
(`\\frac{𝑎}{𝑏}`) and quotes, so MathCAT writes a LaTeX document's
equations when they are rewritten: after an edit in the professional view,
on a paste, or when a document changes to LaTeX.

MathCAT's state is per thread, and its braille code is a preference: the
LaTeX is written by a MathCAT of its own, on a thread of its own, so the
editor's equation, position and braille code are never touched.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Sequence

from mathessible.mathcat.prepare import prepare_for_mathcat

# The ASCII operators MathCAT writes with a space before and none after (`x =0`).
_OPERATOR = re.compile(r"(?<=[\w}\])'!|]) ([=+\-<>])(?=[^\s}\])&,;^_])")
_AFTER_OPENING = re.compile(r"(?<=[{(\[]) +")
_TEXT = re.compile(r"\\text\{[^{}]*\}")
# MathCAT's empty slot (⬚); `{}` is LaTeX's, built as an empty slot again.
_SLOT = re.compile(r"\{\\dottedsquare\}|\\dottedsquare(?![A-Za-z])")


def tidy_latex(latex: str) -> str:
    """MathCAT's LaTeX spaced evenly: a space on both sides of a binary `= + - < >`, none inside an opening
    bracket (`{ -b` is `{-b`). A text's own spaces (`\\text{if }`) are kept."""
    texts = _TEXT.findall(latex)
    # Each text stands in as `\\text{}` while the math around it is spaced.
    latex = _AFTER_OPENING.sub("", _TEXT.sub(lambda _text: "\\text{}", latex))
    latex = _OPERATOR.sub(r" \1 ", latex)
    pieces = latex.split("\\text{}")
    return pieces[0] + "".join(text + piece for text, piece in zip(texts, pieces[1:], strict=True))


def equation_latex(mathml: Sequence[str], decimal_separator: str = ",") -> list[str | None]:
    """Each equation's MathML as LaTeX, None for one MathCAT could not write (or without MathCAT)."""
    written: list[str | None] = [None] * len(mathml)

    def write() -> None:
        try:
            import mathessible_mathcat as native

            native.initialize("en", "ClearSpeak", "Medium")
            native.preference("DecimalSeparator", decimal_separator)
            native.preference("BrailleCode", "LaTeX")
        except (ImportError, OSError, RuntimeError, ValueError):
            return
        for index, equation in enumerate(mathml):
            try:
                native.set_expression(prepare_for_mathcat(equation))
                written[index] = tidy_latex(_SLOT.sub("{}", native.braille("").strip()))
            except (OSError, RuntimeError, ValueError):
                written[index] = None

    worker = threading.Thread(target=write, name="mathessible-latex", daemon=True)
    worker.start()
    worker.join()
    return written
