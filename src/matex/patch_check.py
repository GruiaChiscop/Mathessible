"""Whether the local MathCAT/UnicodeMathML patches are applied in this checkout.

The submodules point at the upstream commits; MateX's fixes are files in
`patches/`, applied by scripts/bootstrap.sh. Someone who runs `uv sync`
without bootstrap gets an unpatched MathCAT build and converter: MateX
starts, but reads and builds some equations wrongly. `missing_patches`
finds that (git can tell whether a patch is already in a working tree), so
the app can say so at startup.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# (submodule directory, its folder under patches/).
PATCH_SETS = (("MathCAT", "mathcat"), ("UnicodeMathML", "unicodemathml"))


def checkout_root() -> Path:
    return Path(__file__).resolve().parents[2]


def missing_patches(root: Path | None = None) -> list[str] | None:
    """Patches not applied, as "MathCAT/0005-....patch"; None when it cannot be told (no git, no checkout)."""
    root = checkout_root() if root is None else root
    missing: list[str] = []
    checked = False
    for submodule, folder in PATCH_SETS:
        directory = root / submodule
        patches = sorted((root / "patches" / folder).glob("*.patch"))
        if not patches or not (directory / ".git").exists():
            continue
        for patch in patches:
            try:
                result = subprocess.run(
                    ["git", "-C", str(directory), "apply", "--reverse", "--check", str(patch)],
                    capture_output=True,
                    timeout=10,
                )
            except (OSError, subprocess.SubprocessError):
                return None
            checked = True
            if result.returncode != 0:
                missing.append(f"{submodule}/{patch.name}")
    return missing if checked else None
