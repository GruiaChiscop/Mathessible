import tempfile
import unittest
from pathlib import Path

from mathessible.templates.saved_equations import (
    SavedEquation,
    find_equation,
    load_equations,
    save_equations,
    with_equation,
    without_equation,
)


class SavedEquationsTests(unittest.TestCase):
    def test_saved_and_loaded_with_any_characters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "equations.json"
            self.assertEqual(load_equations(path), [])
            equations = [SavedEquation("Quadratic", "x=(-b±√(b^2-4ac))/2a"), SavedEquation("Euler", "e^iπ+1=0")]
            save_equations(equations, path)
            self.assertEqual(load_equations(path), equations)
            self.assertIn("√", path.read_text(encoding="utf-8"))  # Readable, not escaped.

    def test_a_bad_file_or_entry_is_left_out(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "equations.json"
            path.write_text('[{"name": "A", "source": "a"}, {"name": "", "source": "b"}, {"name": "C"}, 3]')
            self.assertEqual(load_equations(path), [SavedEquation("A", "a")])
            path.write_text("not json")
            self.assertEqual(load_equations(path), [])

    def test_saving_a_name_again_replaces_it_in_place(self) -> None:
        equations = [SavedEquation("Area", "πr^2"), SavedEquation("Euler", "e^iπ+1=0")]
        self.assertEqual(
            with_equation(equations, " area ", "π r^2"),
            [SavedEquation("area", "π r^2"), SavedEquation("Euler", "e^iπ+1=0")],
        )
        self.assertEqual(with_equation(equations, "Pythagoras", "a^2+b^2=c^2")[-1].name, "Pythagoras")
        self.assertEqual(find_equation(equations, "EULER"), equations[1])
        self.assertEqual(without_equation(equations, "euler"), [equations[0]])


if __name__ == "__main__":
    unittest.main()
