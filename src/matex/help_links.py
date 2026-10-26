"""The Help menu's pages: MateX's documentation lives on GitHub, not in the app."""

from __future__ import annotations

from importlib import metadata

REPOSITORY = "https://github.com/GruiaChiscop/MateX"
ISSUES = f"{REPOSITORY}/issues/new"

# (menu label, page in the repository), in the Help menu's order.
HELP_PAGES: tuple[tuple[str, str], ...] = (
    ("&Quick Start Guide", "docs/quick-start.md"),
    ("&User Guide", "docs/user-guide.md"),
    ("&Keyboard Shortcuts", "docs/keyboard-shortcuts.md"),
)

ABOUT = (
    "An accessible maths editor: UnicodeMath equations in Markdown, read, "
    "navigated and brailled through MathCAT.\n\n"
    "Built on MathCAT (DAISY Consortium) and UnicodeMathML (Murray Sargent III), "
    "both under the MIT licence. NVDA's symbol dictionaries, downloaded on request, "
    "are under NVDA's licence (GPL-2.0).\n\n"
    "MateX is distributed under the GNU General Public License, version 2 or later."
)


def page_url(path: str) -> str:
    return f"{REPOSITORY}/blob/main/{path}"


def version() -> str:
    try:
        return metadata.version("matex")
    except metadata.PackageNotFoundError:
        return "unknown"
