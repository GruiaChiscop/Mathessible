import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from mathessible.documents.tex_compile import (
    DownloadProgress,
    TexInstallation,
    compile_tex,
    download_progress,
    engine_for,
    find_installation,
    first_error,
    install_tinytex,
    megabytes,
    missing_file,
    package_holding,
    tinytex_install_command,
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

    def test_tinytex_is_installed_without_changing_the_path(self) -> None:
        command = tinytex_install_command("darwin")
        self.assertIn("--no-path", command[-1])
        self.assertIn("https://tinytex.yihui.org/install-bin-unix.sh", command[-1])
        self.assertEqual(tinytex_install_command("win32")[0], "powershell")


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
        for program in ("pdflatex", "tlmgr"):
            executable(self.bin / program)
        self.tex = Path(self.folder.name, "paper.tex")
        self.tex.write_text("\\documentclass{article}\\usepackage{siunitx}\\begin{document}x\\end{document}")
        self.installation = TexInstallation("TinyTeX", self.bin, ("pdflatex",))
        self.calls: list[list[str]] = []

    def runner(self, logs: list[tuple[int, str]]):
        """LaTeX stood in for: each pdflatex run writes the next log (and a PDF when it succeeds)."""

        def run(command: list[str], **options: object) -> subprocess.CompletedProcess:
            self.calls.append(command)
            name = Path(command[0]).name
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
        self.assertIn([os.fspath(self.bin / "tlmgr"), "install", "siunitx"], self.calls)

    def test_compiled_again_while_the_log_asks(self) -> None:
        logs = [(0, "LaTeX Warning: Label(s) may have changed. Rerun to get cross-references right."), (0, "done")]
        compile_tex(self.tex, self.installation, self.runner(logs))
        self.assertEqual(sum(Path(call[0]).name == "pdflatex" for call in self.calls), 2)

    def test_an_error_is_reported_with_its_line(self) -> None:
        result = compile_tex(self.tex, self.installation, self.runner([(1, ERROR_LOG)]))
        self.assertIsNone(result.pdf)
        self.assertEqual((result.error, result.line), ("Undefined control sequence.", 12))

    def test_a_package_that_cannot_be_found_is_an_error(self) -> None:
        log = MISSING_LOG.replace("siunitx", "nowhere")
        result = compile_tex(self.tex, self.installation, self.runner([(1, log)]))
        self.assertIsNone(result.pdf)
        self.assertIn("nowhere.sty", result.error)


METER = (
    b"  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current\n"
    b"                                 Dload  Upload   Total   Spent    Left  Speed\n"
    b"\r  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0\n"
    b"\r  0 64.0M    0  285k    0     0   867k      0  0:01:15 --:--:--  0:01:15  867k"
    b"\r 48 64.0M   48 30.9M    0     0  23.2M      0  0:00:02  0:00:01  0:00:01 30.6M"
    b"\r100 64.0M  100 64.0M    0     0  25.1M      0  0:00:02  0:00:02 --:--:-- 25.1M\n"
    b"tlmgr postaction install script xetex\n"
)


class FakeProcess:
    def __init__(self, data: bytes, code: int = 0):
        import io

        self.stdout = io.BufferedReader(io.BytesIO(data))
        self.returncode = code
        self.killed = False

    def kill(self) -> None:
        self.killed = True

    def wait(self) -> int:
        return self.returncode


class TinyTexInstallTests(unittest.TestCase):
    def test_curls_meter_is_read(self) -> None:
        self.assertEqual(
            download_progress(" 48 64.0M   48 30.9M    0     0  23.2M"), DownloadProgress(48, "64.0M", "30.9M")
        )
        self.assertIsNone(download_progress("  % Total    % Received % Xferd"))
        self.assertIsNone(download_progress("  0     0    0     0    0     0      0"))
        self.assertEqual((megabytes("64.0M"), megabytes("285k"), megabytes("1.5G")), ("64.0", "0.3", "1536.0"))

    def test_the_download_is_reported_then_its_unpacking(self) -> None:
        reported: list[DownloadProgress | None] = []
        ok, output = install_tinytex(reported.append, popen=lambda *_args, **_options: FakeProcess(METER))
        self.assertTrue(ok)
        self.assertEqual([meter.percent if meter else None for meter in reported], [0, 48, 100, None])
        self.assertIn("postaction", output)

    def test_a_cancelled_install_is_stopped(self) -> None:
        process = FakeProcess(METER)
        ok, _output = install_tinytex(lambda _meter: None, lambda: True, lambda *_args, **_options: process)
        self.assertFalse(ok)
        self.assertTrue(process.killed)


if __name__ == "__main__":
    unittest.main()
