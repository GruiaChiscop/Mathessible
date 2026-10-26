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
    # BRF export: liblouis's table for the text ("" is the system language's), and the page.
    braille_text_table: str = ""
    brf_cells_per_line: int = 40
    brf_lines_per_page: int = 25
    # Braille page numbers (BANA formats require them in transcriptions; Word adds none unless asked).
    brf_page_numbers: bool = True
    # PDF export (Typst): the page, the text, numbering, the outline, the source attached, the standard.
    pdf_paper: str = "a4"
    pdf_landscape: bool = False
    pdf_margins: tuple[int, int, int, int] = (25, 25, 25, 25)  # mm: top, right, bottom, left.
    pdf_font: str = "Libertinus Serif"
    pdf_font_size: int = 11
    pdf_line_spacing: float = 0.65  # Leading, in em.
    pdf_justify: bool = False
    pdf_page_numbers: bool = True
    pdf_page_number_position: str = "bottom-center"
    pdf_table_of_contents: bool = False
    pdf_attach_source: bool = True
    pdf_standard: str = "ua-1"
    pdf_author: str = ""
    pdf_equation_numbering: str = ""
    pdf_heading_numbering: str = ""
    pdf_text_colour: str = ""
    pdf_heading_colour: str = ""
    pdf_link_colour: str = ""
    pdf_columns: int = 1
    # Symbol shortcuts (<<, ->, <=) as soon as their last character is typed.
    convert_shortcuts_immediately: bool = True
    # Templates and structure edits write control words (\sum, \sqrt, \of)
    # instead of the symbols they stand for; the converter reads both.
    template_control_words: bool = True
    # Open equations straight in professional view (built), where they can
    # be typed into too; an empty equation still opens linear.
    open_built: bool = False
    # Word's autobuild: Space or an operator builds what has become complete
    # of what was typed; the rest stays linear text in the equation.
    build_as_you_type: bool = True
    # Say what was built ("built fraction") when typing builds a structure.
    announce_built: bool = True
    # Math AutoCorrect (control words, shortcuts, argument boxes) in normal text too.
    autocorrect_in_text: bool = False
    # As Word's "Use Math AutoCorrect rules outside of math regions": anywhere in the document's Markdown.
    autocorrect_in_document: bool = False
    # Say a symbol nothing named (MathCAT, the dictionary) by its Unicode name (🜁: "alchemical symbol for air").
    name_unknown_symbols: bool = True
    # Remove the spaces that change nothing when an equation is saved or shown linear, as Word does.
    remove_extra_spaces: bool = True
    # The equation editor's zoom, in percent (View > Zoom In/Out, Cmd+Option+= and -).
    equation_zoom: int = 100
    # Closing lim_(...)/log_(...) opens the argument (and builds) at once,
    # instead of on the Space after it, as Word does.
    argument_on_closing_paren: bool = False
    # Which symbols.dic names symbols in speech (symbol_dictionary.py).
    symbol_dictionary: str = "mathessible-en"
    auto_zoom_out: bool = False
    show_preview: bool = False
    recognized_functions: tuple[str, ...] = DEFAULT_RECOGNIZED_FUNCTIONS
    # Math AutoCorrect, as Word's one list (autocorrect.py): what the user
    # added or changed, (what is typed, what it becomes), and the defaults
    # they deleted; only these differences are saved.
    math_autocorrect: tuple[tuple[str, str], ...] = ()
    math_autocorrect_removed: tuple[str, ...] = ()
    # A deleted default control word (`\alpha`) still shows as its symbol in
    # the built equation; off, as in Word, it stays the text typed.
    removed_words_as_symbols: bool = False


def default_settings_path() -> Path:
    return Path.home() / ".mathessible" / "settings.json"


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
        braille_text_table=str(data.get("braille_text_table", "")),
        brf_cells_per_line=_bounded(data.get("brf_cells_per_line"), 40, BRF_CELLS),
        brf_lines_per_page=_bounded(data.get("brf_lines_per_page"), 25, BRF_LINES),
        brf_page_numbers=bool(data.get("brf_page_numbers", True)),
        pdf_paper=_option(data.get("pdf_paper"), PDF_PAPERS, "a4"),
        pdf_landscape=bool(data.get("pdf_landscape", False)),
        pdf_margins=_margins(data.get("pdf_margins")),
        pdf_font=str(data.get("pdf_font") or "Libertinus Serif"),
        pdf_font_size=_bounded(data.get("pdf_font_size"), 11, PDF_FONT_SIZES),
        pdf_line_spacing=_spacing(data.get("pdf_line_spacing")),
        pdf_justify=bool(data.get("pdf_justify", False)),
        pdf_page_numbers=bool(data.get("pdf_page_numbers", True)),
        pdf_page_number_position=_option(data.get("pdf_page_number_position"), PDF_NUMBER_POSITIONS, "bottom-center"),
        pdf_table_of_contents=bool(data.get("pdf_table_of_contents", False)),
        pdf_attach_source=bool(data.get("pdf_attach_source", True)),
        pdf_standard=_option(data.get("pdf_standard"), PDF_STANDARDS, "ua-1"),
        pdf_author=str(data.get("pdf_author", "")),
        pdf_equation_numbering=_option(data.get("pdf_equation_numbering"), PDF_EQUATION_NUMBERING, ""),
        pdf_heading_numbering=_option(data.get("pdf_heading_numbering"), PDF_HEADING_NUMBERING, ""),
        pdf_text_colour=_option(data.get("pdf_text_colour"), PDF_COLOURS, ""),
        pdf_heading_colour=_option(data.get("pdf_heading_colour"), PDF_COLOURS, ""),
        pdf_link_colour=_option(data.get("pdf_link_colour"), PDF_COLOURS, ""),
        pdf_columns=_bounded(data.get("pdf_columns"), 1, PDF_COLUMNS),
        convert_shortcuts_immediately=bool(data.get("convert_shortcuts_immediately", True)),
        template_control_words=bool(data.get("template_control_words", True)),
        open_built=bool(data.get("open_built", False)),
        build_as_you_type=bool(data.get("build_as_you_type", True)),
        announce_built=bool(data.get("announce_built", True)),
        autocorrect_in_text=bool(data.get("autocorrect_in_text", False)),
        autocorrect_in_document=bool(data.get("autocorrect_in_document", False)),
        name_unknown_symbols=bool(data.get("name_unknown_symbols", True)),
        remove_extra_spaces=bool(data.get("remove_extra_spaces", True)),
        equation_zoom=_zoom(data.get("equation_zoom", 100)),
        argument_on_closing_paren=bool(data.get("argument_on_closing_paren", False)),
        symbol_dictionary=str(data.get("symbol_dictionary", "mathessible-en")),
        auto_zoom_out=bool(data.get("auto_zoom_out", False)),
        show_preview=bool(data.get("show_preview", False)),
        recognized_functions=_normalize_functions(data.get("recognized_functions")),
        math_autocorrect=_normalize_autocorrect(data.get("math_autocorrect")),
        math_autocorrect_removed=_normalize_removed(data.get("math_autocorrect_removed")),
        removed_words_as_symbols=bool(data.get("removed_words_as_symbols", False)),
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


def function_name(text: str) -> str | None:
    """A recognized function as typed in its dialog, in the case it is kept in; None if not a name."""
    name = text.strip()
    if not name or any(character.isspace() or character == "," for character in name):
        return None
    return _normalize_functions((name,))[0]


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


def _normalize_removed(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(sorted({item.strip() for item in value if isinstance(item, str) and item.strip()}))


# The zoom steps of the equation editor, in percent, as a browser has them.
ZOOM_LEVELS = (50, 67, 80, 90, 100, 110, 125, 150, 175, 200, 250, 300)


# PDF export choices: (value, label) as Settings shows them.
PDF_PAPERS = (("a4", "A4"), ("a5", "A5"), ("a3", "A3"), ("us-letter", "US Letter"), ("us-legal", "US Legal"))
PDF_NUMBER_POSITIONS = (
    ("bottom-center", "Bottom, centred"),
    ("bottom-right", "Bottom, right"),
    ("top-right", "Top, right"),
)
# Typst's standards for each choice ("tagged": a tagged PDF, no standard checked).
PDF_STANDARDS = (
    ("tagged", "Tagged PDF"),
    ("ua-1", "PDF/UA-1 (accessible, checked)"),
    ("ua-1+a-3a", "PDF/UA-1 and PDF/A-3a (accessible and archival)"),
    ("a-3a", "PDF/A-3a (archival)"),
)
PDF_EQUATION_NUMBERING = (("", "None"), ("(1)", "(1), (2), (3)"), ("[1]", "[1], [2], [3]"))
PDF_HEADING_NUMBERING = (("", "None"), ("1.", "1., 2., 3."), ("1.1", "1, 1.1, 1.1.1"))
# Named colours, all dark enough for text on white (WCAG AA); "" is the default black.
PDF_COLOURS = (
    ("", "Default (black)"),
    ("#333333", "Dark grey"),
    ("#1F4E79", "Dark blue"),
    ("#0645AD", "Link blue"),
    ("#1E5E2F", "Dark green"),
    ("#8B1A1A", "Dark red"),
    ("#5B2C6F", "Dark purple"),
)
PDF_COLUMNS = (1, 3)
PDF_FONT_SIZES = (6, 36)
PDF_MARGINS = (0, 100)


def pdf_standards(choice: str) -> tuple[str, ...]:
    """Typst's `pdf_standards` for a PDF_STANDARDS choice."""
    return () if choice == "tagged" else tuple(choice.split("+"))


def _option(value: object, options: tuple[tuple[str, str], ...], default: str) -> str:
    return value if isinstance(value, str) and value in dict(options) else default


def _margins(value: object) -> tuple[int, int, int, int]:
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return tuple(_bounded(margin, 25, PDF_MARGINS) for margin in value)  # type: ignore[return-value]
    return (25, 25, 25, 25)


def _spacing(value: object) -> float:
    return float(value) if isinstance(value, (int, float)) and 0.2 <= value <= 3 else 0.65


# The BRF page sizes Settings allows: cells per line, lines per page.
BRF_CELLS = (10, 100)
BRF_LINES = (5, 100)


def _bounded(value: object, default: int, bounds: tuple[int, int]) -> int:
    """A saved number within `bounds`, or `default`."""
    if isinstance(value, int) and not isinstance(value, bool) and bounds[0] <= value <= bounds[1]:
        return value
    return default


def _zoom(value: object) -> int:
    """A saved zoom, or 100 when it is not one of `ZOOM_LEVELS`."""
    return value if isinstance(value, int) and value in ZOOM_LEVELS else 100
