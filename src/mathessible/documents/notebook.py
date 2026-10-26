from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

MANIFEST_NAME = "mathessible.json"
FORMAT_NAME = "mathessible-notebook"
FORMAT_VERSION = 1


class NotebookError(ValueError):
    pass


def _write_text_atomic(path: Path, source: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as document:
        document.write(source)
    temporary.replace(path)


@dataclass(frozen=True, slots=True)
class NotebookPage:
    id: str
    title: str
    file: str


@dataclass(slots=True)
class Notebook:
    root: Path
    title: str
    pages: list[NotebookPage]

    @classmethod
    def create(cls, root: str | Path, title: str | None = None) -> Notebook:
        root = Path(root).expanduser()
        if root.exists() and any(root.iterdir()):
            raise NotebookError("The selected folder is not empty")
        root.mkdir(parents=True, exist_ok=True)
        (root / "pages").mkdir()
        notebook = cls(root=root, title=title or root.name, pages=[])
        notebook.add_page("Page 1")
        return notebook

    @classmethod
    def open(cls, root: str | Path) -> Notebook:
        root = Path(root).expanduser()
        manifest_path = root / MANIFEST_NAME
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise NotebookError(f"The selected folder does not contain {MANIFEST_NAME}") from error
        except (OSError, json.JSONDecodeError) as error:
            raise NotebookError(f"The notebook manifest could not be read: {error}") from error
        if data.get("format") != FORMAT_NAME or data.get("version") != FORMAT_VERSION:
            raise NotebookError("Unknown or incompatible notebook format")
        title = data.get("title")
        raw_pages = data.get("pages")
        if not isinstance(title, str) or not title.strip() or not isinstance(raw_pages, list):
            raise NotebookError("The notebook manifest is incomplete")
        pages: list[NotebookPage] = []
        seen_ids: set[str] = set()
        for item in raw_pages:
            if not isinstance(item, dict):
                raise NotebookError("The manifest contains an invalid page")
            page_id = item.get("id")
            page_title = item.get("title")
            file = item.get("file")
            if not all(isinstance(value, str) and value for value in (page_id, page_title, file)):
                raise NotebookError("The manifest contains an incomplete page")
            if page_id in seen_ids:
                raise NotebookError("The manifest contains duplicate page identifiers")
            page = NotebookPage(page_id, page_title, file)
            cls._validate_page_path(root, page)
            if not (root / file).is_file():
                raise NotebookError(f"Page file is missing: {file}")
            seen_ids.add(page_id)
            pages.append(page)
        if not pages:
            raise NotebookError("A notebook must contain at least one page")
        return cls(root=root, title=title, pages=pages)

    @property
    def manifest_path(self) -> Path:
        return self.root / MANIFEST_NAME

    def save_manifest(self) -> None:
        data = {
            "format": FORMAT_NAME,
            "version": FORMAT_VERSION,
            "title": self.title,
            "pages": [{"id": page.id, "title": page.title, "file": page.file} for page in self.pages],
        }
        _write_text_atomic(
            self.manifest_path,
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        )

    def add_page(self, title: str, source: str = "", index: int | None = None) -> NotebookPage:
        title = title.strip()
        if not title:
            raise NotebookError("A page must have a title")
        number = 1
        existing = {page.id for page in self.pages}
        while f"page-{number}" in existing:
            number += 1
        page_id = f"page-{number}"
        page = NotebookPage(page_id, title, f"pages/{page_id}.md")
        path = self._page_path(page)
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_text_atomic(path, source)
        if index is None:
            self.pages.append(page)
        else:
            self.pages.insert(index, page)
        try:
            self.save_manifest()
        except OSError:
            self.pages.remove(page)
            path.unlink(missing_ok=True)
            raise
        return page

    def rename_page(self, index: int, title: str) -> None:
        title = title.strip()
        if not title:
            raise NotebookError("A page must have a title")
        page = self.pages[index]
        self.pages[index] = NotebookPage(page.id, title, page.file)
        try:
            self.save_manifest()
        except OSError:
            self.pages[index] = page
            raise

    def move_page(self, index: int, destination: int) -> int:
        if not 0 <= index < len(self.pages):
            raise IndexError(index)
        destination = max(0, min(destination, len(self.pages) - 1))
        page = self.pages.pop(index)
        self.pages.insert(destination, page)
        try:
            self.save_manifest()
        except OSError:
            self.pages.pop(destination)
            self.pages.insert(index, page)
            raise
        return destination

    def delete_page(self, index: int) -> None:
        if len(self.pages) == 1:
            raise NotebookError("A notebook must keep at least one page")
        page = self.pages.pop(index)
        try:
            self.save_manifest()
        except OSError:
            self.pages.insert(index, page)
            raise
        self._page_path(page).unlink(missing_ok=True)

    def read_page(self, index: int) -> str:
        with self._page_path(self.pages[index]).open("r", encoding="utf-8", newline="") as document:
            return document.read()

    def write_page(self, index: int, source: str) -> None:
        _write_text_atomic(self._page_path(self.pages[index]), source)

    def page_path(self, index: int) -> Path:
        return self._page_path(self.pages[index])

    def _page_path(self, page: NotebookPage) -> Path:
        self._validate_page_path(self.root, page)
        return self.root / page.file

    @staticmethod
    def _validate_page_path(root: Path, page: NotebookPage) -> None:
        path = (root / page.file).resolve()
        pages_root = (root / "pages").resolve()
        if not path.is_relative_to(pages_root) or path.suffix.lower() != ".md":
            raise NotebookError(f"Unsafe page path: {page.file}")
