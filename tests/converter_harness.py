"""The real UnicodeMathML converter for tests, run under Node instead of the app's WebView.

The dist scripts run fine in a bare `vm` context; this loads them once per
call and converts every source given, so a test can check what the
converter really builds without the GUI.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest

from mathessible.unicodemath import distribution_directory, latex_converter_path

needs_node = unittest.skipUnless(shutil.which("node"), "Node is needed to run the UnicodeMathML converter")

# The options the app's renderer page passes (unicodemath.renderer_page).
RENDERER_OPTIONS = {
    "splitInput": True,
    "resolveControlWords": True,
    "displaystyle": True,
    "debug": False,
    "caching": True,
    "tracing": False,
    "forceMathJax": False,
    "defaultIntents": True,
    "speakSelectionEnds": False,
    "doubleStruckMode": "us-tech",
    "transposeChar": "T",
}

_PROGRAM = """
const fs = require('fs'), vm = require('vm');
const context = {performance: require('perf_hooks').performance, console: {log() {}, warn() {}, error() {}}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), context);
vm.runInContext(fs.readFileSync(process.argv[3], 'utf8').replace(/^\ufeff/, ''), context);
const request = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(request.sources.map(source => {
  // As the renderer page's mathessibleConvert: LaTeX through Sargent's TeX2UnicodeMath first.
  let unicodemath = source;
  if (request.latex) {
    try {
      unicodemath = vm.runInContext('TeX2UnicodeMath(' + JSON.stringify(source) + ')', context);
    } catch (error) {
      return {mathml: '', parseError: null, unicodemath: null, error: 'LaTeX: ' + String(error)};
    }
  }
  const result = context.convertUnicodeMathToMathML(unicodemath, request.options);
  return {mathml: result.mathml, parseError: result.parseError || null, unicodemath: unicodemath};
})));
"""


def convert_all(sources: list[str], latex: bool = False, **options: object) -> list[dict]:
    """Each source's {"mathml", "parseError", "unicodemath"} (LaTeX sources with `latex`); `options` added to the
    renderer's."""
    distribution = distribution_directory()
    scripts = [distribution / "unicodemathml-parser.js", distribution / "unicodemathml.js", latex_converter_path()]
    completed = subprocess.run(
        ["node", "-e", _PROGRAM, *map(str, scripts)],
        input=json.dumps({"sources": sources, "latex": latex, "options": {**RENDERER_OPTIONS, **options}}),
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def convert(source: str, **options: object) -> str:
    return convert_all([source], **options)[0]["mathml"]


def builds(mathml: str) -> bool:
    """No total failure (`mathcolor="#F00"` around everything)."""
    return 'mathcolor="#F00"' not in mathml


def has_error(mathml: str) -> bool:
    """Any error marker: a total failure or a dangling token (`#F01`)."""
    return 'mathcolor="#F0' in mathml
