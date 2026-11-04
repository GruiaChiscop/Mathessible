"""The Help menu's pages: Mathessible's documentation lives on GitHub, not in the app."""

from __future__ import annotations

from importlib import metadata

from mathessible.i18n import N_

REPOSITORY = "https://github.com/GruiaChiscop/Mathessible"
ISSUES = f"{REPOSITORY}/issues/new"

# Explore Graph's sound follows AudioFunctions+, from this Erasmus+ project: (label, address).
SONIFICATION_CREDIT = N_(
    "How a graph sounds here comes from AudioFunctions+, a web application of SONAIRGRAPH, an Erasmus+ project "
    "led by the University of Turin. Mathessible wrote its own version and is not part of the project."
)
SONIFICATION_PAGES: tuple[tuple[str, str], ...] = (
    (N_("Audio&Functions+ website"), "https://sonairgraph.github.io/audiofunctions-plus/"),
    (N_("SONAIRGRAPH &Erasmus+ project"), "https://sonairgraph.unito.it/"),
)

# (menu label, page in the repository), in the Help menu's order.
HELP_PAGES: tuple[tuple[str, str], ...] = (
    (N_("&Quick Start Guide"), "docs/quick-start.md"),
    (N_("&User Guide"), "docs/user-guide.md"),
    (N_("&Keyboard Shortcuts"), "docs/keyboard-shortcuts.md"),
)

ABOUT = N_(
    "An accessible maths editor: UnicodeMath equations in Markdown, read, "
    "navigated and brailled through MathCAT.\n\n"
    "Built on MathCAT (DAISY Consortium) and UnicodeMathML (Murray Sargent III), "
    "both under the MIT licence. NVDA's symbol dictionaries, downloaded on request, "
    "are under NVDA's licence (GPL-2.0).\n\n"
    "Mathessible is distributed under the GNU General Public License, version 2 or later."
)


def page_url(path: str) -> str:
    return f"{REPOSITORY}/blob/main/{path}"


def version() -> str:
    try:
        return metadata.version("mathessible")
    except metadata.PackageNotFoundError:
        return "unknown"
