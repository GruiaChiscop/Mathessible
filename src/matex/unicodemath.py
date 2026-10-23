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
    (the renderer's `matexRender`/`matexHighlight`). Retrying is safe.
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
           color: var(--text); background: var(--page); font-size: 34px;
           -webkit-user-select: none; user-select: none; cursor: default; }
    body.preview { font-size: 28px; }
    #equation { max-width: 100%; }
    math { font-family: "STIX Two Math", "Cambria Math", "Latin Modern Math", math; }
    .matex-current { outline: 3px solid var(--focus); outline-offset: 3px;
                     background: var(--highlight); border-radius: 4px; }
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
    window.matexConvert = function(source, decimalComma) {
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
        parseOffset: parseError ? parseError.offset : null,
        parseFound: parseError ? parseError.found : null
      };
    };
    window.matexRender = function(mathml, preview) {
      document.body.classList.toggle("preview", !!preview);
      const equation = document.getElementById("equation");
      equation.innerHTML = mathml;
      equation.querySelectorAll("*").forEach(node => node.setAttribute("aria-hidden", "true"));
      return true;
    };
    // One id, or several separated by spaces (a selection's leaves).
    window.matexHighlight = function(identifier) {
      document.querySelectorAll(".matex-current").forEach(node => node.classList.remove("matex-current"));
      if (!identifier) return false;
      const nodes = identifier.split(" ").map(id => document.getElementById(id)).filter(node => node);
      if (!nodes.length) return false;
      nodes.forEach(node => node.classList.add("matex-current"));
      nodes[0].scrollIntoView({block: "nearest", inline: "nearest"});
      return true;
    };
    // A click on part of the equation tells the editor which node it was,
    // so sighted users can point at what MathCAT should move to.
    document.addEventListener("mousedown", event => {
      const node = event.target.closest && event.target.closest("#equation [id]");
      const handler = window.matex || (window.webkit && window.webkit.messageHandlers
                                       && window.webkit.messageHandlers.matex);
      if (handler) handler.postMessage(node ? node.id : "");
      event.preventDefault();
    });
    window.matexReady = true;
  </script>
</body>
</html>"""
    # WebKit blocks file:// script subresources in pages created with SetPage.
    # Keeping both official files inline also makes page readiness deterministic.
    page = page_start + parser_javascript + "\n" + converter_javascript + page_end
    return page, base_url


def render_script(mathml: str, preview: bool = False) -> str:
    return f"window.matexRender({json.dumps(mathml)}, {json.dumps(preview)})"


def highlight_script(identifier: str | None) -> str:
    return f"window.matexHighlight({json.dumps(identifier)})"


def conversion_script(source: str, token: int | None = None, decimal_comma: bool = True) -> str:
    """The script converting `source`; `decimal_comma` False makes "1,2" a list (only "." is decimal)."""
    call = f"window.matexConvert({json.dumps(source)}, {json.dumps(decimal_comma)})"
    if token is None:
        return f"JSON.stringify({call})"
    return f"JSON.stringify(Object.assign({call}, {{token: {int(token)}}}))"


def decode_conversion(value: str, token: int | None = None) -> ConversionResult:
    """Decode RunScript's result across the WebKit, Edge and WebView2 backends.

    With a `token`, a result that is not that conversion's own raises
    `StrayScriptResult`.
    """
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
    mathml = decoded.get("mathml")
    error = decoded.get("error")
    if not isinstance(mathml, str):
        raise UnicodeMathError("The UnicodeMathML converter did not return MathML")
    if error is not None and not isinstance(error, str):
        error = str(error)
    offset = decoded.get("parseOffset")
    found = decoded.get("parseFound")
    return ConversionResult(
        mathml=mathml,
        error=error,
        parse_offset=offset if isinstance(offset, int) else None,
        parse_found=found if isinstance(found, str) else None,
    )
