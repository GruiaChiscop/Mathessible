import os
import tempfile
import unittest
from pathlib import Path

from mathessible.documents.recent_files import menu_labels, remember, still_there
from mathessible.documents.recovery import Recovered, delete_record, pending_records, write_record


class RecentFilesTests(unittest.TestCase):
    def test_the_last_opened_comes_first_once_within_the_limit(self) -> None:
        recent = remember(("/a.md", "/b.md"), Path("/b.md"))
        self.assertEqual(recent, (str(Path("/b.md").resolve()), "/a.md"))
        self.assertEqual(len(remember([f"/{n}.md" for n in range(12)], Path("/new.md"))), 10)

    def test_gone_files_are_dropped_and_twins_show_their_folder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            there = Path(directory) / "x.md"
            there.write_text("x")
            self.assertEqual(still_there([str(there), "/no/such.md"]), (str(there),))
        self.assertEqual(
            menu_labels(["/Algebra/notes.md", "/Geometry/notes.md", "/Algebra/book.msnb"]),
            ["notes.md — Algebra", "notes.md — Geometry", "book.msnb"],
        )


class RecoveryTests(unittest.TestCase):
    def record(self, process: int) -> Recovered:
        return Recovered("document", "/doc.md", 0, "doc.md", "unsaved $x$", process, 1.0)

    def test_only_what_a_stopped_mathessible_left(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            write_record("mine", self.record(os.getpid()), folder)  # This process: still working.
            write_record("lost", self.record(2**22 + 12345), folder)  # No such process.
            (folder / "broken.json").write_text("{")
            self.assertEqual([name for name, _record in pending_records(folder)], ["lost"])
            self.assertEqual(pending_records(folder)[0][1].source, "unsaved $x$")
            delete_record("lost", folder)
            delete_record("lost", folder)  # Already gone: nothing happens.
            self.assertEqual(pending_records(folder), [])


if __name__ == "__main__":
    unittest.main()
