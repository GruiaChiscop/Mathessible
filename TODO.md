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

- [ ] Footnotes in the document: `[^label]` and its note, kept in the
  Markdown as that extension writes them.
- [ ] Insert Footnote, as in Word (the reference at the caret, the note
  to type), and moving between a reference and its note.
- [ ] Equations inside notes.
- [ ] Footnotes in the preview and in every export: HTML (notes at the
  end, linked both ways), PDF (Typst's footnotes, tagged), BRF (the
  braille formats' notes) and DOCX.

## PDF export

- [x] Stage 1: page, text, page numbers, header, metadata, outline and
  table of contents, tagged PDF with every equation's spoken form,
  PDF/UA-1 and PDF/A-3a, the Markdown source attached.
- [x] Stage 2: open and permission passwords (after Typst, which has
  none; not with PDF/A), a watermark, heading and equation numbering,
  colours, columns.
- [ ] Stage 3: PDF/UA-2 with MathML in the Formula tags, when Typst has it.
- [ ] Open a PDF with an attached Markdown source in Mathessible.

## DOCX export

- [ ] File > Export > Word Document (.docx): text, headings, lists,
  tables, links, and every equation as a native Word equation (OMML),
  with its own dialog and Settings defaults, as the other exports.

## A professional application

- [ ] The interface in more languages, Romanian first (a translation
  system, gettext or wx's own; every string in English in the code).
- [ ] The equations' spoken form in the PDF in the document's language:
  MathCAT has no Romanian yet, so it is English today.
- [ ] Check with VoiceOver what is only tested without a screen: the Find
  dialog (wx's generic one), Undo after the commands that change the
  document (Change to Display, Replace All, AutoCorrect in the text) and
  File > Print.
- [ ] Settings' height (720 px with the PDF tab): fine on a laptop, but
  still tall.
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
- [ ] LaTeX input in the equation editor.
- [ ] The visual design of the equation editor.
