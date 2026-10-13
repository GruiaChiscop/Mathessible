import unittest

from matex.mathcat import MathCatNavigator
from matex.mathml_model import MathMLModelError, MathMLDocument, sanitize_mathml


MATRIX = """<math display="block"><mrow><mo>(</mo><mtable intent=":matrix(2,2)">
<mtr><mtd><mi>a</mi></mtd><mtd><mi>b</mi></mtd></mtr>
<mtr><mtd><mi>c</mi></mtd><mtd><mi>d</mi></mtd></mtr>
</mtable><mo>)</mo></mrow></math>"""

INTEGRAL = """<math><mrow><mrow intent=":nary(a,b,$naryand)">
<msubsup><mo>∫</mo><mi>a</mi><mi>b</mi></msubsup><mi arg="naryand">x</mi>
</mrow><mi>d</mi><mi>x</mi></mrow></math>"""


class MathMLModelTests(unittest.TestCase):
    def test_semantic_roles_for_fraction_and_scripts(self) -> None:
        document = MathMLDocument.parse(
            """<math id="root"><mfrac id="fraction"><mi id="num">x</mi>
            <msup id="den"><mi id="base">y</mi><mn id="power">2</mn></msup>
            </mfrac></math>"""
        )
        self.assertEqual(document.semantic_role("num"), "numerator")
        self.assertEqual(document.semantic_role("den"), "denominator")
        self.assertEqual(document.semantic_role("base"), "base")
        self.assertEqual(document.semantic_role("power"), "superscript")

    def test_integral_limits_are_structural(self) -> None:
        document = MathMLDocument.parse(
            """<math id="root"><mrow id="integral"><msubsup id="limits">
            <mo id="operator">∫</mo><mn id="lower">0</mn><mi id="upper">∞</mi>
            </msubsup><mi id="body">x</mi></mrow></math>"""
        )
        self.assertEqual(document.semantic_role("lower"), "lower limit")
        self.assertEqual(document.semantic_role("upper"), "upper limit")
        self.assertEqual(document.regions("lower"), ("lower limit",))
        self.assertEqual(document.regions("upper"), ("upper limit",))

    def test_limit_condition_is_structural(self) -> None:
        document = MathMLDocument.parse(
            """<math id="root"><mrow id="expr"><munder id="limit">
            <mo id="lim">lim</mo><mrow id="condition"><mi id="x">x</mi>
            <mo id="arrow">→</mo><mi id="infinity">∞</mi></mrow></munder>
            <mi id="f">f</mi></mrow></math>"""
        )
        self.assertEqual(document.semantic_role("condition"), "limit condition")
        self.assertIn("limit condition", document.regions("x"))

    def test_integrand_and_function_argument_boundaries(self) -> None:
        document = MathMLDocument.parse(
            """<math id="root"><mrow id="nary" intent=":nary(a,b,$naryand)">
            <msubsup id="op"><mo id="int">∫</mo><mi id="a">a</mi><mi id="b">b</mi></msubsup>
            <mi id="integrand" arg="naryand">x</mi></mrow><mi id="dx">d</mi>
            <mrow id="function" intent=":function"><mi id="sin">sin</mi><mo id="apply">⁡</mo>
            <mrow id="argument" intent=":fenced"><mo id="open">(</mo><mi id="y">y</mi>
            <mo id="close">)</mo></mrow></mrow><mo id="plus">+</mo></math>"""
        )
        self.assertIn("integrand", document.regions("integrand"))
        self.assertEqual(document.exited_regions("integrand", "dx"), ("integrand",))
        self.assertEqual(document.entered_regions("dx", "integrand"), ("integrand",))
        self.assertIn("argument", document.regions("y"))
        self.assertEqual(document.exited_regions("close", "plus"), ("argument",))
        self.assertEqual(document.entered_regions("plus", "y"), ("argument",))

    def test_recognized_functions_create_function_name_and_argument_regions(self) -> None:
        document = MathMLDocument.parse(
            """<math id="root"><mrow id="function"><mi id="tg">tg</mi>
            <mo id="apply">⁡</mo><mrow id="argument" intent=":fenced">
            <mo id="open">(</mo><mi id="x">x</mi><mo id="close">)</mo>
            </mrow><mo id="plus">+</mo><mi id="y">y</mi></mrow></math>""",
            recognized_functions=("tg",),
        )
        self.assertEqual(document.regions("tg"), ("function name",))
        self.assertEqual(document.regions("x"), ("argument",))
        self.assertEqual(document.exited_regions("tg", "x"), ("function name",))
        self.assertEqual(document.entered_regions("tg", "x"), ("argument",))

    def test_mathcat_speech_is_augmented_when_leaving_integrand(self) -> None:
        navigator = MathCatNavigator(language="en")
        navigator.load(INTEGRAL)
        navigator.command("ZoomIn")
        navigator.command("ZoomIn")
        navigator.command("MoveNext")
        speech = navigator.command_with_boundaries("MoveNext")
        self.assertEqual(speech, "end integrand")
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "d")

    def test_mathcat_navigation_announces_integral_limit_boundaries(self) -> None:
        navigator = MathCatNavigator(language="en")
        navigator.load("""<math id="root"><mrow id="integral"><msubsup id="limits">
        <mo id="operator">∫</mo><mi id="a">a</mi><mi id="b">b</mi>
        </msubsup><mi id="body">x</mi></mrow></math>""")
        navigator.command_with_boundaries("ZoomIn")
        navigator.command_with_boundaries("ZoomIn")

        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "start lower limit")
        self.assertTrue(navigator.command_with_boundaries("MoveNext"))
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "end lower limit")
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "start upper limit")
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "b")

    def test_mathcat_navigation_announces_limit_condition_boundaries(self) -> None:
        navigator = MathCatNavigator(language="en")
        navigator.load("""<math id="root"><mrow id="expr"><munder id="limit">
        <mo id="lim">lim</mo><mrow id="condition"><mi id="x">x</mi>
        <mo id="arrow">→</mo><mi id="infinity">∞</mi></mrow></munder>
        <mi id="f">f</mi></mrow></math>""")
        navigator.command_with_boundaries("ZoomIn")

        self.assertEqual(navigator.command_with_boundaries("ZoomIn"), "start limit condition")
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "x")
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "approaches")
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "infinity")
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "end limit condition")

    def test_mathcat_navigation_announces_recognized_function_boundaries(self) -> None:
        navigator = MathCatNavigator(language="en", recognized_functions=("tg",))
        navigator.load("""<math id="root"><mrow id="function"><mi id="tg">tg</mi>
        <mo id="apply">⁡</mo><mrow id="argument" intent=":fenced">
        <mo id="open">(</mo><mi id="x">x</mi><mo id="close">)</mo>
        </mrow><mo id="plus">+</mo><mi id="y">y</mi></mrow></math>""")

        self.assertIn("tangent", navigator.command_with_boundaries("ZoomIn"))
        self.assertEqual(navigator.command_with_boundaries("ZoomIn"), "start function name")
        self.assertIn("tangent", navigator.command_with_boundaries("MoveNext"))
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "end function name")
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "start argument")
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "x")
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "end argument")
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "plus")

    def test_mathcat_speech_is_augmented_when_entering_structural_regions(self) -> None:
        navigator = MathCatNavigator(language="en")
        navigator.load("""<math id="root"><mfrac id="fraction"><mi id="num">x</mi>
        <mi id="den">y</mi></mfrac></math>""")

        speech = navigator.command_with_boundaries("ZoomIn")
        self.assertEqual(speech, "start fraction")
        speech = navigator.command_with_boundaries("MoveNext")
        self.assertEqual(speech, "start numerator")

        speech = navigator.command_with_boundaries("MoveNext")
        self.assertEqual(speech, "x")
        speech = navigator.command_with_boundaries("MoveNext")
        self.assertEqual(speech, "end numerator")
        speech = navigator.command_with_boundaries("MoveNext")
        self.assertEqual(speech, "start denominator")
        speech = navigator.command_with_boundaries("MoveNext")
        self.assertEqual(speech, "y")

    def test_fraction_end_is_a_virtual_navigation_stop(self) -> None:
        navigator = MathCatNavigator(language="en")
        navigator.load("""<math id="root"><mrow id="row"><mfrac id="fraction">
        <mi id="num">x</mi><mi id="den">y</mi></mfrac><mo id="plus">+</mo>
        <mi id="z">z</mi></mrow></math>""")
        navigator.command("ZoomIn")
        navigator.command("ZoomIn")
        navigator.command_with_boundaries("MoveNext")
        navigator.command_with_boundaries("MoveNext")
        navigator.command_with_boundaries("MoveNext")

        speech = navigator.command_with_boundaries("MoveNext")
        self.assertEqual(speech, "end denominator")
        speech = navigator.command_with_boundaries("MoveNext")
        self.assertEqual(speech, "end fraction")
        speech = navigator.command_with_boundaries("MoveNext")
        self.assertEqual(speech, "plus")

    def test_current_context_reports_structural_position(self) -> None:
        navigator = MathCatNavigator(language="en")
        navigator.load("""<math id="root"><mrow id="row"><mfrac id="fraction">
        <mi id="num">x</mi><mi id="den">y</mi></mfrac><mo id="plus">+</mo>
        <mi id="z">z</mi></mrow></math>""")
        navigator.command("ZoomIn")
        navigator.command("ZoomIn")
        self.assertEqual(navigator.current_context(), "inside numerator; inside fraction")

        navigator.command_with_boundaries("MoveNext")
        self.assertEqual(navigator.current_context(), "at end numerator")

        navigator.command_with_boundaries("MoveNext")
        self.assertEqual(navigator.current_context(), "at start denominator")

        navigator.command_with_boundaries("MoveNext")
        self.assertEqual(navigator.current_context(), "inside denominator; inside fraction")

    def test_current_context_reports_matrix_cell_position(self) -> None:
        navigator = MathCatNavigator(language="en")
        navigator.load(MATRIX)
        navigator.cell_command("MoveCellNext")
        self.assertEqual(navigator.current_context(), "row 1, column 1; inside matrix")

    def test_read_current_zone_reports_nearest_structural_region(self) -> None:
        navigator = MathCatNavigator(language="en")
        navigator.load("""<math id="root"><mrow id="row"><mfrac id="fraction">
        <mi id="num">x</mi><mi id="den">y</mi></mfrac><mo id="plus">+</mo>
        <mi id="z">z</mi></mrow></math>""")
        navigator.command("ZoomIn")
        navigator.command("ZoomIn")
        self.assertEqual(navigator.read_current_zone(), "numerator, x")

        navigator.command_with_boundaries("MoveNext")
        self.assertEqual(navigator.read_current_zone(), "end numerator")

        navigator.command_with_boundaries("MoveNext")
        self.assertEqual(navigator.read_current_zone(), "start denominator")

        navigator.command_with_boundaries("MoveNext")
        self.assertEqual(navigator.read_current_zone(), "denominator, y")

    def test_read_current_zone_reports_matrix_cell(self) -> None:
        navigator = MathCatNavigator(language="en")
        navigator.load(MATRIX)
        navigator.cell_command("MoveCellNext")
        self.assertEqual(navigator.read_current_zone(), "cell row 1, column 1, a")

    def test_linear_navigation_enters_nested_structures_with_right_arrow(self) -> None:
        navigator = MathCatNavigator(language="en")
        navigator.load("""<math id="root"><mrow id="row"><mfrac id="fraction">
        <mi id="num">x</mi><mrow id="den"><mi id="y">y</mi><mo id="plus">+</mo>
        <mn id="one">1</mn></mrow></mfrac><mo id="equals">=</mo>
        <mi id="z">z</mi></mrow></math>""")
        navigator.command("ZoomIn")

        self.assertEqual(navigator.current_id, "fraction")
        self.assertEqual(navigator.linear_command("MoveNext"), "start numerator")
        self.assertEqual(navigator.current_id, "num")
        self.assertEqual(navigator.linear_command("MoveNext"), "x")
        self.assertEqual(navigator.linear_command("MoveNext"), "end numerator")
        self.assertEqual(navigator.linear_command("MoveNext"), "start denominator")
        self.assertIn("y", navigator.linear_command("MoveNext"))
        self.assertEqual(navigator.current_id, "y")
        self.assertEqual(navigator.linear_command("MoveNext"), "plus")
        self.assertEqual(navigator.linear_command("MoveNext"), "1")
        self.assertEqual(navigator.linear_command("MoveNext"), "end denominator")
        self.assertEqual(navigator.linear_command("MoveNext"), "end fraction")
        self.assertIn("equal", navigator.linear_command("MoveNext"))

    def test_stepping_over_a_whole_fraction_is_not_entering_or_leaving_it(self) -> None:
        document = MathMLDocument.parse(
            """<math id="root"><mrow id="row"><mfrac id="fraction"><mi id="num">a</mi>
            <mi id="den">b</mi></mfrac><mo id="plus">+</mo><mi id="c">c</mi></mrow></math>"""
        )
        self.assertEqual(document.regions("fraction"), ())
        self.assertEqual(document.exited_regions("fraction", "plus"), ())
        self.assertEqual(document.entered_regions("plus", "fraction"), ())
        self.assertEqual(document.regions("num"), ("numerator", "fraction"))

    def test_nested_fractions_are_separate_regions(self) -> None:
        document = MathMLDocument.parse(
            """<math id="root"><mfrac id="outer"><mfrac id="inner"><mi id="a">a</mi>
            <mi id="b">b</mi></mfrac><mi id="c">c</mi></mfrac></math>"""
        )
        self.assertEqual(document.exited_regions("a", "b"), ("numerator",))
        self.assertEqual(document.entered_regions("a", "b"), ("denominator",))
        self.assertEqual(document.exited_regions("b", "c"), ("denominator", "fraction", "numerator"))
        self.assertEqual(document.entered_regions("b", "c"), ("denominator",))

    def test_zoom_ignores_the_structure_being_zoomed_into(self) -> None:
        document = MathMLDocument.parse(
            """<math id="root"><mfrac id="fraction"><mi id="num">a</mi><mi id="den">b</mi></mfrac></math>"""
        )
        self.assertEqual(document.entered_regions("fraction", "num", ignore_id="fraction"), ("numerator",))
        self.assertEqual(document.exited_regions("num", "fraction", ignore_id="fraction"), ("numerator",))

    def test_nearest_first_cell_prefers_the_next_matrix_and_the_current_row(self) -> None:
        document = MathMLDocument.parse(
            """<math id="root"><mrow id="row"><mi id="x">x</mi><mo id="eq">=</mo>
            <mtable id="table"><mtr id="r1"><mtd id="c11"><mi id="a">a</mi></mtd><mtd id="c12"><mi id="b">b</mi></mtd></mtr>
            <mtr id="r2"><mtd id="c21"><mi id="c">c</mi></mtd><mtd id="c22"><mspace id="empty"/></mtd></mtr></mtable>
            <mo id="plus">+</mo><mn id="one">1</mn></mrow></math>"""
        )
        self.assertEqual(document.nearest_first_cell("x"), "a")
        self.assertEqual(document.nearest_first_cell("root"), "a")
        self.assertEqual(document.nearest_first_cell("one"), "a")
        self.assertEqual(document.nearest_first_cell("r2"), "c")
        self.assertIsNone(MathMLDocument.parse('<math id="root"><mi id="x">x</mi></math>').nearest_first_cell("x"))

    def test_moving_back_after_a_boundary_stop_really_moves_back(self) -> None:
        navigator = MathCatNavigator(language="en")
        navigator.load("""<math id="root"><mrow id="row"><mfrac id="fraction">
        <mi id="num">x</mi><mi id="den">y</mi></mfrac><mo id="plus">+</mo>
        <mi id="z">z</mi></mrow></math>""")
        navigator.command("ZoomIn")
        navigator.command("ZoomIn")
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "end numerator")
        navigator.command_with_boundaries("MovePrevious")
        self.assertEqual(navigator.current_id, "num")

    def test_cell_navigation_jumps_into_a_matrix_from_outside(self) -> None:
        navigator = MathCatNavigator(language="en")
        # Fenced, as the real converter emits "(■(...))": MathCAT reads an
        # unfenced mtable as lines of equations, with no "next column".
        navigator.load("""<math id="root"><mrow id="row"><mi id="x">x</mi><mo id="eq">=</mo>
        <mrow id="fenced" intent=":fenced"><mo id="open">(</mo>
        <mtable id="table" intent=":array(2,2)"><mtr id="r1"><mtd id="c11"><mi id="a">a</mi></mtd><mtd id="c12"><mi id="b">b</mi></mtd></mtr>
        <mtr id="r2"><mtd id="c21"><mi id="c">c</mi></mtd><mtd id="c22"><mi id="d">d</mi></mtd></mtr></mtable>
        <mo id="close">)</mo></mrow></mrow></math>""")
        navigator.command("ZoomIn")
        self.assertEqual(navigator.current_id, "x")
        navigator.cell_command("MoveCellNext")
        position = navigator.current_table_position
        self.assertIsNotNone(position)
        self.assertEqual((position.row, position.column), (1, 1))
        navigator.cell_command("MoveCellNext")
        position = navigator.current_table_position
        self.assertEqual((position.row, position.column), (1, 2))

    def test_converter_determinant_is_read_and_navigated_as_a_determinant(self) -> None:
        # Exactly what UnicodeMathML emits for "|■(a&b@c&d)|".
        navigator = MathCatNavigator(language="en")
        speech = navigator.load(
            '<math display="block"><mrow intent="determinant($a)"><mo>|</mo><mtable arg="a">'
            "<mtr><mtd><mi>a</mi></mtd><mtd><mi>b</mi></mtd></mtr>"
            "<mtr><mtd><mi>c</mi></mtd><mtd><mi>d</mi></mtd></mtr>"
            "</mtable><mo>|</mo></mrow></math>"
        )
        self.assertIn("2 by 2 determinant", speech)
        navigator.command("ZoomIn")
        self.assertIn("eigh", navigator.cell_command("MoveCellNext"))
        self.assertIn("b", navigator.cell_command("MoveCellNext"))
        position = navigator.current_table_position
        self.assertEqual((position.row, position.column), (1, 2))

    FRACTION_SUMS = """<math id="root"><mfrac id="fraction">
        <mrow id="num"><mi id="a">a</mi><mo id="plus1">+</mo><mn id="one">1</mn></mrow>
        <mrow id="den"><mi id="b">b</mi><mo id="plus2">+</mo><mi id="c">c</mi></mrow>
        </mfrac></math>"""

    def test_end_of_math_first_closes_the_enclosing_regions(self) -> None:
        navigator = MathCatNavigator(language="en", auto_zoom_out=True)
        navigator.load(self.FRACTION_SUMS)
        navigator.command("ZoomIn")
        navigator.command("MoveNext")
        navigator.command("ZoomIn")
        navigator.command("MoveNext")
        navigator.command("MoveNext")
        self.assertEqual(navigator.current_id, "c")
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "end denominator")
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "end fraction")
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "end of math")
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "end of math")
        self.assertEqual(navigator.current_id, "c")

    def test_without_auto_zoom_out_right_stays_at_the_end_of_a_zoomed_group(self) -> None:
        navigator = MathCatNavigator(language="en", auto_zoom_out=False)
        navigator.load(self.FRACTION_SUMS)
        navigator.command("ZoomIn")
        self.assertEqual(navigator.current_id, "num")
        navigator.command("ZoomIn")
        navigator.command("MoveNext")
        navigator.command("MoveNext")
        self.assertEqual(navigator.current_id, "one")
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "end of numerator")
        self.assertEqual(navigator.current_id, "one")
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "end of numerator")
        navigator.command_with_boundaries("ZoomOut")
        self.assertEqual(navigator.current_id, "num")
        self.assertEqual(navigator.command_with_boundaries("MoveNext"), "end numerator")
        self.assertEqual(navigator.current_id, "den")

    def test_without_auto_zoom_out_left_stays_at_the_start_of_a_zoomed_group(self) -> None:
        navigator = MathCatNavigator(language="en", auto_zoom_out=False)
        navigator.load(self.FRACTION_SUMS)
        navigator.command("ZoomIn")
        navigator.command("MoveNext")
        navigator.command("ZoomIn")
        self.assertEqual(navigator.current_id, "b")
        self.assertEqual(navigator.command_with_boundaries("MovePrevious"), "start of denominator")
        self.assertEqual(navigator.current_id, "b")

    def test_leading_separators_are_removed_from_speech(self) -> None:
        navigator = MathCatNavigator(language="en")
        navigator.load(MATRIX)
        self.assertFalse(navigator.command("ZoomIn").startswith(("; ", ", ")))

    def test_mathcat_canonical_tree_tracks_matrix_cells(self) -> None:
        navigator = MathCatNavigator(language="en")
        navigator.load(MATRIX)
        speech = navigator.cell_command("MoveCellNext")
        position = navigator.current_table_position
        self.assertIsNotNone(position)
        self.assertEqual((position.row, position.column), (1, 1))
        self.assertIn("column 1", speech)

        speech = navigator.cell_command("MoveCellNext")
        position = navigator.current_table_position
        self.assertEqual((position.row, position.column), (1, 2))
        self.assertIn("column 2", speech)

        speech = navigator.command("MoveCellDown")
        position = navigator.current_table_position
        self.assertEqual((position.row, position.column), (2, 2))
        self.assertIn("row 2, column 2", speech)

        speech = navigator.move_to_column_boundary(False)
        position = navigator.current_table_position
        self.assertEqual((position.row, position.column), (1, 2))
        self.assertIn("row 1, column 2", speech)

        speech = navigator.move_to_column_boundary(True)
        position = navigator.current_table_position
        self.assertEqual((position.row, position.column), (2, 2))
        self.assertIn("row 2, column 2", speech)


class SanitizeMathMLTests(unittest.TestCase):
    def test_passes_through_known_elements_and_attributes(self) -> None:
        source = '<math display="block"><mfrac><mi intent=":numerator">x</mi><mn>2</mn></mfrac></math>'
        self.assertEqual(sanitize_mathml(source), source)

    def test_rejects_non_math_root(self) -> None:
        with self.assertRaises(MathMLModelError):
            sanitize_mathml("<script>alert(1)</script>")

    def test_rejects_disallowed_descendant_elements(self) -> None:
        with self.assertRaises(MathMLModelError):
            sanitize_mathml('<math><mtext><script>alert(1)</script></mtext></math>')

    def test_drops_annotation_children_of_semantics(self) -> None:
        source = (
            "<math><semantics><mi>x</mi>"
            '<annotation-xml encoding="text/html">'
            "<script>alert(1)</script></annotation-xml>"
            "</semantics></math>"
        )
        self.assertEqual(sanitize_mathml(source), "<math><semantics><mi>x</mi></semantics></math>")

    def test_strips_disallowed_attributes_but_keeps_allowed_ones(self) -> None:
        source = '<math><mi onclick="alert(1)" mathvariant="italic" style="color:red">x</mi></math>'
        self.assertEqual(sanitize_mathml(source), '<math><mi mathvariant="italic">x</mi></math>')

    def test_escapes_text_content(self) -> None:
        source = "<math><mtext>1 &lt; 2</mtext></math>"
        self.assertEqual(sanitize_mathml(source), source)


    def test_tables_are_numbered_in_reading_order_and_cells_found_by_position(self) -> None:
        document = MathMLDocument.parse(
            """<math><mtable id="outer"><mtr><mtd id="o11"><mtable id="inner">
            <mtr><mtd><mi id="x">x</mi></mtd></mtr>
            <mtr><mtd><mi id="z">z</mi></mtd><mtd><mi id="w">w</mi></mtd></mtr>
            </mtable></mtd><mtd><mi id="b">b</mi></mtd></mtr></mtable></math>"""
        )
        self.assertEqual([table.identifier for table in document.tables()], ["outer", "inner"])
        self.assertEqual(document.table_index("inner"), 1)
        self.assertEqual(document.cell_target(1, 2, 2), "w")
        self.assertEqual(document.cell_target(0, 1, 2), "b")
        # A short row gives its last cell; a missing row or table gives None.
        self.assertEqual(document.cell_target(1, 1, 2), "x")
        self.assertIsNone(document.cell_target(1, 3, 1))
        self.assertIsNone(document.cell_target(2, 1, 1))

    def test_linear_left_retraces_linear_right_stop_by_stop(self) -> None:
        navigator = MathCatNavigator(language="en", auto_zoom_out=True)
        navigator.load(MathMLModelTests.FRACTION_SUMS)
        navigator.command("ZoomIn")
        forward = [navigator.linear_command("MoveNext") for _ in range(12)]
        self.assertIn("end numerator", forward)
        self.assertIn("start denominator", forward)
        self.assertEqual(forward[-1], "end of math")
        stops = [speech for index, speech in enumerate(forward) if index == 0 or speech != forward[index - 1]]
        backward = [navigator.linear_command("MovePrevious") for _ in range(len(stops) - 1)]
        self.assertEqual(backward, list(reversed(stops[:-1])))

    def test_linear_end_boundary_highlights_what_was_left(self) -> None:
        navigator = MathCatNavigator(language="en", auto_zoom_out=True)
        navigator.load(MathMLModelTests.FRACTION_SUMS)
        navigator.command("ZoomIn")
        speech = ""
        while speech != "end numerator":
            speech = navigator.linear_command("MoveNext")
        # MathCAT is already on the denominator; the numerator's "1" stays lit.
        self.assertEqual(navigator.current_id, "den")
        self.assertEqual(navigator.display_id, "one")

    def test_reloading_for_new_settings_keeps_the_cursor(self) -> None:
        navigator = MathCatNavigator(language="en", auto_zoom_out=False)
        navigator.load(MathMLModelTests.FRACTION_SUMS)
        navigator.command("ZoomIn")
        navigator.command("ZoomIn")
        self.assertEqual(navigator.current_id, "a")
        navigator.auto_zoom_out = True
        navigator.load(navigator.mathml, keep_position=True)
        self.assertEqual(navigator.current_id, "a")

if __name__ == "__main__":
    unittest.main()
