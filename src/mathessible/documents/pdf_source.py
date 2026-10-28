"""The Markdown a PDF exported by Mathessible carries, to open it again.

The PDF export attaches each page's Markdown (`pdf_export`, "Attach the
Markdown source"): one file for a document, one per page for a notebook,
each page's number in its description, since a PDF lists its attachments
by name. Reading them back needs no Typst: pypdf reads the attachments,
decrypting a PDF that has only a permissions password.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from mathessible.i18n import _

# The attachment's description, as `pdf_export` writes it for a notebook's page.
PAGE_DESCRIPTION = "The Markdown source of page {number}, to edit in Mathessible"
DOCUMENT_DESCRIPTION = "The Markdown source, to edit in Mathessible"
_PAGE_NUMBER = re.compile(r"\bpage (\d+)\b")


class PdfSourceError(ValueError):
    """The PDF holds no Markdown to open, or cannot be read."""


@dataclass(frozen=True, slots=True)
class AttachedPage:
    title: str
    source: str


def attached_markdown(data: bytes) -> tuple[str, list[AttachedPage]]:
    """The PDF's title and its attached Markdown pages, in the notebook's order."""
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as error:  # pragma: no cover - pypdf is a dependency.
        raise PdfSourceError(str(error)) from error
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise PdfSourceError(_("This PDF needs a password to open, so Mathessible cannot read its source."))
        files = [
            item
            for item in reader.attachment_list
            if item.name.lower().endswith((".md", ".markdown")) or item.subtype == "/text/markdown"
        ]
        title = (reader.metadata.title if reader.metadata else None) or ""
    except PdfReadError as error:
        raise PdfSourceError(_("This file is not a PDF Mathessible can read.")) from error
    if not files:
        raise PdfSourceError(
            _(
                "This PDF has no Markdown source attached. Only PDFs exported by Mathessible with "
                '"Attach the Markdown source" can be opened.'
            )
        )

    def order(item: object) -> tuple[int, str]:
        found = _PAGE_NUMBER.search(item.description or "")
        return (int(found.group(1)) if found else 0, item.name)

    pages = []
    for item in sorted(files, key=order):
        try:
            source = item.content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise PdfSourceError(_("The Markdown attached to this PDF is not UTF-8 text.")) from error
        name = item.name.rsplit(".", 1)[0]
        pages.append(AttachedPage(name, source))
    return title, pages
