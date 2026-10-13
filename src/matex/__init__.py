"""MateX accessible mathematics editor prototype."""

from .model import EquationDocument, MathCursor
from .parser import ParseError, parse_unicodemath

__all__ = ["EquationDocument", "MathCursor", "ParseError", "parse_unicodemath"]

