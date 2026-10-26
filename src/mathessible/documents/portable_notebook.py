from __future__ import annotations

import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath

from mathessible.documents.notebook import MANIFEST_NAME, Notebook, NotebookError

MAX_ARCHIVE_FILES = 10_000
MAX_UNCOMPRESSED_SIZE = 512 * 1024 * 1024


def mtex_path(path: str | Path) -> Path:
    result = Path(path).expanduser()
    if result.suffix.lower() != ".mathessible":
        result = result.with_suffix(".mathessible")
    return result


def save_portable(notebook: Notebook, destination: str | Path) -> Path:
    destination = mtex_path(destination)
    temporary = destination.with_name(destination.name + ".tmp")
    notebook.save_manifest()
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(notebook.manifest_path, MANIFEST_NAME)
            for page in notebook.pages:
                archive.write(notebook.root / page.file, PurePosixPath(page.file).as_posix())
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def extract_portable(archive_path: str | Path, destination: str | Path) -> Notebook:
    archive_path = Path(archive_path).expanduser()
    destination = Path(destination).expanduser()
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise NotebookError("The temporary notebook folder is not empty")

    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_FILES:
                raise NotebookError("The .mathessible archive contains too many files")
            if sum(entry.file_size for entry in entries) > MAX_UNCOMPRESSED_SIZE:
                raise NotebookError("The .mathessible archive is too large after decompression")
            file_names = [entry.filename for entry in entries if not entry.is_dir()]
            names = set(file_names)
            if len(names) != len(file_names):
                raise NotebookError("The .mathessible archive contains duplicate files")
            if MANIFEST_NAME not in names:
                raise NotebookError(f"The .mathessible archive does not contain {MANIFEST_NAME}")
            for entry in entries:
                relative = _safe_archive_path(entry)
                target = destination.joinpath(*relative.parts)
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry, "r") as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    except (zipfile.BadZipFile, RuntimeError) as error:
        raise NotebookError("The file is not a valid .mathessible notebook") from error
    return Notebook.open(destination)


def _safe_archive_path(entry: zipfile.ZipInfo) -> PurePosixPath:
    if "\\" in entry.filename:
        raise NotebookError(f"Invalid path in .mathessible archive: {entry.filename}")
    path = PurePosixPath(entry.filename)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise NotebookError(f"Unsafe path in .mathessible archive: {entry.filename}")
    if path.parts[0] not in {MANIFEST_NAME, "pages"}:
        raise NotebookError(f"Unknown file in .mathessible archive: {entry.filename}")
    if path.parts[0] == MANIFEST_NAME and len(path.parts) != 1:
        raise NotebookError(f"Invalid path in .mathessible archive: {entry.filename}")
    mode = entry.external_attr >> 16
    if mode and stat.S_ISLNK(mode):
        raise NotebookError(f"Symbolic links are not allowed in .mathessible: {entry.filename}")
    return path
