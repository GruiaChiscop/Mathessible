import io
import unittest

import typst
from pypdf import PdfReader
from pypdf.constants import UserAccessPermissions as Permission

from mathessible.documents.pdf_security import PdfSecurity, permissions, protect

PDF = typst.compile(
    b'#set document(title: "T")\n#set text(lang: "ro")\n= T\nText #math.equation(alt: "x", $x$)',
    pdf_standards=["ua-1"],
)


def read(pdf: bytes) -> PdfReader:
    return PdfReader(io.BytesIO(pdf))


class PdfSecurityTests(unittest.TestCase):
    def test_nothing_asked_leaves_the_pdf_as_it_is(self) -> None:
        self.assertIs(protect(PDF, PdfSecurity()), PDF)

    def test_an_open_password_is_asked_and_the_tags_stay(self) -> None:
        reader = read(protect(PDF, PdfSecurity(open_password="secret")))
        self.assertTrue(reader.is_encrypted)
        self.assertFalse(reader.decrypt("wrong"))
        reader = read(protect(PDF, PdfSecurity(open_password="secret")))
        self.assertTrue(reader.decrypt("secret"))
        self.assertIn("/StructTreeRoot", reader.trailer["/Root"])
        self.assertEqual(reader.trailer["/Root"]["/Lang"], "ro")

    def test_screen_readers_may_always_read(self) -> None:
        nothing_allowed = PdfSecurity(allow_printing=False, allow_copying=False, allow_editing=False)
        flags = permissions(nothing_allowed)
        self.assertTrue(flags & Permission.EXTRACT_TEXT_AND_GRAPHICS)
        self.assertFalse(flags & (Permission.PRINT | Permission.EXTRACT | Permission.MODIFY))
        reader = read(protect(PDF, nothing_allowed))
        self.assertTrue(reader.decrypt(""))  # Opens with no password.
        self.assertTrue(reader.user_access_permissions & Permission.EXTRACT_TEXT_AND_GRAPHICS)
        self.assertFalse(reader.user_access_permissions & Permission.PRINT)


if __name__ == "__main__":
    unittest.main()
