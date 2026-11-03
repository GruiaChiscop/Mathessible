import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mathessible.documents.tex_compile import (
    DownloadProgress,
    TexInstallation,
    compile_accessible_tex,
    compile_tex,
    document_language,
    download_progress,
    engine_for,
    find_installation,
    first_error,
    megabytes,
    missing_file,
    package_holding,
    tagging_metadata,
)

MISSING_LOG = """(./paper.tex
! LaTeX Error: File `siunitx.sty' not found.

Type X to quit or <RETURN> to proceed,
"""
ERROR_LOG = """(./paper.tex
! Undefined control sequence.
l.12 $\\fracc
           {a}{b}$
"""
SEARCH = """tlmgr: package repository https://mirror.example/systems/texlive/tlnet (verified)
siunitx:
\ttexmf-dist/tex/latex/siunitx/siunitx.sty
other:
\ttexmf-dist/tex/latex/other/siunitx.sty.bak
"""


def program(name: str) -> str:
    """A TeX program's file name on this platform: `pdflatex.exe` and `tlmgr.bat` on Windows."""
    if sys.platform != "win32":
        return name
    return f"{name}.bat" if name == "tlmgr" else f"{name}.exe"


def executable(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)


class FindInstallationTests(unittest.TestCase):
    def test_tinytex_in_the_home_folder_is_found_without_the_path(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            executable(Path(home, "Library/TinyTeX/bin/universal-darwin/pdflatex"))
            found = find_installation({"PATH": ""}, Path(home), "darwin")
            self.assertEqual(found.name, "TinyTeX")
            self.assertEqual(found.engines, ("pdflatex",))

    def test_the_path_is_looked_at_too(self) -> None:
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as tools:
            executable(Path(tools, "lualatex"))
            found = find_installation({"PATH": tools}, Path(home), "linux")
            self.assertEqual(found.bin_directory, Path(tools))
            self.assertEqual(found.engines, ("lualatex",))

    def test_none_without_a_distribution(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            found = find_installation({"PATH": home}, Path(home), "linux")
            self.assertTrue(found is None or found.bin_directory in (Path("/usr/bin"), Path("/usr/local/bin")))


class LogTests(unittest.TestCase):
    def test_a_missing_file(self) -> None:
        self.assertEqual(missing_file(MISSING_LOG), "siunitx.sty")
        self.assertIsNone(missing_file(ERROR_LOG))

    def test_the_first_error_and_its_line(self) -> None:
        self.assertEqual(first_error(ERROR_LOG), ("Undefined control sequence.", 12))
        self.assertIsNone(first_error("all well"))

    def test_the_package_holding_a_file(self) -> None:
        self.assertEqual(package_holding(SEARCH, "siunitx.sty"), "siunitx")
        self.assertIsNone(package_holding(SEARCH, "nothing.sty"))

    def test_the_engine(self) -> None:
        installation = TexInstallation("TeX Live", Path("/x"), ("pdflatex", "lualatex", "xelatex"))
        self.assertEqual(engine_for("\\documentclass{article}", installation), "pdflatex")
        self.assertEqual(engine_for("\\usepackage{fontspec}", installation), "lualatex")
        self.assertEqual(engine_for("\\usepackage[math-style=ISO]{unicode-math}", installation), "lualatex")


class CompileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.bin = Path(self.folder.name, "bin")
        for name in ("pdflatex", "tlmgr"):
            executable(self.bin / program(name))
        self.tex = Path(self.folder.name, "paper.tex")
        self.tex.write_text("\\documentclass{article}\\usepackage{siunitx}\\begin{document}x\\end{document}")
        self.installation = TexInstallation("TinyTeX", self.bin, ("pdflatex",))
        self.calls: list[list[str]] = []

    def runner(self, logs: list[tuple[int, str]]):
        """LaTeX stood in for: each pdflatex run writes the next log (and a PDF when it succeeds)."""

        def run(command: list[str], **options: object) -> subprocess.CompletedProcess:
            self.calls.append(command)
            name = Path(command[0]).stem
            if name == "tlmgr":
                return subprocess.CompletedProcess(command, 0, SEARCH if command[1] == "search" else "", "")
            code, log = logs.pop(0)
            self.tex.with_suffix(".log").write_text(log)
            if code == 0:
                self.tex.with_suffix(".pdf").write_bytes(b"%PDF")
            return subprocess.CompletedProcess(command, code, "", "")

        return run

    def test_a_missing_package_is_installed_and_the_document_compiled_again(self) -> None:
        result = compile_tex(self.tex, self.installation, self.runner([(1, MISSING_LOG), (0, "done")]))
        self.assertEqual(result.pdf, self.tex.with_suffix(".pdf"))
        self.assertEqual(result.installed, ("siunitx",))
        self.assertIn([os.fspath(self.bin / program("tlmgr")), "install", "siunitx"], self.calls)

    def test_compiled_again_while_the_log_asks(self) -> None:
        logs = [(0, "LaTeX Warning: Label(s) may have changed. Rerun to get cross-references right."), (0, "done")]
        compile_tex(self.tex, self.installation, self.runner(logs))
        self.assertEqual(sum(Path(call[0]).stem == "pdflatex" for call in self.calls), 2)

    def test_an_error_is_reported_with_its_line(self) -> None:
        result = compile_tex(self.tex, self.installation, self.runner([(1, ERROR_LOG)]))
        self.assertIsNone(result.pdf)
        self.assertEqual((result.error, result.line), ("Undefined control sequence.", 12))

    def test_a_package_that_cannot_be_found_is_an_error(self) -> None:
        log = MISSING_LOG.replace("siunitx", "nowhere")
        result = compile_tex(self.tex, self.installation, self.runner([(1, log)]))
        self.assertIsNone(result.pdf)
        self.assertIn("nowhere.sty", result.error)

    def test_a_tagged_pdf_is_compiled_by_lualatex_with_its_metadata_on_the_command_line(self) -> None:
        executable(self.bin / program("lualatex"))
        installation = TexInstallation("TinyTeX", self.bin, ("pdflatex", "lualatex"))
        result = compile_accessible_tex(self.tex, installation, "ro", self.runner([(0, "done")]))
        self.assertTrue(result.tagged)
        command = self.calls[0]
        self.assertEqual(Path(command[0]).stem, "lualatex")
        self.assertIn("-jobname=paper", command)
        self.assertEqual(command[-1], tagging_metadata("ro") + "\\input{paper.tex}")
        self.assertIn("lang=ro", command[-1])
        self.assertIn("math/setup=mathml-SE", command[-1])

    def test_a_document_with_its_own_metadata_is_compiled_as_it_says(self) -> None:
        executable(self.bin / program("lualatex"))
        self.tex.write_text("\\DocumentMetadata{lang=de}\\documentclass{article}")
        installation = TexInstallation("TinyTeX", self.bin, ("pdflatex", "lualatex"))
        compile_accessible_tex(self.tex, installation, "ro", self.runner([(0, "done")]))
        self.assertEqual(self.calls[0][-1], "paper.tex")

    def test_when_tagging_fails_the_pdf_is_compiled_untagged(self) -> None:
        executable(self.bin / program("lualatex"))
        installation = TexInstallation("TinyTeX", self.bin, ("pdflatex", "lualatex"))
        result = compile_accessible_tex(self.tex, installation, "en", self.runner([(1, ERROR_LOG), (0, "done")]))
        self.assertEqual(result.pdf, self.tex.with_suffix(".pdf"))
        self.assertFalse(result.tagged)
        self.assertEqual(result.tagging_error, "Undefined control sequence.")
        self.assertEqual(Path(self.calls[-1][0]).stem, "pdflatex")

    def test_the_tagging_support_is_installed_and_an_old_tlmgr_updated_first(self) -> None:
        executable(self.bin / program("lualatex"))
        installation = TexInstallation("TinyTeX", self.bin, ("pdflatex", "lualatex"))
        installs = iter([1, 0])
        logs = [(1, "! LaTeX Error: No support files for \\DocumentMetadata found."), (0, "done")]
        latex = self.runner(logs)

        def run(command: list[str], **options: object) -> subprocess.CompletedProcess:
            if Path(command[0]).stem == "tlmgr" and command[1] == "install":
                self.calls.append(command)
                code = next(installs)
                return subprocess.CompletedProcess(
                    command, code, "tlmgr itself needs to be updated." if code else "", ""
                )
            return latex(command, **options)

        result = compile_accessible_tex(self.tex, installation, "en", run)
        self.assertEqual(result.installed, ("latex-lab",))
        self.assertIn([os.fspath(self.bin / program("tlmgr")), "update", "--self"], self.calls)
        self.assertTrue(result.tagged)

    def test_the_documents_language(self) -> None:
        self.assertEqual(document_language("\\usepackage[english,romanian]{babel}", "en"), "ro")
        self.assertEqual(document_language("\\setmainlanguage[variant=british]{english}", "fr"), "en")
        self.assertEqual(document_language("% \\usepackage[french]{babel}", "de"), "de")


class TinyTexInstallTests(unittest.TestCase):
    def test_curls_meter_is_read(self) -> None:
        self.assertEqual(
            download_progress(" 48 64.0M   48 30.9M    0     0  23.2M"), DownloadProgress(48, "64.0M", "30.9M")
        )
        self.assertIsNone(download_progress("  % Total    % Received % Xferd"))
        self.assertIsNone(download_progress("  0     0    0     0    0     0      0"))
        self.assertEqual((megabytes("64.0M"), megabytes("285k"), megabytes("1.5G")), ("64.0", "0.3", "1536.0"))


if __name__ == "__main__":
    unittest.main()
