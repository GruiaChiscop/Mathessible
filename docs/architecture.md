# How Mathessible works

A one-page map of the code, following an equation through the app. Paths
are under `src/mathessible/`; the details and the traps are in
[engineering-notes.md](engineering-notes.md).

## The document

`ui/main_frame.py` is a window with a native Markdown text control
(`ui/document_editor.py`). Equations are `$...$` and `$$...$$` zones
(`documents/markdown_math.py`). `Control+=` (`Alt+=` elsewhere) opens the
zone under the caret in the equation window, a separate `wx.Frame` with
its own menus, which holds one `EquationEditor`. Saving writes the
UnicodeMath text back into the zone: the document only ever contains
plain UnicodeMath.

## The equation editor

`editor/equation_editor.py` is a custom-drawn control (so a screen reader
does not wander into web content), split into mixins:
`renderer` (the WebView), `built` (editing the built equation),
`structures` (context menu and structure edits), `assist` (completion,
symbols, errors, gallery), `drawing`, `keys`. It has two views, switched
with F2, as in Word:

- **Linear**: the source text. Typing goes through Math AutoCorrect
  (`editing/space_conversion.py`, `editing/autocorrect.py`), templates
  insert structures with Tab slots (`templates/`), and when the source is
  complete it builds (Word's autobuild).
- **Professional**: the built equation, read and navigated through
  MathCAT, and editable too.

## From source to speech

```
UnicodeMath source
  │  editing/build_repair.py      fill in what a half-typed equation lacks (only for building)
  │  editing/linear_runs.py       keep what was typed and is not complete yet linear (escaped)
  ▼
UnicodeMathML (JS, in the editor's WebView, which never takes the focus: editor/renderer.py, unicodemath.py)
  │                                converter output, with error markers mathcolor="#F00"/"#F01"
  ▼
mathcat/prepare.py               fix what MathCAT would misread
  ▼
MathCAT (native, mathcat/navigator.py)
  │  speech, braille, navigation; its canonical MathML is what the WebView shows
  ▼
mathcat/mathml_model.py          that MathML as a tree: regions, roles, tables
mathcat/stops.py, structural.py, tables.py
                                 Mathessible's own linear stops, levels and cell moves over it
```

Python never parses UnicodeMath itself: the converter decides what an
equation is, and the converter's error markers are the only test of
whether it builds.

## Editing the built equation

MathML keeps no source positions, so `editing/source_map.py` aligns
MathCAT's leaves with the source text. The caret in the built equation is
a MathCAT position; a key typed there is applied to the source at the
mapped offset (`editor/built.py`), as if typed in the linear view, and the
equation is rebuilt with MathCAT back on the same place. The source may
hold control words (`\sqrt`, `\of`), so template code works on a view with
them resolved (`editing/source_view.py`).

## Around it

- `documents/`: notebooks (a folder or a `.msnb` archive) and HTML export,
  where converter output passes `documents/mathml_sanitize.py` first.
- `symbols/`: the dictionaries that name symbols while typing in the
  linear view (NVDA's `symbols.dic` format).
- `settings.py`, `session_log.py` (`MATHESSIBLE_LOG=1`), `patch_check.py` (the
  startup check that bootstrap's patches are applied).
- `native/mathcat_py/`: the PyO3 binding to the MathCAT submodule.
