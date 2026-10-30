"""Accessible Mermaid flowcharts, drawn locally and exported without a web service.

Mathessible accepts a deliberately small, portable subset of Mermaid: a
``flowchart`` (or ``graph``) in direction TD/TB, BT, LR or RL; process nodes
``step[Do work]``; rounded/terminal nodes ``start([Start])``; decision nodes
``choice{Ready?}``; and ``-->`` arrows, optionally labelled
``-->|Yes|``.  Bare node identifiers are also valid.

The source remains ordinary Mermaid in Markdown.  Python only understands
this flowchart format; equations remain the converter's and MathCAT's concern.
"""

from __future__ import annotations

import io
import re
import textwrap
from base64 import b64encode
from dataclasses import dataclass
from html import escape

from mathessible.i18n import _, ngettext

_HEADER = re.compile(r"^(?:flowchart|graph)\s+(TD|TB|BT|LR|RL)\s*$", re.IGNORECASE)
_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_-]*"
_NODE = re.compile(
    rf"^\s*(?P<id>{_IDENTIFIER})(?:(?P<terminal>\(\[(?P<terminal_text>.*?)\]\))|"
    rf"(?P<decision>\{{(?P<decision_text>.*?)\}})|(?P<rounded>\((?P<rounded_text>.*?)\))|"
    rf"(?P<process>\[(?P<process_text>.*?)\]))?\s*$"
)
_EDGE = re.compile(r"^(?P<left>.+?)\s*-->(?:\|(?P<label>[^|]*)\|)?\s*(?P<right>.+?)\s*$")
_META = re.compile(r"^%%\s*(title|description)\s*:\s*(.*)$", re.IGNORECASE)


class FlowchartError(ValueError):
    """A Mermaid flowchart that cannot be drawn, and why."""


@dataclass(frozen=True, slots=True)
class FlowNode:
    identifier: str
    label: str
    shape: str = "process"  # process, rounded, terminal or decision.


@dataclass(frozen=True, slots=True)
class FlowEdge:
    source: str
    target: str
    label: str = ""


@dataclass(frozen=True, slots=True)
class Flowchart:
    direction: str
    nodes: tuple[FlowNode, ...]
    edges: tuple[FlowEdge, ...]
    title: str = ""
    description: str = ""


def is_flowchart(info: str) -> bool:
    """A fenced block's language says it is Mermaid."""
    return info.strip().split(" ")[0].lower() == "mermaid"


def _node(text: str) -> FlowNode:
    found = _NODE.fullmatch(text)
    if not found:
        raise FlowchartError(_("cannot read the node {node!r}").format(node=text))
    identifier = found.group("id")
    for shape, group in (
        ("terminal", "terminal_text"),
        ("decision", "decision_text"),
        ("rounded", "rounded_text"),
        ("process", "process_text"),
    ):
        if found.group(group) is not None:
            label = found.group(group).strip()
            if not label:
                raise FlowchartError(_("the node {node!r} needs text").format(node=identifier))
            return FlowNode(identifier, label, shape)
    return FlowNode(identifier, identifier)


def parse_flowchart(text: str) -> Flowchart:
    """Parse Mathessible's Mermaid subset; raise :class:`FlowchartError` for other syntax."""
    lines = text.splitlines()
    direction = ""
    title = ""
    description = ""
    ordered: dict[str, FlowNode] = {}
    edges: list[FlowEdge] = []
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line:
            continue
        if metadata := _META.fullmatch(line):
            if metadata.group(1).lower() == "title":
                title = metadata.group(2).strip()
            else:
                description = metadata.group(2).strip()
            continue
        if line.startswith("%%"):
            continue
        if not direction:
            header = _HEADER.fullmatch(line)
            if not header:
                raise FlowchartError(_("a Mermaid flowchart must start with `flowchart TD` (or LR, BT or RL)"))
            direction = "TD" if header.group(1).upper() == "TB" else header.group(1).upper()
            continue
        found = _EDGE.fullmatch(line)
        try:
            nodes = (_node(found.group("left")), _node(found.group("right"))) if found else (_node(line),)
        except FlowchartError as error:
            raise FlowchartError(_("line {number}: {error}").format(number=number, error=error)) from error
        for node in nodes:
            previous = ordered.get(node.identifier)
            explicit = node.label != node.identifier or node.shape != "process"
            if previous is None or (previous.label == previous.identifier and explicit):
                ordered[node.identifier] = node
            elif explicit and previous != node:
                raise FlowchartError(
                    _("line {number}: node {node!r} has two different definitions").format(
                        number=number, node=node.identifier
                    )
                )
        if found:
            edges.append(FlowEdge(nodes[0].identifier, nodes[1].identifier, (found.group("label") or "").strip()))
    if not direction:
        raise FlowchartError(_("a Mermaid flowchart must start with `flowchart TD` (or LR, BT or RL)"))
    if not ordered:
        raise FlowchartError(_("the flowchart needs at least one node"))
    return Flowchart(direction, tuple(ordered.values()), tuple(edges), title, description)


def summary(flowchart: Flowchart) -> str:
    """A compact description of the diagram for alternative text and braille."""
    direction = {
        "TD": _("top to bottom"),
        "BT": _("bottom to top"),
        "LR": _("left to right"),
        "RL": _("right to left"),
    }[flowchart.direction]
    nodes = ngettext("Flowchart with {count} node", "Flowchart with {count} nodes", len(flowchart.nodes)).format(
        count=len(flowchart.nodes)
    )
    edges = ngettext("and {count} connection", "and {count} connections", len(flowchart.edges)).format(
        count=len(flowchart.edges)
    )
    return _("{nodes} {edges}, {direction}.").format(nodes=nodes, edges=edges, direction=direction)


def alternative_text(flowchart: Flowchart) -> str:
    """The diagram's title, author description and structural summary."""
    return " ".join(
        part
        for part in (
            flowchart.title + ("." if flowchart.title else ""),
            flowchart.description,
            summary(flowchart),
        )
        if part
    )


def connection_rows(flowchart: Flowchart) -> list[str]:
    """Connections in reading order, using node labels rather than identifiers."""
    labels = {node.identifier: node.label for node in flowchart.nodes}
    rows = []
    for edge in flowchart.edges:
        values = {"source": labels[edge.source], "target": labels[edge.target], "label": edge.label}
        template = _("{source} to {target}, labelled {label}") if edge.label else _("{source} to {target}")
        rows.append(template.format(**values))
    return rows


def _layout(flowchart: Flowchart) -> dict[str, tuple[float, float]]:
    """A stable layered layout; cycles stay on their earliest established layer."""
    rank = {node.identifier: 0 for node in flowchart.nodes}
    for _iteration in range(len(flowchart.nodes)):
        changed = False
        for edge in flowchart.edges:
            candidate = rank[edge.source] + 1
            if candidate > rank[edge.target] and candidate < len(flowchart.nodes):
                rank[edge.target] = candidate
                changed = True
        if not changed:
            break
    layers: dict[int, list[str]] = {}
    for node in flowchart.nodes:
        layers.setdefault(rank[node.identifier], []).append(node.identifier)
    positions: dict[str, tuple[float, float]] = {}
    for layer, identifiers in layers.items():
        offset = (len(identifiers) - 1) / 2
        for index, identifier in enumerate(identifiers):
            across, along = (index - offset) * 3.5, -layer * 2.25
            if flowchart.direction == "TD":
                point = across, along
            elif flowchart.direction == "BT":
                point = across, -along
            elif flowchart.direction == "LR":
                point = -along, -across
            else:
                point = along, -across
            positions[identifier] = point
    return positions


def draw(flowchart: Flowchart, image_format: str = "svg") -> bytes:
    """Draw the flowchart locally with matplotlib, as SVG or PNG."""
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

    positions = _layout(flowchart)
    xs = [point[0] for point in positions.values()]
    ys = [point[1] for point in positions.values()]
    figure = Figure(figsize=(max(5.0, max(xs) - min(xs) + 3.5), max(3.0, max(ys) - min(ys) + 2.5)), dpi=150)
    axes = figure.add_subplot()
    axes.set_aspect("equal")
    axes.axis("off")
    for edge in flowchart.edges:
        start, end = positions[edge.source], positions[edge.target]
        axes.add_patch(
            FancyArrowPatch(
                start,
                end,
                arrowstyle="-|>",
                mutation_scale=13,
                linewidth=1.4,
                color="black",
                shrinkA=28,
                shrinkB=28,
            )
        )
        if edge.label:
            x, y = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
            axes.text(x, y + 0.16, edge.label, ha="center", va="bottom", fontsize=9, backgroundcolor="white")
    for node in flowchart.nodes:
        x, y = positions[node.identifier]
        width, height = 2.35, 1.05
        if node.shape == "decision":
            patch = Polygon(((x, y + 0.75), (x + 1.45, y), (x, y - 0.75), (x - 1.45, y)), closed=True)
        elif node.shape in ("rounded", "terminal"):
            rounding = 0.5 if node.shape == "terminal" else 0.2
            patch = FancyBboxPatch(
                (x - width / 2, y - height / 2), width, height, boxstyle=f"round,pad=0.08,rounding_size={rounding}"
            )
        else:
            patch = Rectangle((x - width / 2, y - height / 2), width, height)
        patch.set(facecolor="white", edgecolor="black", linewidth=1.5, zorder=2)
        axes.add_patch(patch)
        axes.text(x, y, textwrap.fill(node.label, 20), ha="center", va="center", fontsize=10, zorder=3)
    axes.set_xlim(min(xs) - 2, max(xs) + 2)
    axes.set_ylim(min(ys) - 1.5, max(ys) + 1.5)
    figure.tight_layout()
    output = io.BytesIO()
    figure.savefig(output, format=image_format, transparent=True)
    return output.getvalue()


def flowchart_html(text: str) -> str:
    """A picture, caption and textual connection list for preview and HTML export."""
    try:
        flowchart = parse_flowchart(text)
        picture = b64encode(draw(flowchart)).decode("ascii")
    except FlowchartError as error:
        return f'<div class="flowchart-error"><p>{escape(str(error))}</p><pre><code>{escape(text)}</code></pre></div>\n'
    caption = f"<figcaption>{escape(flowchart.title)}</figcaption>" if flowchart.title else ""
    image = f'<img src="data:image/svg+xml;base64,{picture}" alt="{escape(alternative_text(flowchart))}">'
    items = "".join(f"<li>{escape(row)}</li>" for row in connection_rows(flowchart))
    connections = f"<details><summary>{escape(_('Connections'))}</summary><ol>{items}</ol></details>" if items else ""
    return f'<figure class="flowchart">{image}{caption}{connections}</figure>\n'


def flowchart_block(title: str = "", description: str = "", direction: str = "TD") -> str:
    """A new Mermaid flowchart block, with the caret-friendly ``Process`` placeholder."""
    direction = direction.upper()
    if direction not in ("TD", "BT", "LR", "RL"):
        raise FlowchartError(_("unknown flowchart direction {direction!r}").format(direction=direction))
    metadata = "".join(
        f"%% {name}: {value}\n" for name, value in (("title", title), ("description", description)) if value
    )
    return (
        "```mermaid\n"
        + metadata
        + f"flowchart {direction}\n"
        + f"  start([{_('Start')}]) --> process[{_('Process')}]\n"
        + f"  process --> decision{{{_('Decision?')}}}\n"
        + f"  decision -->|{_('Yes')}| finish([{_('Finish')}])\n"
        + f"  decision -->|{_('No')}| process\n"
        + "```"
    )


def _tex(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "&": r"\&",
        "%": r"\%",
        "#": r"\#",
        "_": r"\_",
    }
    return "".join(replacements.get(character, character) for character in text)


def _untex(text: str) -> str:
    replacements = {
        r"\textbackslash{}": "\\",
        r"\{": "{",
        r"\}": "}",
        r"\&": "&",
        r"\%": "%",
        r"\#": "#",
        r"\_": "_",
    }
    for written, character in replacements.items():
        text = text.replace(written, character)
    return text


def tikz_figure(title: str = "", description: str = "", direction: str = "TD") -> str:
    """A native TikZ figure and canonical Mermaid comments for accessible preview/export."""
    block = flowchart_block(title, description, direction)
    source = block.split("\n", 1)[1].rsplit("\n", 1)[0]
    flowchart = parse_flowchart(source)
    positions = _layout(flowchart)
    comments = "\n".join(f"% mathessible-mermaid: {line}" for line in source.splitlines())
    nodes = []
    for node in flowchart.nodes:
        x, y = positions[node.identifier]
        style = {
            "process": "draw",
            "rounded": "draw, rounded corners",
            "terminal": "draw, rounded corners=8pt",
            "decision": "draw, diamond, aspect=2",
        }[node.shape]
        nodes.append(f"  \\node[{style}, align=center] ({node.identifier}) at ({x:g},{y:g}) {{{_tex(node.label)}}};")
    edges = []
    for edge in flowchart.edges:
        label = f" node[midway, fill=white] {{{_tex(edge.label)}}}" if edge.label else ""
        edges.append(f"  \\draw[->] ({edge.source}) --{label} ({edge.target});")
    caption = f"\n  \\caption{{{_tex(title)}}}" if title else ""
    return (
        "\\begin{figure}\n  \\centering\n"
        + comments
        + "\n\\begin{tikzpicture}[>=stealth]\n"
        + "\n".join(nodes + edges)
        + "\n\\end{tikzpicture}"
        + caption
        + "\n\\end{figure}"
    )


def tikz_flowchart(content: str, title: str = "") -> str | None:
    """Recover Mermaid from a generated TikZ figure (comments first, then its native nodes and edges)."""
    prefix = "% mathessible-mermaid: "
    lines = [line[len(prefix) :] for line in content.splitlines() if line.startswith(prefix)]
    if not lines:
        node_pattern = re.compile(
            rf"^\s*\\node\[(?P<style>[^]]+)]\s*\((?P<id>{_IDENTIFIER})\)\s*"
            rf"at\s*\((?P<x>-?[\d.]+),(?P<y>-?[\d.]+)\)\s*\{{(?P<label>.*)}};\s*$"
        )
        edge_pattern = re.compile(
            rf"^\s*\\draw\[->]\s*\((?P<source>{_IDENTIFIER})\)\s*--"
            rf"(?:\s*node\[midway, fill=white]\s*\{{(?P<label>.*?)}})?\s*"
            rf"\((?P<target>{_IDENTIFIER})\);\s*$"
        )
        nodes: list[tuple[str, str, str, float, float]] = []
        edges: list[tuple[str, str, str]] = []
        for line in content.splitlines():
            if found := node_pattern.fullmatch(line):
                style = found.group("style")
                shape = (
                    "decision"
                    if "diamond" in style
                    else "terminal"
                    if "rounded corners=8pt" in style
                    else "rounded"
                    if "rounded corners" in style
                    else "process"
                )
                nodes.append(
                    (
                        found.group("id"),
                        _untex(found.group("label")),
                        shape,
                        float(found.group("x")),
                        float(found.group("y")),
                    )
                )
            elif found := edge_pattern.fullmatch(line):
                edges.append((found.group("source"), found.group("target"), _untex(found.group("label") or "")))
        if not nodes:
            return None
        by_id = {identifier: (x, y) for identifier, _label, _shape, x, y in nodes}
        if edges:
            source, target, _label = edges[0]
            dx = by_id[target][0] - by_id[source][0]
            dy = by_id[target][1] - by_id[source][1]
            direction = ("LR" if dx > 0 else "RL") if abs(dx) > abs(dy) else ("BT" if dy > 0 else "TD")
        else:
            direction = "TD"
        opening = {"process": ("[", "]"), "rounded": ("(", ")"), "terminal": ("([", "] )"), "decision": ("{", "}")}
        definitions: dict[str, str] = {}
        for identifier, label, shape, _x, _y in nodes:
            before, after = opening[shape]
            if shape == "terminal":
                after = "])"
            definitions[identifier] = f"{identifier}{before}{label}{after}"
        lines = [f"flowchart {direction}"]
        used: set[str] = set()
        for source, target, label in edges:
            left = definitions[source] if source not in used else source
            right = definitions[target] if target not in used else target
            arrow = f"-->|{label}|" if label else "-->"
            lines.append(f"  {left} {arrow} {right}")
            used.update((source, target))
        lines.extend(f"  {definition}" for identifier, definition in definitions.items() if identifier not in used)
    if title and not any(line.lower().startswith("%% title:") for line in lines):
        lines.insert(0, f"%% title: {title}")
    return "```mermaid\n" + "\n".join(lines) + "\n```"
