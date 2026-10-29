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
# A relation after an alignment point (`a & =b`).
_ALIGNED_RELATION = re.compile(r"(?<=&) ([=<>])(?=[^\s}\])&,;^_])")
_AFTER_OPENING = re.compile(r"(?<=[{(\[]) +")
_TEXT = re.compile(r"\\text\{[^{}]*\}")
# MathCAT's empty slot (⬚); `{}` is LaTeX's, built as an empty slot again.
_SLOT = re.compile(r"\{\\dottedsquare\}|\\dottedsquare(?![A-Za-z])")
# The converter's empty slot (`()/()` is `<mfrac><mspace width="0"/>…`), which MathCAT writes `\text{ }`:
# given to MathCAT as its own empty slot, it is written `\dottedsquare`, and so `{}`.
_EMPTY = re.compile(r'<mspace width="0"\s*(?:/>|></mspace>)')
# A space (`\\,`, `\\quad`): MathCAT merges spaces into their neighbours and writes none, so each goes to
# MathCAT as a text of its own, written back as LaTeX's space of that width (in 18ths of an em).
_SPACE = re.compile(r'<mspace width="([^"]*)"\s*(?:/>|></mspace>)')
_SPACE_TEXT = "mathessiblespace"
_WRITTEN_SPACE = re.compile(r"\\text\{" + _SPACE_TEXT + r"(\d+)\}")
_NAMED_WIDTHS = {
    "veryverythinmathspace": 1,
    "verythinmathspace": 2,
    "thinmathspace": 3,
    "mediummathspace": 4,
    "thickmathspace": 5,
    "verythickmathspace": 6,
    "veryverythickmathspace": 7,
}
_EM = re.compile(r"^\s*([\d.]+)\s*em\s*$")


def _space_width(width: str) -> int:
    """A space's width in 18ths of an em (MathML's named spaces, or ems), 0 when it cannot be read."""
    if width in _NAMED_WIDTHS:
        return _NAMED_WIDTHS[width]
    found = _EM.match(width)
    return round(float(found.group(1)) * 18) if found else 0


def _space_command(eighteenths: int) -> str:
    """LaTeX's space nearest that width: \\, \\: \\; \\  \\enspace \\quad \\qquad."""
    if eighteenths <= 0:
        return ""
    for limit, command in ((3, "\\,"), (4, "\\:"), (5, "\\;"), (8, "\\ "), (12, "\\enspace"), (27, "\\quad")):
        if eighteenths <= limit:
            return command
    return "\\qquad"


def _spaces_to_texts(mathml: str) -> str:
    return _SPACE.sub(lambda found: f"<mtext>{_SPACE_TEXT}{_space_width(found.group(1))}</mtext>", mathml)


def _texts_to_spaces(latex: str) -> str:
    def space(found: re.Match[str]) -> str:
        command = _space_command(int(found.group(1)))
        following = found.string[found.end() : found.end() + 1]
        return command + " " if command[-1:].isalpha() and following.isalpha() else command

    return _WRITTEN_SPACE.sub(space, latex)


def tidy_latex(latex: str) -> str:
    """MathCAT's LaTeX spaced evenly: a space on both sides of a binary `= + - < >`, none inside an opening
    bracket (`{ -b` is `{-b`). A text's own spaces (`\\text{if }`) are kept."""
    texts = _TEXT.findall(latex)
    # Each text stands in as `\\text{}` while the math around it is spaced.
    latex = _AFTER_OPENING.sub("", _TEXT.sub(lambda _text: "\\text{}", latex))
    latex = _ALIGNED_RELATION.sub(r" \1 ", _OPERATOR.sub(r" \1 ", latex))
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
                equation = _spaces_to_texts(_EMPTY.sub("<mi>\u2b1a</mi>", equation))
                native.set_expression(prepare_for_mathcat(equation))
                written[index] = _texts_to_spaces(tidy_latex(_SLOT.sub("{}", native.braille("").strip())))
            except (OSError, RuntimeError, ValueError):
                written[index] = None

    worker = threading.Thread(target=write, name="mathessible-latex", daemon=True)
    worker.start()
    worker.join()
    return written
