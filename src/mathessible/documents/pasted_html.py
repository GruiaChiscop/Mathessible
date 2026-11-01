"""Convert clipboard HTML to the Markdown structures supported by the editor.

Never load images, stylesheets or other external resources. Unsupported complex
tables and equations fall back to the clipboard's plain text as a whole.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urlsplit


@dataclass(slots=True)
class Node:
    tag: str
    attrs: dict[str, str]
    children: list[Node | str] = field(default_factory=list)


class Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("root", {})
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {key: value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag not in {"br", "hr", "img", "meta", "link", "input", "wbr", "col"}:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def _render(node: Node | str) -> str:
    if isinstance(node, str):
        text = re.sub(r"\s+", " ", node.replace("\xa0", " "))
        return re.sub(r"([\\`*_{}\[\]<>$|#!])", r"\\\1", text)
    tag = node.tag
    if tag in {"script", "style", "head", "xml", "object", "iframe"}:
        return ""
    if tag.endswith((":omath", ":omathpara")) or tag in {"math", "mml:math"}:
        raise ValueError("Equation conversion is required")
    if tag == "table":
        rows: list[list[str]] = []

        def collect(parent: Node) -> None:
            for child in parent.children:
                if not isinstance(child, Node):
                    continue
                if child.tag == "tr":
                    cells = []
                    for cell in child.children:
                        if not isinstance(cell, Node) or cell.tag not in {"td", "th"}:
                            continue
                        if any(cell.attrs.get(key, "1") != "1" for key in ("colspan", "rowspan")):
                            raise ValueError("Merged cells cannot be represented by a Markdown table")
                        if any(isinstance(part, Node) and part.tag == "table" for part in cell.children):
                            raise ValueError("Nested table")
                        cells.append(_render(cell).strip().replace("\n", "<br>"))
                    if cells:
                        rows.append(cells)
                elif child.tag in {"thead", "tbody", "tfoot"}:
                    collect(child)

        collect(node)
        if not rows:
            return ""
        width = max(map(len, rows))
        lines = ["| " + " | ".join(row + [""] * (width - len(row))) + " |" for row in rows]
        lines.insert(1, "| " + " | ".join(["---"] * width) + " |")
        return "\n\n" + "\n".join(lines) + "\n\n"
    if tag in {"ul", "ol"}:
        lines = []
        for child in node.children:
            if isinstance(child, Node) and child.tag == "li":
                prefix = f"{len(lines) + 1}. " if tag == "ol" else "- "
                content = _render(child).strip().replace("\n", "\n" + " " * len(prefix))
                lines.append(prefix + content)
        return "\n\n" + "\n".join(lines) + "\n\n"
    content = "".join(_render(child) for child in node.children)
    if tag == "br":
        return "\n"
    if tag == "hr":
        return "\n\n---\n\n"
    if tag in {"p", "div", "section", "article"}:
        return "\n\n" + content.strip() + "\n\n"
    if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        return "\n\n" + "#" * int(tag[1]) + " " + content.strip() + "\n\n"
    if tag == "blockquote":
        return "\n\n" + "\n".join("> " + line for line in content.strip().splitlines()) + "\n\n"
    if tag == "a":
        target = node.attrs.get("href", "")
        if target and urlsplit(target).scheme.lower() in {"", "https", "http", "mailto"}:
            target = target.replace(" ", "%20").replace("(", "%28").replace(")", "%29")
            return f"[{content}]({target})"
    style = node.attrs.get("style", "").lower().replace(" ", "")
    marks = ""
    if tag in {"b", "strong"} or "font-weight:bold" in style or "font-weight:700" in style:
        marks += "**"
    if tag in {"i", "em"} or "font-style:italic" in style:
        marks += "*"
    if tag in {"s", "del", "strike"} or "line-through" in style:
        marks += "~~"
    if marks and content.strip():
        return (
            (" " if content.startswith(" ") else "")
            + marks
            + content.strip()
            + marks[::-1]
            + (" " if content.endswith(" ") else "")
        )
    if tag == "img":
        return _render(node.attrs.get("alt", ""))
    return content


def markdown_from_html(html: str) -> str | None:
    """Return a Markdown fragment, or None when plain text is the safer fallback."""
    if len(html) > 2_000_000:
        return None
    # Word can put OMML inside conditional comments; never silently discard it.
    if re.search(r"<(?:\w+:)?oMath\b", html, re.IGNORECASE):
        return None
    parser = Parser()
    try:
        parser.feed(html)
        result = _render(parser.root)
        result = re.sub(r"(?m)^[ \t]+$", "", result)
        return re.sub(r"\n{3,}", "\n\n", result).strip() or None
    except (ValueError, RecursionError):
        return None
