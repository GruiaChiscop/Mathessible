from __future__ import annotations

CHARACTER_NAMES = {
    " ": "space",
    "\t": "tab",
    "\n": "new line",
    "(": "left parenthesis",
    ")": "right parenthesis",
    "[": "left bracket",
    "]": "right bracket",
    "{": "left brace",
    "}": "right brace",
    "+": "plus",
    "-": "minus",
    "*": "asterisk",
    "/": "slash",
    "\\": "backslash",
    "=": "equals",
    "<": "less than",
    ">": "greater than",
    "_": "underscore",
    "^": "caret",
    ".": "period",
    ",": "comma",
    ";": "semicolon",
    ":": "colon",
    "'": "apostrophe",
    '"': "quote",
    "`": "grave accent",
    "~": "tilde",
    "!": "exclamation mark",
    "?": "question mark",
    "@": "at sign",
    "#": "number sign",
    "$": "dollar sign",
    "%": "percent",
    "&": "ampersand",
    "|": "vertical bar",
    "⇒": "implies",
    "→": "right arrow",
    "←": "left arrow",
    "∞": "infinity",
    "≤": "less than or equal to",
    "≥": "greater than or equal to",
    "≠": "not equal to",
    "×": "times",
    "·": "dot",
    "÷": "divided by",
    "±": "plus or minus",
    "√": "square root",
    "∫": "integral",
    "∑": "sum",
    "∏": "product",
    "α": "alpha",
    "β": "beta",
    "γ": "gamma",
    "δ": "delta",
    "π": "pi",
    "θ": "theta",
    "λ": "lambda",
    "μ": "mu",
    "σ": "sigma",
    "φ": "phi",
    "ω": "omega",
}


def character_name(character: str) -> str:
    if not character:
        return ""
    return CHARACTER_NAMES.get(character, character)


def inserted_character(character: str) -> str:
    return character_name(character)


def deleted_character(character: str) -> str:
    name = character_name(character)
    return f"deleted {name}" if name else "deleted"
