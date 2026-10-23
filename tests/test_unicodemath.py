import json
import unittest

from converter_harness import convert, convert_all, has_error, needs_node
from matex.unicodemath import (
    StrayScriptResult,
    code_point_index,
    control_words,
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
        self.assertNotIn("<script src=", page)
        self.assertIn("function convertUnicodeMathToMathML", page)
        self.assertIn("window.matexConvert = function", page)

    def test_webview_result_is_decoded_on_all_common_backends(self) -> None:
        payload = json.dumps({"mathml": "<math><mi>x</mi></math>", "error": None})
        self.assertEqual(decode_conversion(payload).mathml, "<math><mi>x</mi></math>")
        self.assertEqual(decode_conversion(json.dumps(payload)).mathml, "<math><mi>x</mi></math>")

    def test_a_literal_ampersand_is_escaped_for_xml(self) -> None:
        # The converter writes `\\&` and `"&"` as a bare "&", which no XML parser takes.
        payload = json.dumps({"mathml": '<math><mo intent=":text">&</mo><mo>&lt;</mo><mi>&#x1D44E;</mi></math>'})
        self.assertEqual(
            decode_conversion(payload).mathml,
            '<math><mo intent=":text">&amp;</mo><mo>&lt;</mo><mi>&#x1D44E;</mi></math>',
        )

    def test_a_character_split_into_utf16_halves_is_joined(self) -> None:
        # The converter gives 🜁 (U+1F701) as two tokens, one UTF-16 half each.
        payload = json.dumps({"mathml": "<math><mi>x</mi><mo>\ud83d</mo><mo>\udf01</mo></math>"})
        self.assertEqual(decode_conversion(payload).mathml, "<math><mi>x</mi><mo>\U0001f701</mo></math>")
        lone = json.dumps({"mathml": '<math><mo intent=":text">\ud83d</mo></math>'})
        self.assertEqual(decode_conversion(lone).mathml, '<math><mo intent=":text">\ufffd</mo></math>')

    def test_another_scripts_result_is_recognized_as_stray(self) -> None:
        own = json.dumps({"mathml": "<math><mi>x</mi></math>", "error": None, "token": 7})
        self.assertEqual(decode_conversion(own, 7).mathml, "<math><mi>x</mi></math>")
        # matexRender/matexHighlight answer "true"/"false"; an older
        # conversion carries another token.
        for stray in ("true", "false", json.dumps({"mathml": "<math/>", "error": None, "token": 6})):
            with self.assertRaises(StrayScriptResult):
                decode_conversion(stray, 7)
        self.assertIn("{token: 7}", conversion_script("x", 7))
        self.assertIn('window.matexConvert("x", false)', conversion_script("x", decimal_comma=False))
        stopped = decode_conversion(
            json.dumps({"mathml": "<math/>", "error": None, "parseOffset": 3, "parseFound": ")"})
        )
        self.assertEqual((stopped.parse_offset, stopped.parse_found), (3, ")"))
        # 𝑥 is two UTF-16 units.
        self.assertEqual(code_point_index("𝑥+)", 3), 2)

    def test_parse_error_markers_are_detected(self) -> None:
        self.assertTrue(mathml_has_parse_error('<math><mo mathcolor="#F01">/</mo></math>'))
        self.assertFalse(mathml_has_parse_error("<math><mi>x</mi></math>"))

    @needs_node
    def test_decimal_comma_is_an_option(self) -> None:
        # patches/unicodemathml/0001: without decimalComma, "{1,2,3}" is a list of three.
        self.assertIn("<mn>1,2</mn>", convert("{1,2,3}", decimalComma=True))
        self.assertIn("<mn>1</mn><mo>,</mo><mn>2</mn><mo>,</mo><mn>3</mn>", convert("{1,2,3}", decimalComma=False))

    @needs_node
    def test_a_function_applied_to_a_subscripted_letter_converts(self) -> None:
        # patches/unicodemathml/0003: "sin qa_n" threw in preprocess.
        self.assertIn("<msub>", convert("sin qa_n"))

    @needs_node
    def test_the_parser_says_where_it_stopped(self) -> None:
        # patches/unicodemathml/0002: where parsing stopped, in the source's own offsets.
        results = convert_all(["\\alpha+b)", "a&b", "x+1"])
        self.assertEqual(
            [result["parseError"] for result in results],
            [{"offset": 8, "found": ")"}, {"offset": 1, "found": "&"}, None],
        )

    @needs_node
    def test_official_engine_covers_major_syntax_families(self) -> None:
        cases = {
            "a/(b+c)": "<mfrac",
            "√(n&a+b)": "<mroot",
            "x_i^2": "<msubsup",
            "∫_0^∞▒f(x)ⅆx": 'intent=":nary',
            "(■(a&b@c&d))": "<mtable",
            "f̂(x)": "<mover",
            "sin⁡θ": 'intent=":function',
            "\\alpha+\\beta": "𝛼",
        }
        results = convert_all(list(cases))
        missing = [
            source
            for (source, needle), result in zip(cases.items(), results, strict=True)
            if needle not in result["mathml"]
        ]
        self.assertEqual(missing, [])

    @needs_node
    def test_official_engine_marks_incomplete_input_with_error_color(self) -> None:
        cases = ["a/", "√(", "x_", "(a+b"]
        unmarked = [
            source for source, result in zip(cases, convert_all(cases), strict=True) if not has_error(result["mathml"])
        ]
        self.assertEqual(unmarked, [])

    def test_control_words_come_from_the_converter_table(self) -> None:
        words = control_words()
        self.assertGreater(len(words), 500)
        self.assertEqual(words["circ"], "∘")
        self.assertEqual(words["alpha"], "α")
        self.assertEqual(words["matrix"], "■")
        # Word's root shortcuts, which start with a digit.
        self.assertEqual((words["2root"], words["3root"], words["4root"]), ("√", "∛", "∜"))
        self.assertEqual(words["nbsp"], "\u00a0")  # A \\u escape in the JS.
        self.assertNotIn("Bigl", words)  # Empty in the table.
        self.assertNotIn("Faraday", words)  # A playground example, not a symbol.


if __name__ == "__main__":
    unittest.main()
