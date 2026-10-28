"""A .tex file compiled to PDF by the user's own LaTeX distribution, so that its packages work.

Mathessible finds an installed distribution itself (`find_installation`):
an application started from the Finder does not get the shell's PATH, so
the usual places are looked at too (MacTeX's /Library/TeX/texbin, TinyTeX
in the home folder, TeX Live's /usr/local/texlive, MiKTeX). With none, it
offers TinyTeX (`tinytex_install_command`): small, installed in the home
folder without an administrator password, by its authors' own script.

Compiling runs pdflatex (LuaLaTeX or XeLaTeX when the document loads
fontspec or unicode-math) as many times as its log asks, at most four.
TinyTeX installs a missing package only for R: here a "File `x.sty' not
found" makes tlmgr look up and install the package that holds it, and the
document is compiled again.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

ENGINES = ("pdflatex", "lualatex", "xelatex")
TINYTEX_SCRIPT = "https://tinytex.yihui.org/install-bin-unix.sh"
TINYTEX_WINDOWS_SCRIPT = "https://tinytex.yihui.org/install-bin-windows.bat"
_MISSING_FILE = re.compile(r"File `([^']+)' not found")
_ERROR = re.compile(r"^! (.+)$", re.MULTILINE)
_ERROR_LINE = re.compile(r"^l\.(\d+)", re.MULTILINE)
_RERUN = re.compile(r"Rerun to get|Label\(s\) may have changed|Please rerun", re.IGNORECASE)
_UNICODE_FONTS = re.compile(r"\\usepackage\s*(?:\[[^\]]*\])?\s*\{[^}]*\b(?:fontspec|unicode-math)\b")
_PACKAGE_LINE = re.compile(r"^([A-Za-z0-9_.\-]+):\s*$")
_RUNS = 4
# A line of curl's progress meter: percent, total, percent received, received ("  48 64.0M   48 30.9M ...").
_CURL_METER = re.compile(r"^\s*(\d{1,3})\s+([\d.]+[kMG]?)\s+\d{1,3}\s+([\d.]+[kMG]?)\s")

Runner = Callable[..., subprocess.CompletedProcess]


@dataclass(frozen=True, slots=True)
class TexInstallation:
    name: str  # "TinyTeX", "MacTeX", "MiKTeX" or "TeX Live".
    bin_directory: Path
    engines: tuple[str, ...]

    def program(self, name: str) -> Path:
        suffix = ".exe" if sys.platform == "win32" else ""
        return self.bin_directory / f"{name}{suffix}"


@dataclass(frozen=True, slots=True)
class CompileResult:
    pdf: Path | None
    error: str = ""  # LaTeX's first error, with its line ("l.12"), when there is no PDF.
    line: int | None = None
    installed: tuple[str, ...] = field(default_factory=tuple)  # Packages tlmgr installed on the way.


def _executable(directory: Path, name: str) -> bool:
    for candidate in (directory / name, directory / f"{name}.exe"):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return True
    return False


def _candidates(environ: dict[str, str], home: Path, platform: str) -> list[Path]:
    places: list[Path] = []
    if platform == "darwin":
        places += sorted((home / "Library" / "TinyTeX" / "bin").glob("*"))
        places.append(Path("/Library/TeX/texbin"))
    elif platform == "win32":
        appdata = environ.get("APPDATA", "")
        if appdata:
            places += sorted((Path(appdata) / "TinyTeX" / "bin").glob("*"))
        local = environ.get("LOCALAPPDATA", "")
        if local:
            places.append(Path(local) / "Programs" / "MiKTeX" / "miktex" / "bin" / "x64")
        places.append(Path("C:/Program Files/MiKTeX/miktex/bin/x64"))
        places += sorted(Path("C:/texlive").glob("*/bin/windows"), reverse=True)
    else:
        places += sorted((home / ".TinyTeX" / "bin").glob("*"))
    if platform != "win32":
        places += sorted(Path("/usr/local/texlive").glob("*/bin/*"), reverse=True)
    places += [Path(entry) for entry in environ.get("PATH", "").split(os.pathsep) if entry]
    if platform != "win32":
        places += [Path("/opt/homebrew/bin"), Path("/usr/local/bin"), Path("/usr/bin")]
    return places


def _name(directory: Path) -> str:
    text = str(directory)
    if "TinyTeX" in text:
        return "TinyTeX"
    if "MiKTeX" in text:
        return "MiKTeX"
    if text.startswith("/Library/TeX"):
        return "MacTeX"
    return "TeX Live"


def find_installation(
    environ: dict[str, str] | None = None, home: Path | None = None, platform: str | None = None
) -> TexInstallation | None:
    """The first LaTeX distribution found (TinyTeX first, the one Mathessible installs), None without one."""
    environ = dict(os.environ) if environ is None else environ
    home = Path.home() if home is None else home
    platform = sys.platform if platform is None else platform
    seen: set[Path] = set()
    for directory in _candidates(environ, home, platform):
        if directory in seen:
            continue
        seen.add(directory)
        engines = tuple(engine for engine in ENGINES if _executable(directory, engine))
        if engines:
            return TexInstallation(_name(directory), directory, engines)
    return None


def tinytex_directory(
    environ: dict[str, str] | None = None, home: Path | None = None, platform: str | None = None
) -> Path:
    """Where TinyTeX's installer puts it: ~/Library/TinyTeX (macOS), %APPDATA%\\TinyTeX, ~/.TinyTeX."""
    environ = dict(os.environ) if environ is None else environ
    home = Path.home() if home is None else home
    platform = sys.platform if platform is None else platform
    if platform == "darwin":
        return home / "Library" / "TinyTeX"
    if platform == "win32":
        return Path(environ.get("APPDATA", str(home))) / "TinyTeX"
    return home / ".TinyTeX"


def tinytex_install_command(platform: str | None = None) -> list[str]:
    """TinyTeX's own installer, as its authors give it, without changing the PATH (no password asked)."""
    platform = sys.platform if platform is None else platform
    if platform == "win32":
        script = (
            f"$f = Join-Path $env:TEMP 'install-bin-windows.bat'; "
            f"Invoke-WebRequest -UseBasicParsing '{TINYTEX_WINDOWS_SCRIPT}' -OutFile $f; & cmd /c $f"
        )
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]
    return ["/bin/sh", "-c", f'curl -sL "{TINYTEX_SCRIPT}" | sh -s - --no-path']


@dataclass(frozen=True, slots=True)
class DownloadProgress:
    percent: int
    total: str  # As curl writes sizes: "64.0M", "285k".
    received: str


def download_progress(meter_line: str) -> DownloadProgress | None:
    """One line of curl's progress meter (its lines end in a carriage return), None for its headings."""
    found = _CURL_METER.match(meter_line)
    if found is None or found.group(2) == "0":
        return None
    return DownloadProgress(min(100, int(found.group(1))), found.group(2), found.group(3))


def megabytes(size: str) -> str:
    """curl's size ("64.0M", "285k", "1.2G") in megabytes, one decimal ("64.0", "0.3", "1228.8")."""
    factor = {"k": 1 / 1024, "M": 1.0, "G": 1024.0}.get(size[-1:], 1 / 1024 / 1024)
    number = float(size.rstrip("kMG") or 0)
    return f"{number * factor:.1f}"


def install_tinytex(
    progress: Callable[[DownloadProgress | None], None],
    cancelled: Callable[[], bool] = lambda: False,
    popen: Callable[..., subprocess.Popen] = subprocess.Popen,
) -> tuple[bool, str]:
    """TinyTeX's own installer, run while its download is reported (`progress`: each meter line, then None
    once it unpacks); stopped when `cancelled`. Whether it ended well, and what it wrote."""
    process = popen(tinytex_install_command(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = bytearray()
    line = bytearray()
    downloaded = False
    while True:
        if cancelled():
            process.kill()
            process.wait()
            return False, output.decode("utf-8", "replace")
        chunk = process.stdout.read1(4096) if hasattr(process.stdout, "read1") else process.stdout.read(4096)
        if not chunk:
            break
        output += chunk
        for byte in chunk:
            if byte in (10, 13):  # curl rewrites its meter line with a carriage return.
                meter = download_progress(line.decode("utf-8", "replace"))
                if meter is not None:
                    progress(meter)
                    downloaded = downloaded or meter.percent == 100
                elif downloaded:
                    progress(None)
                line.clear()
            else:
                line.append(byte)
    process.wait()
    return process.returncode == 0, output.decode("utf-8", "replace")


def engine_for(source: str, installation: TexInstallation) -> str:
    """pdflatex, or LuaLaTeX (else XeLaTeX) for a document that loads fontspec or unicode-math."""
    if _UNICODE_FONTS.search(source):
        for engine in ("lualatex", "xelatex"):
            if engine in installation.engines:
                return engine
    return "pdflatex" if "pdflatex" in installation.engines else installation.engines[0]


def missing_file(log: str) -> str | None:
    """The file LaTeX did not find (`times.sty`), from its log."""
    found = _MISSING_FILE.search(log)
    return None if found is None else found.group(1)


def first_error(log: str) -> tuple[str, int | None] | None:
    """LaTeX's first error (`! Undefined control sequence.`) and its line, from its log."""
    found = _ERROR.search(log)
    if found is None:
        return None
    line = _ERROR_LINE.search(log, found.end())
    return found.group(1).strip(), int(line.group(1)) if line else None


def package_holding(search_output: str, filename: str) -> str | None:
    """The package `tlmgr search --global --file /name` names for that file (`psnfss:` before its path)."""
    package = None
    for line in search_output.splitlines():
        heading = _PACKAGE_LINE.match(line)
        if heading is not None:
            package = heading.group(1)
        elif package and line.strip().endswith("/" + filename):
            return package
    return None


def compile_tex(
    path: Path,
    installation: TexInstallation,
    run: Runner = subprocess.run,
    install_missing: bool = True,
    progress: Callable[[str], None] = lambda _message: None,
) -> CompileResult:
    """Compile `path` beside itself (its PDF and log next to it), installing missing packages with tlmgr."""
    source = path.read_text(encoding="utf-8", errors="replace")
    engine = engine_for(source, installation)
    command = [str(installation.program(engine)), "-interaction=nonstopmode", "-halt-on-error", path.name]
    installed: list[str] = []
    tried: set[str] = set()
    log_path = path.with_suffix(".log")
    runs = 0
    while runs < _RUNS:
        runs += 1
        progress(engine)
        completed = run(command, cwd=path.parent, capture_output=True, text=True, errors="replace", timeout=600)
        log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else completed.stdout
        if completed.returncode != 0:
            missing = missing_file(log)
            if (
                install_missing
                and missing
                and missing not in tried
                and (package := _install(installation, missing, run))
            ):
                tried.add(missing)
                installed.append(package)
                progress(package)
                runs -= 1  # A run that only found a missing package does not count.
                continue
            error = first_error(log) or (completed.stderr.strip() or f"{engine} failed", None)
            return CompileResult(None, error[0], error[1], tuple(installed))
        if not _RERUN.search(log):
            break
    pdf = path.with_suffix(".pdf")
    return CompileResult(
        pdf if pdf.is_file() else None, "" if pdf.is_file() else f"{engine} wrote no PDF", None, tuple(installed)
    )


def _install(installation: TexInstallation, filename: str, run: Runner) -> str | None:
    """Install the package holding `filename` with tlmgr; its name, or None when it cannot."""
    if not _executable(installation.bin_directory, "tlmgr"):
        return None
    tlmgr = str(installation.program("tlmgr"))
    try:
        search = run(
            [tlmgr, "search", "--global", "--file", "/" + filename], capture_output=True, text=True, timeout=300
        )
        package = package_holding(search.stdout, filename)
        if package is None:
            return None
        done = run([tlmgr, "install", package], capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.SubprocessError):
        return None
    return package if done.returncode == 0 else None
