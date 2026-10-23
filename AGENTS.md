# Agent Guide (MateX)

General rules for coding agents working on MateX. The detailed engineering
notes (what was built, why, and the traps found on the way) are in
[docs/engineering-notes.md](docs/engineering-notes.md), with a one-page
map in [docs/architecture.md](docs/architecture.md): read the section
for the area you are changing before you change it, and record new traps
and decisions there, not here. Keep this file to rules; do not mirror
README.md.

## Project

MateX is a prototype accessible maths editor (a wxPython desktop app). A
Markdown document is edited natively; `$...$`/`$$...$$` zones open an
equation editor that edits UnicodeMath and speaks, navigates and brailles
equations through MathCAT. The aim is to match Microsoft Word's equation
editor, then go beyond it on accessibility. Word's linear format *is*
UnicodeMath, and the converter MateX uses is Murray Sargent's own
(`UnicodeMathML`), so where Word's behaviour is unclear, UnicodeMath's
specification (Unicode Technical Note #28) is the reference.

Code, identifiers, comments and documentation are in English, British
spelling.

## Product Rules

- Everything must stay keyboard-operable and MathCAT-navigable: no
  mouse-only UI. MathCAT navigation, the braille strip and plain-text
  UnicodeMath stored in Markdown are MateX's advantages over Word; do not
  trade them away for editing speed.
- Dialogs use native controls and make no announcements of their own:
  screen readers read native controls. MateX speaks for itself only in
  the equation editor, which it draws.
- Reading the built equation is always MathCAT's, never the symbol
  dictionary's. The dictionary only echoes typing and reads the linear
  view's source. Do not add hard-coded name tables for symbols.
- The editor adds no space to the equation source except UnicodeMath's
  operand-ending spaces (the ones its own lineariser writes), and never
  removes the user's spaces.
- Converter-output fixes for MathCAT go through `prepare_for_mathcat`
  ([mathcat/prepare.py](src/matex/mathcat/prepare.py)); the converter's
  own markers (`mathcolor="#F00"`/`"#F01"`) are the only test of whether a
  source builds.
- Equations are understood only by the converter (UnicodeMathML in a
  WebView) and MathCAT; Python never parses UnicodeMath itself. Without
  the native MathCAT extension the editor still edits the source as text,
  but professional view refuses (`MATHCAT_MISSING`) and the app warns at
  startup.

## Code Rules

- Code lives by concern in `src/matex/`: `editor/` and `ui/` are the wx
  code, `editing/`, `templates/`, `mathcat/`, `documents/` and `symbols/`
  the logic (the table is in the engineering notes, "Code Organisation").
  Imports are absolute (`from matex.editing.source_map import ...`).
- New logic goes in a wx-free module with unit tests. GUI modules guard
  `import wx` and expose a stub class without it, so the package stays
  importable for tests.
- Templates and structure edits go through `source_view` (`edit_in_view`,
  `view_of`), since the source may hold control words (`\sqrt`, `\of`).
  A new Insert entry is added to `insert_catalog`, not as a key handler.
- `EquationEditor` and `MathCatNavigator` are split into mixins that only
  add methods; all state lives in their `__init__`/dataclass fields.
- Style: `uv run ruff check` and `uv run ruff format` (configured in
  pyproject.toml) must pass. Beyond them: `from __future__ import
  annotations`, frozen/slotted dataclasses for values, explicit exception
  tuples (bare `except Exception` only where assistive output must never
  crash the editor). A formatting-only commit goes in
  `.git-blame-ignore-revs`.
- Colours come from [ui/theme.py](src/matex/ui/theme.py), whose tests enforce
  WCAG contrast in light and dark appearance.

## Validation

- `uv run python -m unittest discover -s tests -v` after every change.
  Tests that need the real converter use `tests/converter_harness.py`
  (Node), not a copy of its runner.
- To probe the converter without the GUI, load the dist JS under `node`
  (see "Probing the converter" in the engineering notes).
- GUI code has no automated tests: GUI changes are tested by hand in the
  running app, so give short test steps. Start MateX for a test with
  `MATEX_LOG=1 uv run matex` and read the session log in `~/.matex/logs/`
  afterwards instead of asking the tester what happened.
- Before relaunching MateX, check that no older instance is still running.

## Submodules and Patches

- `MathCAT/` and `UnicodeMathML/` are submodules at their upstream commits.
  MateX's fixes to them are files in `patches/`, applied by
  `scripts/bootstrap.sh`; the app warns at startup when one is missing
  ([patch_check.py](src/matex/patch_check.py)).
- Changing either submodule is allowed when a fix belongs there. Keep the
  change minimal, save it as a numbered patch with a header saying what
  and why, and list it in the engineering notes. A change left only inside
  the submodule is lost on a fresh clone.
- MathCAT's `.rs` files are CRLF: use `git -C MathCAT apply`, not `patch`.
  Its rules are bundled into the extension: after changing them, run
  `uv sync --reinstall-package matex-mathcat`.
- No `cargo fmt` or formatting sweeps inside `MathCAT/`.

## Security-Sensitive Code

- [documents/mathml_sanitize.py](src/matex/documents/mathml_sanitize.py) `sanitize_mathml` is
  the allow-list before converter output is embedded in exported HTML.
  Adding a tag or attribute is a security decision.
- [documents/notebook.py](src/matex/documents/notebook.py) `_validate_page_path` and
  [documents/portable_notebook.py](src/matex/documents/portable_notebook.py)
  `_safe_archive_path` guard against path traversal and symlinks; route
  every new page or file field through them.

## Do Not

- Run git commands (commit, push, submodule changes) unless asked.
- Edit `.venv/`, `.tools/`, `.uv-cache/` or `native/mathcat_py/target/`
  (generated caches).
- Commit NVDA's symbol dictionaries (GPL-2.0, downloaded on demand).
- "Fix" the checkout-only layout by hard-coding paths: MateX runs from this
  checkout (`uv run matex`), a known prototype limitation.
