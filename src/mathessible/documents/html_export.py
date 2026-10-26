from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from html import escape
from pathlib import Path

from markdown_it import MarkdownIt

from mathessible.documents.markdown_math import find_math_zones
from mathessible.documents.mathml_sanitize import sanitize_mathml

MathConverter = Callable[[str], str]

# The converter writes every equation as display="block"; `$...$` is inline.
_BLOCK_DISPLAY = re.compile(r'^(<math\b[^>]*?\sdisplay=")block(")')


@dataclass(frozen=True, slots=True)
class ExportPage:
    title: str
    source: str


def render_markdown(source: str, convert_math: MathConverter) -> str:
    """Render safe Markdown and replace math zones with native MathML."""
    replacements: dict[str, str] = {}
    transformed = source
    for index, zone in reversed(list(enumerate(find_math_zones(source)))):
        token = f"MATHESSIBLEMATHZONE{index}TOKEN"
        while token in source:
            token += "X"
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
        replacements[token] = rendered
        placeholder = f"\n\n{token}\n\n" if zone.display else token
        transformed = transformed[: zone.start] + placeholder + transformed[zone.end :]

    renderer = MarkdownIt("commonmark", {"html": False, "linkify": True}).enable("table")
    rendered_markdown = renderer.render(transformed)
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


def notebook_html(
    title: str,
    pages: Sequence[ExportPage],
    convert_math: MathConverter,
) -> str:
    if not pages:
        raise ValueError("An exported notebook must contain at least one page")

    navigation: list[str] = []
    sections: list[str] = []
    for index, page in enumerate(pages, start=1):
        identifier = f"page-{index}"
        navigation.append(f'<li><a href="#{identifier}">{escape(page.title)}</a></li>')
        sections.append(
            f'<section class="notebook-page" id="{identifier}" aria-labelledby="{identifier}-title">\n'
            f'<h2 id="{identifier}-title">{escape(page.title)}</h2>\n'
            f"{render_markdown(page.source, convert_math)}"
            "</section>"
        )

    safe_title = escape(title)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; line-height: 1.55; }}
    body {{ max-width: 58rem; margin: 0 auto; padding: 1.5rem; }}
    a {{ color: LinkText; }}
    nav {{ border-block: 1px solid GrayText; margin-block: 1.5rem 2.5rem; padding-block: 1rem; }}
    .notebook-page {{ margin-block: 3rem; }}
    .math-inline math {{ font-size: 1.08em; }}
    .math-display {{ margin-block: 1.25rem; overflow-x: auto; text-align: center; }}
    .math-display math {{ font-size: 1.25em; }}
    .math-error {{ color: #b00020; }}
    table {{ border-collapse: collapse; }}
    th, td {{ border: 1px solid GrayText; padding: .35rem .6rem; }}
    pre {{ overflow-x: auto; padding: .8rem; background: color-mix(in srgb, CanvasText 8%, Canvas); }}
    @media print {{
      nav {{ display: none; }}
      .notebook-page {{ break-before: page; }}
      .notebook-page:first-of-type {{ break-before: auto; }}
    }}
  </style>
</head>
<body>
  <header><h1>{safe_title}</h1></header>
  <nav aria-label="Notebook pages">
    <h2>Pages</h2>
    <ol>{"".join(navigation)}</ol>
  </nav>
  <main>
    {"".join(sections)}
  </main>
</body>
</html>
"""


def write_notebook_html(
    destination: str | Path,
    title: str,
    pages: Sequence[ExportPage],
    convert_math: MathConverter,
) -> Path:
    path = Path(destination).expanduser()
    if path.suffix.lower() not in {".html", ".htm"}:
        path = path.with_suffix(".html")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(notebook_html(title, pages, convert_math), encoding="utf-8", newline="")
    temporary.replace(path)
    return path
