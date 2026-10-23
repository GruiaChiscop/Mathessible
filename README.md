# MateX

A prototype accessible maths editor: documents are Markdown, equations are
written in UnicodeMath (the linear format of Microsoft Word's equation
editor), and every equation can be read, navigated and edited with a
screen reader and a braille display, through
[MathCAT](https://github.com/daisy/MathCAT).

What it does so far:

- UnicodeMath, converted to MathML by the official converter,
  `MurrayIII/UnicodeMathML` (a submodule): fractions, radicals, scripts,
  accents, brackets, functions, n-ary operators, matrices, cases, equation
  arrays and control words (`\alpha`, `\sum`, …).
- An equation editor with two views, as in Word: **linear** (the
  UnicodeMath source) and **professional** (the built equation), switched
  with `F2`.
- Speech, navigation and braille from MathCAT, announced through Prism
  (with a console fallback when no screen reader is available).
- Word's editing aids: Math AutoCorrect for control words and shortcuts
  (`\pi`, `->`), a completion list for control words, templates with
  Tab-able slots, a structure gallery, matrix row and column editing,
  fraction styles, and building the equation as you type.
- Notebooks of Markdown pages, saved as a folder or a single `.mtex` file,
  and export to accessible HTML with native MathML.

The equation editor is drawn by MateX itself, not a native text field, so
that VoiceOver does not enter web navigation or announce an equation
twice. A system WebView converts UnicodeMath to MathML and shows the
rendered equation, but never takes the focus. MathCAT receives the same
MathML; what MateX says about the built equation is MathCAT's speech. A
minimal reader in `matex.ast` is used only if the native extension cannot
be loaded.

## Quick installation with uv

```shell
sh scripts/bootstrap.sh
```

The script initialises the submodules, applies MateX's patches to them
(see below), installs uv and the Rust toolchain locally if they are
missing, creates `.venv`, compiles the MathCAT binding, syncs the versions
in `uv.lock` and runs the tests. On Windows and Linux uv can install
Python by itself. On macOS wxPython needs a Framework build of Python: the
script finds one installed through Homebrew or python.org, and explains
what is missing if there is none. The project's Python version is 3.14.

## Local changes to MathCAT and UnicodeMathML

The `MathCAT` and `UnicodeMathML` submodules point at the original
upstream commits (`daisy/MathCAT`, `MurrayIII/UnicodeMathML`). MateX's
fixes to them are kept separately, as files in `patches/mathcat/` and
`patches/unicodemathml/`; each file's header says what it changes and
why. `scripts/bootstrap.sh` applies them after fetching the submodules
(skipping those already applied), so after a fresh clone run:

```shell
git clone --recursive <repository address>
cd MateX
sh scripts/bootstrap.sh
```

Running `uv sync` alone, without the bootstrap script, builds MathCAT
**without** the fixes: MateX starts, but reads or builds some equations
wrongly. MateX checks this at startup and, if any fix is missing, says
which and asks you to run the script. After changing MathCAT's rules
(`Rules/`), rebuild the native extension with
`uv sync --reinstall-package matex-mathcat`.

Changes made inside the submodules are not part of MateX's commits; a new
fix is saved as a file in `patches/` (for example with
`git -C MathCAT diff > patches/mathcat/0006-….patch`, plus a header). The
MathCAT and UnicodeMathML licences (MIT) stay in the submodules.

## Everyday commands

After installation, with uv on your `PATH`:

```shell
uv sync
uv run matex
uv run python -m unittest discover -s tests -v
```

If the script installed uv locally, use `.tools/uv` instead of `uv`.

To record a test session (keys, what MateX says, the source and caret,
commands and errors) in `~/.matex/logs/`:

```shell
MATEX_LOG=1 uv run matex
```

## Editing equations

In the **linear view** you type UnicodeMath and move with the arrow keys,
Backspace, Delete, Home and End (on macOS also `Command`+Left/Right for
the start and end). Up/Down read the source; with Shift they select to its
start or end. A control word is converted when you type Space or a
punctuation mark after it (`\alpha` becomes α), and while you type one the
matching words are offered: Up/Down browse them, Tab takes one, Escape
closes the list. Tab and Shift+Tab move between a template's slots. Math
AutoCorrect is one list, as in Word (`Settings → Math AutoCorrect…`): the
control words, MateX's shortcuts and your own entries, each of which can
be changed or deleted. `\R ℝ` works like a control word, and `deg °` is
replaced when you type Space after it. A deleted control word stays the
text you typed, unless "Deleted AutoCorrect control words still show as
their symbol" is on.

With **Build equations as you type** (on by default), as in Word, the
equation is built as soon as it is complete, on Space or an operator or
punctuation mark, and typing goes on in the professional view. With
**Open equations built**, equations open straight in the professional
view (an empty one still opens linear).

In the **professional view** you are on MathCAT's reading of the built
equation:

- Left/Right move by character, `Option`+Left/Right (`Ctrl` elsewhere) by
  element, Home/End to the start and end.
- Up/Down read the previous or next row of a matrix, cases or equation
  array, or the whole equation.
- `Command+Option`+arrows on macOS (`Ctrl+Alt`+arrows elsewhere) move
  between matrix cells.
- Typing, Backspace and Delete edit the equation where the caret is, and
  it is rebuilt. Templates, Undo/Redo and Tab work as in the linear view.
- `Shift+Option+Space` (`Shift+Alt+Space` elsewhere) says where typing
  would go, for example "after 1, end of numerator, before 2".
- `Cmd+C`/`Cmd+X` copy or cut the current element (a whole fraction, a
  numerator, a symbol), and `Cmd+V` pastes where typing would go. On a
  whole structure, the first Backspace or Delete only asks ("the
  fraction, press again to delete it") and a second one, straight after,
  deletes it.
- Shift with the arrow keys selects, by character or by element.
- `F10` (View → Writing Mode) switches between writing and exploring:
  while exploring nothing changes the equation and Space reads the
  current element.
- `F8` lists the equation's errors; Enter on one selects it.

The context menu (right click, `Shift+F10` or the Menu key) works in both
views. It inserts templates, switches the view, and, when the caret is in
one, edits a matrix (rows above or below, columns left or right, deleting
the current row or column), cases or an equation array, a fraction's style
(stacked, skewed, linear, small), a root's index and an integral's or a
sum's limits.

The **Insert** menu has the templates, each with its shortcut where Word
has one, the matrix and symbol dialogs, and the **Structure Gallery**
(`Cmd+Shift+G`): Word's structure categories (Fraction, Script, Radical,
Integral, Large Operator, Bracket, Function, Accent, Limit and Log,
Operator, Matrix), each a list of variants. Shift+Tab goes to the
categories, Enter inserts, and "Written as" shows how the structure is
typed in the linear view.

## Markdown and equations

The main window is a native Markdown editor. Inline equations are written
between `$...$` and display equations between `$$...$$`. With the caret
in one, `Alt+=` on Windows and Linux or `Control+=` on macOS opens it in
the equation editor. The same command in ordinary text creates a new
inline equation, or wraps the selection in delimiters.

In the equation editor, `Enter` saves the equation and starts a new line
after it, as in Word; another `Alt+=` (`Control+=` on macOS) saves and
returns to the Markdown. `Escape` cancels the edit without changing the
document. Dollar signs preceded by a backslash, and those in Markdown code
blocks or code spans, are not taken as equations.

View → Document Preview (`Ctrl+Shift+P`) shows the formatted document,
with rendered equations, beside the Markdown editor. It is off by default
and remembered between sessions. In the equation editor, the linear view
shows a preview of the equation under the source, and the professional
view shows the rendered equation with the current element highlighted;
clicking part of the equation moves MathCAT's cursor there.

Documents are saved as UTF-8 Markdown files from the File menu, with New,
Open, Save and Save As and the standard shortcuts `Ctrl/Command+N`,
`Ctrl/Command+O`, `Ctrl/Command+S` and `Ctrl/Command+Shift+S`. The `.md`
extension is added when none is given. MateX asks before discarding
unsaved changes, including an equation still open in the equation editor.

Each document or notebook opens in its own window. `New Window`, `Open`
and the notebook commands keep the existing windows. `Close Window` closes
only the current document, and `Quit` checks every window for unsaved
changes. The `Window` menu moves to the next or previous window and brings
them all to the front.

## Notebooks and pages

A MateX notebook is an ordinary folder. `matex.json` keeps the title and
the order of the pages, and the `pages` folder holds one UTF-8 `.md` file
per page, so a notebook stays readable without MateX and works well with
version control.

The Notebook menu creates and opens notebooks, adds, renames and deletes
pages, and moves them up or down. The accessible "Notebook pages" list
appears beside the editor. When you change page, MateX saves the current
one, including an equation being edited.

To move or share a notebook, it can be saved as a single `.mtex` file: a
compressed archive with the manifest and every Markdown page. MateX
creates, opens and edits `.mtex` notebooks directly, and saving repacks
the archive atomically. Unsafe paths, symbolic links and archives that
would unpack to an excessive size are refused on opening.

`File → Export as HTML…` exports the current document, or every page of
the notebook, as a single HTML file: a table of contents, Markdown
formatting, tables, and the UnicodeMath equations converted to native
MathML, so the result stays accessible and needs neither JavaScript nor
an internet connection.

## Symbol dictionaries

The names spoken for symbols while typing, deleting and moving in the
linear view come from a dictionary in NVDA's `symbols.dic` format. MateX
has its own, in English. NVDA's dictionaries are downloaded from the NVDA
repository, from within the app with `Settings → Download NVDA
dictionaries…` (choosing the languages from a list), or from the command
line:

```shell
uv run matex-fetch-symbols          # every language
uv run matex-fetch-symbols ro en    # only these
```

They are saved in `~/.matex/symbols/` and chosen in `Settings → Symbol
dictionary`. The download notes, in the first lines of each file, the
source (NVDA), the language, the address and the date; the Settings list
shows "NVDA" only for files with that note, never because of a file name.
`Import dictionary…`, in the same place, brings in any file in the same
format (written by hand or copied from an NVDA installation). An NVDA
dictionary in another language falls back to NVDA's English one, if
downloaded, and then to MateX's own for what it does not define. The
built equation is always read by MathCAT, not by these dictionaries.

## Licence

MateX is distributed under the GNU General Public License, version 2 or
(at your option) any later version. NVDA's dictionaries are not part of
the repository; they are downloaded on request and are under NVDA's
licence (GPL-2.0).
