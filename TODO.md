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

## Later

- [x] Braille export (BRF) of a document or notebook.
- [ ] BRF: the switch indicators UEB text needs around Nemeth maths (see
  what MathCAT offers), and page numbers.
- [x] The text braille table's default follows the system's preferred
  languages (Python's locale is "C" in a macOS app).
- [ ] Propose Mathessible's patches upstream (`patches/mathcat`,
  `patches/unicodemathml`).
- [ ] LaTeX input in the equation editor.
- [ ] The visual design of the equation editor.
