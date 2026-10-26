# To do

Planned work, roughly in order. What is already done is described in the
[user guide](docs/user-guide.md) and the
[engineering notes](docs/engineering-notes.md).

## Help menu

MateX has no help of its own inside the app. All the documentation lives on
GitHub, and the Help menu opens it in the browser.

- [ ] A Help menu in the document window, with these items:
  - Quick Start Guide
  - User Guide
  - Keyboard Shortcuts
  - Report a Problem (GitHub issues)
  - About MateX: the version and the licences of MathCAT, UnicodeMathML and
    NVDA's symbol dictionaries.

  On macOS, About goes in the application menu, as wx does for `wx.ID_ABOUT`.
  The links open with `wx.LaunchDefaultBrowser`.
- [ ] One constant for the repository's GitHub address, used by every Help
  item.
- [ ] Blocked: the repository has no GitHub remote yet, so the addresses are
  not known.

## Documentation on GitHub

- [ ] `docs/quick-start.md`: from installing to the first equation, read,
  navigated and saved, in one page.
- [ ] `docs/keyboard-shortcuts.md`: every shortcut, as tables per place:
  - the document window;
  - the equation editor, in the linear view and in the professional view;
  - the dialogs.

  Each table has macOS and Windows/Linux columns. This replaces the
  shortcut list on F1 that was planned inside the app.
- [ ] Link both pages from the README and from the user guide.

## Later

- [ ] Braille export (BRF) of a document or notebook.
- [ ] Propose MateX's patches upstream (`patches/mathcat`,
  `patches/unicodemathml`).
- [ ] LaTeX input in the equation editor.
- [ ] The visual design of the equation editor.
