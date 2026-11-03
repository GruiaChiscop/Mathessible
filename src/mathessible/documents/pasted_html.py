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
    # Each rule under its (tag, class), either of them None; its number keeps the stylesheet's order.
    rules: dict[tuple[str | None, str | None], list[tuple[int, str]]] = {}
    number = 0
    for node in nodes:
        if node.tag == "style":
            css = "".join(part for part in node.children if isinstance(part, str))
            for selectors, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
                for selector in selectors.split(","):
                    match = re.fullmatch(r"([a-zA-Z][\w-]*)?(?:\.([\w-]+))?", selector.strip())
                    if match and (match[1] or match[2]):
                        key = (match[1].lower() if match[1] else None, match[2])
                        rules.setdefault(key, []).append((number, declarations))
                        number += 1
    if not rules:
        return
    for node in nodes:
        keys = [(node.tag, None)]
        for name in node.attrs.get("class", "").split():
            keys += [(None, name), (node.tag, name)]
        matched = sorted(rule for key in keys for rule in rules.get(key, ()))
        if matched:
            node.attrs["style"] = ";".join(
                [*(declarations for _, declarations in matched), node.attrs.get("style", "")]
            )


def _render(node: Node | str) -> str:
    if isinstance(node, str):
        text = re.sub(r"\s+", " ", node.replace("\xa0", " "))
        return re.sub(r"([\\`*_{}\[\]<>$|#!~])", r"\\\1", text)
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
        lines = ["| " + " | ".join(row) + " |" for row in rows]
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
    properties = _properties(node)
    if tag == "div" and properties.get("white-space", "").startswith("pre"):
        # A code editor's copy (VS Code's): its text as it is, Markdown or equations included.
        return "\n\n" + _lines(node).strip("\n") + "\n\n"
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
    weight, slant = properties.get("font-weight", ""), properties.get("font-style", "")
    decoration = properties.get("text-decoration", "") + " " + properties.get("text-decoration-line", "")
    marks = ""
    # Google Docs wraps a whole copy in <b style="font-weight:normal">: the style wins over the tag.
    if weight in {"bold", "bolder", "600", "700", "800", "900"} or (
        tag in {"b", "strong"} and weight not in {"normal", "lighter", "100", "200", "300", "400", "500"}
    ):
        marks += "**"
    if slant in {"italic", "oblique"} or (tag in {"i", "em"} and slant != "normal"):
        marks += "*"
    if "line-through" in decoration or (tag in {"s", "del", "strike"} and "none" not in decoration.split()):
        marks += "~~"
    if marks:
        content = _marked(content, marks)
    if tag in {"p", "div", "section", "article"}:
        return "\n\n" + content.strip() + "\n\n"
    if tag == "img":
        return _render(node.attrs.get("alt", ""))
    return content


def _properties(node: Node) -> dict[str, str]:
    """The node's style (its stylesheet rules, then its own), lower case and without !important."""
    properties = {}
    for declaration in node.attrs.get("style", "").lower().split(";"):
        key, separator, value = declaration.partition(":")
        if separator:
            properties[key.strip()] = value.replace("!important", "").strip()
    return properties


def _marked(content: str, marks: str) -> str:
    """Emphasis around each paragraph of the content: Markdown's marks do not span a blank line, and
    never enclose a heading, list, quotation, table or code block (those keep their own)."""
    parts = re.split(r"(\n{2,})", content)
    for index, part in enumerate(parts):
        text = part.strip()
        if not text or "\n" in text or re.match(r"(?:[#>|`-]|\d+\.)", text):
            continue
        parts[index] = (
            (" " if part.startswith(" ") else "") + marks + text + marks[::-1] + (" " if part.endswith(" ") else "")
        )
    return "".join(parts)


def _lines(node: Node | str) -> str:
    """A pre-formatted block's text as it shows: each <div> or <p> a line, each <br> a line break."""
    if isinstance(node, str):
        return node.replace("\xa0", " ")
    if node.tag in {"script", "style"}:
        return ""
    if node.tag == "br":
        return "\n"
    text = "".join(_lines(child) for child in node.children)
    return text.removesuffix("\n") + "\n" if node.tag in {"div", "p"} else text


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
