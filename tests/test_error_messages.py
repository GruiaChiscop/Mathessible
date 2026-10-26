import errno
import unittest

import typst

from mathessible.error_messages import explain


class ExplainTests(unittest.TestCase):
    def test_file_errors_are_said_plainly(self) -> None:
        self.assertIn("not allowed", explain(PermissionError(13, "Permission denied", "/x")))
        self.assertEqual(
            explain(FileNotFoundError(2, "No such file", "/x")), "The file or folder is not there any more."
        )
        self.assertEqual(explain(OSError(errno.ENOSPC, "No space left on device")), "The disk is full.")
        self.assertIn("UTF-8", explain(UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")))

    def test_typst_errors_say_what_to_do(self) -> None:
        try:
            typst.compile(b"= T\nText", pdf_standards=["ua-1"])
        except RuntimeError as error:
            self.assertEqual(explain(error), "PDF/UA requires a title: give one in the export's Document tab.")
        else:
            self.fail("Typst accepted a PDF/UA document with no title")
        self.assertTrue(explain(RuntimeError("Typst could not make the PDF:\nsomething new")).endswith("something new"))

    def test_other_errors_keep_their_first_line(self) -> None:
        self.assertEqual(explain(ValueError("The first line.\nTechnical detail")), "The first line.")


if __name__ == "__main__":
    unittest.main()
