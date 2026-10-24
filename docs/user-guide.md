# MateX user guide

How to write, read and edit with MateX. For what the project is, see the
[README](../README.md); for how it works inside,
[architecture.md](architecture.md).

The equation editor is drawn by MateX itself, not a native text field, so
that VoiceOver does not enter web navigation or announce an equation
twice. What MateX says about the built equation is MathCAT's speech,
announced through the running screen reader (or printed to the console
when there is none). Without the native MathCAT extension, equations can
only be edited as text, and MateX says so at startup.

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

## Editing equations

### The linear view

In the **linear view** you type UnicodeMath and move with the arrow keys,
Backspace, Delete, Home and End (on macOS also `Command`+Left/Right for
the start and end). Up/Down read the source; with Shift they select to its
start or end. A control word is converted when you type Space or a
punctuation mark after it (`\alpha` becomes α), and while you type one the
matching words are offered: Up/Down browse them, Tab takes one, Escape
closes the list. Tab and Shift+Tab move between a template's slots. Math
AutoCorrect is one list, as in Word (`Settings → Math AutoCorrect…`): the
control words, MateX's shortcuts and your own entries, each of which can
be changed or deleted. As in Word, `\mathbb{R}` becomes ℝ when its brace
closes, and `\doubleR`, `\scriptL`, `\frakturg` give the math alphabets.
Your own `\R ℝ` works like a control word, and `deg °` is replaced when
you type Space after it. A deleted control word stays the
text you typed, unless "Deleted AutoCorrect control words still show as
their symbol" is on.

### Building as you type

With **Build equations as you type** (on by default), as in Word, what
you type is built as soon as it is complete, on Space or an operator or
punctuation mark, and typing goes on in the professional view. What is
not complete yet stays linear text inside the built equation: in
`a/b+c/`, a/b is a fraction and `c/` is still read as "c divided by"
until `d` and Space build it. Linear text stays linear when you move
away from it; Undo right after a build takes it back. As in Word, Space
builds a chain of scripts one at a time: in `a^b^c` the first Space
builds b to the c, the second builds a to that power, while an operator
such as `+` builds the whole chain at once.

With **Remove extra spaces** (on by default), as Word's linear format
has none, the spaces that change nothing are removed when the equation
is saved or shown in the linear view: `a^b^c  ` is saved as `a^b^c`,
`x + y = 1` as `x+y=1`. A space that ends an operand stays (`a_1 b`: b is
not in the subscript), and so does one after a word (`sin x`) and every
space in a normal text. As with Word's
Linear and Professional on a selection, `F2` with a selection in the
professional view (Shift with the arrows) turns only that part linear,
and `F2` on a selection holding linear text builds it again. **Say what was
built** (on by default) adds "built fraction" when typing builds a
structure. With
**Open equations built**, equations open straight in the professional
view (an empty one still opens linear).

### The professional view

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

### The context menu

The context menu (right click, `Shift+F10` or the Menu key) works in both
views. It inserts templates, switches the view, and, when the caret is in
one, edits a matrix (rows above or below, columns left or right, deleting
the current row or column), cases or an equation array, a fraction's style
(stacked, skewed, linear, small), a root's index and an integral's or a
sum's limits.

### Normal text

**Normal Text** (`Cmd+Shift+T`, `Ctrl+Shift+T` elsewhere; Insert menu),
as Word's button: text such as "if" or "for all" written upright, with
its spaces, as UnicodeMath's quoted text (`"for all "x`). In math it
starts a text, at the end of a text it goes back to math, in the middle
it splits it, and on a selection it turns it into text or back into
math. In normal text nothing converts or builds; **Use Math AutoCorrect
in normal text** (off by default) lets control words and shortcuts
convert there too.

### Unknown symbols

A symbol MathCAT and the symbol dictionary do not know reaches the
screen reader as itself; with **Name unknown symbols** (on by default)
MateX says its Unicode name instead (🜁, "alchemical symbol for air").
Letters (ș, 中) and a text's punctuation are left as they are.

### Templates and the Structure Gallery

The **Insert** menu has the templates, each with its shortcut where Word
has one (an integral's, sum's or product's operand is a box, as in Word:
`+` typed in it stays inside; Space after `\int_0^1` typed by hand opens
it too), the matrix and symbol dialogs, and the **Structure Gallery**
(`Cmd+Shift+G`): Word's structure categories (Fraction, Script, Radical,
Integral, Large Operator, Bracket, Function, Accent, Limit and Log,
Operator, Matrix), each a list of variants. Shift+Tab goes to the
categories, Enter inserts, and "Written as" shows how the structure is
typed in the linear view.

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
