from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import partial
from html import escape
from pathlib import Path

from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin

from mathessible.documents.front_matter import LATEX, equation_language
from mathessible.documents.front_matter import body as without_front_matter
from mathessible.documents.markdown_math import find_math_zones, with_marks
from mathessible.documents.mathml_sanitize import sanitize_mathml

MathConverter = Callable[[str], str]

# The converter writes every equation as display="block"; `$...$` is inline.
_BLOCK_DISPLAY = re.compile(r'^(<math\b[^>]*?\sdisplay=")block(")')


@dataclass(frozen=True, slots=True)
class ExportPage:
    title: str
    source: str

    @property
    def latex(self) -> bool:
        """The page's equations are LaTeX (its front matter says `math: latex`)."""
        return equation_language(self.source) == LATEX


def for_page[F: Callable[..., object]](convert: F, page: ExportPage) -> F:
    """An export's equation function for this page: called with `latex=True` on a LaTeX page.

    The functions the exports are given take a page's equation source; the
    app's also take `latex`, which a UnicodeMath page never passes.
    """
    return partial(convert, latex=True) if page.latex else convert


def _note_number(tokens: Sequence[object], index: int) -> str:
    return str(tokens[index].meta["id"] + 1)


def _footnote_reference(self: object, tokens: Sequence[object], index: int, options: object, env: dict) -> str:
    identifier = self.rules["footnote_anchor_name"](tokens, index, options, env)
    sub = tokens[index].meta.get("subId", 0)
    reference = identifier + (f":{sub}" if sub > 0 else "")
    number = _note_number(tokens, index)
    return (
        f'<sup class="footnote-ref"><a href="#fn{identifier}" id="fnref{reference}" role="doc-noteref" '
        f'aria-label="Footnote {number}">{number}</a></sup>'
    )


def _footnotes_open(self: object, tokens: Sequence[object], index: int, options: object, env: dict) -> str:
    return '<section class="footnotes" role="doc-endnotes" aria-label="Footnotes">\n<hr>\n<ol class="footnotes-list">\n'


def _footnote_back_link(self: object, tokens: Sequence[object], index: int, options: object, env: dict) -> str:
    identifier = self.rules["footnote_anchor_name"](tokens, index, options, env)
    sub = tokens[index].meta.get("subId", 0)
    reference = identifier + (f":{sub}" if sub > 0 else "")
    number = _note_number(tokens, index)
    return (
        f' <a href="#fnref{reference}" class="footnote-backref" role="doc-backlink" '
        f'aria-label="Back to reference {number}">\u21a9\ufe0e</a>'
    )


def markdown_parser(**options: bool) -> MarkdownIt:
    """markdown-it as every export reads Markdown: CommonMark, no raw HTML, tables, footnotes."""
    parser = MarkdownIt("commonmark", {"html": False, **options}).enable(["table", "strikethrough"])
    return parser.use(footnote_plugin)


def render_markdown(source: str, convert_math: MathConverter, prefix: str = "") -> str:
    """Render safe Markdown and replace math zones with native MathML; `prefix` keeps a page's note ids apart."""
    source = without_front_matter(source)
    replacements: dict[str, str] = {}
    zones = find_math_zones(source)
    tokens: list[str] = []
    for index in range(len(zones)):
        token = f"MATHESSIBLEMATHZONE{index}TOKEN"
        while token in source:
            token += "X"
        tokens.append(token)
    for index, zone in enumerate(zones):
        equation = zone.content(source)
        try:
            mathml = sanitize_mathml(convert_math(equation))
            if zone.display:
                rendered = f'<div class="math-display">{mathml}</div>'
            else:
                inline = _BLOCK_DISPLAY.sub(r"\g<1>inline\g<2>", mathml, count=1)
                rendered = f'<span class="math-inline">{inline}</span>'
        except (RuntimeError, ValueError, OSError):
            delimiter = zone.delimiter
            rendered = (
                f'<code class="math-error" title="Equation could not be converted">'
                f"{escape(delimiter + equation + delimiter)}</code>"
            )
        replacements[tokens[index]] = rendered
    transformed = with_marks(source, zones, tokens.__getitem__)

    renderer = markdown_parser(linkify=True)
    renderer.add_render_rule("footnote_ref", _footnote_reference)
    renderer.add_render_rule("footnote_block_open", _footnotes_open)
    renderer.add_render_rule("footnote_anchor", _footnote_back_link)
    rendered_markdown = renderer.render(transformed, {"docId": prefix} if prefix else {})
    for token, rendered in replacements.items():
        rendered_markdown = rendered_markdown.replace(f"<p>{token}</p>", rendered)
        rendered_markdown = rendered_markdown.replace(token, rendered)
    return rendered_markdown


# The live preview pane: a fixed shell page whose body is replaced in place
# (so scrolling survives edits) with the same sanitized output as export.
PREVIEW_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <style>
    :root { color-scheme: light dark; font-family: system-ui, sans-serif; line-height: 1.6; }
    body { max-width: 46rem; margin: 0 auto; padding: 1.25rem 1.5rem 3rem; font-size: 17px; }
    a { color: LinkText; }
    math { font-family: "STIX Two Math", "Cambria Math", "Latin Modern Math", math; }
    .math-inline math { font-size: 1.1em; }
    .math-display { margin-block: 1.1rem; overflow-x: auto; text-align: center; }
    .math-display math { font-size: 1.35em; }
    .math-error { color: #b00020; }
    @media (prefers-color-scheme: dark) { .math-error { color: #ff8a80; } }
    table { border-collapse: collapse; }
    th, td { border: 1px solid GrayText; padding: .35rem .6rem; }
    pre { overflow-x: auto; padding: .8rem; background: color-mix(in srgb, CanvasText 8%, Canvas); }
    .empty { color: GrayText; font-style: italic; }
    .footnotes { font-size: .9em; margin-top: 2rem; }
  </style>
</head>
<body>
  <main id="document" aria-label="Document preview"></main>
  <script>
    window.mathessibleSetDocument = function(html) {
      document.getElementById("document").innerHTML = html;
      return true;
    };
  </script>
</body>
</html>
"""


def preview_update_script(source: str, convert_math: MathConverter) -> str:
    """JavaScript that fills `PREVIEW_PAGE` with the rendered document."""
    body = render_markdown(source, convert_math) if source.strip() else '<p class="empty">Empty document</p>'
    return f"window.mathessibleSetDocument({json.dumps(body)})"


@dataclass(frozen=True, slots=True)
class HtmlOptions:
    author: str = ""
    description: str = ""
    language: str = "en"
    table_of_contents: bool = True  # A notebook's pages, a document's headings.
    font: str = "sans"  # "sans" (the system's) or "serif".
    colour_scheme: str = "auto"  # "auto" (the reader's system), "light" or "dark".


STANDARD_HTML = HtmlOptions()
_HEADING = re.compile(r"<h([1-6])>(.*?)</h\1>", re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_FONTS = {"sans": "system-ui, sans-serif", "serif": '"Iowan Old Style", Georgia, "Times New Roman", serif'}
_SCHEMES = {"auto": "light dark", "light": "light", "dark": "dark"}


def _with_heading_ids(html: str, prefix: str) -> tuple[str, list[tuple[int, str, str]]]:
    """The headings given ids, and (level, id, text) for each, for a table of contents."""
    found: list[tuple[int, str, str]] = []

    def anchor(match: re.Match[str]) -> str:
        identifier = f"{prefix}{len(found) + 1}"
        found.append((int(match.group(1)), identifier, _TAG.sub("", match.group(2)).strip()))
        return f'<h{match.group(1)} id="{identifier}">{match.group(2)}</h{match.group(1)}>'

    return _HEADING.sub(anchor, html), found


def notebook_html(
    title: str,
    pages: Sequence[ExportPage],
    convert_math: MathConverter,
    options: HtmlOptions = STANDARD_HTML,
) -> str:
    """One HTML file: a notebook's pages under its title, or one document as it is, with MathML equations."""
    if not pages:
        raise ValueError("An exported notebook must contain at least one page")

    contents: list[str] = []
    if len(pages) == 1:
        body, headings = _with_heading_ids(
            render_markdown(pages[0].source, for_page(convert_math, pages[0])), "section-"
        )
        if options.table_of_contents and len(headings) > 1:
            items = "".join(
                f'<li class="level-{level}"><a href="#{identifier}">{text}</a></li>'
                for level, identifier, text in headings
                if level <= 3
            )
            contents.append(f'<nav aria-label="Contents">\n<h2>Contents</h2>\n<ul>{items}</ul>\n</nav>')
        main = body
        header = ""
    else:
        sections: list[str] = []
        navigation: list[str] = []
        for index, page in enumerate(pages, start=1):
            identifier = f"page-{index}"
            navigation.append(f'<li><a href="#{identifier}">{escape(page.title)}</a></li>')
            body, _headings = _with_heading_ids(
                render_markdown(page.source, for_page(convert_math, page), identifier), f"{identifier}-section-"
            )
            sections.append(
                f'<section class="notebook-page" id="{identifier}" aria-labelledby="{identifier}-title">\n'
                f'<h2 id="{identifier}-title">{escape(page.title)}</h2>\n{body}</section>'
            )
        if options.table_of_contents:
            contents.append(
                f'<nav aria-label="Notebook pages">\n<h2>Pages</h2>\n<ol>{"".join(navigation)}</ol>\n</nav>'
            )
        main = "".join(sections)
        header = f"<header><h1>{escape(title)}</h1></header>"

    metadata = "".join(
        f'\n  <meta name="{name}" content="{escape(value)}">'
        for name, value in (("author", options.author), ("description", options.description))
        if value
    )
    font = _FONTS.get(options.font, _FONTS["sans"])
    scheme = _SCHEMES.get(options.colour_scheme, "light dark")
    return f"""<!doctype html>
<html lang="{escape(options.language or "en")}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>{metadata}
  <style>
    :root {{ color-scheme: {scheme}; font-family: {font}; line-height: 1.55; }}
    body {{ max-width: 58rem; margin: 0 auto; padding: 1.5rem; }}
    a {{ color: LinkText; }}
    nav {{ border-block: 1px solid GrayText; margin-block: 1.5rem 2.5rem; padding-block: 1rem; }}
    nav .level-2 {{ margin-inline-start: 1.25rem; }}
    nav .level-3 {{ margin-inline-start: 2.5rem; }}
    .notebook-page {{ margin-block: 3rem; }}
    math {{ font-family: "STIX Two Math", "Cambria Math", "Latin Modern Math", math; }}
    .math-inline math {{ font-size: 1.08em; }}
    .math-display {{ margin-block: 1.25rem; overflow-x: auto; text-align: center; }}
    .math-display math {{ font-size: 1.25em; }}
    .math-error {{ color: #b00020; }}
    table {{ border-collapse: collapse; }}
    th, td {{ border: 1px solid GrayText; padding: .35rem .6rem; }}
    pre {{ overflow-x: auto; padding: .8rem; background: color-mix(in srgb, CanvasText 8%, Canvas); }}
    .footnotes {{ font-size: .9em; margin-top: 2rem; }}
    @media print {{
      nav {{ display: none; }}
      .notebook-page {{ break-before: page; }}
      .notebook-page:first-of-type {{ break-before: auto; }}
    }}
  </style>
</head>
<body>
  {header}
  {"".join(contents)}
  <main>
    {main}
  </main>
</body>
</html>
"""


def write_notebook_html(
    destination: str | Path,
    title: str,
    pages: Sequence[ExportPage],
    convert_math: MathConverter,
    options: HtmlOptions = STANDARD_HTML,
) -> Path:
    path = Path(destination).expanduser()
    if path.suffix.lower() not in {".html", ".htm"}:
        path = path.with_suffix(".html")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(notebook_html(title, pages, convert_math, options), encoding="utf-8", newline="")
    temporary.replace(path)
    return path
