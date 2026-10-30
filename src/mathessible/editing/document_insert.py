"""What the document's Insert menu writes: headings, lists, quotations, code, a rule, links, images, tables.

Each works on the document's text, its selection `start`..`end` (equal for
the caret alone), and gives the new text and where the caret goes, as
`TemplateEdit` does for an equation's templates. A Markdown document gets
Markdown, the common syntax every export reads (CommonMark, with GitHub's
tables); a .tex file (`tex`) gets LaTeX's own: `\\section{...}`,
`itemize`, `quote`, `verbatim`, `\\href`, a `figure`, a `tabular`.

Line commands (a heading, a list, a quotation) act on the lines the
selection touches, or on the caret's line; a block (code, a table, a
rule) goes on lines of its own, a blank line around it in Markdown.
"""

from __future__ import annotations

import re

from mathessible.templates.template_source import TemplateEdit

# LaTeX's sectioning commands for the six heading levels (an article has no \chapter).
TEX_HEADINGS = ("section", "subsection", "subsubsection", "paragraph", "subparagraph", "subparagraph")
_MARKDOWN_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
_MARKDOWN_LIST = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+")


def _line_span(source: str, start: int, end: int) -> tuple[int, int]:
    """The start of the first line the selection touches and the end of its last."""
    first = source.rfind("\n", 0, start) + 1
    last = source.find("\n", end if end == start or source[end - 1 : end] != "\n" else end - 1)
    return first, len(source) if last < 0 else last


def _block(source: str, start: int, end: int, block: str, caret_in_block: int, tex: bool) -> TemplateEdit:
    """`block` in place of the selection, on lines of its own (Markdown: a blank line around it)."""
    before, after = source[:start], source[end:]
    gap = "\n" if tex else "\n\n"
    opening = "" if not before or before.endswith(gap) else (gap if not before.endswith("\n") else gap[1:])
    closing = "" if after.startswith(gap) else (gap if not after.startswith("\n") else gap[1:])
    if not after:
        closing = "\n"
    text = opening + block + closing
    return TemplateEdit(before + text + after, start + len(opening) + caret_in_block, "")


def heading(source: str, start: int, end: int, level: int, tex: bool) -> TemplateEdit:
    """The caret's line (or the selected text, in .tex) as a heading of `level` (1 to 6)."""
    level = max(1, min(6, level))
    first, last = _line_span(source, start, end)
    if tex:
        text = source[start:end] if start != end else source[first:last].strip()
        command = f"\\{TEX_HEADINGS[level - 1]}{{{text}}}"
        if start != end:
            updated = source[:start] + command + source[end:]
            return TemplateEdit(updated, start + len(command), "")
        updated = source[:first] + command + source[last:]
        caret = first + len(command) - 1 if not text else first + len(command)
        return TemplateEdit(updated, caret, "")
    line = _MARKDOWN_HEADING.sub("", source[first:last])
    marked = "#" * level + " " + line
    return TemplateEdit(source[:first] + marked + source[last:], first + len(marked), "")


def list_items(source: str, start: int, end: int, numbered: bool, tex: bool) -> TemplateEdit:
    """The lines the selection touches (or the caret's line) as a bulleted or numbered list."""
    first, last = _line_span(source, start, end)
    lines = source[first:last].split("\n")
    if tex:
        environment = "enumerate" if numbered else "itemize"
        items = "\n".join(f"  \\item {line.strip()}" for line in lines)
        block = f"\\begin{{{environment}}}\n{items}\n\\end{{{environment}}}"
        caret = len(f"\\begin{{{environment}}}\n") + len(items)
        return _block(source[:first] + source[last:], first, first, block, caret, tex)
    marked = []
    for number, line in enumerate(lines, 1):
        indent, content = re.match(r"^(\s*)(.*)$", _MARKDOWN_LIST.sub(r"\1", line)).groups()
        marked.append(f"{indent}{number}. {content}" if numbered else f"{indent}- {content}")
    text = "\n".join(marked)
    return TemplateEdit(source[:first] + text + source[last:], first + len(text), "")


def quotation(source: str, start: int, end: int, tex: bool) -> TemplateEdit:
    """The lines the selection touches (or the caret's line) as a quotation."""
    first, last = _line_span(source, start, end)
    text = source[first:last]
    if tex:
        block = f"\\begin{{quote}}\n{text.strip()}\n\\end{{quote}}"
        return _block(
            source[:first] + source[last:], first, first, block, len("\\begin{quote}\n") + len(text.strip()), tex
        )
    quoted = "\n".join(f"> {line}" if line.strip() else ">" for line in text.split("\n"))
    return TemplateEdit(source[:first] + quoted + source[last:], first + len(quoted), "")


def code_block(source: str, start: int, end: int, tex: bool) -> TemplateEdit:
    """The selection (or nothing) as a block of code, shown as typed."""
    code = source[start:end].strip("\n")
    opening, closing = ("\\begin{verbatim}\n", "\n\\end{verbatim}") if tex else ("```\n", "\n```")
    return _block(source, start, end, f"{opening}{code}{closing}", len(opening) + len(code), tex)


def horizontal_rule(source: str, start: int, end: int, tex: bool) -> TemplateEdit:
    """A rule across the page, on a line of its own."""
    rule = "\\noindent\\rule{\\linewidth}{0.4pt}" if tex else "---"
    edit = _block(source, start, end, rule, len(rule), tex)
    return TemplateEdit(edit.source, edit.caret, "")


def link(source: str, start: int, end: int, text: str, address: str, tex: bool) -> TemplateEdit:
    """A link in place of the selection: `[text](address)`, LaTeX's `\\href{address}{text}` (hyperref)."""
    text = text or address
    written = f"\\href{{{address}}}{{{text}}}" if tex else f"[{text}]({address.replace(' ', '%20')})"
    return TemplateEdit(source[:start] + written + source[end:], start + len(written), "")


def image(source: str, start: int, end: int, path: str, description: str, tex: bool) -> TemplateEdit:
    """An image on lines of its own, `description` its text for those who cannot see it (and its caption
    in .tex, in a `figure`)."""
    if tex:
        block = (
            "\\begin{figure}\n  \\centering\n  \\includegraphics[width=\\linewidth]{"
            + path
            + "}\n  \\caption{"
            + description
            + "}\n\\end{figure}"
        )
        return _block(source, start, end, block, len(block), tex)
    written = f"![{description}]({path.replace(' ', '%20')})"
    return _block(source, start, end, written, len(written), tex)


def table(source: str, start: int, end: int, rows: int, columns: int, header: bool, tex: bool) -> TemplateEdit:
    """A table of `rows` by `columns` to fill in, its first row the header, the caret in its first cell."""
    rows, columns = max(1, rows), max(1, columns)
    if tex:
        spec = "l" * columns
        lines = [" & ".join(["  "] * columns).rstrip() + " \\\\" for _ in range(rows)]
        if header:
            lines.insert(1, "\\hline")
        block = f"\\begin{{tabular}}{{{spec}}}\n\\hline\n" + "\n".join(lines) + "\n\\hline\n\\end{tabular}"
        caret = len(f"\\begin{{tabular}}{{{spec}}}\n\\hline\n")
        return _block(source, start, end, block, caret, tex)
    cell = "   "
    first_row = "|" + "|".join(cell for _ in range(columns)) + "|"
    separator = "|" + "|".join(" --- " for _ in range(columns)) + "|"
    body = [first_row for _ in range(rows - 1 if header else rows)]
    # A Markdown table always has a header row; without one asked for, it stays empty.
    lines = [first_row, separator, *body] if header else [first_row, separator, *body]
    block = "\n".join(lines)
    return _block(source, start, end, block, 2, tex)


_USEPACKAGE = re.compile(r"\\usepackage\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")


def with_package(edit: TemplateEdit, package: str) -> TemplateEdit:
    """A .tex edit with `\\usepackage{package}` added to the preamble when it is not there yet (`\\href` needs
    hyperref, `\\includegraphics` graphicx): after the last \\usepackage, else before \\begin{document}."""
    source = edit.source
    begin = source.find("\\begin{document}")
    if begin < 0:
        return edit
    loaded = {name.strip() for found in _USEPACKAGE.finditer(source, 0, begin) for name in found.group(1).split(",")}
    if package in loaded:
        return edit
    packages = list(_USEPACKAGE.finditer(source, 0, begin))
    at = source.find("\n", packages[-1].end()) + 1 if packages else begin
    if at <= 0:
        at = begin
    line = f"\\usepackage{{{package}}}\n"
    caret = edit.caret + len(line) if edit.caret >= at else edit.caret
    return TemplateEdit(source[:at] + line + source[at:], caret, edit.announcement)
