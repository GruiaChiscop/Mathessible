"""Equations read aloud in a document's language, for an export's alt text.

The editor's MathCAT speaks the speech language and holds the equation
being edited. MathCAT's state is per thread, so a document's equations
are read by a MathCAT of their own, started in the document's language
on a thread that ends with the export: the editor's language, equation
and position are never touched. A language MathCAT does not have is read
in English.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence

from mathessible.i18n import interface_language
from mathessible.mathcat.common import _clean_speech
from mathessible.mathcat.navigator import mathcat_language
from mathessible.mathcat.prepare import prepare_for_mathcat


def speech_language(document_language: str) -> str:
    """MathCAT's language for a document in `document_language` ("fr", "pt-BR"): English when it has none."""
    return interface_language("", [document_language] if document_language else [])


def equation_speech(
    mathml: Sequence[str],
    language: str,
    decimal_separator: str = ",",
    speech_style: str = "SimpleSpeak",
    verbosity: str = "Medium",
) -> list[str]:
    """Each equation's speech in `language` (a document's), "" for one MathCAT could not read."""
    speeches = [""] * len(mathml)

    def read() -> None:
        try:
            import mathessible_mathcat as native

            native.initialize(mathcat_language(speech_language(language)), speech_style, verbosity)
            native.preference("DecimalSeparator", decimal_separator)
        except (ImportError, OSError, RuntimeError, ValueError):
            return
        for index, equation in enumerate(mathml):
            try:
                native.set_expression(prepare_for_mathcat(equation))
                speeches[index] = _clean_speech(native.speak_expression()).strip()
            except (OSError, RuntimeError, ValueError):
                speeches[index] = ""

    worker = threading.Thread(target=read, name="mathessible-document-speech", daemon=True)
    worker.start()
    worker.join()
    return speeches
