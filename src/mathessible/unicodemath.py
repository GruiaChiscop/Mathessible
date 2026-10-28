from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path


class UnicodeMathError(ValueError):
    """Raised when the official UnicodeMathML parser rejects an expression."""


class StrayScriptResult(UnicodeMathError):
    """RunScript handed back another script's result instead of the conversion's.

    wxWidgets' synchronous `RunScript` takes the first script result that
    arrives while it waits, including one from an earlier `RunScriptAsync`
    (the renderer's `mathessibleRender`/`mathessibleHighlight`). Retrying is safe.
    """


@dataclass(frozen=True, slots=True)
class ConversionResult:
    mathml: str
    error: str | None = None
    # Where the parser stopped when nothing parsed (`#F00`), in the source's
    # UTF-16 units (patches/unicodemathml/0002), and what it found there
    # (None: the source ended too early).
    parse_offset: int | None = None
    parse_found: str | None = None


def code_point_index(text: str, utf16_offset: int) -> int:
    """The `text` index of a JavaScript (UTF-16) offset: 𝑥 and friends are two units there."""
    units = 0
    for index, character in enumerate(text):
        if units >= utf16_offset:
            return index
        units += 2 if ord(character) > 0xFFFF else 1
    return len(text)


def mathml_has_parse_error(mathml: str) -> bool:
    """Return True when UnicodeMathML marks converter output as incomplete/invalid."""
    return 'mathcolor="#F0' in mathml or "mathcolor='#F0" in mathml


def distribution_directory() -> Path:
    """Locate the JavaScript distribution supplied by the UnicodeMathML submodule."""
    repository_root = Path(__file__).resolve().parents[2]
    directory = repository_root / "UnicodeMathML" / "dist"
    required = (directory / "unicodemathml-parser.js", directory / "unicodemathml.js")
    if not all(path.is_file() for path in required):
        raise FileNotFoundError(
            "The UnicodeMathML submodule is not initialized. Run: git submodule update --init --recursive"
        )
    return directory


# One `'word': 'symbol',` entry per line of UnicodeMathML's controlWords table.
# The converter writes a literal "&" (`\\&`, `"&"`) unescaped, which is not XML.
_BARE_AMPERSAND = re.compile(r"&(?!(?:[A-Za-z]+|#[0-9]+|#x[0-9A-Fa-f]+);)")
# It also splits some characters past U+FFFF into their UTF-16 halves, one
# token each (🜁 is `<mo>\\ud83d</mo><mo>\\udf01</mo>`), which no UTF-8 text holds.
_SPLIT_PAIR = re.compile(r"<(m[a-z]+)([^>]*)>([\ud800-\udbff])</\1>\s*<m[a-z]+[^>]*>([\udc00-\udfff])</m[a-z]+>")
_LONE_SURROGATE = re.compile(r"[\ud800-\udfff]")


def _join_split_pairs(mathml: str) -> str:
    """One token per character again (`_SPLIT_PAIR`); a half left alone becomes U+FFFD."""
    joined = _SPLIT_PAIR.sub(
        lambda match: (
            f"<{match[1]}{match[2]}>"
            + (match[3] + match[4]).encode("utf-16", "surrogatepass").decode("utf-16")
            + f"</{match[1]}>"
        ),
        mathml,
    )
    joined = joined.encode("utf-16", "surrogatepass").decode("utf-16", "replace")  # Pairs left within a token.
    return _LONE_SURROGATE.sub("\ufffd", joined)


_CONTROL_WORD_ENTRY = re.compile(r"^\s*'([A-Za-z0-9]+)':\s*'((?:[^'\\]|\\u[0-9A-Fa-f]{4})*)'")


@cache
def control_words() -> dict[str, str]:
    """The converter's own control-word table (`\\circ` -> "∘", ...), read from its JS.

    Read rather than copied, so it follows the UnicodeMathML submodule. Left
    out: empty entries (\\Bigl, ...) and the circled numbers ①-⒇, which in
    UnicodeMathML index the examples of its playground page, not symbols.
    """
    script = (distribution_directory() / "unicodemathml.js").read_text(encoding="utf-8")
    start = script.index("const controlWords = {")
    end = script.index("\n}", start)
    words: dict[str, str] = {}
    for line in script[start:end].splitlines()[1:]:
        match = _CONTROL_WORD_ENTRY.match(line)
        if match is None:
            continue
        word, symbol = match.groups()
        symbol = re.sub(r"\\u([0-9A-Fa-f]{4})", lambda escape: chr(int(escape.group(1), 16)), symbol)
        if symbol and not "①" <= symbol <= "⒇":
            words[word] = symbol
    return words


def latex_converter_path() -> Path:
    """Murray Sargent's LaTeX converter (LaTeX to UnicodeMath, MathML to LaTeX), from UnicodeMathML's playground.

    It is not in the dist build, but is the same project's (MIT): the converter itself
    calls its `TeX2UnicodeMath` for a source in `\\( ... \\)`.
    """
    path = distribution_directory().parent / "playground" / "assets" / "TeX.js"
    if not path.is_file():
        raise FileNotFoundError(
            "The UnicodeMathML submodule is not initialized. Run: git submodule update --init --recursive"
        )
    return path


def renderer_page() -> tuple[str, str]:
    """Return the private, non-accessible page used only for visual MathML rendering."""
    distribution = distribution_directory()
    base_url = distribution.as_uri() + "/"
    parser_javascript = (distribution / "unicodemathml-parser.js").read_text(encoding="utf-8-sig")
    converter_javascript = (distribution / "unicodemathml.js").read_text(encoding="utf-8-sig")
    page_start = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <style>
    :root { color-scheme: light dark; --text: #1d1d1f; --page: #ffffff;
            --focus: #0063d6; --highlight: #d7e8ff; }
    @media (prefers-color-scheme: dark) {
      :root { --text: #ececf0; --page: #1e1e1e; --focus: #5aa2ff; --highlight: #20426e; }
    }
    html, body { width: 100%; height: 100%; margin: 0; overflow: auto; }
    body { display: flex; align-items: center; justify-content: center;
           box-sizing: border-box; padding: 14px 18px;
           color: var(--text); background: var(--page); font-size: calc(34px * var(--mathessible-zoom, 1));
           -webkit-user-select: none; user-select: none; cursor: text; }
    body.preview { font-size: calc(28px * var(--mathessible-zoom, 1)); }
    #equation { max-width: 100%; }
    math { font-family: "STIX Two Math", "Cambria Math", "Latin Modern Math", math; }
    .mathessible-current { outline: 3px solid var(--focus); outline-offset: 3px;
                     background: var(--highlight); border-radius: 4px; }
    .mathessible-selected { background: var(--highlight); border-radius: 2px; }
    #mathessible-caret { position: absolute; width: 2px; background: var(--focus); display: none;
                   pointer-events: none; animation: mathessible-blink 1.06s steps(1) infinite; }
    @keyframes mathessible-blink { 50% { opacity: 0; } }
    .unicodemathml-error { color: #b00020; font-family: sans-serif; font-size: 16px; }
  </style>
  <script>
"""
    page_end = """
  </script>
</head>
<body aria-hidden="true">
  <div id="equation" aria-hidden="true"></div>
  <script>
    window.mathessibleConvert = function(source, decimalComma, latex) {
      if (latex) {
        // A LaTeX equation: Sargent's own LaTeX to UnicodeMath, then the converter as always.
        try {
          source = TeX2UnicodeMath(source);
        } catch (error) {
          return {mathml: "", error: "LaTeX: " + String(error), parseOffset: null, parseFound: null};
        }
      }
      const result = convertUnicodeMathToMathML(source, {
        decimalComma: decimalComma !== false,
        splitInput: true,
        resolveControlWords: true,
        displaystyle: true,
        debug: false,
        caching: true,
        tracing: false,
        forceMathJax: false,
        defaultIntents: true,
        speakSelectionEnds: false,
        doubleStruckMode: "us-tech",
        transposeChar: "T"
      });
      const holder = document.createElement("div");
      holder.innerHTML = result.mathml;
      const errorNode = holder.querySelector(".unicodemathml-error-message");
      const parseError = result.parseError || null;
      return {
        mathml: result.mathml,
        error: errorNode ? errorNode.textContent : null,
        // A LaTeX source's offsets are in the UnicodeMath it became, not in the LaTeX.
        parseOffset: parseError && !latex ? parseError.offset : null,
        parseFound: parseError && !latex ? parseError.found : null
      };
    };
    // An equation's MathML as LaTeX (Sargent's MathMLtoTeX), for a document changed to LaTeX.
    window.mathessibleToLaTeX = function(mathml) {
      try {
        return {latex: MathMLtoTeX(mathml)};
      } catch (error) {
        return {error: String(error)};
      }
    };
    // Pasted MathML (a web page's, Word's) back to UnicodeMath, by the converter's own lineariser.
    window.mathessibleFromMathML = function(mathml) {
      try {
        return {unicodemath: MathMLtoUnicodeMath(mathml)};
      } catch (error) {
        return {error: String(error)};
      }
    };
    window.mathessibleRender = function(mathml, preview) {
      document.body.classList.toggle("preview", !!preview);
      const equation = document.getElementById("equation");
      equation.innerHTML = mathml;
      const caret = document.getElementById("mathessible-caret");
      if (caret) caret.style.display = "none";  // A new equation: no caret until one is placed.
      equation.querySelectorAll("*").forEach(node => node.setAttribute("aria-hidden", "true"));
      return true;
    };
    // One id, or several separated by spaces (a selection's leaves).
    // With `selected`, a selection's leaves (shaded); else the element being read (outlined).
    window.mathessibleHighlight = function(identifier, selected) {
      document.querySelectorAll(".mathessible-current, .mathessible-selected").forEach(
        node => node.classList.remove("mathessible-current", "mathessible-selected"));
      if (!identifier) return false;
      const nodes = identifier.split(" ").map(id => document.getElementById(id)).filter(node => node);
      if (!nodes.length) return false;
      nodes.forEach(node => node.classList.add(selected ? "mathessible-selected" : "mathessible-current"));
      nodes[0].scrollIntoView({block: "nearest", inline: "nearest"});
      return true;
    };
    // Where typing goes, as a text field's caret: at an element's edge ("before"/"after"),
    // or between the characters of a token ("inside", `index` characters in). null hides it.
    window.mathessibleCaret = function(spec) {
      let caret = document.getElementById("mathessible-caret");
      if (!caret) {
        caret = document.createElement("div");
        caret.id = "mathessible-caret";
        caret.setAttribute("aria-hidden", "true");
        document.body.appendChild(caret);
      }
      const node = spec && document.getElementById(spec.id);
      if (!node) { caret.style.display = "none"; return false; }
      let rect = node.getBoundingClientRect();
      let x = spec.side === "before" ? rect.left : rect.right;
      const text = node.firstChild;
      if (spec.side === "inside" && text && text.nodeType === Node.TEXT_NODE) {
        const range = document.createRange();
        const offset = Math.min(spec.index, text.length);
        range.setStart(text, offset);
        range.setEnd(text, offset);
        const at = range.getBoundingClientRect();
        if (at.height) x = at.left;
      }
      const height = Math.max(rect.height, parseFloat(getComputedStyle(document.body).fontSize) * 0.9);
      const top = rect.top + rect.height / 2 - height / 2;
      caret.style.left = (x + window.scrollX - 1) + "px";
      caret.style.top = (top + window.scrollY) + "px";
      caret.style.height = height + "px";
      caret.style.display = "block";
      caret.style.animation = "none";
      void caret.offsetWidth;  // Restart the blink: the caret stays on while typing.
      caret.style.animation = "";
      node.scrollIntoView({block: "nearest", inline: "nearest"});
      return true;
    };
    // The mouse tells the editor where it points, as JSON: the element, the side of
    // it the pointer is on ("before"/"after"), or "inside" a token with the characters
    // before the pointer; `kind` is "down", "drag", "up" or "double" (a double click).
    function mathessiblePoint(event, kind) {
      const node = event.target.closest && event.target.closest("#equation [id]");
      if (!node) return {kind: kind, id: ""};
      const rect = node.getBoundingClientRect();
      const point = {kind: kind, id: node.id, side: event.clientX < rect.left + rect.width / 2 ? "before" : "after"};
      const text = node.firstChild;
      if (!node.children.length && text && text.nodeType === Node.TEXT_NODE && text.length > 1
          && document.caretRangeFromPoint) {
        const range = document.caretRangeFromPoint(event.clientX, event.clientY);
        if (range && range.startContainer === text && range.startOffset > 0 && range.startOffset < text.length) {
          point.side = "inside";
          point.index = range.startOffset;
        }
      }
      return point;
    }
    function mathessiblePost(point) {
      const handler = window.mathessible || (window.webkit && window.webkit.messageHandlers
                                       && window.webkit.messageHandlers.mathessible);
      if (handler) handler.postMessage(JSON.stringify(point));
    }
    let mathessibleDragging = false, mathessibleLastDrag = "";
    document.addEventListener("mousedown", event => {
      mathessibleDragging = event.button === 0;
      mathessibleLastDrag = "";
      mathessiblePost(mathessiblePoint(event, event.detail === 2 ? "double" : "down"));
      event.preventDefault();
    });
    document.addEventListener("mousemove", event => {
      if (!mathessibleDragging || !(event.buttons & 1)) return;
      const point = mathessiblePoint(event, "drag");
      const key = point.id + point.side + (point.index || "");
      if (key !== mathessibleLastDrag) { mathessibleLastDrag = key; mathessiblePost(point); }
    });
    document.addEventListener("mouseup", event => {
      if (mathessibleDragging) mathessiblePost({kind: "up", id: ""});
      mathessibleDragging = false;
    });
    window.mathessibleZoom = function(factor) {
      document.documentElement.style.setProperty("--mathessible-zoom", factor);
      return true;
    };
    window.mathessibleReady = true;
  </script>
</body>
</html>"""
    # WebKit blocks file:// script subresources in pages created with SetPage.
    # Keeping both official files inline also makes page readiness deterministic.
    latex_javascript = latex_converter_path().read_text(encoding="utf-8-sig")
    page = page_start + parser_javascript + "\n" + converter_javascript + "\n" + latex_javascript + page_end
    return page, base_url


def render_script(mathml: str, preview: bool = False) -> str:
    return f"window.mathessibleRender({json.dumps(mathml)}, {json.dumps(preview)})"


def highlight_script(identifier: str | None, selected: bool = False) -> str:
    return f"window.mathessibleHighlight({json.dumps(identifier)}, {json.dumps(selected)})"


def zoom_script(factor: float) -> str:
    return f"window.mathessibleZoom({json.dumps(factor)})"


def caret_script(spec: dict | None) -> str:
    """Show the caret at an insertion point (`mathessibleCaret`: id, side, index), or hide it with None."""
    return f"window.mathessibleCaret({json.dumps(spec)})"


def conversion_script(source: str, token: int | None = None, decimal_comma: bool = True, latex: bool = False) -> str:
    """The script converting `source` (LaTeX with `latex`); `decimal_comma` False makes "1,2" a list."""
    call = f"window.mathessibleConvert({json.dumps(source)}, {json.dumps(decimal_comma)}, {json.dumps(latex)})"
    if token is None:
        return f"JSON.stringify({call})"
    return f"JSON.stringify(Object.assign({call}, {{token: {int(token)}}}))"


def from_mathml_script(mathml: str, token: int) -> str:
    """The script turning pasted MathML into UnicodeMath (`mathessibleFromMathML`)."""
    return f"JSON.stringify(Object.assign(window.mathessibleFromMathML({json.dumps(mathml)}), {{token: {int(token)}}}))"


def to_latex_script(mathml: str, token: int) -> str:
    """The script turning an equation's MathML into LaTeX (`mathessibleToLaTeX`)."""
    return f"JSON.stringify(Object.assign(window.mathessibleToLaTeX({json.dumps(mathml)}), {{token: {int(token)}}}))"


def decode_to_latex(value: str, token: int) -> str:
    """The LaTeX `mathessibleToLaTeX` gave; its failure raises `UnicodeMathError`."""
    decoded = _decoded(value, token)
    latex = decoded.get("latex")
    if not isinstance(latex, str):
        raise UnicodeMathError(str(decoded.get("error") or "the equation could not be written as LaTeX"))
    return latex


def _decoded(value: str, token: int | None) -> dict:
    """RunScript's JSON result as a dict; another script's result raises `StrayScriptResult`."""
    decoded: object = value
    for _ in range(2):
        if not isinstance(decoded, str):
            break
        try:
            decoded = json.loads(decoded)
        except json.JSONDecodeError:
            break
    if token is not None and (not isinstance(decoded, dict) or decoded.get("token") != token):
        raise StrayScriptResult("The UnicodeMathML converter returned another script's result")
    if not isinstance(decoded, dict):
        raise UnicodeMathError("The UnicodeMathML converter returned an unknown result")
    return decoded


def decode_from_mathml(value: str, token: int) -> str:
    """The UnicodeMath `mathessibleFromMathML` gave; its failure raises `UnicodeMathError`."""
    decoded = _decoded(value, token)
    unicodemath = decoded.get("unicodemath")
    if not isinstance(unicodemath, str):
        raise UnicodeMathError(str(decoded.get("error") or "the MathML could not be converted"))
    return unicodemath


def decode_conversion(value: str, token: int | None = None) -> ConversionResult:
    """Decode RunScript's result across the WebKit, Edge and WebView2 backends.

    With a `token`, a result that is not that conversion's own raises
    `StrayScriptResult`.
    """
    decoded = _decoded(value, token)
    mathml = decoded.get("mathml")
    error = decoded.get("error")
    if not isinstance(mathml, str):
        raise UnicodeMathError("The UnicodeMathML converter did not return MathML")
    if error is not None and not isinstance(error, str):
        error = str(error)
    offset = decoded.get("parseOffset")
    found = decoded.get("parseFound")
    return ConversionResult(
        mathml=_BARE_AMPERSAND.sub("&amp;", _join_split_pairs(mathml)),
        error=error,
        parse_offset=offset if isinstance(offset, int) else None,
        parse_found=found if isinstance(found, str) else None,
    )
