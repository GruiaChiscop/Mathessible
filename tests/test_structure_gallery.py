import unittest

from matex.build_repair import repairs
from matex.math_templates import move_to_slot
from matex.settings import DEFAULT_RECOGNIZED_FUNCTIONS
from matex.source_view import edit_in_view
from matex.structure_gallery import CATEGORIES, written_form

from converter_harness import builds, convert_all, needs_node


def _items():
    return [(category.name, item) for category in CATEGORIES for item in category.items]


class StructureGalleryTests(unittest.TestCase):
    def test_every_category_has_structures_and_every_label_is_unique(self) -> None:
        self.assertEqual(len(CATEGORIES), 12)
        for category in CATEGORIES:
            labels = [item.label for item in category.items]
            self.assertTrue(labels, category.name)
            self.assertEqual(len(labels), len(set(labels)), category.name)

    def test_every_structure_inserts_or_opens_a_dialog(self) -> None:
        for name, item in _items():
            with self.subTest(category=name, structure=item.label):
                if item.insert is None:
                    self.assertIn(item.dialog, ("matrix", "symbol"))
                    continue
                edit = edit_in_view("x+", 2, item.insert, True)
                self.assertTrue(edit.announcement)
                if not item.label.endswith(("arrow", "Hat", "Bar", "Dot", "dot", "Tilde", "Check", "Acute", "Grave", "Breve")):
                    self.assertNotEqual(edit.source, "x+")
                    self.assertTrue(written_form(item, True))

    def test_written_form_follows_the_control_word_setting(self) -> None:
        skewed = next(item for item in CATEGORIES[0].items if item.label == "Skewed fraction")
        self.assertEqual(written_form(skewed, True), "()\\sdiv()")
        self.assertEqual(written_form(skewed, False), "()⁄()")
        vector = next(item for item in CATEGORIES[7].items if item.label == "Vector arrow")
        self.assertEqual(written_form(vector, True), "x\\vec")

    def test_an_accent_goes_on_the_base_before_the_caret(self) -> None:
        hat = next(item for item in CATEGORIES[7].items if item.label == "Hat")
        self.assertEqual(hat.insert("a+x", 3).source, "a+x̂")
        self.assertEqual(hat.insert("(a+b)", 5).source, "(a+b)̂")
        refused = hat.insert("a+", 2)
        self.assertEqual(refused.source, "a+")
        self.assertIn("type the base first", refused.announcement)

    def test_new_fraction_styles_and_signs_have_tab_slots(self) -> None:
        for source, first in (("()⁄()", "empty numerator"), ("¯()", "empty content"), ("∐_()^()▒", "empty lower limit")):
            with self.subTest(source=source):
                self.assertEqual(move_to_slot(source, 0).announcement, first)

    def test_gallery_functions_are_recognized_by_default(self) -> None:
        functions = next(category for category in CATEGORIES if category.name == "Function")
        for item in functions.items:
            self.assertIn(item.label, DEFAULT_RECOGNIZED_FUNCTIONS)

    @needs_node
    def test_every_structure_builds_with_the_real_converter(self) -> None:
        # Fresh templates may be half-typed (an empty integrand or index):
        # some repair (build_repair) must build them, as the editor does.
        sources = [edit_in_view("x+", 2, item.insert, False).source for _name, item in _items() if item.insert]
        candidates = [[repair.text for repair in repairs(source)] for source in sources]
        texts = [text for options in candidates for text in options]
        results = convert_all(texts)  # One Node run for every candidate.
        built = {text: builds(result["mathml"]) for text, result in zip(texts, results, strict=True)}
        failed = [
            source for source, options in zip(sources, candidates, strict=True) if not any(built[text] for text in options)
        ]
        self.assertEqual(failed, [])
