# To do

Planned work, roughly in order. What is already done is described in the
[user guide](docs/user-guide.md) and the
[engineering notes](docs/engineering-notes.md).

## Help menu

Mathessible has no help of its own inside the app. All the documentation lives on
GitHub, and the Help menu opens it in the browser.

- [x] A Help menu in the document window: Quick Start Guide, User Guide,
  Keyboard Shortcuts, Report a Problem and About Mathessible (in the application
  menu on macOS). The addresses are in `src/mathessible/help_links.py`.
- [x] `docs/quick-start.md` and `docs/keyboard-shortcuts.md`, linked from
  the README and the user guide.
- [x] The Help menu in the equation editor's window too, which has its own
  menu bar.
- [ ] Keep `docs/keyboard-shortcuts.md` up to date with every new shortcut.
- [ ] A GitHub wiki, once there is more documentation than a few pages in
  `docs/`; the README and the Help menu then point to it.

## Footnotes (important)

CommonMark has no footnotes, but the common extension does (GitHub,
Pandoc, markdown-it's footnote plugin): `text[^1]` and, anywhere,
`[^1]: The note.` Typst has `#footnote[...]`, HTML a notes section with
links back, liblouis and BRF need a braille transcriber's convention.

- [x] Footnotes in the document: `[^label]` and its note, kept in the
  Markdown as that extension writes them.
- [x] Insert Footnote, as in Word (the reference at the caret, the note
  to type), and moving between a reference and its note.
- [x] Equations inside notes.
- [x] Footnotes in the preview and in every export: HTML (notes at the
  end, linked both ways), PDF (Typst's footnotes, tagged), BRF (the
  braille formats' notes) and DOCX. BRF writes the note's number in
  brackets and the notes after the text, not yet BANA's note formats.
- [x] A header and footer kept in the document (front matter), for the
  PDF and Word exports.

## PDF export

- [x] Stage 1: page, text, page numbers, header, metadata, outline and
  table of contents, tagged PDF with every equation's spoken form,
  PDF/UA-1 and PDF/A-3a, the Markdown source attached.
- [x] Stage 2: open and permission passwords (after Typst, which has
  none; not with PDF/A), a watermark, heading and equation numbering,
  colours, columns.
- [ ] Stage 3: PDF/UA-2 with MathML in the Formula tags, when Typst has it.
- [x] Open a PDF with an attached Markdown source in Mathessible.

## DOCX export

- [x] File > Export > Word Document (.docx): text, headings, lists,
  tables, links, and every equation as a native Word equation (OMML),
  with its own dialog and Settings defaults, as the other exports.
- [x] Open the exported document in Word and check it by hand: the
  equations, the numbered equation, the table of contents.

## An editor for writing papers

Mathessible should serve for complex work, theses and papers, not only a
school exercise: hence LaTeX's whole environment, and the basics every
editor for writing has, without copying Word.

- [ ] An Insert menu in the document: tables, lists of every kind
  (bulleted, numbered, tasks, definitions), headings, links (`Cmd+K`,
  `Ctrl+K`), images, quotations, code, a rule, and charts. Done:
  headings, bulleted and numbered lists, quotations, code, a rule, links,
  images and tables, task and definition lists
  (`editing/document_insert.py`). Left: the charts. What Markdown
  lacks comes from its extensions (markdown-it's plugins, as the
  footnotes do); in a .tex file each is LaTeX's own (`tabular`,
  `\section`, `\href`). Charts of three kinds: a function's graph
  (y = x², from the equation; pgfplots in .tex), charts from data (bars,
  lines, pie, from a table of values) and diagrams (flowcharts, Mermaid
  in Markdown, TikZ in .tex).
- [x] The editor's basic elements beside the menu bar, as editors for
  writing have them: a toolbar (bold, italic, headings, lists, equation,
  table, link, citation), a status bar with counts (words, characters,
  the current section, the line) and formatting shortcuts (`Cmd+B`,
  `Cmd+I`, `Cmd+1`…`6` for headings, `Cmd+K` for a link), in Markdown and
  in .tex alike.

## A professional application

- [ ] The interface in more languages than MathCAT's 14, Romanian first:
  the translation system is there (docs/translating.md), but equations
  would still be spoken in another language.
- [x] The equations' spoken form in the PDF in the document's language,
  when MathCAT has it (English otherwise: it has no Romanian).
- [x] Check the Find dialog (wx's generic one) with VoiceOver.
- [x] Check with VoiceOver what is only tested without a screen: Undo
  after the commands that change the document (Change to Display, Replace
  All, AutoCorrect in the text) and File > Print.
- [x] Settings' height (720 px with the PDF tab): the PDF's defaults are two
  tabs, PDF Layout and PDF Content, as in the export's dialog (544 px).
- [ ] Distribution: a macOS application (`.app`) with an icon, `.md` and
  `.msnb` files opening in it, signing and notarisation, an installer;
  Windows and Linux built and tried (liblouis needs clang-cl on
  Windows); Mathessible running outside its checkout.
- [ ] Versions: a changelog and releases on GitHub (it is 0.1.0).

## Later

- [x] Braille export (BRF) of a document or notebook.
- [x] BRF: the switch indicators UEB text needs around Nemeth maths, and
  page numbers.
- [x] The text braille table's default follows the system's preferred
  languages (Python's locale is "C" in a macOS app).
- [ ] Propose Mathessible's patches upstream (`patches/mathcat`,
  `patches/unicodemathml`).
- [x] LaTeX documents, stage 1: `math: latex` in the front matter, the
  equations stored as LaTeX and built, read, brailled and exported
  through Sargent's TeX2UnicodeMath; the built view read-only.
- [x] LaTeX, stage 2: editing in the professional view (the UnicodeMath
  the LaTeX builds as, written again in LaTeX by MathCAT only after an
  edit there; Word rewrites it on every return), the Insert menu writing
  LaTeX in the linear view.
- [x] LaTeX: `\pmatrix{...}`, and a math alphabet over a structure
  (`\mathbf{\frac{a}{b}}`), in Sargent's TeX2UnicodeMath.
- [x] LaTeX, stage 3a: `.tex` files opened and saved as written, their
  equations (`$`, `\(`, `\[`, `equation`, `align` ...) edited.
- [x] LaTeX, stage 3b: a `.tex` file's preview and accessible exports
  (HTML, PDF, Word, BRF, Print), from the common text commands (sections,
  emphasis, lists, footnotes, title); other commands keep their text.
- [x] LaTeX: tables (`tabular`), figures and `\ref`/`\cite` numbers in a
  `.tex` file's preview and exports, an `align`'s rows' numbers and a
  `.bib` bibliography included.
- [x] LaTeX, stage 3c: the PDF of a `.tex` file compiled by the user's own
  LaTeX installation (TinyTeX offered and installed when there is none,
  missing packages installed with tlmgr), so that packages work.
- [x] LaTeX: a tagged, accessible PDF from a `.tex` file (LuaLaTeX's
  `\DocumentMetadata` tagging), and `\newcommand` macros understood in
  the equation editor.
- [x] Opening Markdown written elsewhere (GitHub, Pandoc) whose equations
  are LaTeX but which has no `math: latex`: asked whether to mark it.
- [ ] The visual design of the equation editor.
