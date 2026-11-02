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


def _apply_styles(root: Node) -> None:
    """Read simple class/tag rules emitted by Office and Cocoa, without fetching CSS."""
    nodes: list[Node] = []

    def visit(node: Node) -> None:
        nodes.append(node)
        for child in node.children:
            if isinstance(child, Node):
                visit(child)

    visit(root)
    rules: list[tuple[str, str]] = []
    for node in nodes:
        if node.tag == "style":
            css = "".join(part for part in node.children if isinstance(part, str))
            for selectors, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
                rules.extend((selector.strip(), declarations) for selector in selectors.split(","))
    for node in nodes:
        matched = []
        for selector, declarations in rules:
            match = re.fullmatch(r"([a-zA-Z][\w-]*)?(?:\.([\w-]+))?", selector)
            if (
                match
                and (not match[1] or node.tag == match[1].lower())
                and (not match[2] or match[2] in node.attrs.get("class", "").split())
            ):
                matched.append(declarations)
        node.attrs["style"] = ";".join([*matched, node.attrs.get("style", "")])


def _render(node: Node | str) -> str:
    if isinstance(node, str):
        text = re.sub(r"\s+", " ", node.replace("\xa0", " "))
        return re.sub(r"([\\`*_{}\[\]<>$|#!])", r"\\\1", text)
    tag = node.tag
    if tag in {"script", "style", "head", "xml", "object", "iframe"}:
        return ""
    if tag.endswith((":omath", ":omathpara")) or tag in {"math", "mml:math"}:
        raise ValueError("Equation conversion is required")
    if tag in {"code", "pre"}:

        def literal(part: Node | str) -> str:
            if isinstance(part, str):
                return part
            return "\n" if part.tag == "br" else "".join(literal(child) for child in part.children)

        value = literal(node)
        fence = "`" * max(3 if tag == "pre" else 1, max((len(run) + 1 for run in re.findall(r"`+", value)), default=1))
        if tag == "pre":
            return "\n\n" + fence + "\n" + value.rstrip("\n") + "\n" + fence + "\n\n"
        return fence + " " + value.replace("\n", " ") + " " + fence
    if tag == "table":
        merged = False
        rows: list[list[str]] = []
        occupied: dict[tuple[int, int], str] = {}
        row_number = 0

        def contains_table(parent: Node) -> bool:
            return any(
                isinstance(child, Node) and (child.tag == "table" or contains_table(child)) for child in parent.children
            )

        def collect(parent: Node) -> None:
            nonlocal row_number, merged
            for child in parent.children:
                if not isinstance(child, Node):
                    continue
                if child.tag == "tr":
                    column = 0
                    for cell in child.children:
                        if not isinstance(cell, Node) or cell.tag not in {"td", "th"}:
                            continue
                        while (row_number, column) in occupied:
                            column += 1
                        colspan = int(cell.attrs.get("colspan", "1"))
                        rowspan = int(cell.attrs.get("rowspan", "1"))
                        merged = merged or colspan > 1 or rowspan > 1
                        if not 1 <= colspan <= 100 or not 1 <= rowspan <= 100 or column + colspan > 100:
                            raise ValueError("Table span exceeds import limits")
                        if row_number + rowspan > 1000:
                            raise ValueError("Table exceeds import limits")
                        if contains_table(cell):
                            raise ValueError("Nested table")
                        value = re.sub(r"\n+", "<br>", _render(cell).strip())
                        if value in {"^", ">"}:
                            value = "\\" + value
                        for down in range(rowspan):
                            for across in range(colspan):
                                position = (row_number + down, column + across)
                                if position in occupied:
                                    raise ValueError("Overlapping table spans")
                                occupied[position] = value if down == across == 0 else "^" if down else ">"
                        column += colspan
                    row_number += 1
                    if row_number > 1000:
                        raise ValueError("Table exceeds import limits")
                elif child.tag in {"thead", "tbody", "tfoot"}:
                    collect(child)

        collect(node)
        if not occupied:
            return ""
        width = max(column for _, column in occupied) + 1
        height = max(row for row, _ in occupied) + 1
        rows = [[occupied.get((row, column), "") for column in range(width)] for row in range(height)]
        width = max(map(len, rows))
        lines = ["| " + " | ".join(row + [""] * (width - len(row))) + " |" for row in rows]
        lines.insert(1, "| " + " | ".join(["---"] * width) + " |")
        content = "\n".join(lines)
        return "\n\n" + ("```table\n" + content + "\n```" if merged else content) + "\n\n"
    if tag in {"ul", "ol"}:
        lines = []
        number = int(node.attrs.get("start", "1"))
        for child in node.children:
            if isinstance(child, Node) and child.tag == "li":
                number = int(child.attrs.get("value", str(number)))
                prefix = f"{number}. " if tag == "ol" else "- "
                content = _render(child).strip().replace("\n", "\n" + " " * len(prefix))
                lines.append(prefix + content)
                number += 1
        return "\n\n" + "\n".join(lines) + "\n\n"
    content = "".join(_render(child) for child in node.children)
    if tag == "br":
        return "\n"
    if tag == "hr":
        return "\n\n---\n\n"
    if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        return "\n\n" + "#" * int(tag[1]) + " " + content.strip() + "\n\n"
    if tag == "blockquote":
        return "\n\n" + "\n".join("> " + line for line in content.strip().splitlines()) + "\n\n"
    if tag == "a":
        target = node.attrs.get("href", "")
        if target and urlsplit(target).scheme.lower() in {"", "https", "http", "mailto"}:
            target = target.replace(" ", "%20").replace("(", "%28").replace(")", "%29")
            return f"[{content}]({target})"
    properties = {}
    for declaration in node.attrs.get("style", "").lower().split(";"):
        key, separator, value = declaration.partition(":")
        if separator:
            properties[key.strip()] = value.strip()
    style = ";".join(f"{key}:{value}" for key, value in properties.items())
    marks = ""
    if tag in {"b", "strong"} or "font-weight:bold" in style or "font-weight:700" in style:
        marks += "**"
    if tag in {"i", "em"} or "font-style:italic" in style:
        marks += "*"
    if tag in {"s", "del", "strike"} or "line-through" in style:
        marks += "~~"
    if marks and content.strip():
        content = (
            (" " if content.startswith(" ") else "")
            + marks
            + content.strip()
            + marks[::-1]
            + (" " if content.endswith(" ") else "")
        )
    if tag in {"p", "div", "section", "article"}:
        return "\n\n" + content.strip() + "\n\n"
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
        _apply_styles(parser.root)
        result = _render(parser.root)
        result = re.sub(r"(?m)^[ \t]+$", "", result)
        return re.sub(r"\n{3,}", "\n\n", result).strip() or None
    except (ValueError, RecursionError):
        return None


def has_merged_cells(html: str) -> bool:
    """Detect structural loss before offering a flattened Markdown paste."""
    parser = Parser()
    parser.feed(html)
    pending = [parser.root]
    while pending:
        node = pending.pop()
        if node.tag in {"td", "th"} and any(node.attrs.get(key, "1") != "1" for key in ("rowspan", "colspan")):
            return True
        pending.extend(child for child in node.children if isinstance(child, Node))
    return False
