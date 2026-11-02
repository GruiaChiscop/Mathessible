"""Discovery and update checks for optional tools, without GUI dependencies."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from mathessible.documents.optional_tools import ToolError, find_pandoc, managed_directory, version
from mathessible.documents.tex_compile import find_installation
from mathessible.i18n import _


@dataclass(frozen=True, slots=True)
class UpdateCheck:
    path: str
    installed: str
    latest: str
    available: bool
    managed: bool


def locate(tool: str, configured: str = "") -> str:
    """Return the value to show in Settings: executable or LaTeX bin directory."""
    if tool == "pandoc":
        return find_pandoc(configured) or ""
    found = find_installation(configured=configured)
    return str(found.bin_directory) if found else ""


def is_managed(tool: str, path: str) -> bool:
    root = managed_directory(tool)
    return (
        bool(path)
        and not root.is_symlink()
        and Path(path).resolve().is_relative_to(root.resolve())
        and (root / "mathessible-install.json").is_file()
    )


def release(tool: str) -> dict:
    repo = "jgm/pandoc" if tool == "pandoc" else "rstudio/tinytex-releases"
    try:
        request = Request(f"https://api.github.com/repos/{repo}/releases/latest", headers={"User-Agent": "Mathessible"})
        with urlopen(request, timeout=30) as response:
            data = json.loads(response.read(2_000_001))
        if not isinstance(data, dict) or not isinstance(data.get("tag_name"), str):
            raise ValueError("Invalid release")
        return data
    except (OSError, ValueError) as error:
        raise ToolError(_("Could not check for updates. Try again later.")) from error


def newer(latest: str, installed: str) -> bool:
    def parts(value):
        match = re.search(r"\d+(?:\.\d+)*", value)
        if not match:
            raise ToolError(_("The installed version could not be compared."))
        return tuple(int(part) for part in match[0].split("."))

    left, right = parts(latest), parts(installed)
    width = max(len(left), len(right))
    return left + (0,) * (width - len(left)) > right + (0,) * (width - len(right))


def check(tool: str, configured: str = "") -> UpdateCheck:
    path = locate(tool, configured)
    if not path:
        raise ToolError(_("No executable was found. Correct the path or clear it for automatic detection."))
    managed = is_managed(tool, path)
    if tool == "pandoc":
        installed = version(path)
        latest = release(tool)["tag_name"]
        return UpdateCheck(path, installed, latest, newer(latest, installed), managed)
    found = find_installation(configured=path)
    installed = version(str(found.program(found.engines[0])))
    tlmgr = found.program("tlmgr")
    if not tlmgr.is_file():
        raise ToolError(
            _("This LaTeX distribution does not provide tlmgr. Use its own package manager to check for updates.")
        )
    try:
        result = subprocess.run(
            [str(tlmgr), "--machine-readable", "update", "--list"],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ToolError(
            _(
                "Could not check LaTeX package updates. The repository may be unavailable or require a newer TeX Live distribution."
            )
        ) from error
    if "end-of-header" not in result.stdout or "end-of-updates" not in result.stdout:
        raise ToolError(_("The LaTeX update response could not be understood."))
    body = result.stdout.split("end-of-header", 1)[1].split("end-of-updates", 1)[0]
    updates = any(re.match(r"^\S+\s+[uaf]\s", line) for line in body.splitlines())
    return UpdateCheck(path, installed, _("TeX Live package repository"), updates, managed)
