"""Optional, local Pandoc bridge. No GUI imports or automatic installation.

Call from a worker when used by a GUI. Readers/writers are deliberately limited
to text and JSON; filters, templates, external resources and PDF engines are not
accepted through this interface.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from enum import StrEnum

from mathessible.documents.optional_tools import find_pandoc
from mathessible.documents.pandoc_ast import clean
from mathessible.settings import load_settings

# Pandoc's Markdown as Mathessible reads it: CommonMark's syntax with its tables (pipe tables, and grid
# tables where a cell holds blocks or cells are merged, see grid_tables), footnotes, task and definition
# lists, strikethrough and `$` equations; none of Pandoc's own (attributes, spans, raw HTML, line blocks).
_MARKDOWN_EXTENSIONS = (
    "+pipe_tables+grid_tables-simple_tables-multiline_tables-table_captions"
    "-raw_html-raw_tex-raw_attribute-native_divs-native_spans-bracketed_spans-fenced_divs"
    "-link_attributes-header_attributes-fenced_code_attributes-inline_code_attributes-implicit_figures"
    "-superscript-subscript-inline_notes-citations-line_blocks-fancy_lists-example_lists"
    "-yaml_metadata_block-pandoc_title_block-smart"
)


class Format(StrEnum):
    HTML = "html"
    JSON = "json"
    DOCX = "docx"
    MARKDOWN = "markdown" + _MARKDOWN_EXTENSIONS


class PandocError(RuntimeError):
    """A conversion failed; callers must keep the original content."""


class PandocMissing(PandocError):
    """No executable was found. Pandoc is an optional dependency."""


def executable() -> str | None:
    """An explicit installation overrides PATH; an invalid override never falls back."""
    return find_pandoc(load_settings().pandoc_path or os.environ.get("MATHESSIBLE_PANDOC", ""))


def convert(
    source: str | bytes, source_format: Format, target_format: Format, limit: int = 2_000_000, timeout: int = 10
) -> str:
    """Convert UTF-8 text (or a binary document, a .docx's bytes) locally, with bounded input and a deadline.

    Output is untrusted document data, not safe HTML. Consumers must validate it.
    Warnings are failures so unsupported input cannot silently disappear.
    """
    if not isinstance(source_format, Format) or not isinstance(target_format, Format):
        raise ValueError("Use an explicitly supported Pandoc format")
    data = source if isinstance(source, bytes) else source.encode("utf-8")
    if len(data) > limit:
        raise PandocError("Input exceeds the Pandoc conversion limit")
    program = executable()
    if program is None:
        raise PandocMissing("Pandoc is not installed or its configured path is unavailable")
    try:
        result = subprocess.run(
            [
                program,
                "--sandbox",
                "--fail-if-warnings",
                "--wrap=none",
                "--from=" + source_format.value,
                "--to=" + target_format.value,
            ],
            input=data,
            capture_output=True,
            timeout=timeout,
            check=True,
        )
        if len(result.stdout) > 16_000_000:
            raise PandocError("Output exceeds the Pandoc conversion limit")
        return result.stdout.decode("utf-8")
    except subprocess.TimeoutExpired as error:
        raise PandocError("Pandoc conversion timed out") from error
    except (OSError, subprocess.SubprocessError, UnicodeError) as error:
        # Do not echo stderr: it can contain private clipboard text.
        raise PandocError("Pandoc could not convert this content") from error


def read_html(source: str) -> dict:
    """Read HTML as Pandoc's JSON document, preserving table blocks and spans.

    This is an intermediate representation, not Markdown ready for insertion.
    """
    return _document(convert(source, Format.HTML, Format.JSON))


def read_docx(data: bytes) -> dict:
    """Read a Word document (its bytes, on standard input) as Pandoc's JSON document: its equations as
    LaTeX, its footnotes, its tables, its pictures by their place in the archive (`media/image1.png`)."""
    return _document(convert(data, Format.DOCX, Format.JSON, limit=50_000_000, timeout=60))


def write_markdown(document: dict) -> str:
    """Pandoc's document as Mathessible's Markdown (see _MARKDOWN_EXTENSIONS)."""
    return convert(json.dumps(document), Format.JSON, Format.MARKDOWN, limit=16_000_000, timeout=30).strip("\n")


def html_to_markdown(html: str, image_source: Callable[[str], str | None] | None = None) -> str:
    """Pasted HTML as Markdown through Pandoc, for what the local conversion (pasted_html) cannot hold."""
    return write_markdown(clean(read_html(html), image_source))


def _document(text: str) -> dict:
    try:
        document = json.loads(text)
    except (ValueError, RecursionError) as error:
        raise PandocError("Pandoc returned invalid JSON") from error
    if (
        not isinstance(document, dict)
        or not isinstance(document.get("blocks"), list)
        or not isinstance(document.get("meta"), dict)
        or not isinstance(document.get("pandoc-api-version"), list)
    ):
        raise PandocError("Pandoc returned an invalid document")
    return document
