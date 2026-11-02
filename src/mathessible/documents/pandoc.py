"""Optional, local Pandoc bridge. No GUI imports or automatic installation.

Call from a worker when used by a GUI. Readers/writers are deliberately limited
to text and JSON; filters, templates, external resources and PDF engines are not
accepted through this interface.
"""

from __future__ import annotations

import json
import os
import subprocess
from enum import StrEnum

from mathessible.documents.optional_tools import find_pandoc
from mathessible.settings import load_settings


class Format(StrEnum):
    HTML = "html"
    JSON = "json"
    MARKDOWN = "markdown+grid_tables-pipe_tables-simple_tables-multiline_tables-raw_html-raw_tex"


class PandocError(RuntimeError):
    """A conversion failed; callers must keep the original content."""


class PandocMissing(PandocError):
    """No executable was found. Pandoc is an optional dependency."""


def executable() -> str | None:
    """An explicit installation overrides PATH; an invalid override never falls back."""
    return find_pandoc(load_settings().pandoc_path or os.environ.get("MATHESSIBLE_PANDOC", ""))


def convert(source: str, source_format: Format, target_format: Format) -> str:
    """Convert UTF-8 text locally, with bounded input and a ten-second deadline.

    Output is untrusted document data, not safe HTML. Consumers must validate it.
    Warnings are failures so unsupported input cannot silently disappear.
    """
    if not isinstance(source_format, Format) or not isinstance(target_format, Format):
        raise ValueError("Use an explicitly supported Pandoc format")
    data = source.encode("utf-8")
    if len(data) > 2_000_000:
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
            timeout=10,
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
    try:
        document = json.loads(convert(source, Format.HTML, Format.JSON))
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
