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
import uuid
import zipfile
from collections.abc import Callable
from pathlib import Path
from urllib.request import Request, urlopen

from mathessible.i18n import _


class ToolError(RuntimeError):
    pass


def tools_directory(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".mathessible" / "tools"


def managed_directory(tool: str, home: Path | None = None) -> Path:
    if tool not in {"pandoc", "TinyTeX"}:
        raise ValueError("Unknown optional tool")
    return tools_directory(home) / tool


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
        elif system == "win32" and not arm:
            suffix = "windows-x86_64.zip"
        else:
            raise ToolError(_("No supported Pandoc download for this platform"))
        return f"pandoc-{tag}-{suffix}"
    if system == "darwin":
        return f"TinyTeX-1-darwin-{tag}.tar.xz"
    if system == "linux":
        return f"TinyTeX-1-linux-{'arm64' if arm else 'x86_64'}-{tag}.tar.xz"
    if system == "win32" and not arm:
        return f"TinyTeX-{tag}.zip"
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


def publish(root: Path, target: Path) -> None:
    """Keep a recoverable previous copy and roll back if the final rename fails."""
    backup = target.with_name(target.name + ".previous-" + uuid.uuid4().hex[:12])
    existed = target.exists()
    if existed:
        target.rename(backup)
    try:
        root.rename(target)
    except OSError:
        if existed:
            backup.rename(target)
        raise


def install(
    tool: str, progress: Callable[[int], None], cancelled: Callable[[], bool] = lambda: False, *, replace: bool = False
) -> Path:
    """Download an official checksummed release, validate it, then publish atomically.

    Replacement requires explicit opt-in and a private installation manifest.
    The previous managed copy is retained for recovery.
    No PATH, registry, Homebrew, shell profile or external installation is changed.
    """
    target = managed_directory(tool)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.parent / f".{tool}.installing"
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise ToolError(_("Another installation is in progress")) from error
    try:
        if target.is_symlink() or (
            target.exists() and not (replace and (target / "mathessible-install.json").is_file())
        ):
            raise ToolError(_("A private installation already exists; it was left unchanged"))
        repo = "jgm/pandoc" if tool == "pandoc" else "rstudio/tinytex-releases"
        request = Request(f"https://api.github.com/repos/{repo}/releases/latest", headers={"User-Agent": "Mathessible"})
        with urlopen(request, timeout=30) as response:
            release = json.loads(response.read(2_000_001))
        name = asset_name(tool, release["tag_name"], sys.platform, platform.machine())
        asset = next((item for item in release["assets"] if item["name"] == name), None)
        if asset is None or not str(asset.get("digest", "")).startswith("sha256:"):
            raise ToolError(_("No checksummed release is available for this platform"))
        url = asset["browser_download_url"]
        if not url.startswith(f"https://github.com/{repo}/releases/download/"):
            raise ToolError(_("Unexpected release download URL"))
        with tempfile.TemporaryDirectory(prefix=f".{tool}-", dir=target.parent) as temporary:
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
                json.dumps({"release": release["tag_name"], "sha256": digest.hexdigest()})
            )
            publish(root, target)
            progress(100)
        return target
    except (OSError, ValueError, KeyError, tarfile.TarError, zipfile.BadZipFile) as error:
        raise ToolError(str(error)) from error
    finally:
        lock.rmdir()


def update_tinytex(cancelled: Callable[[], bool] = lambda: False) -> Path:
    """Update packages in an isolated copy; preserve the working installation on failure."""
    target = managed_directory("TinyTeX")
    if target.is_symlink() or not (target / "mathessible-install.json").is_file():
        raise ToolError(_("Only a Mathessible-managed installation can be updated."))
    lock = target.parent / ".TinyTeX.installing"
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise ToolError(_("Another installation is in progress")) from error
    try:
        with tempfile.TemporaryDirectory(prefix=".TinyTeX-update-", dir=target.parent) as temporary:
            root = Path(temporary) / "TinyTeX"
            shutil.copytree(target, root, symlinks=True)
            if cancelled():
                raise ToolError(_("Installation cancelled"))
            programs = [p for p in (root / "bin").glob("*/tlmgr*") if p.name in {"tlmgr", "tlmgr.bat", "tlmgr.exe"}]
            if not programs:
                raise ToolError(_("The archive does not contain the expected executable"))
            program = programs[0]
            if not program.resolve().is_relative_to(root.resolve()):
                raise ToolError(_("The package manager points outside the private installation."))
            # A bounded operation on the staged copy; cancellation discards it afterwards.
            subprocess.run([str(program), "update", "--self", "--all"], capture_output=True, timeout=600, check=True)
            if cancelled():
                raise ToolError(_("Installation cancelled"))
            publish(root, target)
        return target
    except (OSError, subprocess.SubprocessError) as error:
        raise ToolError(_("TinyTeX could not be updated. The previous installation was kept.")) from error
    finally:
        lock.rmdir()
