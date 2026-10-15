from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


DEFAULT_RECOGNIZED_FUNCTIONS: tuple[str, ...] = (
    "sin",
    "cos",
    "tan",
    "tg",
    "cot",
    "ctg",
    "sec",
    "csc",
    "log",
    "ln",
    "sqrt",
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
    # Symbol shortcuts (<<, ->, <=) as soon as their last character is typed.
    convert_shortcuts_immediately: bool = True
    # Templates and structure edits write control words (\sum, \sqrt, \of)
    # instead of the symbols they stand for; the converter reads both.
    template_control_words: bool = True
    # Which symbols.dic names symbols in speech (symbol_dictionary.py).
    symbol_dictionary: str = "matex-en"
    auto_zoom_out: bool = False
    show_preview: bool = False
    recognized_functions: tuple[str, ...] = DEFAULT_RECOGNIZED_FUNCTIONS


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
        convert_shortcuts_immediately=bool(data.get("convert_shortcuts_immediately", True)),
        template_control_words=bool(data.get("template_control_words", True)),
        symbol_dictionary=str(data.get("symbol_dictionary", "matex-en")),
        auto_zoom_out=bool(data.get("auto_zoom_out", False)),
        show_preview=bool(data.get("show_preview", False)),
        recognized_functions=_normalize_functions(data.get("recognized_functions")),
    )


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
        if not name or name in seen:
            continue
        result.append(name)
        seen.add(name)
    return tuple(result) or DEFAULT_RECOGNIZED_FUNCTIONS
