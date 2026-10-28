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


def within_environment(latex: str, environment: str, typed: str) -> str:
    """LaTeX written for an equation whose rows a .tex environment holds (`align`: `environment` "aligned"),
    without that environment's own `\\begin`/`\\end`, spaced at its ends as the LaTeX typed was."""
    if not environment:
        return latex
    opening, closing = f"\\begin{{{environment}}}", f"\\end{{{environment}}}"
    stripped = latex.strip()
    if stripped.startswith(opening) and stripped.endswith(closing):
        latex = stripped[len(opening) : -len(closing)].strip()
    leading = typed[: len(typed) - len(typed.lstrip())]
    trailing = typed[len(typed.rstrip()) :]
    return f"{leading}{latex}{trailing}"
