"""Pandoc's document (its JSON AST) cut down to what Mathessible's Markdown holds, before Pandoc writes it.

Pandoc is given no filters (see pandoc.py); this runs in Python on the JSON it read. What a Mathessible
document cannot hold is not written as raw HTML or attributes, which the editor would show as text:

- raw HTML and TeX are left out (what a web page or Word adds around its text);
- a Div, Span or Figure gives way to its content, its classes and styles dropped;
- an image is kept only when `image_source` gives it a place (an imported Word document's pictures,
  docx_import); otherwise its description stands for it, as in a local paste.
"""

from __future__ import annotations

from collections.abc import Callable

_SPLICED = {"Div": 1, "Span": 1, "Figure": 2}  # Element: the index of its content in "c".
_DROPPED = {"RawInline", "RawBlock"}


def clean(document: dict, image_source: Callable[[str], str | None] | None = None) -> dict:
    """A copy of the document, as described above. `image_source` maps an image's source to the path to
    write, or None for its description instead."""
    return {**document, "blocks": _walk(document.get("blocks", []), image_source)}


def _walk(value: object, image_source: Callable[[str], str | None] | None) -> object:
    if isinstance(value, dict):
        return {key: _walk(item, image_source) for key, item in value.items()}
    if not isinstance(value, list):
        return value
    result: list[object] = []
    for item in value:
        if isinstance(item, dict) and isinstance(item.get("t"), str):
            result += _element(item, image_source)
        else:
            result.append(_walk(item, image_source))
    return result


def _element(element: dict, image_source: Callable[[str], str | None] | None) -> list[object]:
    """What stands for the element in its list: itself (its content cleaned), its content, or nothing."""
    kind, content = element["t"], element.get("c")
    if kind in _DROPPED:
        return []
    if kind in _SPLICED and isinstance(content, list) and len(content) > _SPLICED[kind]:
        inner = content[_SPLICED[kind]]
        if kind == "Figure" and isinstance(content[1], list) and len(content[1]) == 2:
            caption = content[1][1]
            if _text(caption) and _text(caption) not in _descriptions(inner):
                inner = [*inner, *caption]  # The figure's caption, after its picture, unless it describes it.
        return _walk(inner, image_source)
    if kind == "Image" and isinstance(content, list) and len(content) == 3:
        _attributes, description, (source, title) = content
        target = image_source(source) if image_source else None
        if target is None:
            return _walk(description, image_source)
        return [{"t": "Image", "c": [["", [], []], _walk(description, image_source), [target, title]]}]
    return [{**element, "c": _walk(content, image_source)} if "c" in element else element]


def has_math(document: dict) -> bool:
    """Whether Pandoc read an equation (Word's, as LaTeX)."""
    pending: list[object] = [document.get("blocks", [])]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            if value.get("t") == "Math":
                return True
            pending += value.values()
        elif isinstance(value, list):
            pending += value
    return False


def _text(value: object) -> str:
    """The words of Pandoc's inlines or blocks, spaces between them."""
    words: list[str] = []
    pending: list[object] = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            if item.get("t") == "Str":
                words.append(item.get("c", ""))
            elif "c" in item:
                pending.append(item["c"])
        elif isinstance(item, list):
            pending += reversed(item)
    return " ".join(words)


def _descriptions(blocks: object) -> set[str]:
    """The descriptions of the images in these blocks."""
    found: set[str] = set()
    pending: list[object] = [blocks]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            if item.get("t") == "Image" and isinstance(item.get("c"), list) and len(item["c"]) == 3:
                found.add(_text(item["c"][1]))
            elif "c" in item:
                pending.append(item["c"])
        elif isinstance(item, list):
            pending += item
    return found
