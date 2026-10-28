"""A template or symbol inserted into LaTeX typed in the linear view.

The Insert entries are UnicodeMath templates; in a LaTeX equation MathCAT
writes each one as LaTeX (`mathcat.latex`), its empty slots `{}`, and it is
inserted here: the caret goes into the first empty slot, as a template's
does in UnicodeMath. A control word is never run into a letter (`\\alpha`
before `x` is not `\\alphax`): a space keeps the two apart, as LaTeX needs.
"""

from __future__ import annotations

import re

_ENDS_IN_CONTROL_WORD = re.compile(r"(?<!\\)\\[A-Za-z]+$")


def insert_latex(source: str, caret: int, latex: str) -> tuple[str, int]:
    """The source with `latex` inserted at the caret, and the caret in its first empty slot (else after it)."""
    before, after = source[:caret], source[caret:]
    if _ENDS_IN_CONTROL_WORD.search(before) and latex[:1].isalpha():
        latex = " " + latex
    if _ENDS_IN_CONTROL_WORD.search(latex) and after[:1].isalpha():
        latex += " "
    slot = latex.find("{}")
    new_caret = caret + (slot + 1 if slot >= 0 else len(latex))
    return before + latex + after, new_caret
