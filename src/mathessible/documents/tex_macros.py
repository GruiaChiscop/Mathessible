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
_NAME_SPACE = re.compile(r"\\[,;:! ]|[~\s]")
_COMMENT = re.compile(r"(?<!\\)%.*$", re.MULTILINE)
# Expansions per equation: more means a command that expands into itself (`\def\a{\a}`).
_EXPANSION_LIMIT = 500


@dataclass(frozen=True, slots=True)
class LatexMacro:
    """A defined command: its arguments, the default of an optional first one (None without), its body;
    an `operator`'s body is its name (`\\DeclareMathOperator{\\tr}{tr}`)."""

    parameters: int
    default: str | None
    body: str
    operator: bool = False


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
            macro = LatexMacro(0, None, body[0], operator=True)
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


def _operator(latex: str, end: int, name: str) -> tuple[str, int]:
    """A declared operator's name at `end` (its scripts after it): upright, then its scripts, then the
    function application (U+2061), so that it builds, reads and brailles as a function (`tr` of A) and
    MathCAT writes it back as `\\operatorname{tr}`."""
    scripts = ""
    while True:
        position = _skip_spaces(latex, end)
        limits = re.match(r"\\(?:no)?limits(?![A-Za-z])", latex[position:])
        if limits:
            end = position + limits.end()
            continue
        if latex[position : position + 1] in ("_", "^") and position < len(latex):
            argument = _argument(latex, position + 1)
            if argument is None:
                break
            scripts += f"{latex[position]}{{{argument[0]}}}"
            end = argument[1]
            continue
        break
    # A space in the name (`arg\\,max`) splits it in the converter: the name is built without it.
    name = _NAME_SPACE.sub("", name)
    return f"\\mathrm{{{name}}}{scripts}\u2061", end


def expand_macros(latex: str, macros: Mapping[str, LatexMacro]) -> str:
    """An equation with the document's commands (and its own) expanded, and its definitions removed."""
    definitions = _definitions(latex)
    for definition in reversed(definitions):
        latex = latex[: definition.start] + latex[definition.end :]
    macros = {**macros, **{definition.name: definition.macro for definition in definitions}}
    if not macros and "\\operatorname" not in latex:
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
        if name == "operatorname":
            # `\operatorname{tr}`, which the converter does not know, is built as a declared operator.
            star = word.end() + (latex[word.end() : word.end() + 1] == "*")
            text = _argument(latex, star)
            if text is not None:
                replacement, end = _operator(latex, text[1], text[0])
                latex = latex[:backslash] + replacement + latex[end:]
                position = backslash + len(replacement)
                expansions += 1
                continue
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
        if macro.operator:
            replacement, end = _operator(latex, end, macro.body)
            latex = latex[:backslash] + replacement + latex[end:]
            position = backslash + len(replacement)
            expansions += 1
            continue
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


# Letters standing for a command's arguments while MathCAT writes its body (`\vect{Q}` as `\mathbf Q`).
PLACEHOLDERS = ("Q", "W", "K", "Z")


def macro_sample(name: str, macro: LatexMacro) -> str | None:
    """The command with placeholder arguments (`\\vect{Q}`), whose expansion MathCAT writes for
    `fold_macros`; None for an operator (folded by its name) or a command with too many arguments."""
    if macro.operator or macro.parameters > len(PLACEHOLDERS):
        return None
    arguments = PLACEHOLDERS[: macro.parameters]
    if macro.default is not None and arguments:
        return f"\\{name}[{arguments[0]}]" + "".join(f"{{{argument}}}" for argument in arguments[1:])
    return f"\\{name}" + "".join(f"{{{argument}}}" for argument in arguments)


def _pieces(written: str) -> list[str | int]:
    """MathCAT's LaTeX of a sample as literal text and holes (the placeholders' argument numbers)."""
    pieces: list[str | int] = []
    literal = ""
    index = 0
    while index < len(written):
        word = _CONTROL_WORD.match(written, index)
        if word:
            literal += word.group(0)
            index = word.end()
            continue
        if written[index] in PLACEHOLDERS:
            if literal:
                pieces.append(literal)
            pieces.append(PLACEHOLDERS.index(written[index]))
            literal = ""
        else:
            literal += written[index]
        index += 1
    if literal:
        pieces.append(literal)
    return pieces


def _match_literal(latex: str, position: int, literal: str) -> int | None:
    """Where `literal` ends when it is found at `position`, spaces on either side not counted."""
    for character in literal:
        if character.isspace():
            continue
        position = _skip_spaces(latex, position)
        if latex[position : position + 1] != character:
            return None
        position += 1
    if re.search(r"\\[A-Za-z]+$", literal.rstrip()) and latex[position : position + 1].isalpha():
        return None  # `\epsilon` is not the start of `\epsilonx`.
    return position


def _balanced(text: str) -> bool:
    depth = 0
    index = 0
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        depth += {"{": 1, "}": -1}.get(text[index], 0)
        if depth < 0:
            return False
        index += 1
    return depth == 0


def _match(latex: str, position: int, pieces: list[str | int], holes: dict[int, str]) -> int | None:
    """Where `pieces` end when they are found at `position` (`holes` filled with the arguments)."""
    if not pieces:
        return position
    piece, rest = pieces[0], pieces[1:]
    if isinstance(piece, str):
        end = _match_literal(latex, position, piece)
        return None if end is None else _match(latex, end, rest, holes)
    start = _skip_spaces(latex, position)
    group = _group(latex, start)
    candidates: list[tuple[str, int]] = [group] if group is not None else []
    if not rest:
        token = _argument(latex, start)
        candidates += [token] if token is not None and group is None else []
    else:
        candidates += [(latex[start:end], end) for end in range(start + 1, len(latex) + 1)]
    for content, end in candidates:
        if not content.strip() or not _balanced(content) or (piece in holes and holes[piece] != content):
            continue
        tried = {**holes, piece: content}
        found = _match(latex, end, rest, tried)
        if found is not None:
            holes.update(tried)
            return found
    return None


def fold_macros(latex: str, macros: Mapping[str, LatexMacro], written: Mapping[str, str]) -> str:
    """LaTeX MathCAT wrote for an edited equation, with the document's commands put back: each command's
    body as MathCAT writes it (`written`, by name, from `macro_sample`) becomes the command again
    (`\\mathbb R` is `\\R`), and an operator's `\\operatorname{tr}` its `\\tr`. The caller checks
    that the result builds as the LaTeX did."""
    for name, macro in macros.items():
        if not macro.operator or not name.isalpha():
            continue
        operator = re.compile(r"\\operatorname\*?\{" + re.escape(_NAME_SPACE.sub("", macro.body)) + r"\}")
        latex = operator.sub(
            lambda found, name=name: (
                f"\\{name}" + (" " if found.string[found.end() : found.end() + 1].isalpha() else "")
            ),
            latex,
        )
    patterns = []
    for name, text in written.items():
        macro = macros.get(name)
        pieces = _pieces(text)
        literal = "".join(piece for piece in pieces if isinstance(piece, str))
        # A body written without a command (`x`) would fold every x of the equation.
        if macro is not None and name.isalpha() and "\\" in literal:
            patterns.append((len(text), name, macro, pieces))
    patterns.sort(key=lambda pattern: -pattern[0])  # The longest body first: `\frac{\partial Q}{...}`.
    for _length, name, macro, pieces in patterns:
        position = 0
        while position < len(latex):
            holes: dict[int, str] = {}
            end = _match(latex, position, pieces, holes) if not latex[position].isspace() else None
            if end is None:
                position += 1
                continue
            arguments = [holes.get(number, "") for number in range(macro.parameters)]
            optional = arguments[0].strip() if arguments else ""
            if macro.default is not None and optional in (macro.default.strip(), f"{{{macro.default.strip()}}}"):
                # The optional argument as its default is left out (`\pd{f}{x}`, not `\pd[{}]{f}{x}`).
                command = f"\\{name}" + "".join(f"{{{argument}}}" for argument in arguments[1:])
            elif macro.default is not None and arguments:
                command = f"\\{name}[{arguments[0]}]" + "".join(f"{{{argument}}}" for argument in arguments[1:])
            else:
                command = f"\\{name}" + "".join(f"{{{argument}}}" for argument in arguments)
            if not arguments and latex[end : end + 1].isalpha():
                command += " "
            latex = latex[:position] + command + latex[end:]
            position += len(command)
    return latex
