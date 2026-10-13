import json
import shutil
import subprocess
import unittest

from matex.unicodemath import (
    StrayScriptResult,
    conversion_script,
    decode_conversion,
    distribution_directory,
    mathml_has_parse_error,
    renderer_page,
)


class UnicodeMathMLTests(unittest.TestCase):
    def test_browser_distribution_is_available(self) -> None:
        distribution = distribution_directory()
        self.assertTrue((distribution / "unicodemathml-parser.js").is_file())
        self.assertTrue((distribution / "unicodemathml.js").is_file())

    def test_renderer_inlines_javascript_for_webkit(self) -> None:
        page, _base_url = renderer_page()
        self.assertNotIn('<script src=', page)
        self.assertIn("function convertUnicodeMathToMathML", page)
        self.assertIn("window.matexConvert = function", page)

    def test_webview_result_is_decoded_on_all_common_backends(self) -> None:
        payload = json.dumps({"mathml": "<math><mi>x</mi></math>", "error": None})
        self.assertEqual(decode_conversion(payload).mathml, "<math><mi>x</mi></math>")
        self.assertEqual(decode_conversion(json.dumps(payload)).mathml, "<math><mi>x</mi></math>")

    def test_another_scripts_result_is_recognized_as_stray(self) -> None:
        own = json.dumps({"mathml": "<math><mi>x</mi></math>", "error": None, "token": 7})
        self.assertEqual(decode_conversion(own, 7).mathml, "<math><mi>x</mi></math>")
        # matexRender/matexHighlight answer "true"/"false"; an older
        # conversion carries another token.
        for stray in ("true", "false", json.dumps({"mathml": "<math/>", "error": None, "token": 6})):
            with self.assertRaises(StrayScriptResult):
                decode_conversion(stray, 7)
        self.assertIn('{token: 7}', conversion_script("x", 7))

    def test_parse_error_markers_are_detected(self) -> None:
        self.assertTrue(mathml_has_parse_error('<math><mo mathcolor="#F01">/</mo></math>'))
        self.assertFalse(mathml_has_parse_error("<math><mi>x</mi></math>"))

    @unittest.skipUnless(shutil.which("node"), "Node este folosit numai pentru testul parserului oficial")
    def test_official_engine_covers_major_syntax_families(self) -> None:
        distribution = distribution_directory()
        cases = {
            "a/(b+c)": "<mfrac",
            "√(n&a+b)": "<mroot",
            "x_i^2": "<msubsup",
            "∫_0^∞▒f(x)ⅆx": 'intent=\":nary',
            "(■(a&b@c&d))": "<mtable",
            "f̂(x)": "<mover",
            "sin⁡θ": 'intent=\":function',
            "\\alpha+\\beta": "𝛼",
        }
        program = """
const fs = require('fs');
const vm = require('vm');
const { performance } = require('perf_hooks');
const context = { performance };
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), context);
const cases = JSON.parse(process.argv[3]);
const results = {};
for (const [source, needle] of Object.entries(cases)) {
  const conversion = context.convertUnicodeMathToMathML(source, {
    splitInput: true,
    resolveControlWords: true,
    displaystyle: true,
    debug: false,
    caching: true,
    tracing: false,
    forceMathJax: false,
    defaultIntents: true,
    speakSelectionEnds: false,
    doubleStruckMode: 'us-tech',
    transposeChar: 'T'
  });
  results[source] = conversion.mathml.includes(needle);
}
process.stdout.write(JSON.stringify(results));
"""
        completed = subprocess.run(
            [
                "node",
                "-e",
                program,
                str(distribution / "unicodemathml-parser.js"),
                str(distribution / "unicodemathml.js"),
                json.dumps(cases),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        results = json.loads(completed.stdout)
        self.assertEqual([source for source, passed in results.items() if not passed], [])

    @unittest.skipUnless(shutil.which("node"), "Node este folosit numai pentru testul parserului oficial")
    def test_official_engine_marks_incomplete_input_with_error_color(self) -> None:
        distribution = distribution_directory()
        cases = ["a/", "√(", "x_", "(a+b"]
        program = """
const fs = require('fs');
const vm = require('vm');
const { performance } = require('perf_hooks');
const context = { performance };
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), context);
const cases = JSON.parse(process.argv[3]);
const results = {};
for (const source of cases) {
  const conversion = context.convertUnicodeMathToMathML(source, {
    splitInput: true,
    resolveControlWords: true,
    displaystyle: true,
    debug: false,
    caching: true,
    tracing: false,
    forceMathJax: false,
    defaultIntents: true,
    speakSelectionEnds: false,
    doubleStruckMode: 'us-tech',
    transposeChar: 'T'
  });
  results[source] = conversion.mathml.includes('mathcolor="#F0');
}
process.stdout.write(JSON.stringify(results));
"""
        completed = subprocess.run(
            [
                "node",
                "-e",
                program,
                str(distribution / "unicodemathml-parser.js"),
                str(distribution / "unicodemathml.js"),
                json.dumps(cases),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        results = json.loads(completed.stdout)
        self.assertEqual([source for source, passed in results.items() if not passed], [])


if __name__ == "__main__":
    unittest.main()
