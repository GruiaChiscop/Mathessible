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
