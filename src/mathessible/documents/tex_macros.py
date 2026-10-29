"""A LaTeX document's own commands (`\\newcommand{\\R}{\\mathbb{R}}`), expanded in its equations before they are built.

Papers define their notation: `\\newcommand`, `\\renewcommand`,
`\\providecommand` (with arguments, `[2]`, and an optional first one's
default, `[2][x]`), `\\def\\R{...}` (`\\def\\pd#1#2{...}`) and
`\\DeclareMathOperator{\\tr}{tr}`. The converter knows none of them (its own
`\\newcommand` works only within one equation and is unreliable), so an
equation is built, read, brailled and exported with them expanded; the
equation's source keeps them as typed. The definitions are found anywhere
in a .tex file (outside comments), and in a Markdown document's LaTeX,
whose equations may hold them as MathJax allows (`$\\newcommand{\\R}{...}$`).
Expansion is text substitution, as TeX's own, with a limit for a command
that expands into itself.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from mathessible.documents.markdown_math import find_math_zones

_DEFINITION = re.compile(r"\\(?:(?:new|renew|provide)command|DeclareMathOperator|def)(?![A-Za-z])\*?")
_CONTROL_WORD = re.compile(r"\\([A-Za-z]+|.)")
_ENDS_IN_CONTROL_WORD = re.compile(r"(?<!\\)\\[A-Za-z]+$")
_PARAMETER = re.compile(r"#([1-9#])")
_COMMENT = re.compile(r"(?<!\\)%.*$", re.MULTILINE)
# Expansions per equation: more means a command that expands into itself (`\def\a{\a}`).
_EXPANSION_LIMIT = 500


@dataclass(frozen=True, slots=True)
class LatexMacro:
    """A defined command: its arguments, the default of an optional first one (None without), its body."""

    parameters: int
    default: str | None
    body: str


@dataclass(frozen=True, slots=True)
class _Definition:
    start: int
    end: int
    name: str
    macro: LatexMacro


def _skip_spaces(latex: str, position: int) -> int:
    while position < len(latex) and latex[position] in " \t\n":
        position += 1
    return position


def _group(latex: str, position: int) -> tuple[str, int] | None:
    """The braced group opening at `position`: its content and where it ends."""
    if position >= len(latex) or latex[position] != "{":
        return None
    depth = 0
    index = position
    while index < len(latex):
        if latex[index] == "\\":
            index += 2
            continue
        if latex[index] == "{":
            depth += 1
        elif latex[index] == "}":
            depth -= 1
            if depth == 0:
                return latex[position + 1 : index], index + 1
        index += 1
    return None


def _optional(latex: str, position: int) -> tuple[str, int] | None:
    """The bracketed argument opening at `position` (`[2]`, `[x_0]`): its content and where it ends."""
    if position >= len(latex) or latex[position] != "[":
        return None
    depth = 0
    for index in range(position, len(latex)):
        if latex[index] == "{":
            depth += 1
        elif latex[index] == "}":
            depth -= 1
        elif latex[index] == "]" and depth == 0:
            return latex[position + 1 : index], index + 1
    return None


def _argument(latex: str, position: int) -> tuple[str, int] | None:
    """A command's argument at `position`, spaces skipped: a braced group's content, else one token."""
    position = _skip_spaces(latex, position)
    if position >= len(latex) or latex[position] == "}":
        return None
    group = _group(latex, position)
    if group is not None:
        return group
    word = _CONTROL_WORD.match(latex, position)
    end = word.end() if word else position + 1
    return latex[position:end], end


def _name(latex: str, position: int) -> tuple[str, int] | None:
    """The command being defined: `{\\R}` or `\\R`."""
    position = _skip_spaces(latex, position)
    group = _group(latex, position)
    if group is not None:
        word = _CONTROL_WORD.fullmatch(group[0].strip())
        return (word.group(1), group[1]) if word else None
    word = _CONTROL_WORD.match(latex, position)
    return (word.group(1), word.end()) if word else None


def _definitions(latex: str) -> list[_Definition]:
    found: list[_Definition] = []
    for definition in _DEFINITION.finditer(latex):
        if found and definition.start() < found[-1].end:
            continue  # Inside the body of the one before (`\newcommand{\a}{\def\b{}}`).
        named = _name(latex, definition.end())
        if named is None:
            continue
        name, position = named
        kind = definition.group(0).rstrip("*")
        if kind == "\\def":
            # `\def\pd#1#2{...}`: the parameters are the #n before the body.
            brace = latex.find("{", position)
            if brace < 0:
                continue
            parameters = len(re.findall(r"#[1-9]", latex[position:brace]))
            body = _group(latex, brace)
            if body is None:
                continue
            found.append(_Definition(definition.start(), body[1], name, LatexMacro(parameters, None, body[0])))
            continue
        if kind == "\\DeclareMathOperator":
            body = _group(latex, _skip_spaces(latex, position))
            if body is None:
                continue
            macro = LatexMacro(0, None, f"\\mathrm{{{body[0]}}}")
            found.append(_Definition(definition.start(), body[1], name, macro))
            continue
        parameters, default = 0, None
        position = _skip_spaces(latex, position)
        count = _optional(latex, position)
        if count is not None and count[0].strip().isdigit():
            parameters, position = int(count[0]), _skip_spaces(latex, count[1])
            given = _optional(latex, position)
            if given is not None:
                default, position = given[0], _skip_spaces(latex, given[1])
        body = _group(latex, position)
        if body is None:
            continue
        found.append(_Definition(definition.start(), body[1], name, LatexMacro(parameters, default, body[0])))
    return found


def find_macros(latex: str) -> dict[str, LatexMacro]:
    """The commands `latex` defines, by name (without its backslash); a later definition wins."""
    return {definition.name: definition.macro for definition in _definitions(latex)}


def document_macros(source: str, tex: bool) -> dict[str, LatexMacro]:
    """The commands a document defines: a .tex file anywhere outside its comments, Markdown anywhere."""
    return find_macros(_COMMENT.sub("", source) if tex else source)


def _substitute(body: str, arguments: list[str]) -> str:
    def argument(found: re.Match[str]) -> str:
        if found.group(1) == "#":
            return "#"
        number = int(found.group(1))
        return arguments[number - 1] if number <= len(arguments) else ""

    return _PARAMETER.sub(argument, body)


def expand_macros(latex: str, macros: Mapping[str, LatexMacro]) -> str:
    """An equation with the document's commands (and its own) expanded, and its definitions removed."""
    definitions = _definitions(latex)
    for definition in reversed(definitions):
        latex = latex[: definition.start] + latex[definition.end :]
    macros = {**macros, **{definition.name: definition.macro for definition in definitions}}
    if not macros:
        return latex
    position = 0
    expansions = 0
    while position < len(latex) and expansions < _EXPANSION_LIMIT:
        backslash = latex.find("\\", position)
        if backslash < 0:
            break
        word = _CONTROL_WORD.match(latex, backslash)
        name = word.group(1) if word else ""
        macro = macros.get(name)
        if word is None or macro is None:
            position = backslash + (len(word.group(0)) if word else 1)
            continue
        end = word.end()
        arguments: list[str] = []
        if macro.default is not None:
            given = _optional(latex, _skip_spaces(latex, end))
            if given is not None:
                arguments.append(given[0])
                end = given[1]
            else:
                arguments.append(macro.default)
        while len(arguments) < macro.parameters:
            argument = _argument(latex, end)
            if argument is None:
                break
            arguments.append(argument[0])
            end = argument[1]
        if macro.parameters == 0 and name.isalpha():
            end = _skip_spaces(latex, end)  # TeX drops the spaces after a control word.
        replacement = _substitute(macro.body, arguments)
        if _ENDS_IN_CONTROL_WORD.search(replacement) and latex[end : end + 1].isalpha():
            replacement += " "  # `\e x` with `\e` as `\epsilon` is `\epsilon x`, not `\epsilonx`.
        latex = latex[:backslash] + replacement + latex[end:]
        position = backslash  # The replacement may use other commands.
        expansions += 1
    return latex


def expand_markdown_macros(source: str) -> str:
    """A Markdown document with LaTeX equations, its commands expanded in each equation, for the
    preview and the exports; the document itself keeps them."""
    macros = document_macros(source, tex=False)
    if not macros:
        return source
    pieces: list[str] = []
    position = 0
    for zone in find_math_zones(source):
        start, end = zone.content_start, zone.content_end
        pieces.append(source[position:start])
        pieces.append(expand_macros(source[start:end], macros))
        position = end
    pieces.append(source[position:])
    return "".join(pieces)
