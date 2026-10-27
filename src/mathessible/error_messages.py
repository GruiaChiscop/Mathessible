"""What went wrong, said plainly: the message boxes show this; the technical text goes to the log."""

from __future__ import annotations

import errno

from mathessible.i18n import N_, _

# Typst's own errors for a PDF standard, and what they mean to the writer.
_TYPST = (
    ("missing document title", N_("PDF/UA requires a title: give one in the export's Document tab.")),
    (
        "missing alt text",
        N_("PDF/UA requires every equation to be readable, and one could not be: export as Tagged PDF."),
    ),
    ("attached file", N_("PDF/A-2 does not allow attachments: choose PDF/A-3a, or do not attach the source.")),
    ("unknown font", N_("A font is not installed: choose another in the export's Layout tab.")),
)


def explain(error: BaseException) -> str:
    """One or two sentences a writer can act on, for an error from saving, opening or exporting."""
    if isinstance(error, PermissionError):
        return _(
            "Mathessible is not allowed to use this file or folder. Choose another place, or check its permissions."
        )
    if isinstance(error, FileNotFoundError):
        return _("The file or folder is not there any more.")
    if isinstance(error, IsADirectoryError):
        return _("That is a folder, not a file.")
    if isinstance(error, OSError) and error.errno == errno.ENOSPC:
        return _("The disk is full.")
    if isinstance(error, UnicodeError):
        return _("The file is not text in UTF-8, so Mathessible cannot read it.")
    if isinstance(error, ImportError):
        return _("Mathessible's native part (MathCAT and liblouis) is missing. Run scripts/bootstrap.sh.")
    text = str(error).strip()
    if type(error).__name__ == "TypstError" or text.startswith("Typst could not make the PDF"):
        first = next((line for line in text.splitlines() if line.strip() and "Typst could not" not in line), text)
        for marker, advice in _TYPST:
            if marker in first:
                return _(advice)
        return _("Typst could not typeset the PDF: {error}").format(error=first.strip())
    if "liblouis could not translate" in text:
        return _("The braille table could not be loaded. Choose another in the export's dialog.")
    return text.splitlines()[0] if text else type(error).__name__
