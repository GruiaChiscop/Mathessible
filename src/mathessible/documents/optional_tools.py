"""Private optional-tool installations, independent of wx and package managers."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.request import Request, urlopen

from mathessible.data_paths import data_directory
from mathessible.i18n import _
from mathessible.processes import running

_REPOSITORIES = {"pandoc": "jgm/pandoc", "TinyTeX": "rstudio/tinytex-releases"}


class ToolError(RuntimeError):
    pass


def tools_directory(home: Path | None = None) -> Path:
    return data_directory(home=home) / "tools"


def managed_directory(tool: str, home: Path | None = None) -> Path:
    if tool not in {"pandoc", "TinyTeX"}:
        raise ValueError("Unknown optional tool")
    return tools_directory(home) / tool


def release(tool: str) -> dict:
    """The tool's latest GitHub release, as GitHub's API describes it."""
    repo = _REPOSITORIES[tool]
    try:
        request = Request(f"https://api.github.com/repos/{repo}/releases/latest", headers={"User-Agent": "Mathessible"})
        with urlopen(request, timeout=30) as response:
            data = json.loads(response.read(2_000_001))
        if not isinstance(data, dict) or not isinstance(data.get("tag_name"), str):
            raise ValueError("Invalid release")
        return data
    except (OSError, ValueError) as error:
        raise ToolError(_("Could not check for updates. Try again later.")) from error


def tlmgr_program(directory: Path, system: str | None = None) -> Path | None:
    """TeX Live's package manager in a bin directory: `tlmgr.bat` on Windows, where `tlmgr` is a shell script."""
    system = sys.platform if system is None else system
    for name in ("tlmgr.bat", "tlmgr.exe") if system == "win32" else ("tlmgr",):
        if (directory / name).is_file():
            return directory / name
    return None


def installed_program(tool: str, root: Path) -> Path:
    """What Settings selects in a private installation: Pandoc's executable, or TinyTeX's bin directory."""
    candidates = sorted(root.rglob("pandoc*") if tool == "pandoc" else root.glob("bin/*/pdflatex*"))
    for path in candidates:
        if path.name in {"pandoc", "pandoc.exe", "pdflatex", "pdflatex.exe"} and path.is_file():
            return path if tool == "pandoc" else path.parent
    raise ToolError(_("The archive does not contain the expected executable"))


@contextmanager
def _installing(tool: str) -> Iterator[None]:
    """One installation of a tool at a time. The lock holds its process's number, so one left by a
    Mathessible that stopped (a crash, a power cut) is taken over instead of blocking every later one."""
    lock = managed_directory(tool).parent / f".{tool}.installing"
    lock.parent.mkdir(parents=True, exist_ok=True)
    for _attempt in range(2):
        try:
            with lock.open("x", encoding="ascii") as file:
                file.write(str(os.getpid()))
            break
        except FileExistsError:
            try:
                owner = int(lock.read_text(encoding="ascii").strip())
            except (OSError, ValueError):
                owner = 0  # Unreadable, or the folder an earlier version used: no owner.
            if owner == os.getpid() or running(owner):
                raise ToolError(_("Another installation is in progress")) from None
            try:
                lock.rmdir() if lock.is_dir() else lock.unlink()
            except OSError as error:
                raise ToolError(_("Another installation is in progress")) from error
    else:
        raise ToolError(_("Another installation is in progress"))
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def find_pandoc(configured: str = "") -> str | None:
    if configured:
        return shutil.which(str(Path(configured).expanduser()))
    found = shutil.which("pandoc")
    if found:
        return found
    if sys.platform == "darwin":
        for folder in ("/opt/homebrew/bin", "/usr/local/bin"):
            found = shutil.which(str(Path(folder) / "pandoc"))
            if found:
                return found
    root = managed_directory("pandoc")
    for name in ("pandoc", "pandoc.exe"):
        for candidate in sorted(root.rglob(name)) if root.exists() else ():
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    return None


def version(program: str) -> str:
    try:
        result = subprocess.run([program, "--version"], capture_output=True, timeout=5, check=True)
        return result.stdout.decode("utf-8", "replace").splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError) as error:
        raise ToolError(_("Could not read the executable version")) from error


def asset_name(tool: str, tag: str, system: str, machine: str) -> str:
    arm = machine.lower() in {"arm64", "aarch64"}
    if machine.lower() not in {"arm64", "aarch64", "x86_64", "amd64"}:
        raise ToolError(_("No supported download for this processor"))
    if tool == "pandoc":
        if system == "darwin":
            suffix = f"{'arm64' if arm else 'x86_64'}-macOS.zip"
        elif system == "linux":
            suffix = f"linux-{'arm64' if arm else 'amd64'}.tar.gz"
        elif system == "win32":
            suffix = "windows-x86_64.zip"  # Also on ARM64: Windows 11 runs x64 programs, and Pandoc has no ARM build.
        else:
            raise ToolError(_("No supported Pandoc download for this platform"))
        return f"pandoc-{tag}-{suffix}"
    if system == "darwin":
        return f"TinyTeX-1-darwin-{tag}.tar.xz"
    if system == "linux":
        return f"TinyTeX-1-linux-{'arm64' if arm else 'x86_64'}-{tag}.tar.xz"
    if system == "win32":
        return f"TinyTeX-{tag}.zip"  # Also on ARM64, as Pandoc.
    raise ToolError(_("No supported TinyTeX download for this platform"))


def unpack(archive: Path, destination: Path, cancelled: Callable[[], bool]) -> None:
    """Extract inside a staging folder. Tar symlinks may only point within it."""
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as bundle:
            if sum(item.file_size for item in bundle.infolist()) > 4_000_000_000:
                raise ToolError(_("Archive is too large"))
            for item in bundle.infolist():
                target = destination / item.filename
                if not target.resolve().is_relative_to(destination.resolve()) or "\\" in item.filename:
                    raise ToolError(_("Unsafe archive path"))
                if cancelled():
                    raise ToolError(_("Installation cancelled"))
                bundle.extract(item, destination)
                if not item.is_dir() and item.external_attr >> 16 & 0o111:
                    target.chmod(0o755)
    else:
        with tarfile.open(archive) as bundle:
            members = bundle.getmembers()
            if sum(item.size for item in members) > 4_000_000_000:
                raise ToolError(_("Archive is too large"))
            for item in members:
                if cancelled():
                    raise ToolError(_("Installation cancelled"))
                bundle.extract(item, destination, filter="data")


def publish(root: Path, target: Path, keep_previous: bool = True) -> None:
    """Replace the target by renaming, rolling back if the final rename fails.

    With `keep_previous` the replaced copy stays beside it for recovery, as the only one: older ones
    are removed. Without it (a copy published moments before, now updated) it is removed itself.
    """
    backup = target.with_name(target.name + ".previous-" + uuid.uuid4().hex[:12])
    existed = target.exists()
    if existed:
        _rename(target, backup)
    try:
        _rename(root, target)
    except OSError:
        if existed:
            _rename(backup, target)
        raise
    if not existed:
        return
    if keep_previous:
        for older in target.parent.glob(target.name + ".previous-*"):
            if older != backup:
                shutil.rmtree(older, ignore_errors=True)
    else:
        shutil.rmtree(backup, ignore_errors=True)


def _rename(source: Path, target: Path) -> None:
    """Rename, retried for a few seconds on Windows: a program just run (`version`) stays locked a moment
    after it exits (by Windows, or a virus scanner reading it), and renaming its folder is refused."""
    for attempt in range(20):
        try:
            os.rename(source, target)
            return
        except PermissionError:
            if sys.platform != "win32" or attempt == 19:
                raise
            time.sleep(0.25)


def _remove_staging(tool: str, folder: Path) -> None:
    """Staging folders an earlier attempt could not remove (Windows kept a file locked), while no
    installation of the tool runs (the caller holds its lock)."""
    for leftover in folder.glob(f".{tool}-*") if folder.exists() else ():
        if leftover.is_dir():
            shutil.rmtree(leftover, ignore_errors=True)


def install(
    tool: str, progress: Callable[[int], None], cancelled: Callable[[], bool] = lambda: False, *, replace: bool = False
) -> Path:
    """Download an official checksummed release, validate it, then publish atomically.

    Replacement requires explicit opt-in and a private installation manifest.
    The previous managed copy is retained for recovery.
    No PATH, registry, Homebrew, shell profile or external installation is changed.
    """
    target = managed_directory(tool)
    with _installing(tool):
        _remove_staging(tool, target.parent)
        return _install(tool, target, progress, cancelled, replace)


def _install(
    tool: str, target: Path, progress: Callable[[int], None], cancelled: Callable[[], bool], replace: bool
) -> Path:
    try:
        if target.is_symlink() or (
            target.exists() and not (replace and (target / "mathessible-install.json").is_file())
        ):
            raise ToolError(_("A private installation already exists; it was left unchanged"))
        repo = _REPOSITORIES[tool]
        latest = release(tool)
        name = asset_name(tool, latest["tag_name"], sys.platform, platform.machine())
        asset = next((item for item in latest["assets"] if item["name"] == name), None)
        if asset is None or not str(asset.get("digest", "")).startswith("sha256:"):
            raise ToolError(_("No checksummed release is available for this platform"))
        url = asset["browser_download_url"]
        if not url.startswith(f"https://github.com/{repo}/releases/download/"):
            raise ToolError(_("Unexpected release download URL"))
        # A staging file Windows still locks is left for the next installation (`_remove_staging`).
        with tempfile.TemporaryDirectory(
            prefix=f".{tool}-", dir=target.parent, ignore_cleanup_errors=True
        ) as temporary:
            staging = Path(temporary)
            archive = staging / "download"
            digest = hashlib.sha256()
            received = 0
            with (
                urlopen(Request(url, headers={"User-Agent": "Mathessible"}), timeout=30) as response,
                archive.open("wb") as output,
            ):
                while chunk := response.read(256 * 1024):
                    if cancelled():
                        raise ToolError(_("Installation cancelled"))
                    received += len(chunk)
                    if received > 1_000_000_000:
                        raise ToolError(_("Download exceeds the size limit"))
                    digest.update(chunk)
                    output.write(chunk)
                    progress(min(90, int(received * 90 / max(1, asset["size"]))))
            if "sha256:" + digest.hexdigest() != asset["digest"]:
                raise ToolError(_("Download checksum did not match"))
            unpacked = staging / "unpacked"
            unpacked.mkdir()
            unpack(archive, unpacked, cancelled)
            binary = "pandoc" if tool == "pandoc" else "pdflatex"
            names = {binary, binary + ".exe"}
            programs = [path for path in unpacked.rglob("*") if path.name in names and path.is_file()]
            if not programs:
                raise ToolError(_("The archive does not contain the expected executable"))
            program = programs[0]
            # Validate before publishing; TinyTeX is relocatable and needs no PATH registration.
            version(str(program))
            root = unpacked
            if tool == "TinyTeX":
                root = program.parent.parent.parent  # TinyTeX/bin/<platform>/pdflatex
                if root == staging or not root.is_relative_to(unpacked):
                    raise ToolError(_("Unexpected TinyTeX archive layout"))
            if cancelled():
                raise ToolError(_("Installation cancelled"))
            (root / "mathessible-install.json").write_text(
                json.dumps({"release": latest["tag_name"], "sha256": digest.hexdigest()})
            )
            publish(root, target)
            progress(100)
        return target
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError, zipfile.BadZipFile) as error:
        raise ToolError(str(error)) from error


def update_tinytex(cancelled: Callable[[], bool] = lambda: False, keep_previous: bool = True) -> Path:
    """Update packages in an isolated copy; preserve the working installation on failure.

    `keep_previous=False` for a copy installed moments before: it need not be kept for recovery.
    """
    target = managed_directory("TinyTeX")
    if target.is_symlink() or not (target / "mathessible-install.json").is_file():
        raise ToolError(_("Only a Mathessible-managed installation can be updated."))
    with _installing("TinyTeX"):
        _remove_staging("TinyTeX", target.parent)
        return _update_tinytex(target, cancelled, keep_previous)


def _update_tinytex(target: Path, cancelled: Callable[[], bool], keep_previous: bool) -> Path:
    try:
        with tempfile.TemporaryDirectory(
            prefix=".TinyTeX-update-", dir=target.parent, ignore_cleanup_errors=True
        ) as temporary:
            root = Path(temporary) / "TinyTeX"
            shutil.copytree(target, root, symlinks=True)
            if cancelled():
                raise ToolError(_("Installation cancelled"))
            programs = [program for folder in sorted((root / "bin").glob("*")) if (program := tlmgr_program(folder))]
            if not programs:
                raise ToolError(_("The archive does not contain the expected executable"))
            program = programs[0]
            if not program.resolve().is_relative_to(root.resolve()):
                raise ToolError(_("The package manager points outside the private installation."))
            # A bounded operation on the staged copy; cancellation discards it afterwards.
            subprocess.run([str(program), "update", "--self", "--all"], capture_output=True, timeout=600, check=True)
            if cancelled():
                raise ToolError(_("Installation cancelled"))
            publish(root, target, keep_previous)
        return target
    except (OSError, subprocess.SubprocessError) as error:
        raise ToolError(_("TinyTeX could not be updated. The previous installation was kept.")) from error
