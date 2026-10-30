"""Control-word completion while typing (`\\al` offers `\\alpha`), and symbol search.

Word shows a list of matching control words as soon as one is begun; here
the list is spoken (the first suggestion and how many there are) and
browsed with Up/Down, Tab takes the current one. Both work on the
converter's own control-word table (`unicodemath.control_words`), like
autocorrect; names spoken for symbols come from the symbol dictionary.

In LaTeX (`latex_completion_at`) the words are the ones the converter's
LaTeX reader knows (`unicodemath.latex_words`), always kept as words, and
after `\\begin{` the environments it builds: taking one writes its
`\\end{...}` too, the caret between the two. After `\\ref{` or `\\cite{`
(`argument_completion_at`) the names are the document's labels or its
bibliography's keys, closed by `}`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from mathessible.templates.template_source import TemplateEdit

SymbolNamer = Callable[[str], str | None]


@dataclass(frozen=True, slots=True)
class Suggestion:
    word: str
    symbol: str

    def speech(self, name: SymbolNamer | None = None) -> str:
        """ "alpha" ("α" is called alpha too), or "le, less than or equal to"."""
        spoken = name(self.symbol) if name is not None else None
        if not spoken or spoken.lower() == self.word.lower():
            return self.word
        return f"{self.word}, {spoken}"

    def label(self, name: SymbolNamer | None = None) -> str:
        """The list text for the search: `\\le  ≤  less than or equal to`."""
        spoken = name(self.symbol) if name is not None else None
        text = f"\\{self.word}   {self.symbol}"
        return f"{text}   {spoken}" if spoken else text


@dataclass(frozen=True, slots=True)
class Completion:
    """The control word begun at `start` (its backslash) up to `end`, and what it may become."""

    start: int
    end: int
    suggestions: tuple[Suggestion, ...]
    index: int = 0
    # "begin" or "end" for an environment's name after `\\begin{` or `\\end{`, "argument" for a label or key
    # after `\\ref{` or `\\cite{` (`start` is the name's), else "".
    environment: str = ""

    @property
    def current(self) -> Suggestion:
        return self.suggestions[self.index]

    def moved(self, step: int) -> Completion:
        """The next (step 1) or previous (-1) suggestion, wrapping around."""
        count = len(self.suggestions)
        return Completion(self.start, self.end, self.suggestions, (self.index + step) % count, self.environment)

    def speech(self, name: SymbolNamer | None = None) -> str:
        return f"{self.current.speech(name)}, {self.index + 1} of {len(self.suggestions)}"


def completion_at(source: str, caret: int, table: Mapping[str, str]) -> Completion | None:
    """The completion for a control word being typed right before `caret`, or None.

    At least one letter after the backslash. None when nothing matches, or
    when the only match is the word already typed in full (nothing to offer).
    """
    caret = max(0, min(caret, len(source)))
    start = caret
    while start > 0 and source[start - 1].isascii() and source[start - 1].isalnum():
        start -= 1
    if start == caret or start == 0 or source[start - 1] != "\\":
        return None
    if start >= 2 and source[start - 2] == "\\":
        return None  # "\\" is a literal backslash, not a control word.
    prefix = source[start:caret]
    words = sorted(word for word in table if word.startswith(prefix))
    if prefix in table:
        words.remove(prefix)
        words.insert(0, prefix)  # The word typed so far first, then the longer ones.
    if not words or words == [prefix]:
        return None
    return Completion(start - 1, caret, tuple(Suggestion(word, table[word]) for word in words))


_ENVIRONMENT_NAME = re.compile(r"\\(begin|end)\s*\{([A-Za-z]*)$")
# A command's name argument begun before the caret: `\\ref{eq:`, `\\cite{knuth, la` (the last of a list).
_ARGUMENT = re.compile(r"\\([A-Za-z]+)\*?\s*(?:\[[^\]]*\]\s*)*\{(?:[^{},]*,\s*)*([^{},\s]*)$")


def argument_completion_at(source: str, caret: int, names: Mapping[str, Sequence[str]]) -> Completion | None:
    """A name begun as a command's argument (`\\ref{eq:` offers `eq:energy`): `names` are each command's
    (`ref`: the document's labels, `cite`: its bibliography's keys). None when nothing matches."""
    caret = max(0, min(caret, len(source)))
    found = _ARGUMENT.search(source, max(0, caret - 200), caret)
    if found is None or found.end() != caret or found.group(1) not in names:
        return None
    prefix = found.group(2)
    matches = sorted({name for name in names[found.group(1)] if name.startswith(prefix) and name != prefix})
    if not matches:
        return None
    return Completion(caret - len(prefix), caret, tuple(Suggestion(name, "") for name in matches), 0, "argument")


def latex_completion_at(
    source: str, caret: int, words: Mapping[str, str], environments: Sequence[str]
) -> Completion | None:
    """In LaTeX: an environment's name begun after `\\begin{`/`\\end{` (`\\begin{pm` offers pmatrix), else a
    control word (`completion_at`)."""
    caret = max(0, min(caret, len(source)))
    found = _ENVIRONMENT_NAME.search(source, 0, caret)
    if found is not None and found.end() == caret:
        prefix = found.group(2)
        names = sorted(name for name in environments if name.startswith(prefix) and name != prefix)
        if not names:
            return None
        start = caret - len(prefix)
        return Completion(start, caret, tuple(Suggestion(name, "") for name in names), 0, found.group(1))
    return completion_at(source, caret, words)


def accept_completion(source: str, completion: Completion, convert: bool) -> TemplateEdit:
    """Replace the begun word with the chosen one: its symbol (`convert`, as Space would), or the word.

    An environment's name is closed (`pmatrix}`); after `\\begin{` its `\\end{pmatrix}` follows, the caret
    between them, where the environment's rows go.
    """
    suggestion = completion.current
    if completion.environment:
        rest = source[completion.end :]
        closing = "" if rest.startswith("}") else "}"
        after = completion.end + (1 if not closing else 0)
        name = suggestion.word
        text = source[: completion.start] + name + closing
        caret = len(text) if closing else completion.start + len(name) + 1
        if completion.environment == "argument":
            if rest[:1] == ",":  # A name in the middle of a list (\\cite{a, |, b}): no brace of its own.
                text = source[: completion.start] + name
                caret = len(text)
            return TemplateEdit(text + source[completion.end :], caret, name)
        if completion.environment == "begin":
            ending = f"\\end{{{name}}}"
            return TemplateEdit(text + source[completion.end : after] + ending + source[after:], caret, name)
        return TemplateEdit(text + source[completion.end :], caret, name)
    replacement = suggestion.symbol if convert else f"\\{suggestion.word}"
    updated = source[: completion.start] + replacement + source[completion.end :]
    caret = completion.start + len(replacement)
    return TemplateEdit(updated, caret, suggestion.word)


def search_symbols(query: str, table: Mapping[str, str], name: SymbolNamer | None = None) -> list[Suggestion]:
    """Control words matching `query`, best first: by word start, inside the word, then by spoken name.

    The symbol itself also matches (searching "≤" finds `\\le`, `\\leq`).
    An empty query lists everything, alphabetically.
    """
    needle = query.strip().lstrip("\\").lower()
    if not needle:
        return [Suggestion(word, table[word]) for word in sorted(table)]
    ranked: list[tuple[int, int, str]] = []
    for word, symbol in table.items():
        lowered = word.lower()
        if lowered.startswith(needle):
            rank = 0
        elif needle in lowered:
            rank = 1
        elif query.strip() == symbol:
            rank = 0
        else:
            spoken = (name(symbol) if name is not None else None) or ""
            if needle not in spoken.lower():
                continue
            rank = 2
        ranked.append((rank, len(word), word))
    return [Suggestion(word, table[word]) for _rank, _length, word in sorted(ranked)]


def symbol_insertion(source: str, caret: int, suggestion: Suggestion, control_words: bool) -> TemplateEdit:
    """Insert a searched symbol at `caret`: as its control word (`control_words`) or the symbol itself.

    A control word gets a space after it when a letter or digit follows,
    or nothing does (the user types there next), as templates do.
    """
    caret = max(0, min(caret, len(source)))
    if control_words:
        following = source[caret : caret + 1]
        text = f"\\{suggestion.word}" + (" " if not following or following.isalnum() else "")
    else:
        text = suggestion.symbol
    return TemplateEdit(source[:caret] + text + source[caret:], caret + len(text), suggestion.word)
