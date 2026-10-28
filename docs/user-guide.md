# Mathessible user guide

How to write, read and edit with Mathessible. For what the project is, see the
[README](../README.md); for how it works inside,
[architecture.md](architecture.md). New to Mathessible? Start with the
[quick start](quick-start.md); every key is in
[keyboard-shortcuts.md](keyboard-shortcuts.md). Mathessible's Help menu opens
these pages on GitHub.

The equation editor is drawn by Mathessible itself, not a native text field, so
that VoiceOver does not enter web navigation or announce an equation
twice. What Mathessible says about the built equation is MathCAT's speech,
announced through the running screen reader (or printed to the console
when there is none). Without the native MathCAT extension, equations can
only be edited as text, and Mathessible says so at startup.

## Settings

`Settings…` (`Command+,` on macOS, in the Edit menu elsewhere) groups the
settings in tabs: Language (see below), Typing (Math AutoCorrect and what
converts while typing), Building (building as you type, recognised
functions), Navigation, Speech (symbol dictionaries, unknown symbols),
Braille (the braille code and your own braille signs), and PDF, HTML and
Word (the defaults of each export). On macOS it is a window,
as in Mac apps: every change applies and is saved at once, and Escape or
`Command+W` closes it. On Windows and Linux it is a dialog with OK,
Cancel and Apply.

### Language

Mathessible is offered in MathCAT's languages, so that the menus and
dialogs can be in the language equations are spoken in: English, German,
Greek, Spanish, Finnish, French, Hungarian, Indonesian, Norwegian Bokmål,
Polish, Portuguese (Brazil), Russian, Swedish, Vietnamese and Chinese
(Taiwan). The Language tab has two choices:

- **Interface**: the language of the menus, dialogs and what Mathessible
  says about editing (for example "equation saved"). "The system's" (the
  default) takes the first of your system's preferred languages that is
  offered, else English. The interface changes the next time Mathessible
  starts.
- **Speech of equations**: the language MathCAT speaks equations in, and
  in which the equation editor names its stops ("start fraction",
  "in the numerator"). "The interface's" (the default) follows the
  interface. This changes at once.

What you type is never translated, and an exported document keeps the
language of its own text; the language field of an export's Document tab
only labels it. Only English is written by the project. The other
languages are drafts that a native speaker has yet to review, so some
wording may be odd; [translating.md](translating.md) says how to correct
it.

## Markdown and equations

The main window is a native Markdown editor. Inline equations are written
between `$...$` and display equations between `$$...$$`. With the caret
in one, `Alt+=` on Windows and Linux or `Control+=` on macOS opens it in
the equation editor. The same command in ordinary text creates a new
inline equation, or wraps the selection in delimiters.

In the equation editor, `Enter` saves the equation and starts a new line
after it, as in Word; another `Alt+=` (`Control+=` on macOS) saves and
returns to the Markdown. `Escape` cancels the edit without changing the
document. As in Word, Edit → Change Equation to Display (or
to Inline), with the caret in an equation, makes an inline equation a
display one, on a line of its own, or a display one inline, where it
is; in the equation editor it is in the Equation menu and applies when
the equation is saved. Dollar signs preceded by a backslash, and those in Markdown code
blocks or code spans, are not taken as equations.

View → Document Preview (`Ctrl+Shift+P`) shows the formatted document,
with rendered equations, beside the Markdown editor. It is off by default
and remembered between sessions. In the equation editor, the linear view
shows a preview of the equation under the source, and the professional
view shows the rendered equation with a caret where typing goes, as in a
text field (in exploration mode, F10, the element being read is outlined
instead). A click puts the caret there, between two characters of a
number too, a drag selects, and a double click selects the element. In
the linear view the source line scrolls to keep the caret in view, and
a double click selects a word. View → Zoom In and Zoom Out
(`Command+Option+=` and `Command+Option+-`, `Ctrl+Alt` elsewhere;
`Command+=` is the subscript template) enlarge both views; Actual Size
(`Command+Option+0`) goes back to 100%.

### Footnotes

Insert → Footnote (`Command+Shift+F`, `Ctrl+Alt+F` elsewhere) puts a
footnote reference at the caret, `[^1]`, and its note at the end of the
document, `[^1]: `, with the caret in it to type the note, as in Word.
This is the footnote syntax GitHub and Pandoc read. A note may hold
equations, and may be anywhere in the document; labels are names, so
`[^limits]` works too, and the exports number the notes in the order
their references come. Insert → Go to Footnote or Reference
(`Command+Option+Shift+F`, `Ctrl+Alt+Shift+F`) goes from a reference to
its note, and from a note back to its reference. The preview and every
export have them: HTML with the notes at the end, linked both ways; PDF
and Word as their own footnotes, at the bottom of the page; BRF with
the number in brackets and the notes after the text.

### Equations in LaTeX

A document's equations are UnicodeMath, unless its front matter says
`math: latex`; then they are LaTeX, kept in the document as you type
them (`$\frac{a}{b}$`), as GitHub and Pandoc write Markdown math. Edit →
Equations in LaTeX makes a document LaTeX, or UnicodeMath again: it
asks first, then writes every equation again from what it builds, so
spacing and some details can change (an equation that does not build is
kept as it is, and Undo restores them all). `Settings → Typing` can
start every new document and notebook page in LaTeX.

Markdown written elsewhere, as GitHub and Pandoc write it, has LaTeX
equations but no `math: latex`. When a document you open has equations
that build only as LaTeX (`\frac{a}{b}`, `\mathbb{R}`, `\begin{cases}`),
Mathessible asks whether to mark it as a LaTeX document; Leave as It Is
keeps reading them as UnicodeMath.

In a LaTeX document the equation editor's linear view is the LaTeX,
typed as it is written: no Math AutoCorrect or suggestions while you
type, nothing built until you ask, with the built equation previewed
under it. The Insert menu and its shortcuts insert LaTeX there
(`\frac{}{}`, the caret in the first empty slot). F2 builds it in the
professional view, edited there as any equation, with templates and
Math AutoCorrect. Leaving the professional view (F2, or saving the
equation) keeps your LaTeX exactly as you typed it if you only read it
there; after an edit there, it is written again from the edited equation
(`\frac{a}{b}`, `x \in \mathbb R^n`), and one Undo in the linear view
brings back the LaTeX as it was. Word, too, writes an equation's LaTeX
again when it goes back to the linear view.

Speech, braille, the preview, copying and every export work as for
UnicodeMath. Most LaTeX math is understood (fractions, roots, scripts,
sums and integrals, `\begin{pmatrix}`, `\begin{cases}`, `\left( \right)`,
`\pmatrix{...}` and Word's `\matrix{...}`, `\mathbb{R}` and
`\mathbf{...}`, `\text{}`).

### LaTeX files

File → Open also opens a LaTeX document (`.tex`), and Save keeps it a
`.tex` file, exactly as it was written but for the equations you edit.
Its equations are found by LaTeX's own marks: `$...$`, `\(...\)`,
`$$...$$`, `\[...\]` and the `equation`, `align`, `gather`, `multline`,
`eqnarray` and `math` environments (comments, `\verb` and `verbatim` are
skipped). `Control+=` on an equation opens it in the equation editor, as
in a LaTeX Markdown document; an edited equation goes back between its
own marks, and a new one is written `$...$` (inline) or `\[...\]`
(display). An `align` environment's rows are edited as one equation,
its line breaks shown as ↵ (Up and Down go from line to line and read it; in the professional view they go from row to row); `\label`, `\tag` and `\nonumber` stay in
the text but are not read as math.

For now a `.tex` document has no preview, export, print, footnotes or
header and footer: those read Markdown. They are planned, and so is a
PDF compiled by your own LaTeX installation, with the packages you use.

### Header and footer

Insert → Header and Footer… sets the document's header and footer: a
line of text at the top and the bottom of every page of the PDF and
Word exports, beside the page number. They are kept in the document, at
its top, as front matter (the block Pandoc and GitHub read between two
`---` lines):

```
---
header: Calculus notes
footer: Chapter 2
---
```

and can be edited there too. In a notebook, each page has its own.

Edit → Find (`Command+F`, `Ctrl+F` elsewhere) and Replace
(`Command+Option+F`, `Ctrl+H`) search the Markdown, equations' source
included; Find Next and Find Previous (`Command+G` and
`Command+Shift+G`, `F3` and `Shift+F3`) go on from the selection and
wrap around. The Find dialog stays open beside the document, and Escape
closes it. Replace replaces the selected match and finds the next one.

Documents are UTF-8 Markdown files. The File menu has, in the order Mac
applications have them:

- **New** (`Command+N`, `Ctrl+N` elsewhere): a new document, in a window
  of its own.
- **Open…** (`Command+O`): a Markdown document, a notebook saved as one
  `.msnb` file, or a PDF Mathessible exported with its Markdown source
  attached (the default), which opens as the document or notebook it was
  made from, not yet saved: Save puts it beside the PDF, as a `.md` (you
  choose where) or a `.msnb`, never over the PDF. A PDF that needs a
  password to open cannot be read. **Open Recent** lists the last ten documents and
  notebooks opened or saved, and **Clear Menu** empties it. An untouched
  Untitled window is used for what is opened; something already open is
  brought to the front instead of being opened twice.
- **Close Window** (`Command+W`), **Save** (`Command+S`), **Save As…**
  (`Command+Shift+S`; `.md` is added when no extension is given) and
  **Revert to Saved**, which, after asking, goes back to the document (or
  the notebook's page) as it was last saved.
- **Export**: HTML, PDF and BRF.
- **Print…** (`Command+P`): the document, or every page of the notebook,
  as the preview shows it, through the system's print panel (its own
  page setup and Save as PDF included).

Mathessible asks before discarding unsaved changes, including an
equation still open in the equation editor, and `Quit` checks every
window. Every thirty seconds, a window with unsaved changes also writes
them to `~/.mathessible/recovery/`; should Mathessible stop unexpectedly
(a crash, a power cut), it offers them back when it starts again:
**Recover** opens them as unsaved changes, **Discard** forgets them.

Each document or notebook has its own window. The `Window` menu moves to
the next or previous window and brings them all to the front. Documents
and notebooks given on the command line (`uv run mathessible notes.md`)
are opened at start.

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
control words, Mathessible's shortcuts and your own entries, each of which can
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

`Settings → Recognized Functions…`, as Word's list, holds the names
built as functions (sin, log, lim…): Space after one opens its argument,
and it is read and navigated as function name and argument. Type a name
and Add it, choose one and Delete it, or Reset to Defaults.

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
in an equation's normal text** (off by default) lets control words and
shortcuts convert there too.

In the document itself, **Use Math AutoCorrect in the document**
(Settings → Typing, off by default; Word's rule outside math regions)
converts an entry wherever it is typed, in the text or between `$`: a
control word when a space, a punctuation mark or Enter is typed after it
(`\alpha` then Space gives "α "), and a symbol shortcut as soon as its
last character is typed (`->` gives "→"), as in Word, while **Convert
symbol shortcuts as soon as they are typed** is on (it is by default);
off, a shortcut waits for Space or Enter.

### Unknown symbols

A symbol MathCAT and the symbol dictionary do not know reaches the
screen reader as itself; with **Name unknown symbols** (on by default)
Mathessible says its Unicode name instead (🜁, "alchemical symbol for air").
Letters (ș, 中) and a text's punctuation are left as they are.

### Equation numbers and equation arrays

An equation's number goes after it, as in Word: `E=mc^2#(1)` (Insert →
Equation Number puts `#()` at the end). Moving through the built
equation, the number is one stop, "equation number 1", after the
equation; typing on it goes into the number. An equation array lines up
equations at `&` (`█(x+y&=1@x-y&=3)`, Insert → Equation Array), read as
"equation 1", "equation 2"; the whole array can have one number,
`█(...)#(2)`, but not one per line.

### Copying to Word and the web

A copied equation, or a part of one, goes to the clipboard twice: as
its UnicodeMath text and as MathML. Pasted into Word it is a built
equation, and a web page or editor that shows MathML shows it built too;
pasted where only text goes, it is the UnicodeMath. In the document, a
selection with equations is copied the same way, its text formatted and
its equations as MathML, so it pastes into Word as text with built
equations. An equation that does not build is copied as text only.

Pasting into the equation editor works the other way round. Word's
equations paste as their UnicodeMath, which is what Word copies as text;
with Word's "Copy MathML to the clipboard as plain text" option, or from
a web page that shows an equation as MathML, Mathessible converts the MathML
to UnicodeMath, its letters as you would type them (`x`, not `𝑥`). A
selection of a web page with several equations pastes as its text.

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

As in Word, Equation → Save as New Equation… keeps the equation being
edited under a name you give; saving a name again replaces it. Your
equations come first in the Structure Gallery, as **My Equations**, and
Delete (the button or the key) removes the selected one, after asking.
They are kept in `~/.mathessible/equations.json`, each with its name and
its UnicodeMath, so a class can share one file.

## Braille

The braille strip under the equation shows MathCAT's braille for the
built equation, in the code chosen in `Settings → Braille code` (Nemeth,
UEB, CMU, French, Russian, Swedish, Vietnamese, or ASCIIMath and LaTeX
as text). A symbol the code defines no sign for comes out as a hex code;
Nemeth and UEB leave such symbols to the transcriber.

`Settings → Braille signs…` gives your own sign for a symbol, over the
code chosen above; it replaces the code's own sign too. Type the symbol
as itself, as a control word (`\sqsubset`) or as its code (`U+228F`),
and the braille as cells or as dot numbers with hyphens between cells
(`4-456-126`). The signs are kept per code in `~/.mathessible/braille/`, one
plain text file each (`Nemeth.txt`), a symbol and its braille per line,
so a class can share one file:

```
# Square image of and original of: the class's signs.
⊏ ⠈⠸⠣
⊐ 4-456-28
```

### PDF export

`File → Export → PDF…` opens the export's dialog, in four tabs, for this
PDF only:

- **Document**: the title, author, subject, keywords and language, which
  the PDF keeps (PDF/UA requires a title and a language).
- **Layout**: the paper (A4, A5, A3, US Letter or US Legal), the four
  margins, columns (one to three), the font (Typst's own or any
  installed), its size and the line spacing, landscape and justified
  text.
- **Content**: a watermark across every page, where
  the page numbers go, numbers for headings (1., 1.1) and for display
  equations ((1), [1]; a number written in the equation, `#(1)`, is kept
  as it is, so a document with its own numbers is best left without),
  the colours of the text, the headings and the links (dark colours
  only, readable on white), page numbers, a table of contents from the
  headings, and whether the Markdown source is attached, so that the PDF
  can be opened in Mathessible again.
- **Security**: the **standard** (a tagged PDF, PDF/UA-1, the default,
  PDF/UA-1 with PDF/A-3a, or PDF/A-3a), a password to open the PDF, a
  password for permissions, and whether printing, copying and editing
  are allowed. Whatever is forbidden, screen readers can always read the
  PDF, as PDF/UA requires. PDF/A does not allow passwords.

Layout and content start from `Settings → PDF`, the defaults; **Save as
Defaults** makes this PDF's layout, content, standard and author the
defaults. The title, watermark and passwords belong to one PDF and are
never kept; the header and footer are the document's (Insert → Header
and Footer).

The PDF is typeset by Typst and tagged for screen readers: headings,
paragraphs, lists, tables and links are marked as such, the headings are
bookmarks, and every equation carries its spoken form, MathCAT's, for a
screen reader to read, in the language given in the Document tab when
MathCAT speaks it (English otherwise), whatever the editor's speech
language. Equations are typeset as built structures
(fractions, roots, limits, matrices, cases, equation arrays and numbers).

### Word export

`File → Export → Word Document…` writes the document, or every page of
the notebook, as a Word document (`.docx`). Every equation is a native
Word equation, which Word edits and reads aloud as its own: fractions,
roots, scripts, sums and integrals with their limits, functions,
accents, braces, matrices (cases included), equation arrays aligned at
their `&`, and numbered equations, numbered as Word numbers them.
Headings use Word's Heading styles, so the navigation pane, a table of
contents and screen readers find them; lists, tables, quotes, code,
links, bold and italic are kept, and the document's title, author,
subject, keywords and language are set.

Its dialog asks for those properties and chooses the paper, the margins,
the font, its size, the line spacing, landscape, justified text, page
numbers and a table of contents, which Word fills in when the document
is opened: Word first asks whether to update the document's fields (its
usual question for any field, as with documents from Pandoc), and Yes
fills in the table. The page and the text start from `Settings → Word`, which
**Save as Defaults** changes.

### BRF export

`File → Export → BRF (Braille)…` writes the document, or every page of
the notebook, as a BRF file, ready to emboss or to read on a braille
display. Its dialog chooses the code the equations are in (by default
the braille strip's, Nemeth unless changed; your own braille signs for
that code included), the **text braille table** (liblouis's tables:
Romanian uncontracted, English UEB uncontracted or contracted, and many
more; by default the one for the first of the system's preferred
languages that has a table), the cells per line and lines per page (40
and 25 by default) and page numbers. The table, the page and page
numbers start from `Settings → Braille`, which **Save as Defaults**
changes; the equations' code there stays the braille strip's.

A paragraph starts in cell 3, a list item in cell 1 with its runovers in
cell 3, a display equation in cell 5 with its runovers in cell 7, and a
main heading is centred; a blank line separates them, and lines break
between words. An equation that does not build is written as its
UnicodeMath, in text braille. Each notebook page starts a new braille
page, under its title. Every page has its braille page number at the
right of its last line, as the Braille Authority of North America's
formats have it; **Number the pages** in `Settings → Braille` (on by
default) turns them off. With UEB text and Nemeth maths, each equation is
between the opening Nemeth Code indicator and the Nemeth Code
terminator (`_%` and `_:`), as UEB requires.

## Notebooks and pages

A Mathessible notebook is an ordinary folder. `mathessible.json` keeps the title and
the order of the pages, and the `pages` folder holds one UTF-8 `.md` file
per page, so a notebook stays readable without Mathessible and works well with
version control.

The Notebook menu has **New Notebook…** (`Command+Option+N`, `Ctrl+Alt+N`
elsewhere), a notebook in one `.msnb` file, which File → Open opens like
a document; **New Notebook Folder…** and **Open Notebook Folder…**, for a
notebook kept as a folder; **Save Notebook as Single File…**; **Add Page**
(`Command+Shift+N`), **Rename Page…** and **Delete Page…** (after
asking); **Move Page Up** and **Move Page Down** (`Command+Option+Up` and
`Down`); and **Previous Page** and **Next Page** (`Command+Option+Page Up`
and `Page Down`). The accessible "Notebook pages" list appears beside
the editor. When you change page, Mathessible saves the current one,
including an equation being edited.

A notebook in one `.msnb` file is a compressed archive with the manifest
and every Markdown page, to move or share. Mathessible creates, opens
and edits `.msnb` notebooks directly, and saving repacks the archive
atomically. Unsafe paths, symbolic links and archives that
would unpack to an excessive size are refused on opening.

`File → Export → HTML…` exports the current document, or every page of
the notebook, as a single HTML file: Markdown formatting, tables, and
the UnicodeMath equations converted to native MathML, so the result
stays accessible and needs neither JavaScript nor an internet
connection. Its dialog asks for the title, author, description and
language, and chooses the font (sans serif or serif), the colours (light
or dark as the reader's system has it, or always light or dark) and a
table of contents: a notebook's pages, or a document's headings. A
document is exported as itself; a notebook under its title, page after
page. The font, colours and table of contents start from
`Settings → HTML`, which **Save as Defaults** changes.

Every export's dialog has **Open the file once exported**, remembered for
the next export. No message has to be dismissed afterwards: the status
bar and the screen reader say "exported", with the file's name. When
something fails, the message says what, and what to do about it; the
technical details go to the session log.

## Symbol dictionaries

The names spoken for symbols while typing, deleting and moving in the
linear view come from a dictionary in NVDA's `symbols.dic` format. Mathessible
has its own, in English. NVDA's dictionaries are downloaded from the NVDA
repository, from within the app with `Settings → Download NVDA
dictionaries…` (choosing the languages from a list), or from the command
line:

```shell
uv run mathessible-fetch-symbols          # every language
uv run mathessible-fetch-symbols ro en    # only these
```

They are saved in `~/.mathessible/symbols/` and chosen in `Settings → Symbol
dictionary`. The download notes, in the first lines of each file, the
source (NVDA), the language, the address and the date; the Settings list
shows "NVDA" only for files with that note, never because of a file name.
`Import dictionary…`, in the same place, brings in any file in the same
format (written by hand or copied from an NVDA installation). An NVDA
dictionary in another language falls back to NVDA's English one, if
downloaded, and then to Mathessible's own for what it does not define. The
built equation is always read by MathCAT, not by these dictionaries.
