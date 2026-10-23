"""The equation being edited: its UnicodeMath source, nothing parsed in Python.

Everything about the equation's structure comes from the converter
(UnicodeMathML) and MathCAT; the editor keeps only the text.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class EquationSource:
    source: str = ""
