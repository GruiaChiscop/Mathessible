"""Passwords and permissions for an exported PDF (Typst writes none): AES-256, after Typst.

Whatever is forbidden, extraction for accessibility stays allowed, as
PDF/UA requires: a screen reader can always read the document. The tags,
bookmarks, metadata and attachments are kept (the whole PDF is cloned).
"""

from __future__ import annotations

import io
import secrets
from dataclasses import dataclass

from pypdf import PdfReader, PdfWriter
from pypdf.constants import UserAccessPermissions as Permission


@dataclass(frozen=True, slots=True)
class PdfSecurity:
    open_password: str = ""  # Asked when the PDF is opened.
    permissions_password: str = ""  # Lifts the restrictions below.
    allow_printing: bool = True
    allow_copying: bool = True
    allow_editing: bool = True

    @property
    def restricts(self) -> bool:
        return not (self.allow_printing and self.allow_copying and self.allow_editing)

    @property
    def active(self) -> bool:
        return bool(self.open_password or self.permissions_password or self.restricts)


def permissions(security: PdfSecurity) -> int:
    """The permission bits: accessibility extraction always, the others as chosen."""
    flags = Permission.EXTRACT_TEXT_AND_GRAPHICS
    if security.allow_printing:
        flags |= Permission.PRINT | Permission.PRINT_TO_REPRESENTATION
    if security.allow_copying:
        flags |= Permission.EXTRACT
    if security.allow_editing:
        flags |= Permission.MODIFY | Permission.ADD_OR_MODIFY | Permission.FILL_FORM_FIELDS | Permission.ASSEMBLE_DOC
    return int(flags)


def protect(pdf: bytes, security: PdfSecurity) -> bytes:
    """The PDF encrypted with AES-256; as it is when `security` asks for nothing.

    Restrictions with no permissions password get a random one, so they
    hold (nobody can lift them, the PDF must be exported again).
    """
    if not security.active:
        return pdf
    owner = security.permissions_password or (secrets.token_urlsafe(24) if security.restricts else "")
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf)))
    writer.encrypt(
        user_password=security.open_password,
        owner_password=owner or security.open_password,
        permissions_flag=permissions(security),
        algorithm="AES-256",
    )
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
