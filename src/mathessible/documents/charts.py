"""Charts in a document: a function's graph or a chart of data, kept as text and drawn by matplotlib.

A chart is a fenced block whose language is `chart`, so the document keeps
what it shows as text a screen reader reads, and every export draws it:

    ```chart
    type: function
    function: sin(x); cos(x)
    x: -6.28 .. 6.28
    title: Sine and cosine
    description: Two waves, a quarter period apart.
    ```

    ```chart
    type: bar
    title: Scores
    | Name | Score |
    | --- | --- |
    | Ann | 9 |
    | Bob | 7 |
    ```

`type` is `function`, `bar`, `line`, `scatter` or `pie`. A function is a
calculator's expression in x (`x^2 - 1`, `2*sin(x)`, `sqrt(abs(x))`, `e^x`),
evaluated safely (`expression_function`: arithmetic, the usual functions and
constants, nothing else), several separated by `;`. Data is a Markdown table:
its first column the labels (or x), each other column a series. What a
reader without the picture gets is `description` (written by the author) and,
for data, the table itself; `summary` says the rest in words.
"""

from __future__ import annotations

import ast
import io
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field

KINDS = ("function", "bar", "line", "scatter", "pie")
_RANGE = re.compile(r"^\s*(-?[\w.+*/^()π-]+)\s*(?:\.\.|to|,)\s*(-?[\w.+*/^()π-]+)\s*$")
_FUNCTIONS: dict[str, Callable[..., float]] = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "exp": math.exp,
    "log": math.log,
    "ln": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "sqrt": math.sqrt,
    "abs": abs,
    "floor": math.floor,
    "ceil": math.ceil,
}
_CONSTANTS = {"pi": math.pi, "π": math.pi, "e": math.e, "tau": math.tau}


_LINES = ("-", "--", ":", "-.")
_MARKERS = ("o", "s", "^", "D")
_HATCHES = ("", "//", "..", "xx")


class ChartError(ValueError):
    """A chart that cannot be drawn, and why."""


@dataclass(frozen=True, slots=True)
class Chart:
    kind: str
    title: str = ""
    description: str = ""
    functions: tuple[str, ...] = ()
    x_range: tuple[float, float] = (-10.0, 10.0)
    labels: tuple[str, ...] = ()  # Data: the first column (the categories, or x).
    series: tuple[tuple[str, tuple[float, ...]], ...] = ()  # Data: each other column, its name and values.
    x_label: str = ""
    y_label: str = ""
    header: tuple[str, ...] = field(default=())


def _number(text: str) -> float:
    return float(expression_function(text)(0.0))


def expression_function(expression: str) -> Callable[[float], float]:
    """A calculator's expression in x as a function; `ChartError` for anything else (no names but x, the
    usual functions and constants; `^` is a power, and `2x` a product)."""
    text = expression.strip().replace("^", "**").replace("π", "pi").replace("·", "*").replace("×", "*")
    text = re.sub(r"(\d)\s*([a-zA-Z(])", r"\1*\2", text)  # 2x, 3sin(x), 2(x+1)
    text = re.sub(r"\)\s*([\w(])", r")*\1", text)  # (x+1)(x-1), (x)x
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as error:
        raise ChartError(f"cannot read the function {expression!r}") from error
    allowed = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Call,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.Mod,
        ast.FloorDiv,
        ast.USub,
        ast.UAdd,
    )
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            raise ChartError(f"cannot read the function {expression!r}")
        if isinstance(node, ast.Name) and node.id != "x" and node.id not in _FUNCTIONS and node.id not in _CONSTANTS:
            raise ChartError(f"unknown name {node.id!r} in {expression!r}")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise ChartError(f"cannot read the function {expression!r}")
        if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS):
            raise ChartError(f"unknown function in {expression!r}")
    # Numbers as floats, so that a huge power overflows at once instead of being worked out exactly (9^9^9^9).
    tree = ast.fix_missing_locations(_Floats().visit(tree))
    code = compile(tree, "<chart>", "eval")
    names = {**_FUNCTIONS, **_CONSTANTS}

    def function(x: float) -> float:
        try:
            value = eval(code, {"__builtins__": {}}, {**names, "x": x})  # noqa: S307 (checked above)
            return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else math.nan
        except (ArithmeticError, ValueError, OverflowError):
            return math.nan

    return function


class _Floats(ast.NodeTransformer):
    def visit_Constant(self, node: ast.Constant) -> ast.Constant:  # noqa: N802 (ast's name)
        return ast.copy_location(ast.Constant(float(node.value)), node) if isinstance(node.value, int) else node


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_chart(text: str) -> Chart:
    """The chart a `chart` block's text describes; `ChartError` when it cannot be drawn."""
    settings: dict[str, str] = {}
    rows: list[list[str]] = []
    for line in text.splitlines():
        if line.strip().startswith("|"):
            if not re.fullmatch(r"\|?[\s:|-]+\|?", line.strip()):
                rows.append(_cells(line))
        elif ":" in line:
            key, _colon, value = line.partition(":")
            settings[key.strip().lower()] = value.strip()
    kind = settings.get("type", "function" if "function" in settings else "bar").lower()
    if kind not in KINDS:
        raise ChartError(f"unknown chart type {kind!r}")
    common = {
        "title": settings.get("title", ""),
        "description": settings.get("description", ""),
        "x_label": settings.get("x label", settings.get("xlabel", "")),
        "y_label": settings.get("y label", settings.get("ylabel", "")),
    }
    if kind == "function":
        functions = tuple(part.strip() for part in settings.get("function", "").split(";") if part.strip())
        if not functions:
            raise ChartError("a function chart needs `function:`")
        for function in functions:
            expression_function(function)
        x_range = (-10.0, 10.0)
        if "x" in settings:
            found = _RANGE.match(settings["x"])
            if not found:
                raise ChartError(f"cannot read the range {settings['x']!r} (write it as -3 .. 3)")
            x_range = (_number(found.group(1)), _number(found.group(2)))
            if not x_range[0] < x_range[1]:
                raise ChartError("the range's start must be below its end")
        return Chart(kind, functions=functions, x_range=x_range, **common)
    if len(rows) < 2 or len(rows[0]) < 2:
        raise ChartError("a chart of data needs a table: its labels, then a column of values")
    header, body = rows[0], rows[1:]
    series = []
    for column in range(1, len(header)):
        try:
            values = tuple(
                float(row[column].replace(",", ".")) if column < len(row) and row[column] else math.nan for row in body
            )
        except ValueError as error:
            raise ChartError(f"the column {header[column]!r} has a value that is not a number") from error
        series.append((header[column], values))
    if kind == "pie":
        if len(series) != 1:
            raise ChartError("a pie chart needs exactly one series")
        values = series[0][1]
        if any(value < 0 for value in values if not math.isnan(value)):
            raise ChartError("a pie chart cannot contain negative values")
        if not any(value > 0 for value in values if not math.isnan(value)):
            raise ChartError("a pie chart needs at least one positive value")
    return Chart(kind, labels=tuple(row[0] for row in body), series=tuple(series), header=tuple(header), **common)


def samples(chart: Chart, count: int = 400) -> list[tuple[str, list[float], list[float]]]:
    """A function chart's curves: each function's name and its points (NaN where it is undefined)."""
    start, end = chart.x_range
    xs = [start + (end - start) * index / (count - 1) for index in range(count)]
    curves = []
    for expression in chart.functions:
        function = expression_function(expression)
        curves.append((expression, xs, [function(x) for x in xs]))
    return curves


def summary(chart: Chart) -> str:
    """The chart in words, after its author's description: what is drawn, its range and extremes."""

    def number(value: float) -> str:
        return "0" if abs(value) < 1e-9 * 1e6 else f"{value:.4g}"  # A rounding's 2.5e-05 is 0.

    if chart.kind == "function":
        parts = []
        for expression, _xs, ys in samples(chart):
            defined = [y for y in ys if not math.isnan(y)]
            extent = f", from {number(min(defined))} to {number(max(defined))}" if defined else ""
            parts.append(f"y = {expression}{extent}")
        start, end = chart.x_range
        return f"Graph of {'; '.join(parts)}, for x from {number(start)} to {number(end)}."
    names = ", ".join(name for name, _values in chart.series)
    kind = {"bar": "Bar chart", "line": "Line chart", "scatter": "Scatter plot", "pie": "Pie chart"}[chart.kind]
    first = chart.header[0] if chart.header else "values"
    return f"{kind} of {names}, for {len(chart.labels)} values of {first}: {', '.join(chart.labels)}."


def draw(chart: Chart, image_format: str = "svg", width: float = 6.0, height: float = 3.6) -> bytes:
    """The chart drawn by matplotlib, as SVG (the preview, HTML, PDF) or PNG (Word)."""
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib.figure import Figure

    figure = Figure(figsize=(width, height), dpi=150)
    axes = figure.add_subplot()
    if chart.kind == "function":
        for index, (expression, xs, ys) in enumerate(samples(chart)):
            # Told apart by their lines, not their colours alone (colour blindness, printing in grey).
            axes.plot(xs, ys, label=f"y = {expression}", linestyle=_LINES[index % len(_LINES)])
        axes.axhline(0, color="0.6", linewidth=0.8)
        axes.axvline(0, color="0.6", linewidth=0.8)
        axes.grid(True, alpha=0.3)
        if len(chart.functions) > 1:
            axes.legend()
    elif chart.kind == "pie":
        name, values = chart.series[0]
        axes.pie([0 if math.isnan(value) else value for value in values], labels=list(chart.labels), autopct="%1.0f%%")
        axes.axis("equal")
    else:
        positions = list(range(len(chart.labels)))
        count = len(chart.series)
        for index, (name, values) in enumerate(chart.series):
            if chart.kind == "bar":
                width_each = 0.8 / count
                axes.bar(
                    [p - 0.4 + width_each * (index + 0.5) for p in positions],
                    values,
                    width_each,
                    label=name,
                    hatch=_HATCHES[index % len(_HATCHES)],
                    edgecolor="white",
                )
            elif chart.kind == "line":
                axes.plot(
                    positions,
                    values,
                    marker=_MARKERS[index % len(_MARKERS)],
                    linestyle=_LINES[index % len(_LINES)],
                    label=name,
                )
            else:
                axes.scatter(positions, values, marker=_MARKERS[index % len(_MARKERS)], label=name)
        axes.set_xticks(positions, list(chart.labels))
        axes.grid(True, axis="y", alpha=0.3)
        if count > 1:
            axes.legend()
    # The title is not drawn: every export gives the chart its caption (figcaption, Typst's figure, Word's).
    if chart.x_label:
        axes.set_xlabel(chart.x_label)
    if chart.y_label:
        axes.set_ylabel(chart.y_label)
    figure.tight_layout()
    out = io.BytesIO()
    figure.savefig(out, format=image_format)
    return out.getvalue()


def alternative_text(chart: Chart) -> str:
    """What is read instead of the picture: its title, its author's description, then `summary`."""
    return " ".join(
        part for part in (chart.title + ("." if chart.title else ""), chart.description, summary(chart)) if part
    )


def is_chart(info: str) -> bool:
    """A fenced block's language says it is a chart."""
    return info.strip().split(" ")[0].lower() == "chart"


def data_rows(chart: Chart) -> list[list[str]]:
    """A chart of data's table, header first, as text (for HTML, braille, a reader's table)."""
    if chart.kind == "function":
        return []
    rows = [list(chart.header)]
    for index, label in enumerate(chart.labels):
        rows.append([label, *(f"{values[index]:g}" for _name, values in chart.series)])
    return rows


def chart_html(text: str) -> str:
    """A chart for the preview and HTML: its picture (SVG, its alternative text the chart in words), its title
    as the caption and, for data, its table under a disclosure; what is wrong when it cannot be drawn."""
    from base64 import b64encode
    from html import escape

    try:
        chart = parse_chart(text)
        picture = b64encode(draw(chart)).decode("ascii")
    except ChartError as error:
        return f'<div class="chart-error"><p>{escape(str(error))}</p><pre><code>{escape(text)}</code></pre></div>\n'
    caption = f"<figcaption>{escape(chart.title)}</figcaption>" if chart.title else ""
    image = f'<img src="data:image/svg+xml;base64,{picture}" alt="{escape(alternative_text(chart))}">'
    table = ""
    rows = data_rows(chart)
    if rows:
        head = "".join(f"<th>{escape(cell)}</th>" for cell in rows[0])
        body = "".join("<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>" for row in rows[1:])
        table = f"<details><summary>Data</summary><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></details>"
    return f'<figure class="chart">{image}{caption}{table}</figure>\n'


_PGF_DEGREES = {"sin", "cos", "tan"}  # pgfplots' trigonometric functions take degrees.
_PGF_NAMES = {
    "ln": "ln",
    "log": "ln",
    "log10": "log10",
    "log2": "log2",
    "sqrt": "sqrt",
    "abs": "abs",
    "exp": "exp",
    "floor": "floor",
    "ceil": "ceil",
    "asin": "asin",
    "acos": "acos",
    "atan": "atan",
    "sinh": "sinh",
    "cosh": "cosh",
    "tanh": "tanh",
}


def pgf_expression(expression: str) -> str:
    """A calculator's expression in x as pgfplots writes it: `sin(x)` is `sin(deg(x))`, `x^2` stays `x^2`."""
    expression_function(expression)  # Refused as charts refuse it.
    text = expression.strip().replace("π", "pi").replace("·", "*").replace("×", "*")
    text = re.sub(r"(\d)\s*([a-zA-Z(])", r"\1*\2", text)
    tree = ast.parse(text.replace("^", "**"), mode="eval")

    def written(node: ast.AST) -> str:
        if isinstance(node, ast.Expression):
            return written(node.body)
        if isinstance(node, ast.Constant):
            return f"{node.value:g}" if isinstance(node.value, float) else str(node.value)
        if isinstance(node, ast.Name):
            return {"pi": "pi", "tau": "(2*pi)", "e": "e"}.get(node.id, node.id)
        if isinstance(node, ast.UnaryOp):
            return f"-{written(node.operand)}" if isinstance(node.op, ast.USub) else written(node.operand)
        if isinstance(node, ast.BinOp):
            symbol = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.Pow: "^", ast.Mod: " mod "}[
                type(node.op)
            ]
            return f"({written(node.left)}{symbol}{written(node.right)})"
        if isinstance(node, ast.Call):
            name, argument = node.func.id, written(node.args[0])
            if name in _PGF_DEGREES:
                return f"{name}(deg({argument}))"
            return f"{_PGF_NAMES.get(name, name)}({argument})"
        raise ChartError(f"cannot write {expression!r} for pgfplots")

    return written(tree)


def calculator_expression(pgf: str) -> str:
    """A pgfplots expression as the calculator's (`sin(deg(x))` is `sin(x)`), for a .tex file's preview."""
    return re.sub(r"deg\(([^()]*(?:\([^()]*\))*[^()]*)\)", r"\1", pgf).replace("mod", "%")


def chart_block(
    kind: str, title: str, description: str, functions: str, x_range: tuple[str, str], rows: int, columns: int
) -> str:
    """A new chart's block for a Markdown document, its data table to fill in (labels, then each series)."""
    lines = [f"type: {kind}"]
    if title:
        lines.append(f"title: {title}")
    if description:
        lines.append(f"description: {description}")
    if kind == "function":
        lines.append(f"function: {functions}")
        lines.append(f"x: {x_range[0]} .. {x_range[1]}")
    else:
        names = ["Label", *(f"Series {index}" for index in range(1, max(1, columns) + 1))]
        initial = "1" if kind == "pie" else "0"
        lines.append("| " + " | ".join(names) + " |")
        lines.append("|" + "|".join(" --- " for _name in names) + "|")
        lines += [
            "| " + " | ".join([f"Item {row}", *(initial for _name in names[1:])]) + " |"
            for row in range(1, max(1, rows) + 1)
        ]
    return "```chart\n" + "\n".join(lines) + "\n```"


def pgfplots_figure(
    kind: str, title: str, description: str, functions: str, x_range: tuple[str, str], rows: int, columns: int
) -> str:
    """A new chart for a .tex file: a figure holding a pgfplots axis (its data to fill in), its caption the
    title; the description as a comment, which a reader of the source has."""
    if kind == "function":
        expressions = [part.strip() for part in functions.split(";") if part.strip()]
        if not expressions:
            raise ChartError("a function chart needs a function")
        start, end = (f"{_number(x_range[0]):g}", f"{_number(x_range[1]):g}")
        plots = "\n".join(f"      \\addplot {{{pgf_expression(part)}}};" for part in expressions)
        axis = f"axis lines=middle, xlabel=$x$, ylabel=$y$, domain={start}:{end}, samples=200"
    elif kind == "pie":
        labels = [f"Item{row}" for row in range(1, max(1, rows) + 1)]
        comment = f"  % {description}\n" if description else ""
        caption = f"  \\caption{{{title}}}\n" if title else ""
        pieces = ", ".join(f"1/{label}" for label in labels)
        return (
            "\\begin{figure}\n  \\centering\n"
            + comment
            + "  \\begin{tikzpicture}\n"
            + f"    \\pie{{{pieces}}}\n"
            + "  \\end{tikzpicture}\n"
            + caption
            + "\\end{figure}"
        )
    else:
        labels = [f"Item{row}" for row in range(1, max(1, rows) + 1)]
        series = [f"Series {index}" for index in range(1, max(1, columns) + 1)]
        style = {"bar": "ybar", "line": "", "scatter": "only marks", "pie": "ybar"}[kind]
        axis = ", ".join(part for part in (style, "symbolic x coords={" + ",".join(labels) + "}", "xtick=data") if part)
        plots = "\n".join(
            "      \\addplot coordinates {" + " ".join(f"({label},0)" for label in labels) + "};" for _name in series
        )
        plots += "\n      \\legend{" + ",".join(series) + "}"
    comment = f"  % {description}\n" if description else ""
    caption = f"  \\caption{{{title}}}\n" if title else ""
    return (
        "\\begin{figure}\n  \\centering\n"
        + comment
        + "  \\begin{tikzpicture}\n    \\begin{axis}["
        + axis
        + "]\n"
        + plots
        + "\n    \\end{axis}\n  \\end{tikzpicture}\n"
        + caption
        + "\\end{figure}"
    )


_ADDPLOT = re.compile(r"\\addplot\+?\s*(?:\[[^\]]*\])?\s*(coordinates)?\s*\{")
_PIE = re.compile(r"\\pie\s*(?:\[[^\]]*\])?\s*\{")
_AXIS = re.compile(r"\\begin\{axis\}\s*(?:\[(.*?)\])?", re.DOTALL)
_LEGEND = re.compile(r"\\legend\{([^}]*)\}")
_DOMAIN = re.compile(r"domain\s*=\s*([^:,\]]+):([^,\]]+)")
_COORDINATE = re.compile(r"\(\s*([^,()]+?)\s*,\s*([^()]+?)\s*\)")


def _braced(text: str, start: int) -> str:
    """The text inside the braces opened just before `start`."""
    depth, index = 1, start
    while index < len(text) and depth:
        depth += {"{": 1, "}": -1}.get(text[index], 0)
        index += 1
    return text[start : index - 1]


def pgfplots_chart(content: str, title: str = "") -> str | None:
    """A .tex figure's pgfplots axis as a chart block, for its preview and exports to read and draw (None
    when it has no axis, or one Mathessible cannot read): `\\addplot {sin(deg(x))}` a function's graph,
    `\\addplot coordinates {...}` a data series, `ybar` a bar chart, `only marks` a scatter plot."""
    pie = _PIE.search(content)
    if pie is not None:
        pieces = [piece.strip().partition("/") for piece in _braced(content, pie.end()).split(",")]
        if not pieces or any(not slash or not value.strip() or not label.strip() for value, slash, label in pieces):
            return None
        lines = ["type: pie"]
        if title:
            lines.append(f"title: {title}")
        lines += ["| x | Series 1 |", "| --- | --- |"]
        lines += [f"| {label.strip()} | {value.strip()} |" for value, _slash, label in pieces]
        block = "\n".join(lines)
        try:
            parse_chart(block)
        except ChartError:
            return None
        return "```chart\n" + block + "\n```"

    axis = _AXIS.search(content)
    if axis is None:
        return None
    options = axis.group(1) or ""
    plots = [(found.group(1), _braced(content, found.end())) for found in _ADDPLOT.finditer(content)]
    if not plots:
        return None
    lines = []
    if all(kind is None for kind, _text in plots):
        domain = _DOMAIN.search(options)
        start, end = (domain.group(1).strip(), domain.group(2).strip()) if domain else ("-5", "5")
        lines += ["type: function", "function: " + "; ".join(calculator_expression(text.strip()) for _k, text in plots)]
        lines.append(f"x: {start} .. {end}")
    elif all(kind == "coordinates" for kind, _text in plots):
        kind = "bar" if re.search(r"\bx?ybar\b|\bxbar\b", options) else "scatter" if "only marks" in options else "line"
        series = [_COORDINATE.findall(text) for _k, text in plots]
        legend = _LEGEND.search(content)
        names = [name.strip() for name in legend.group(1).split(",")] if legend else []
        names += [f"Series {index}" for index in range(len(names) + 1, len(series) + 1)]
        labels = list(dict.fromkeys(label for points in series for label, _value in points))
        lines.append(f"type: {kind}")
        lines.append("| " + " | ".join(["x", *names[: len(series)]]) + " |")
        lines.append("|" + "|".join(" --- " for _name in range(len(series) + 1)) + "|")
        for label in labels:
            values = [dict(points).get(label, "") for points in series]
            lines.append("| " + " | ".join([label, *values]) + " |")
    else:
        return None
    if title:
        lines.insert(1, f"title: {title}")
    block = "\n".join(lines)
    try:
        parse_chart(block)
    except ChartError:
        return None
    return "```chart\n" + block + "\n```"
