# Contributing to Mathessible

Thank you for helping. Mathessible is an accessible maths editor first: every
change has to work from the keyboard alone and with a screen reader, so
please read "Accessibility" below before you start.

## Getting started

```shell
git clone --recursive <repository address>
cd Mathessible
sh scripts/bootstrap.sh
uv run mathessible
```

`scripts/bootstrap.sh` fetches the MathCAT and UnicodeMathML submodules,
applies Mathessible's patches to them, builds the native MathCAT extension and
runs the tests. Run it again after pulling changes to `patches/`. On macOS
wxPython needs a Framework build of Python (Homebrew's or python.org's);
the script finds one. If it installed uv locally, use `.tools/uv`
instead of `uv`.

[docs/user-guide.md](docs/user-guide.md) describes Mathessible as its users see it.
[docs/architecture.md](docs/architecture.md) explains how an equation goes
through the app in one page. [docs/engineering-notes.md](docs/engineering-notes.md)
is the long record of what was built and why; read the section for the
area you change.

## Checks

Before you commit:

```shell
uv run python -m unittest discover -s tests -v
uv run ruff check
uv run ruff format
```

Tests that need the real UnicodeMathML converter run it under Node
(`tests/converter_harness.py`); without Node they are skipped. The wx
windows have no automated tests: describe how you tested a GUI change by
hand. `MATHESSIBLE_LOG=1 uv run mathessible` records a session (keys, what Mathessible said,
the source and caret, errors) in `~/.mathessible/logs/`, which helps both you and
whoever reviews.

## Where code goes

`src/mathessible/` is split by concern: `editor/` and `ui/` are the wx code;
`editing/`, `templates/`, `mathcat/`, `documents/` and `symbols/` are logic
with no wx, and new logic belongs there, with tests. Imports are absolute
(`from mathessible.editing.source_map import map_leaves`). AGENTS.md lists the
rules in short.

## MathCAT and UnicodeMathML

Both are submodules at their upstream commits. A fix that belongs in one of
them is a numbered file in `patches/mathcat/` or `patches/unicodemathml/`,
with a header saying what it changes and why; `scripts/bootstrap.sh`
applies it. Changes left only inside the submodule are lost on a fresh
clone, and `uv sync` alone builds MathCAT without them: Mathessible checks at
startup and says which fix is missing. To save a fix, for example
`git -C MathCAT diff > patches/mathcat/0006-….patch`, then add the
header. MathCAT's rules are compiled into the extension: after changing
them, run `uv sync --reinstall-package mathessible-mathcat`. Fixes useful to
everyone are worth proposing upstream too.

## Accessibility

- Everything is keyboard-operable; nothing is mouse-only.
- The built equation is read by MathCAT, never by a table of names in
  Mathessible. Symbol names from the dictionaries only echo typing and read the
  linear source.
- Dialogs use native controls and do not speak through Mathessible: screen
  readers read native controls. Mathessible speaks for itself only in the
  equation editor, which it draws.
- Where Word's equation editor has a feature, Mathessible should match it, and
  where Word's behaviour is unclear, UnicodeMath's specification (Unicode
  Technical Note #28) decides.

## Licence

Mathessible is GPL-2.0-or-later. By contributing you agree that your
contribution is distributed under that licence.
