"""Linear runs: what was typed into the built equation and is not built yet, as in Word.

Word builds only the part of what you type that has become unambiguous
(UTN #28 sec. 2.3); the rest stays linear text inside the same equation
until a Space or an operator completes it. MateX keeps one source string
and, beside it, the source ranges still linear. For building, every
build-up operator inside them is escaped (`c\\/`, `\\(c`): the converter
then gives each character as an ordinary token (`intent=":text"`), which
looks and reads like Word's linear text, and the source map still aligns
(the backslashes are `BuildRepair` insertions, never in the real source).

The converter still decides what builds: `build_run` only chooses where
to cut a run, trying the longest built part first.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from matex.editing.insertion_point import STRUCTURE_NAMES
from matex.templates.math_templates import NARY_LABELS

Run = tuple[int, int]
Runs = tuple[Run, ...]

# The parser's `opBuildup` (UnicodeMathML/src/unicodemathml-parser.pegjs), "]" and the quote:
# the characters that make structures. Everything else is already an ordinary token.
BUILD_OPERATORS = frozenset(
    "█⒜⒝ⓑⒸⓓⓗⓣ⍁■@&([{⟨〖⌈⌊├)}⟩〗⌉⌋┤|│∣⏜⏝⏞⏟⏠⏡⎴⎵¯∑⅀⨊∏∐⨋∫∬∭⨌∮∯∰∱⨑∲∳⨍⨎⨏⨕⨖⨗⨘⨙⨚⨛⨜⨒⨓⨔"
    '⋀⋁⋂⋃⨃⨄⨅⨆⨀⨁⨂⨉⫿▒ⅅⅆⅇⅈⅉ¦⒞/⁄∕⊘▭̄▁▢○⟌⃧⬭#⟡⬄⇳⬍⬆⬇⬌□√∛∜_^┬┴Ⅎ✎☁⫷⫸ￗ╱╲╳ⒶⒻ]"'
)


def _escaped(source: str, index: int) -> bool:
    """Whether `source[index]` follows an odd run of backslashes (already literal)."""
    count = 0
    while index - count > 0 and source[index - count - 1] == "\\":
        count += 1
    return count % 2 == 1


def operator_positions(source: str, start: int, end: int) -> list[int]:
    """The unescaped build-up operators in `source[start:end]`."""
    return [
        index
        for index in range(start, min(end, len(source)))
        if source[index] in BUILD_OPERATORS and not _escaped(source, index)
    ]


# No leaf, and nothing the converter or MathCAT says (see `escape_insertions`).
_ZERO_WIDTH_SPACE = "\u200b"
_INVISIBLE_TIMES = "\u2062"
_NAME = re.compile(r"[A-Za-z]{2,} *$")


def escape_insertions(source: str, runs: Runs) -> list[tuple[int, str]]:
    """A backslash before each build-up operator inside the runs (`BuildRepair` insertions).

    A text starting `\\(` or `\\[` is taken for LaTeX's `\\( ... \\)` by the
    converter, which then fails: a zero-width space (no leaf) goes first.
    After a name (`log\\_`, `sin \\(`) the converter would make the escaped
    character the function's argument ("the log of under bar"): an
    invisible times keeps them apart, and MathCAT says nothing for it.
    """
    first = len(source) - len(source.lstrip(" "))
    insertions: list[tuple[int, str]] = []
    for start, end in runs:
        for index in operator_positions(source, start, end):
            if index == first and source[index] in "([":
                insertions.append((index, _ZERO_WIDTH_SPACE + "\\"))
            elif _NAME.search(source, 0, index):
                insertions.append((index, _INVISIBLE_TIMES + "\\"))
            else:
                insertions.append((index, "\\"))
    return insertions


def inside(runs: Runs, offset: int) -> bool:
    return any(start <= offset < end for start, end in runs)


def edit_between(before: str, after: str, caret: int | None = None) -> tuple[int, int, int]:
    """(position, removed, inserted) of the one splice that turns `before` into `after`.

    With `caret` (where the caret is after the edit) an ambiguous splice
    ("a" typed after "a") is put so that it ends at the caret.
    """
    shorter = min(len(before), len(after))
    suffix_limit = shorter if caret is None else min(shorter, max(0, len(after) - caret))
    suffix = 0
    while suffix < suffix_limit and before[len(before) - 1 - suffix] == after[len(after) - 1 - suffix]:
        suffix += 1
    prefix = 0
    while prefix < shorter - suffix and before[prefix] == after[prefix]:
        prefix += 1
    return prefix, len(before) - prefix - suffix, len(after) - prefix - suffix


def shift_runs(runs: Runs, position: int, removed: int, inserted: int) -> Runs:
    """The runs after an edit that is not typing: moved with the text, dropped where it touched them."""
    end = position + removed
    shifted: list[Run] = []
    for start, stop in runs:
        if stop <= position:
            shifted.append((start, stop))
        elif start >= end:
            delta = inserted - removed
            shifted.append((start + delta, stop + delta))
    return tuple(shifted)


def typed(runs: Runs, position: int, removed: int, inserted: int) -> Runs:
    """The runs after typing (or Backspace/Delete) at `position`.

    An edit within a run or at its edge grows or shrinks that run; typing
    anywhere else starts a new one. Deleting outside every run starts none.
    """
    end = position + removed
    result: list[Run] = []
    joined = False
    for start, stop in runs:
        if not joined and start <= position and end <= stop:
            grown = (start, stop - removed + inserted)
            if grown[1] > grown[0]:
                result.append(grown)
            joined = True
        elif stop <= position:
            result.append((start, stop))
        elif start >= end:
            delta = inserted - removed
            result.append((start + delta, stop + delta))
        # Else the edit overlapped the run's edge from outside: it is gone.
    if not joined and inserted:
        result.append((position, position + inserted))
    return tuple(sorted(result))


def run_at(runs: Runs, offset: int) -> Run | None:
    """The run holding `offset`, or ending right at it (the caret after what was just typed)."""
    for start, end in runs:
        if start <= offset <= end:
            return (start, end)
    return None


def split_candidates(source: str, run: Run) -> list[int]:
    """Where a run may be cut, longest built part first: its end, before each operator, its start."""
    start, end = run
    cuts = [end] + [index for index in reversed(operator_positions(source, start, end)) if index > start]
    return [*cuts, start] if start not in cuts else cuts


def errors(mathml: str) -> int:
    """The converter's error markers: a dangling token (#F01) or a total failure (#F00)."""
    return mathml.count('mathcolor="#F0')


def build_run(source: str, runs: Runs, run: Run, convert: Callable[[Runs], str]) -> Runs:
    """`runs` with `run` built as far as it builds: what is left of it stays linear.

    `convert(runs)` is the converter's MathML for the source with those
    runs linear. The longest built part that adds no error marker to
    keeping the whole run linear wins; an error elsewhere in the equation
    never stops the run from building.
    """
    others = tuple(other for other in runs if other != run)
    start, end = run
    baseline = errors(convert(runs))
    for cut in split_candidates(source, run):
        if cut == start:
            break
        rest = ((cut, end),) if cut < end else ()
        candidate = tuple(sorted(others + rest))
        if errors(convert(candidate)) <= baseline:
            return candidate
    return runs


_OPENING_TAG = re.compile(r"<(m[a-z]+)[\s>/]")
_SCRIPT_TAGS = frozenset({"msub", "msup", "msubsup", "munder", "mover", "munderover"})
_FIRST_OPERATOR = re.compile(r"\s*<mo[^>]*>([^<]*)</mo>")


def built_structure(before: str, after: str) -> str | None:
    """The kind of structure a run built ("fraction"), from the MathML before and after it built.

    The first kind there is more of, outermost first ("fraction" for a
    fraction with a superscript in it); None when nothing new was built.
    Scripts on an n-ary sign are its limits: "integral", not "scripts".
    """
    old, new = _OPENING_TAG.findall(before), _OPENING_TAG.findall(after)
    for match in _OPENING_TAG.finditer(after):
        tag = match.group(1)
        if tag in STRUCTURE_NAMES and new.count(tag) > old.count(tag):
            operator = _FIRST_OPERATOR.match(after, match.end() + after[match.end() - 1 :].index(">"))
            if tag in _SCRIPT_TAGS and operator is not None and operator.group(1).strip() in NARY_LABELS:
                return NARY_LABELS[operator.group(1).strip()]
            return STRUCTURE_NAMES[tag]
    return None


def toggle_selection(runs: Runs, start: int, end: int) -> tuple[Runs, bool]:
    """F2 on a selection in the built equation, as Word's Linear/Professional on one: (runs, made linear).

    A selection holding linear text builds it (every run it touches);
    otherwise the selection becomes a linear run of its own.
    """
    touched = [run for run in runs if run[0] < end and start < run[1]]
    if touched:
        return tuple(run for run in runs if run not in touched), False
    return tuple(sorted((*runs, (start, end)))), True
