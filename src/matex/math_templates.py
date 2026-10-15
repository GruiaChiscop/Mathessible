from __future__ import annotations

from dataclasses import dataclass


MAX_MATRIX_SIZE = 10
# Fence name -> (opening, closing) characters wrapped around the bare `■(...)`.
# Only fences the real converter groups cleanly are offered: `(`/`[` give an
# `intent=":fenced"` mrow and `|` a `determinant($a)` one, but `‖` comes back
# as two loose `<mo>`s around the table, so it is deliberately left out.
MATRIX_FENCES = {
    "none": ("", ""),
    "parentheses": ("(", ")"),
    "brackets": ("[", "]"),
    "bars": ("|", "|"),
}
_CLOSING_FENCES = {"(": ")", "[": "]", "|": "|"}
# N-ary operators whose `_(...)`/`^(...)` groups are limits, not scripts.
NARY_LABELS = {"∫": "integral", "∬": "integral", "∭": "integral", "∮": "integral", "∑": "sum", "∏": "product"}
# Functions whose `_(...)` is part of the function: (template, slot role).
# The argument follows a space ("lim_(n→∞) a_n"): with no separator the
# converter folds it into the subscript, and "▒" is a parse error there.
FUNCTION_SCRIPTS = {"lim": ("limit", "limit condition"), "log": ("logarithm", "base")}
# Word's operator structures: an operator with text above (`→┴(...)`) or
# below (`→┬(...)`); both stack as `→┬(below)┴(above)`. Like lim, a space
# must follow, or the converter folds the next operand into the text.
OPERATOR_TEXT_ROLES = {"┴": "text above", "┬": "text below"}
ARROWS = frozenset("→←↔⇒⇐⇔⟶⟵⟷⟹⟸⟺↦⇌")
# What Tab past a template's last slot lands in, after its "▒" or space
# (the n-ary names are the ones MathMLDocument uses too).
NARYAND_ROLES = {
    "integral": "integrand",
    "sum": "summand",
    "product": "factor",
    "limit": "argument",
    "logarithm": "argument",
}


@dataclass(frozen=True, slots=True)
class TemplateEdit:
    source: str
    caret: int
    announcement: str


@dataclass(frozen=True, slots=True)
class _MatrixCell:
    start: int
    end: int
    row: int
    column: int
    matrix_open: int
    matrix_close: int


def insert_fraction_template(source: str, caret: int) -> TemplateEdit:
    return _insert_template(source, caret, "()/()", first_slot_offset=1, announcement="fraction template, empty numerator")


def insert_square_root_template(source: str, caret: int) -> TemplateEdit:
    return _insert_template(source, caret, "√()", first_slot_offset=2, announcement="square root template, empty radicand")


def insert_limit_template(source: str, caret: int) -> TemplateEdit:
    """`lim_() `: caret in the limit condition; Tab goes on to the argument."""
    return _insert_template(source, caret, "lim_() ", first_slot_offset=5, announcement="limit template, empty limit condition")


def insert_logarithm_template(source: str, caret: int) -> TemplateEdit:
    """`log_() `: caret in the base; Tab goes on to the argument. An empty base is fine."""
    return _insert_template(source, caret, "log_() ", first_slot_offset=5, announcement="logarithm template, empty base")


def insert_operator_template(source: str, caret: int, operator: str = "→", above: bool = True) -> TemplateEdit:
    """`→┴() `/`→┬() `: an operator with text above/below, caret in the text."""
    mark = "┴" if above else "┬"
    label = _operator_label(operator)
    return _insert_template(
        source,
        caret,
        f"{operator}{mark}() ",
        first_slot_offset=len(operator) + 2,
        announcement=f"{label} template, empty {OPERATOR_TEXT_ROLES[mark]}",
    )


def insert_root_template(source: str, caret: int) -> TemplateEdit:
    """`√(&)`: an n-th root, caret in the index; Tab goes on to the radicand.

    Unlike empty n-ary limits, an empty index is a parse error for the
    converter (`√(&x)` fails, `√(3&x)` is an mroot), the usual transient
    state of a template that has not been filled in yet.
    """
    return _insert_template(source, caret, "√(&)", first_slot_offset=2, announcement="root template, empty index")


def insert_absolute_value_template(source: str, caret: int) -> TemplateEdit:
    return _insert_template(source, caret, "|()|", first_slot_offset=2, announcement="absolute value template, empty value")


def insert_integral_template(source: str, caret: int, limits: bool = False) -> TemplateEdit:
    return _insert_nary_template(source, caret, symbol="∫", limits=limits)


def insert_sum_template(source: str, caret: int, limits: bool = False) -> TemplateEdit:
    return _insert_nary_template(source, caret, symbol="∑", limits=limits)


def insert_product_template(source: str, caret: int, limits: bool = False) -> TemplateEdit:
    return _insert_nary_template(source, caret, symbol="∏", limits=limits)


def _insert_nary_template(source: str, caret: int, symbol: str, limits: bool) -> TemplateEdit:
    """Insert an n-ary operator sign, caret ready to type the naryand or its limits.

    With `limits`, `∫_()^()▒`: the caret starts in the lower limit, Tab goes
    to the upper one and then past `▒` to the naryand. Empty limits are fine
    for the converter (zero-width `mspace`s, like empty matrix cells, and
    "()" around a limit is transparent), so they can simply be left empty.

    Unlike `/`, `√`, `_`, `^` and `|`, UnicodeMath's n-ary delimiter `▒`
    never makes a following "()" transparent (confirmed against the real
    converter: `∫▒(f(x))` keeps visible parens around the integrand, even
    though `∫▒f(x)` alone renders cleanly). So there is no empty-slot
    placeholder here — the caret is simply placed right after `▒`, and the
    user types the naryand directly, same as in Word once the structure
    exists. A bare "∫▒"/"∑▒"/"∏▒" with nothing typed after it is itself a
    total parse failure (confirmed empirically), same as any other
    freshly-inserted, not-yet-filled template — not a bug, just the
    expected transient state before typing.

    Without limits, the caret is placed right after `▒`.
    """
    label = NARY_LABELS[symbol]
    if limits:
        return _insert_template(
            source, caret, f"{symbol}_()^()▒", first_slot_offset=3, announcement=f"{label} template, empty lower limit"
        )
    return _insert_template(source, caret, f"{symbol}▒", first_slot_offset=2, announcement=f"{label} template")


def insert_matrix_template(source: str, caret: int, rows: int, columns: int, fence: str = "parentheses") -> TemplateEdit:
    """Insert a rows x columns matrix with every cell empty, caret in the first.

    Cells are left genuinely empty (`■(&@&)`) rather than filled with "()"
    placeholders: the real converter keeps "()" inside an `mtd` as visible
    parens (an `intent=":fenced"` mrow), while an empty cell becomes a plain
    zero-width `mspace` and is not flagged as a parse error. Empty cells are
    found as Tab-able slots by `_matrix_cells`, not by the "()" scan.
    """
    if not (1 <= rows <= MAX_MATRIX_SIZE and 1 <= columns <= MAX_MATRIX_SIZE):
        raise ValueError(f"matrix size must be between 1 and {MAX_MATRIX_SIZE} in each direction")
    try:
        opening, closing = MATRIX_FENCES[fence]
    except KeyError:
        raise ValueError(f"unknown matrix fence: {fence}") from None
    body = "@".join("&" * (columns - 1) for _row in range(rows))
    label = "determinant" if fence == "bars" else "matrix"
    return _insert_template(
        source,
        caret,
        f"{opening}■({body}){closing}",
        first_slot_offset=len(opening) + 2,
        announcement=f"{rows} by {columns} {label} template, empty cell, row 1, column 1",
    )


@dataclass(frozen=True, slots=True)
class MatrixPosition:
    row: int
    column: int
    rows: int
    columns: int
    # Which matrix, counting every `■(` in source order from 0 — the same
    # order as the `mtable`s in the converter's MathML.
    index: int


def matrix_position_at(source: str, caret: int) -> MatrixPosition | None:
    """Where the caret sits in the innermost matrix around it, if any."""
    found = _matrix_at(source, caret)
    if found is None:
        return None
    cell, grid = found
    index = _matrix_opens(source).index(cell.matrix_open)
    return MatrixPosition(cell.row, cell.column, len(grid), max(len(row) for row in grid), index)


def matrix_count(source: str) -> int:
    return len(_matrix_opens(source))


def matrix_cell_caret(source: str, index: int, row: int, column: int) -> int | None:
    """A caret inside a matrix cell given by matrix index and 1-based row/column.

    A row shorter than `column` (rows may be ragged) gives its last cell.
    """
    opens = _matrix_opens(source)
    if not 0 <= index < len(opens):
        return None
    in_row = [cell for cell in _matrix_cells(source) if cell.matrix_open == opens[index] and cell.row == row]
    if not in_row:
        return None
    return in_row[min(column, len(in_row)) - 1].start


def _matrix_opens(source: str) -> list[int]:
    return sorted({cell.matrix_open for cell in _matrix_cells(source)})


def insert_matrix_row(source: str, caret: int, below: bool = True) -> TemplateEdit | None:
    found = _matrix_at(source, caret)
    if found is None:
        return None
    cell, grid = found
    index = cell.row if below else cell.row - 1
    grid.insert(index, [""] * max(len(row) for row in grid))
    return _rebuild_matrix(source, cell, grid, index, cell.column - 1, f"inserted row {index + 1}")


def insert_matrix_column(source: str, caret: int, right: bool = True) -> TemplateEdit | None:
    found = _matrix_at(source, caret)
    if found is None:
        return None
    cell, grid = found
    index = cell.column if right else cell.column - 1
    for row in grid:
        # Rows may be ragged in UnicodeMath; pad a short one with empty cells
        # so the new column lands at the same position in every row.
        row.extend([""] * (index - len(row)))
        row.insert(index, "")
    return _rebuild_matrix(source, cell, grid, cell.row - 1, index, f"inserted column {index + 1}")


def delete_matrix_row(source: str, caret: int) -> TemplateEdit | None:
    """Remove the caret's row; None if it is the only one (delete the matrix instead)."""
    found = _matrix_at(source, caret)
    if found is None or len(found[1]) < 2:
        return None
    cell, grid = found
    del grid[cell.row - 1]
    row = min(cell.row - 1, len(grid) - 1)
    return _rebuild_matrix(source, cell, grid, row, cell.column - 1, f"deleted row {cell.row}")


def delete_matrix_column(source: str, caret: int) -> TemplateEdit | None:
    """Remove the caret's column; None if it is the only one."""
    found = _matrix_at(source, caret)
    if found is None or max(len(row) for row in found[1]) < 2:
        return None
    cell, grid = found
    for row in grid:
        if len(row) >= cell.column:
            del row[cell.column - 1]
    # A ragged row that only had the deleted cell still needs one empty cell.
    grid = [row or [""] for row in grid]
    return _rebuild_matrix(source, cell, grid, cell.row - 1, cell.column - 1, f"deleted column {cell.column}")


def _matrix_at(source: str, caret: int) -> tuple[_MatrixCell, list[list[str]]] | None:
    """The innermost cell around the caret, plus its matrix as a grid of cell texts."""
    caret = max(0, min(caret, len(source)))
    cells = _matrix_cells(source)
    around = [cell for cell in cells if cell.start <= caret <= cell.end]
    if not around:
        return None
    # A nested matrix opens after the outer one, so the innermost is the latest.
    cell = max(around, key=lambda candidate: candidate.matrix_open)
    grid: list[list[str]] = []
    for other in cells:
        if other.matrix_open != cell.matrix_open:
            continue
        if other.row > len(grid):
            grid.append([])
        grid[-1].append(source[other.start : other.end])
    return cell, grid


def _rebuild_matrix(
    source: str, cell: _MatrixCell, grid: list[list[str]], row: int, column: int, action: str
) -> TemplateEdit:
    """Write the grid back as the matrix body, caret at the start of (row, column).

    The column is clamped to the target row's length, since rows may be ragged.
    """
    column = min(column, len(grid[row]) - 1)
    body = ""
    caret = cell.matrix_open + 1
    for row_index, cells in enumerate(grid):
        if row_index:
            body += "@"
        for column_index, text in enumerate(cells):
            if column_index:
                body += "&"
            if (row_index, column_index) == (row, column):
                caret = cell.matrix_open + 1 + len(body)
            body += text
    edited = source[: cell.matrix_open + 1] + body + source[cell.matrix_close :]
    label = _matrix_label(source, cell)
    columns = max(len(cells) for cells in grid)
    content = "" if grid[row][column] else "empty cell, "
    return TemplateEdit(
        edited,
        caret,
        f"{action}, {len(grid)} by {columns} {label}, {content}row {row + 1}, column {column + 1}",
    )


def _matrix_label(source: str, cell: _MatrixCell) -> str:
    symbol, after_matrix = cell.matrix_open - 1, cell.matrix_close + 1
    is_determinant = symbol > 0 and after_matrix < len(source) and source[symbol - 1] == source[after_matrix] == "|"
    return "determinant" if is_determinant else "matrix"


def insert_subscript_template(source: str, caret: int) -> TemplateEdit:
    return _insert_script_template(source, caret, connector="_", label="subscript")


def insert_superscript_template(source: str, caret: int) -> TemplateEdit:
    return _insert_script_template(source, caret, connector="^", label="superscript")


def _insert_script_template(source: str, caret: int, connector: str, label: str) -> TemplateEdit:
    """Insert an empty subscript/superscript slot, reusing an existing base.

    Unlike `/` and `√`, UnicodeMath's `_`/`^` only make the *argument*'s
    parens transparent, not the base's: `x_(i)` renders as plain x-sub-i, but
    `(x)_(i)` keeps the parens around x visibly. So a base placeholder is
    only inserted when there is nothing usable immediately before the caret
    (a letter, digit, or closing bracket) to attach the script to instead.
    """
    caret = max(0, min(caret, len(source)))
    has_base = caret > 0 and (source[caret - 1].isalnum() or source[caret - 1] in ")]}")
    if has_base:
        # Offset 2: past the connector and the slot's opening "(".
        return _insert_template(
            source, caret, f"{connector}()", first_slot_offset=2, announcement=f"{label} template, empty {label}"
        )
    return _insert_template(
        source, caret, f"(){connector}()", first_slot_offset=1, announcement=f"{label} template, empty base"
    )


def _insert_template(source: str, caret: int, template: str, first_slot_offset: int, announcement: str) -> TemplateEdit:
    caret = max(0, min(caret, len(source)))
    return TemplateEdit(
        source=source[:caret] + template + source[caret:],
        caret=caret + first_slot_offset,
        announcement=announcement,
    )


@dataclass(frozen=True, slots=True)
class _Slot:
    """A template argument the caret can Tab to, filled or empty.

    `start`/`end` bound its content (inside the "(...)" for a group);
    `exit` is where Tab lands when it leaves the template.
    """

    start: int
    end: int
    template: str
    role: str
    exit: int


def move_to_slot(source: str, caret: int, reverse: bool = False) -> TemplateEdit | None:
    """Tab/Shift+Tab: the next/previous template argument in source order.

    Filled slots count too, so a slot stays reachable after typing in it.
    The caret lands at the end of a slot's content, ready to keep typing.
    Tab from the last slot leaves the template the caret is in.
    """
    slots = _slots(source)
    caret = max(0, min(caret, len(source)))
    if reverse:
        # Slots around the caret are where it already is, not behind it.
        previous = [slot for slot in slots if slot.start < caret and not slot.start <= caret <= slot.end]
        if not previous:
            return None
        return _enter_slot(source, previous[-1])
    for slot in slots:
        if slot.start > caret:
            return _enter_slot(source, slot)
    around = [slot for slot in slots if slot.start <= caret <= slot.end]
    if not around:
        return None
    current = around[-1]
    if current.template in NARYAND_ROLES and source[current.exit - 1 : current.exit] in ("▒", " "):
        naryand = NARYAND_ROLES[current.template]
        return TemplateEdit(source, current.exit, naryand if current.exit < len(source) else f"empty {naryand}")
    return TemplateEdit(source, current.exit, f"end {current.template}")


def _enter_slot(source: str, slot: _Slot) -> TemplateEdit:
    content = source[slot.start : slot.end]
    announcement = f"{slot.role}, {content}" if content else f"empty {slot.role}"
    return TemplateEdit(source, slot.end, announcement)


def _slots(source: str) -> list[_Slot]:
    """Every template argument, sorted by where its content starts.

    An enclosing slot sorts before the ones nested in it (the numerator
    before a root inside it), which is the order Tab visits them in.
    """
    pairs = _matching_parens(source)
    slots: list[_Slot] = []
    for cell in _matrix_cells(source):
        slots.append(
            _Slot(
                cell.start,
                cell.end,
                _matrix_label(source, cell),
                f"cell, row {cell.row}, column {cell.column}",
                _past_fence(source, cell.matrix_open - 1, cell.matrix_close + 1),
            )
        )
    for opening, closing in pairs.items():
        separator = _root_index_separator(source, opening, closing, pairs)
        if separator is not None:
            slots.append(_Slot(opening + 1, separator, "root", "index", closing + 1))
            slots.append(_Slot(separator + 1, closing, "root", "radicand", closing + 1))
            continue
        detected = _detect_group(source, opening, closing)
        if detected is not None:
            slots.append(_Slot(opening + 1, closing, *detected))
    return sorted(slots, key=lambda slot: (slot.start, -slot.end))


def _root_index_separator(source: str, opening: int, closing: int, pairs: dict[int, int]) -> int | None:
    """The `&` splitting `√(index&radicand)` at the root's own depth, if any."""
    if opening == 0 or source[opening - 1] != "√":
        return None
    index = opening + 1
    while index < closing:
        if source[index] == "(" and index in pairs:
            index = pairs[index] + 1
            continue
        if source[index] == "&":
            return index
        index += 1
    return None


def _past_fence(source: str, start: int, end: int) -> int:
    if start > 0 and end < len(source) and _CLOSING_FENCES.get(source[start - 1]) == source[end]:
        return end + 1
    return end


def _matching_parens(source: str) -> dict[int, int]:
    """Map each "(" to its matching ")", by real nesting depth; unmatched ones are skipped."""
    pairs: dict[int, int] = {}
    stack: list[int] = []
    for index, character in enumerate(source):
        if character == "(":
            stack.append(index)
        elif character == ")" and stack:
            pairs[stack.pop()] = index
    return pairs


def _matrix_cells(source: str) -> list[_MatrixCell]:
    """Every cell of every `■(...)` in the source, nested matrices included.

    `&`/`@` only separate cells at the matrix's own depth: anything inside a
    nested "(...)" (a fraction slot, an inner matrix) is skipped as a whole.
    """
    pairs = _matching_parens(source)
    cells: list[_MatrixCell] = []
    for matrix_open, matrix_close in sorted(pairs.items()):
        if matrix_open == 0 or source[matrix_open - 1] != "■":
            continue
        row = column = 1
        start = index = matrix_open + 1
        while index < matrix_close:
            character = source[index]
            if character == "(" and index in pairs:
                index = pairs[index] + 1
                continue
            if character in "&@":
                cells.append(_MatrixCell(start, index, row, column, matrix_open, matrix_close))
                if character == "&":
                    column += 1
                else:
                    row += 1
                    column = 1
                start = index + 1
            index += 1
        cells.append(_MatrixCell(start, matrix_close, row, column, matrix_open, matrix_close))
    return cells


def _nary_limit(source: str, opening: int, closing: int) -> tuple[str, str, int] | None:
    """A "(...)" that is the lower (`∑_(...)`) or upper (`∑_(...)^(...)`, `∑^(...)`) limit.

    Tab past the last limit lands after the `▒`, where the naryand goes.
    """
    if opening < 2 or source[opening - 1] not in "_^":
        return None
    base = opening - 2
    if source[opening - 1] == "^" and source[base] == ")":
        # Step back over the lower limit "_(...)" to the operator.
        lower_open = next((start for start, end in _matching_parens(source).items() if end == base), None)
        if lower_open is None or lower_open < 2 or source[lower_open - 1] != "_":
            return None
        base = lower_open - 2
    label = NARY_LABELS.get(source[base])
    if label is None:
        return None
    role = "lower limit" if source[opening - 1] == "_" else "upper limit"
    exit = closing + 1
    if source[exit : exit + 2].startswith("^("):
        return label, role, exit  # An upper limit follows; it is the next slot.
    if source[exit : exit + 1] == "▒":
        exit += 1
    return label, role, exit


def _function_script(source: str, opening: int, closing: int) -> tuple[str, str, int] | None:
    """The `_(...)` of `lim_(...)`/`log_(...)`; Tab past it lands after the space before the argument."""
    if opening < 1 or source[opening - 1] != "_":
        return None
    for name, (template, role) in FUNCTION_SCRIPTS.items():
        start = opening - 1 - len(name)
        if start < 0 or source[start : opening - 1] != name:
            continue
        if start > 0 and source[start - 1].isalpha():
            continue  # Part of a longer word.
        exit = closing + 1
        if source[exit : exit + 1] == " ":
            exit += 1
        return template, role, exit
    return None


def _operator_label(operator: str) -> str:
    return "arrow" if operator in ARROWS else "operator"


def _operator_text(source: str, opening: int, closing: int) -> tuple[str, str, int] | None:
    """The `(...)` of `→┴(...)`/`→┬(...)`; Tab past it skips the space after it."""
    if opening < 2 or source[opening - 1] not in OPERATOR_TEXT_ROLES:
        return None
    base = opening - 2
    if source[base] == ")" and source[opening - 1] == "┴":
        # `→┬(below)┴(above)`: step back over the text below to the operator.
        below_open = next((start for start, end in _matching_parens(source).items() if end == base), None)
        if below_open is None or below_open < 2 or source[below_open - 1] != "┬":
            return None
        base = below_open - 2
    if source[base].isspace() or source[base] in "()":
        return None
    exit = closing + 1
    if source[exit : exit + 2] == "┴(":
        return _operator_label(source[base]), OPERATOR_TEXT_ROLES[source[opening - 1]], exit
    if source[exit : exit + 1] == " ":
        exit += 1
    return _operator_label(source[base]), OPERATOR_TEXT_ROLES[source[opening - 1]], exit


def _detect_group(source: str, opening: int, closing: int) -> tuple[str, str, int] | None:
    """Classify a "(...)" group as a template argument: (template, role, exit).

    Decided by the delimiter directly outside the group's own "(" and ")" —
    never a fixed window of characters, so whatever precedes or follows the
    group (another template's closing "|", a filled numerator) cannot be
    misread as part of it. Backward-looking checks (what opens this group)
    win over forward-looking ones (what follows it): in "√()/()" the radicand
    is followed by "/", but the "/" belongs to an enclosing fraction whose
    numerator is the whole root. A group only counts as a numerator or base
    when it starts an operand, so the "(x)" of "f(x)/2" is not one.
    `exit` is where Tab lands after leaving the template.
    """
    before = source[opening - 1] if opening > 0 else ""
    after = source[closing + 1] if closing + 1 < len(source) else ""
    nary = (
        _nary_limit(source, opening, closing)
        or _function_script(source, opening, closing)
        or _operator_text(source, opening, closing)
    )
    if nary is not None:
        return nary
    if before == "/":
        return "fraction", "denominator", closing + 1
    if before == "_":
        return "scripts", "subscript", closing + 1
    if before == "^":
        return "scripts", "superscript", closing + 1
    if before == "√":
        return "square root", "radicand", closing + 1
    if before == "|" and after == "|":
        return "absolute value", "value", closing + 2
    if before and (before.isalnum() or before in ")]}"):
        return None
    if after in ("_", "^"):
        return "scripts", "base", closing + 1
    if after == "/":
        return "fraction", "numerator", closing + 1
    return None
