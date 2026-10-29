"""A LaTeX document's text as Mathessible's Markdown, for its preview and its accessible exports.

The .tex file itself is never changed: this is only what the preview, the
HTML, PDF, Word and BRF exports and Print read, as they read a Markdown
document. The equations stay LaTeX (`math: latex`), found by `tex_math`;
an environment's rows are built as its `aligned`. The usual text
commands are read: the title (`\\title`, `\\author`, `\\date` at
`\\maketitle`), sections, `\\emph`/`\\textit`/`\\textbf`/`\\texttt`,
`itemize`, `enumerate`, `description`, `quote`, `verbatim`, `\\footnote`,
`\\href`/`\\url`, LaTeX's special characters and dashes. Sections, equations,
figures and tables are numbered as LaTeX numbers them (`tex_numbers`), so
`\\ref` and `\\eqref` read their numbers; `\\cite` reads the `thebibliography`
entries' (else its keys). A `tabular` is a Markdown table, a figure its
image and caption. Any other command keeps its text arguments and loses its
name, and any other environment keeps its content: a package's command is
never lost text. Only the document's body (`\\begin{document}`) is read, or
the whole file without it.
"""

from __future__ import annotations

import re
from pathlib import Path

from mathessible.documents.tex_macros import document_macros, expand_macros
from mathessible.documents.tex_math import find_tex_math_zones
from mathessible.documents.tex_numbers import TexNumbers, tex_numbers

_HEADINGS = {
    "part": "#",
    "chapter": "#",
    "section": "##",
    "subsection": "###",
    "subsubsection": "####",
    "paragraph": "#####",
    "subparagraph": "######",
}
_STYLES = {
    "emph": "*",
    "textit": "*",
    "textsl": "*",
    "textbf": "**",
    "texttt": "`",
}
_DROPPED = {
    "label",
    "index",
    "vspace",
    "hspace",
    "newpage",
    "clearpage",
    "pagebreak",
    "noindent",
    "centering",
    "tableofcontents",
    "bibliographystyle",
    "bibliography",
    "documentclass",
    "usepackage",
    "newcommand",
    "renewcommand",
    "setlength",
    "pagestyle",
    "thispagestyle",
    "small",
    "large",
    "Large",
    "normalsize",
    "footnotesize",
    "medskip",
    "bigskip",
    "smallskip",
}
_SYMBOLS = {
    "%": "%",
    "$": "\\$",
    "&": "&",
    "#": "\\#",
    "_": "\\_",
    "{": "{",
    "}": "}",
    " ": " ",
    ",": " ",
    ";": " ",
    "!": "",
    "-": "",
    "\\": "  \n",
}
_WORDS = {"LaTeX": "LaTeX", "TeX": "TeX", "ldots": "…", "dots": "…", "textbackslash": "\\\\", "quad": " "}
_COMMENT = re.compile(r"(?<!\\)%.*$", re.MULTILINE)
_BLANK_LINES = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)+")
_MARKDOWN_SPECIAL = re.compile(r"([*_`\[\]<>])")


def _argument(source: str, position: int) -> tuple[str | None, int]:
    """The braced argument at `position` (spaces skipped), and where it ends; None without one."""
    start = position
    while start < len(source) and source[start] in " \t\n":
        start += 1
    if start >= len(source) or source[start] != "{":
        return None, position
    depth = 0
    index = start
    while index < len(source):
        character = source[index]
        if character == "\\":
            index += 2
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1 : index], index + 1
        index += 1
    return source[start + 1 :], len(source)


def _optional(source: str, position: int) -> tuple[str | None, int]:
    if position < len(source) and source[position] == "[":
        end = source.find("]", position)
        if end > 0:
            return source[position + 1 : end], end + 1
    return None, position


_REFERENCES = {"ref", "eqref", "autoref", "cref", "Cref", "pageref"}
_CITATIONS = {"cite", "citep", "citet", "parencite", "textcite", "autocite"}
_RULES = re.compile(r"\\(?:hline|toprule|midrule|bottomrule|cline\s*\{[^}]*\}|cmidrule(?:\([^)]*\))?\s*\{[^}]*\})")
_MULTICOLUMN = re.compile(r"^\s*\\multicolumn\s*\{(\d+)\}\s*\{[^}]*\}\s*\{(.*)\}\s*$", re.DOTALL)
_INCLUDEGRAPHICS = re.compile(r"\\includegraphics\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")


def _top_level_split(text: str, separator: str) -> list[str]:
    """`text` split at `separator` (`&`, `\\\\`) outside braces, an escaped `\\&` not counted."""
    pieces, depth, start, index = [], 0, 0, 0
    while index < len(text):
        if text.startswith(separator, index) and depth == 0:
            pieces.append(text[start:index])
            index += len(separator)
            start = index
            continue
        if text[index] == "\\" and not text.startswith(separator, index):
            index += 2
            continue
        depth += {"{": 1, "}": -1}.get(text[index], 0)
        index += 1
    pieces.append(text[start:])
    return pieces


def _environment_content(source: str, position: int, name: str) -> tuple[str, int]:
    """The content of the environment `name` begun before `position`, and where its `\\end` ends."""
    opening, closing = f"\\begin{{{name}}}", f"\\end{{{name}}}"
    depth, index = 1, position
    while True:
        next_open, next_close = source.find(opening, index), source.find(closing, index)
        if next_close < 0:
            return source[position:], len(source)
        if 0 <= next_open < next_close:
            depth, index = depth + 1, next_open + len(opening)
            continue
        depth -= 1
        if depth == 0:
            return source[position:next_close], next_close + len(closing)
        index = next_close + len(closing)


class _Reader:
    def __init__(self, protected: list[str], numbers: TexNumbers | None = None, folder: Path | None = None):
        self.protected = protected  # Equations and verbatim text, as Markdown, behind their \x00N\x00 marks.
        self.numbers = numbers or TexNumbers()
        self.headings = 0  # The numbered headings read so far.
        self.captions = 0  # The figures' and tables' captions read so far.
        self.folder = folder  # The .tex file's folder, where its images are.
        self.notes: list[str] = []
        self.lists: list[list[str | int]] = []  # Each open list: its marker ("-", "1.") and its items so far.
        self.title: dict[str, str] = {}

    def text(self, source: str) -> str:
        out: list[str] = []
        position = 0
        while position < len(source):
            character = source[position]
            if character == "\x00":
                end = source.index("\x00", position + 1)
                out.append(self.protected[int(source[position + 1 : end])])
                position = end + 1
            elif character == "\\":
                position = self._command(source, position, out)
            elif character in "{}":
                position += 1
            elif character == "~":
                out.append("\u00a0")
                position += 1
            elif source.startswith("---", position):
                out.append("—")
                position += 3
            elif source.startswith("--", position):
                out.append("–")
                position += 2
            elif source.startswith("``", position):
                out.append("“")
                position += 2
            elif source.startswith("''", position):
                out.append("”")
                position += 2
            else:
                out.append(_MARKDOWN_SPECIAL.sub(r"\\\1", character))
                position += 1
        return "".join(out)

    def _command(self, source: str, position: int, out: list[str]) -> int:
        following = source[position + 1 : position + 2]
        if following and not following.isalpha():
            out.append(_SYMBOLS.get(following, following))
            return position + 2
        name_end = position + 1
        while name_end < len(source) and source[name_end].isalpha():
            name_end += 1
        name = source[position + 1 : name_end]
        starred = source[name_end : name_end + 1] == "*"
        position = name_end + starred
        if name == "begin":
            environment, position = _argument(source, position)
            base = (environment or "").rstrip("*")
            if base in ("figure", "table"):
                content, position = _environment_content(source, position, environment or "")
                out.append(self._float(base, content))
                return position
            if base in ("tabular", "tabularx", "longtable", "array"):
                content, position = _environment_content(source, position, environment or "")
                out.append(self._tabular(content))
                return position
            return self._begin(environment or "", source, position, out)
        if name in _REFERENCES:
            key, position = _argument(source, position)
            number = self.numbers.labels.get((key or "").strip(), "??")
            out.append(f"({number})" if name == "eqref" else number)
            return position
        if name in _CITATIONS:
            note, position = _optional(source, position)
            keys, position = _argument(source, position)
            cited = [
                str(self.numbers.citations.get(key.strip(), key.strip()))
                for key in (keys or "").split(",")
                if key.strip()
            ]
            out.append("[" + ", ".join(cited) + (f", {self.text(note)}" if note else "") + "]")
            return position
        if name == "bibitem":
            _label, position = _optional(source, position)
            key, position = _argument(source, position)
            number = self.numbers.citations.get((key or "").strip(), "")
            out.append(f"\n\n[{number}] ")
            while position < len(source) and source[position] in " \t\n":
                position += 1
            return position
        if name == "caption":
            _short, position = _optional(source, position)
            caption, position = _argument(source, position)
            out.append(f"\n\n{self.text(caption or '').strip()}\n\n")
            return position
        if name == "end":
            environment, position = _argument(source, position)
            self._end(environment or "", out)
            return position
        if name == "item":
            label, position = _optional(source, position)
            while position < len(source) and source[position] in " \t\n":
                position += 1
            marker = self.lists[-1][0] if self.lists else "-"
            first = not self.lists or self.lists[-1][1] == 0
            if self.lists:
                self.lists[-1][1] += 1
            indent = "  " * max(0, len(self.lists) - 1)
            while out and not out[-1].strip():
                out.pop()  # A tight list: no blank line between its items.
            if out:
                out[-1] = out[-1].rstrip()
            out.append(f"{chr(10) * 2 if first and len(self.lists) <= 1 else chr(10)}{indent}{marker} ")
            if label is not None:
                out.append(f"**{self.text(label)}** ")
            return position
        if name in _HEADINGS:
            _short, position = _optional(source, position)
            heading, position = _argument(source, position)
            number = ""
            if not starred and name in ("chapter", "section", "subsection", "subsubsection"):
                # The heading's number, as LaTeX shows it (`tex_numbers`).
                numbered = self.numbers.headings
                number = (
                    numbered[self.headings] + " " if self.headings < len(numbered) and numbered[self.headings] else ""
                )
                self.headings += 1
            out.append(f"\n\n{_HEADINGS[name]} {number}{self.text(heading or '').strip()}\n\n")
            return position
        if name in _STYLES:
            content, position = _argument(source, position)
            mark = _STYLES[name]
            inner = self.text(content or "").strip()
            out.append(f"{mark}{inner}{mark}" if inner else "")
            return position
        if name == "footnote":
            _number, position = _optional(source, position)
            note, position = _argument(source, position)
            self.notes.append(self.text(note or "").strip())
            out.append(f"[^{len(self.notes)}]")
            return position
        if name == "href":
            url, position = _argument(source, position)
            label, position = _argument(source, position)
            out.append(f"[{self.text(label or '')}]({url or ''})")
            return position
        if name == "url":
            url, position = _argument(source, position)
            out.append(f"<{url or ''}>")
            return position
        if name in ("title", "author", "date"):
            value, position = _argument(source, position)
            self.title[name] = self.text(value or "").strip()
            return position
        if name == "maketitle":
            out.append(self._title_block())
            return position
        if name in ("par",):
            out.append("\n\n")
            return position
        if name in _WORDS:
            out.append(_WORDS[name])
            return position
        if name in _DROPPED:
            _options, position = _optional(source, position)
            while True:
                argument, after = _argument(source, position)
                if argument is None:
                    return position
                position = after
        # Any other command: its text arguments kept, its name dropped.
        _options, position = _optional(source, position)
        while True:
            argument, after = _argument(source, position)
            if argument is None:
                return position
            out.append(self.text(argument))
            position = after

    def _float(self, kind: str, content: str) -> str:
        """A figure: its image (its caption the image's text) and caption; a table: its caption and table."""
        caption_at = content.find("\\caption")
        caption = ""
        if caption_at >= 0:
            _short, after = _optional(content, caption_at + len("\\caption"))
            text, _end = _argument(content, after)
            caption = self.text(text or "").strip()
        number = (
            self.numbers.captions[self.captions]
            if caption_at >= 0 and self.captions < len(self.numbers.captions)
            else ""
        )
        if caption_at >= 0:
            self.captions += 1
        title = f"{'Figure' if kind == 'figure' else 'Table'} {number}: {caption}" if number else caption
        if kind == "figure":
            images = _INCLUDEGRAPHICS.findall(content)
            alt = re.sub(r"[\[\]$]", "", caption) or "Figure"
            shown = "\n\n".join(f"![{alt}]({self._image(image.strip())})" for image in images)
            return f"\n\n{shown}\n\n{title}\n\n" if title else f"\n\n{shown}\n\n"
        tables = []
        index = 0
        while (found := content.find("\\begin{", index)) >= 0:
            name, after = _argument(content, found + len("\\begin"))
            if (name or "").rstrip("*") in ("tabular", "tabularx", "longtable", "array"):
                inner, index = _environment_content(content, after, name or "")
                tables.append(self._tabular(inner))
            else:
                index = after
        return f"\n\n{title}\n\n" + "".join(tables) if title else "".join(tables)

    def _image(self, path: str) -> str:
        """An image as LaTeX finds it: `\\includegraphics{plot}` is plot.png (or .jpg, .pdf) beside the file."""
        if self.folder is None or Path(path).suffix:
            return path
        for suffix in (".png", ".jpg", ".jpeg", ".svg", ".pdf", ".eps"):
            if (self.folder / f"{path}{suffix}").is_file():
                return f"{path}{suffix}"
        return path

    def _tabular(self, content: str) -> str:
        """A tabular as a Markdown table: its first row the header, its rules left out."""
        _position, start = _optional(content, len(content) - len(content.lstrip()))  # [t], then {lcr}
        _columns, start = _argument(content, start)
        rows = []
        for row in _top_level_split(_RULES.sub("", content[start:]), "\\\\"):
            if not row.strip():
                continue
            cells = []
            for cell in _top_level_split(row, "&"):
                spanned = _MULTICOLUMN.match(cell)
                text = spanned.group(2) if spanned else cell
                cells.append(" ".join(self.text(text).split()).replace("|", "\\|"))
                cells += [""] * (int(spanned.group(1)) - 1 if spanned else 0)
            rows.append(cells)
        if not rows:
            return ""
        width = max(len(row) for row in rows)
        rows = [row + [""] * (width - len(row)) for row in rows]
        lines = ["| " + " | ".join(rows[0]) + " |", "|" + "|".join([" --- "] * width) + "|"]
        lines += ["| " + " | ".join(row) + " |" for row in rows[1:]]
        return "\n\n" + "\n".join(lines) + "\n\n"

    def _begin(self, environment: str, source: str, position: int, out: list[str]) -> int:
        base = environment.rstrip("*")
        if base == "thebibliography":
            out.append("\n\n## References\n\n")
            _widest, position = _argument(source, position)
            return position
        if base in ("itemize", "enumerate", "description"):
            self.lists.append(["1." if base == "enumerate" else "-", 0])
        elif base in ("quote", "quotation", "abstract"):
            out.append("\n\n> ")
        elif base == "document":
            pass
        return _optional(source, position)[1]

    def _end(self, environment: str, out: list[str]) -> None:
        base = environment.rstrip("*")
        if base in ("itemize", "enumerate", "description") and self.lists:
            self.lists.pop()
            out.append("\n\n" if not self.lists else "")
        elif base in ("quote", "quotation", "abstract"):
            out.append("\n\n")

    def _title_block(self) -> str:
        lines = [f"# {self.title['title']}"] if self.title.get("title") else []
        lines += [self.title[key] for key in ("author", "date") if self.title.get(key)]
        return "\n\n" + "\n\n".join(lines) + "\n\n"


def _protect(source: str, numbers: TexNumbers | None = None) -> tuple[str, list[str]]:
    """The source with its equations and verbatim text behind \x00N\x00 marks, and their Markdown: an
    equation with the document's own commands expanded (`tex_macros`), as the exporters build it, and a
    numbered `equation`'s number as its `\\tag`."""
    protected: list[str] = []
    pieces: list[str] = []
    position = 0
    macros = document_macros(source, tex=True)
    for zone in find_tex_math_zones(source):
        pieces.append(_verbatim(source[position : zone.start], protected))
        content = expand_macros(zone.content(source), macros)
        number = numbers.equations.get(zone.start) if numbers is not None else None
        if number and "\\tag" not in content:
            content = f"{content.rstrip()} \\tag{{{number}}}"
        if zone.environment:
            content = f"\\begin{{{zone.environment}}}{content.strip()}\\end{{{zone.environment}}}"
        # An inline equation stays on its line; a display one is a paragraph of its own.
        protected.append(f"\n\n$${content.strip()}$$\n\n" if zone.display else f"${' '.join(content.split())}$")
        pieces.append(f"\x00{len(protected) - 1}\x00")
        position = zone.end
    pieces.append(_verbatim(source[position:], protected))
    return "".join(pieces), protected


_VERBATIM_BLOCK = re.compile(r"\\begin\{(verbatim\*?|lstlisting|Verbatim)\}(.*?)\\end\{\1\}", re.DOTALL)
_VERB = re.compile(r"\\verb\*?([^A-Za-z\s])(.*?)\1")


def _verbatim(text: str, protected: list[str]) -> str:
    def block(found: re.Match[str]) -> str:
        protected.append(f"\n\n```\n{found.group(2).strip(chr(10))}\n```\n\n")
        return f"\x00{len(protected) - 1}\x00"

    def inline(found: re.Match[str]) -> str:
        protected.append(f"`{found.group(2)}`")
        return f"\x00{len(protected) - 1}\x00"

    text = _VERBATIM_BLOCK.sub(block, text)
    text = _VERB.sub(inline, text)
    return _COMMENT.sub("", text)


def tex_to_markdown(source: str, folder: Path | None = None) -> str:
    """The LaTeX document as Markdown with LaTeX equations (`math: latex`), for its preview and exports;
    `folder` is the file's own, where its images are found."""
    numbers = tex_numbers(source)
    text, protected = _protect(source, numbers)
    reader = _Reader(protected, numbers, folder)
    begin = text.find("\\begin{document}")
    if begin >= 0:
        reader.text(text[:begin])  # The preamble: only its \title, \author and \date are kept.
        end = text.find("\\end{document}", begin)
        text = text[begin + len("\\begin{document}") : end if end >= 0 else len(text)]
    # LaTeX ignores a line's leading spaces; Markdown would read four as code.
    text = "\n".join(line.lstrip(" \t") for line in text.split("\n"))
    body = reader.text(text)
    if reader.notes:
        body += "\n\n" + "\n\n".join(f"[^{number}]: {note}" for number, note in enumerate(reader.notes, 1))
    body = _BLANK_LINES.sub("\n\n", body).strip()
    return f"---\nmath: latex\n---\n{body}\n"
