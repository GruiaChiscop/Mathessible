from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


# Word's own Recognized Functions (Equation Options), with the Romanian tg/ctg
# and sqrt. Not lim (its own template). liminf/limsup are typed as one word
# and written `lim inf` with a no-break space, the converter's own spelling
# (space_conversion.FUNCTION_SPELLINGS). Each one gets Space-opens-argument and a
# Tab slot for its argument.
DEFAULT_RECOGNIZED_FUNCTIONS: tuple[str, ...] = (
    "sin",
    "cos",
    "tan",
    "tg",
    "cot",
    "ctg",
    "sec",
    "csc",
    "arcsin",
    "arccos",
    "arctan",
    "arccot",
    "arcsec",
    "arccsc",
    "sinh",
    "cosh",
    "tanh",
    "coth",
    "sech",
    "csch",
    "log",
    "ln",
    "lg",
    "exp",
    "arg",
    "det",
    "dim",
    "ker",
    "hom",
    "deg",
    "gcd",
    "def",
    "max",
    "min",
    "sup",
    "inf",
    "liminf",
    "limsup",
    "Pr",
    "sqrt",
)
# Names whose case matters keep it ("PR" and "pr" are Pr); others are lower-cased.
_CANONICAL_FUNCTIONS = {name.lower(): name for name in DEFAULT_RECOGNIZED_FUNCTIONS}


# The braille codes MathCAT ships (its Rules/Braille), with how they are
# offered in Settings. ASCIIMath and LaTeX are text, for a braille display.
BRAILLE_CODES: tuple[tuple[str, str], ...] = (
    ("Nemeth", "Nemeth (US)"),
    ("UEB", "UEB (Unified English Braille)"),
    ("CMU", "CMU (Spanish, Portuguese)"),
    ("French", "French"),
    ("Russian", "Russian"),
    ("Swedish", "Swedish"),
    ("Vietnam", "Vietnamese"),
    ("ASCIIMath", "ASCIIMath (text)"),
    ("LaTeX", "LaTeX (text)"),
)


@dataclass(slots=True)
class AppSettings:
    linear_navigation: bool = False
    # Every structure gets standalone "start X"/"end X" stops, and the math
    # "start of math"/"end of math" -- in linear and structural navigation.
    structure_stops: bool = True
    # Invisible times (the "3x" in 3x) and friends get a stop of their own.
    invisible_operator_stops: bool = False
    # Control words (\alpha) on Space or punctuation, and shortcuts (->) on Space.
    convert_on_space: bool = True
    # While a control word is typed (\al), suggest the words it may become
    # (\alpha, \aleph): spoken, Up/Down browse them, Tab takes one.
    complete_control_words: bool = True
    # The decimal separator, for the converter (patches/unicodemathml/0001)
    # and MathCAT's speech alike: "," (1,5 is a number; a list needs a
    # space, {1, 2, 3}) or "." (3.14; {1,2,3} is a list).
    decimal_separator: str = ","
    # MathCAT's braille code for the braille strip (BRAILLE_CODES).
    braille_code: str = "Nemeth"
    # Symbol shortcuts (<<, ->, <=) as soon as their last character is typed.
    convert_shortcuts_immediately: bool = True
    # Templates and structure edits write control words (\sum, \sqrt, \of)
    # instead of the symbols they stand for; the converter reads both.
    template_control_words: bool = True
    # Open equations straight in professional view (built), where they can
    # be typed into too; an empty equation still opens linear.
    open_built: bool = False
    # Word's autobuild: in linear view, Space or a closing bracket builds the
    # equation (professional view) once it converts with no error.
    build_as_you_type: bool = True
    # Closing lim_(...)/log_(...) opens the argument (and builds) at once,
    # instead of on the Space after it, as Word does.
    argument_on_closing_paren: bool = False
    # Which symbols.dic names symbols in speech (symbol_dictionary.py).
    symbol_dictionary: str = "matex-en"
    auto_zoom_out: bool = False
    show_preview: bool = False
    recognized_functions: tuple[str, ...] = DEFAULT_RECOGNIZED_FUNCTIONS
    # The user's own Math AutoCorrect entries, as Word's: (what is typed, what
    # it becomes). `\R` -> ℝ acts as a control word; others convert on Space.
    math_autocorrect: tuple[tuple[str, str], ...] = ()


def default_settings_path() -> Path:
    return Path.home() / ".matex" / "settings.json"


def load_settings(path: Path | None = None) -> AppSettings:
    settings_path = path or default_settings_path()
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return AppSettings()
    return AppSettings(
        linear_navigation=bool(data.get("linear_navigation", False)),
        structure_stops=bool(data.get("structure_stops", True)),
        invisible_operator_stops=bool(data.get("invisible_operator_stops", False)),
        convert_on_space=bool(data.get("convert_on_space", True)),
        complete_control_words=bool(data.get("complete_control_words", True)),
        decimal_separator="." if data.get("decimal_separator") == "." else ",",
        braille_code=_braille_code(data.get("braille_code")),
        convert_shortcuts_immediately=bool(data.get("convert_shortcuts_immediately", True)),
        template_control_words=bool(data.get("template_control_words", True)),
        open_built=bool(data.get("open_built", False)),
        build_as_you_type=bool(data.get("build_as_you_type", True)),
        argument_on_closing_paren=bool(data.get("argument_on_closing_paren", False)),
        symbol_dictionary=str(data.get("symbol_dictionary", "matex-en")),
        auto_zoom_out=bool(data.get("auto_zoom_out", False)),
        show_preview=bool(data.get("show_preview", False)),
        recognized_functions=_normalize_functions(data.get("recognized_functions")),
        math_autocorrect=_normalize_autocorrect(data.get("math_autocorrect")),
    )


def _braille_code(value: object) -> str:
    codes = [code for code, _label in BRAILLE_CODES]
    return value if isinstance(value, str) and value in codes else "Nemeth"


def save_settings(settings: AppSettings, path: Path | None = None) -> None:
    settings_path = path or default_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(asdict(settings), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_recognized_functions(text: str) -> tuple[str, ...]:
    return _normalize_functions(text.replace("\n", ",").split(","))


def format_recognized_functions(functions: tuple[str, ...]) -> str:
    return ", ".join(functions)


def _normalize_functions(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return DEFAULT_RECOGNIZED_FUNCTIONS
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        name = item.strip().lower()
        name = _CANONICAL_FUNCTIONS.get(name, name)
        if not name or name in seen:
            continue
        result.append(name)
        seen.add(name)
    return tuple(result) or DEFAULT_RECOGNIZED_FUNCTIONS


def parse_math_autocorrect(text: str) -> tuple[tuple[str, str], ...]:
    """One entry per line: what is typed, a space, what it becomes (`\\R ℝ`, `+- ±`)."""
    entries = []
    for line in text.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            entries.append((parts[0], parts[1].strip()))
    return _normalize_autocorrect(entries)


def format_math_autocorrect(entries: tuple[tuple[str, str], ...]) -> str:
    return "\n".join(f"{typed} {replacement}" for typed, replacement in entries)


def _normalize_autocorrect(value: object) -> tuple[tuple[str, str], ...]:
    """Valid (typed, replacement) pairs, the last one for a typed text winning."""
    if not isinstance(value, (list, tuple)):
        return ()
    entries: dict[str, str] = {}
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        typed, replacement = item
        if not isinstance(typed, str) or not isinstance(replacement, str):
            continue
        typed, replacement = typed.strip(), replacement.strip()
        if not typed or not replacement or any(character.isspace() for character in typed) or typed == "\\":
            continue
        entries.pop(typed, None)
        entries[typed] = replacement
    return tuple(entries.items())
