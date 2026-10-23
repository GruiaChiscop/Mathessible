# MateX

An accessible maths editor. Documents are Markdown; equations are
written in UnicodeMath, the linear format of Microsoft Word's equation
editor; and every equation can be read, navigated and edited with a
screen reader and a braille display, through
[MathCAT](https://github.com/daisy/MathCAT).

MateX is a prototype. It aims to match Word's equation editor feature by
feature, and to go beyond it where a screen reader needs more.

## Features

- **An equation editor modelled on Word's**: a linear view (the
  UnicodeMath source) and a professional view (the built equation),
  building as you type, Math AutoCorrect, templates, a structure gallery,
  normal text, matrix and fraction editing.
- **Speech, navigation and braille from MathCAT**: the built equation is
  read and explored element by element, with its structure (numerator,
  integrand, matrix cell, ...) announced.
- **Editing the built equation directly**: typing, deleting, copying and
  selecting where MathCAT's cursor is, without leaving the professional
  view.
- **Markdown documents and notebooks**: equations as `$...$` and
  `$$...$$`, notebooks of pages saved as a folder or a single `.mtex`
  file, and export to accessible HTML with native MathML.
- **Keyboard first**: everything works from the keyboard, and the
  equation editor speaks for itself, so VoiceOver never wanders into web
  content.

## Getting started

MateX runs from a checkout of this repository, with Python 3.14 and
[uv](https://docs.astral.sh/uv/):

```shell
git clone --recursive <repository address>
cd MateX
sh scripts/bootstrap.sh
uv run matex
```

`scripts/bootstrap.sh` fetches the MathCAT and UnicodeMathML submodules,
applies MateX's patches to them, builds the native MathCAT extension and
runs the tests. On macOS wxPython needs a Framework build of Python
(Homebrew's or python.org's); the script finds one.

## Documentation

- [User guide](docs/user-guide.md): writing and reading equations,
  documents, notebooks and symbol dictionaries.
- [Contributing](CONTRIBUTING.md): checks, where code goes, the patches to
  MathCAT and UnicodeMathML, accessibility rules.
- [Architecture](docs/architecture.md): how an equation goes through the
  app, on one page.
- [Engineering notes](docs/engineering-notes.md): what was built, why, and
  the traps found on the way.

## Built on

- [MathCAT](https://github.com/daisy/MathCAT) (DAISY Consortium):
  speech, navigation and braille for MathML.
- [UnicodeMathML](https://github.com/MurrayIII/UnicodeMathML) (Murray
  Sargent III): the UnicodeMath to MathML converter.
- [wxPython](https://wxpython.org): the native interface.
- Prism (the `prismatoid` package): speech through the running screen
  reader.
- [NVDA](https://www.nvaccess.org)'s symbol dictionaries, downloaded on
  request, for naming symbols while typing.

## Licence

MateX is distributed under the GNU General Public License, version 2 or
(at your option) any later version. MathCAT and UnicodeMathML keep their
own MIT licences, in their submodules; NVDA's dictionaries are not part of
the repository and are under NVDA's licence (GPL-2.0).
