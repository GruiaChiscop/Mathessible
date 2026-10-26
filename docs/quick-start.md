# Quick start

From installing MateX to a first equation, written, read and saved. The
[user guide](user-guide.md) explains everything in more detail, and
[keyboard-shortcuts.md](keyboard-shortcuts.md) lists every key.

## Install and start

MateX runs from a copy of this repository and needs Python 3.14 and
[uv](https://docs.astral.sh/uv/). On macOS, use a Framework build of
Python (Homebrew's or python.org's).

```shell
git clone --recursive https://github.com/GruiaChiscop/MateX.git
cd MateX
sh scripts/bootstrap.sh
uv run matex
```

`scripts/bootstrap.sh` prepares MathCAT and the converter and runs the
tests; it is needed once, and again after an update. Afterwards
`uv run matex` is enough. MateX speaks through the screen reader that is
running (VoiceOver, NVDA, JAWS…).

## Write a document

The window that opens is a Markdown editor: write text as in any text
field. Headings start with `#`, lists with `-`.

## Write an equation

1. Where the equation goes, press `Control+=` on macOS or `Alt+=` on
   Windows and Linux. The equation editor opens.
2. Type the equation in UnicodeMath, as in Word's linear format:
   `x=(-b±√(b^2-4ac))/(2a)`. Control words work too: `\pm` gives ±,
   `\sqrt` gives √.
3. Each part is built as soon as it is complete, and MateX says what you
   typed.
4. Press `Enter` to save the equation and go on writing on a new line,
   or `Control+=` (`Alt+=`) to go back to the text after it. `Escape`
   cancels.

In the document the equation is kept as `$x=(-b±√(b^2-4ac))/(2a)$`.
Between `$$` and `$$` it would be a display equation, on a line of its
own.

## Read an equation

Put the caret in the equation and press `Control+=` (`Alt+=`) again. In
the professional view:

- `Left` and `Right` move through the equation, saying each part:
  "start fraction", "start numerator", "minus b"…
- `Option+Left` and `Option+Right` (`Ctrl` on Windows and Linux) move by
  whole element: a fraction, a root.
- `F10` switches to exploration mode, where nothing changes the
  equation and `Space` reads where you are.
- The braille strip under the equation shows it in the braille code
  chosen in Settings (Nemeth by default).

## Save

`Command+S` (`Ctrl+S`) saves the document as a Markdown file, which any
text editor can open. File → Export as HTML… makes an accessible web page
of it, with the equations as MathML.

## Next

- [User guide](user-guide.md): templates, the structure gallery, editing
  the built equation, notebooks, braille signs and settings.
- [Keyboard shortcuts](keyboard-shortcuts.md).

## Learn more

### UnicodeMath

MateX's equations are UnicodeMath, the same linear format as Word's, so
what is written about Word's equations holds here too.

- [Linear format equations using UnicodeMath and LaTeX in Word](https://support.microsoft.com/en-us/office/linear-format-equations-using-unicodemath-and-latex-in-word-2e00618d-b1fd-49d8-8cb4-8d17f25754f8)
  (Microsoft Support): how fractions, scripts, roots, matrices and the
  rest are typed, with examples.
- [Unicode Technical Note #28](https://www.unicode.org/notes/tn28/), by
  Murray Sargent III: the specification of UnicodeMath, and the
  reference when Word's behaviour is unclear.
- [Math in Office](https://devblogs.microsoft.com/math-in-office/):
  Murray Sargent's blog on UnicodeMath and Office's maths.
- [UnicodeMathML playground](https://murrayiii.github.io/UnicodeMathML/playground/):
  try UnicodeMath in the browser and see the MathML it becomes, with the
  converter MateX uses.

### Control words and symbols

Control words such as `\alpha` or `\int` are Word's Math AutoCorrect
entries.

- [Quick start guide to Math AutoCorrect commands and symbols](https://support.microsoft.com/en-us/topic/9cbc8873-c217-4c87-a059-03d539ef8eea)
  (Microsoft Support): every symbol, with its control word and its
  Unicode value.
- In MateX: Settings → Math AutoCorrect… lists every control word and
  shortcut, which you can change, delete or add to. Insert → Symbol…
  (`Command+Shift+S`, `Ctrl+Shift+S`) finds a symbol by its control word
  or name, and typing a control word offers the matching ones.

### Speech, navigation and braille

- [MathCAT for assistive technology users](https://daisy.github.io/MathCAT/users.html):
  how MathCAT speaks, navigates and brailles maths, and its preferences.
  MateX reads every built equation through MathCAT.
