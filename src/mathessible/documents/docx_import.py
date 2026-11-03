"""A Word document (.docx) imported as a Mathessible document, through Pandoc (optional, pandoc.py).

Word's equations come as LaTeX, so the document is marked `math: latex` (front_matter) and keeps them
as they are, unconverted. Its footnotes are Markdown's, its tables pipe or grid tables (grid_tables).
Its pictures are copied from the archive into `<name>-media/` beside the Markdown file, each archive
path checked first (no absolute paths, `..` or links), and the document points to them there.
"""

from __future__ import annotations

import io
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote

from mathessible.documents import pandoc
from mathessible.documents.document_io import markdown_path, write_markdown
from mathessible.documents.front_matter import LATEX, with_equation_language
from mathessible.documents.pandoc_ast import clean, has_math

_LIMIT = 50_000_000  # The document, and all of its pictures together, as Pandoc's input limit.


class DocxImportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ImportedDocument:
    path: Path
    images: tuple[Path, ...]


def media_folder(destination: Path) -> Path:
    return destination.with_name(destination.stem + "-media")


def import_docx(docx: Path, destination: Path) -> ImportedDocument:
    """Write the .docx as Markdown at `destination` (and its pictures beside it); `pandoc.PandocError` when
    Pandoc is missing or cannot read it, `DocxImportError` for an archive that is not a usable .docx."""
    data = docx.read_bytes()
    if len(data) > _LIMIT:
        raise DocxImportError("The Word document exceeds the import limit")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise DocxImportError("Not a Word document") from error
    destination = markdown_path(destination)
    folder = media_folder(destination)
    pictures: dict[str, Path] = {}  # Archive entry: where it is written.

    def image_source(source: str) -> str | None:
        entry = _picture_entry(archive, source)
        if entry is None:
            return None
        if entry.filename not in pictures:
            name = PurePosixPath(entry.filename).name
            taken = {path.name for path in pictures.values()}
            stem, suffix = PurePosixPath(name).stem, PurePosixPath(name).suffix
            number = 1
            while name in taken:
                number += 1
                name = f"{stem}-{number}{suffix}"
            pictures[entry.filename] = folder / name
        return quote(f"{folder.name}/{pictures[entry.filename].name}")

    document = clean(pandoc.read_docx(data), image_source)
    markdown = pandoc.write_markdown(document) + "\n"
    if has_math(document):
        markdown = with_equation_language(markdown, LATEX)
    if sum(archive.getinfo(entry).file_size for entry in pictures) > _LIMIT:
        raise DocxImportError("The Word document's pictures exceed the import limit")
    if pictures:
        folder.mkdir(exist_ok=True)
        for entry, target in pictures.items():
            target.write_bytes(archive.read(entry))
    write_markdown(destination, markdown)
    return ImportedDocument(destination, tuple(pictures.values()))


def _picture_entry(archive: zipfile.ZipFile, source: str) -> zipfile.ZipInfo | None:
    """The archive's file a picture's source names (Pandoc writes `media/image1.png` for
    `word/media/image1.png`), if it is a safe path to a regular file; else None (its description stays)."""
    source = unquote(source)
    if "\\" in source or ":" in source:
        return None
    path = PurePosixPath(source)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        return None
    for name in (f"word/{path}", str(path)):
        try:
            entry = archive.getinfo(name)
        except KeyError:
            continue
        mode = entry.external_attr >> 16
        if entry.is_dir() or (mode and stat.S_ISLNK(mode)):
            return None
        return entry
    return None
