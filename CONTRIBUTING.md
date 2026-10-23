# Contributing to MateX

Thank you for helping. MateX is an accessible maths editor first: every
change has to work from the keyboard alone and with a screen reader, so
please read "Accessibility" below before you start.

## Getting started

```shell
git clone --recursive <repository address>
cd MateX
sh scripts/bootstrap.sh
uv run matex
```

`scripts/bootstrap.sh` fetches the MathCAT and UnicodeMathML submodules,
applies MateX's patches to them, builds the native MathCAT extension and
runs the tests. Run it again after pulling changes to `patches/`. On macOS
wxPython needs a Framework build of Python (Homebrew's or python.org's);
the script finds one.

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
hand. `MATEX_LOG=1 uv run matex` records a session (keys, what MateX said,
the source and caret, errors) in `~/.matex/logs/`, which helps both you and
whoever reviews.

## Where code goes

`src/matex/` is split by concern: `editor/` and `ui/` are the wx code;
`editing/`, `templates/`, `mathcat/`, `documents/` and `symbols/` are logic
with no wx, and new logic belongs there, with tests. Imports are absolute
(`from matex.editing.source_map import map_leaves`). AGENTS.md lists the
rules in short.

## MathCAT and UnicodeMathML

Both are submodules at their upstream commits. A fix that belongs in one of
them is a numbered file in `patches/mathcat/` or `patches/unicodemathml/`,
with a header saying what it changes and why; `scripts/bootstrap.sh`
applies it. Changes left only inside the submodule are lost on a fresh
clone. MathCAT's rules are compiled into the extension: after changing
them, run `uv sync --reinstall-package matex-mathcat`. Fixes useful to
everyone are worth proposing upstream too.

## Accessibility

- Everything is keyboard-operable; nothing is mouse-only.
- The built equation is read by MathCAT, never by a table of names in
  MateX. Symbol names from the dictionaries only echo typing and read the
  linear source.
- Dialogs use native controls and do not speak through MateX: screen
  readers read native controls. MateX speaks for itself only in the
  equation editor, which it draws.
- Where Word's equation editor has a feature, MateX should match it, and
  where Word's behaviour is unclear, UnicodeMath's specification (Unicode
  Technical Note #28) decides.

## Licence

MateX is GPL-2.0-or-later. By contributing you agree that your
contribution is distributed under that licence.
